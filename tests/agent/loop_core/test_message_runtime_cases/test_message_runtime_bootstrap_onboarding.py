from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.loop_core.message_runtime_parts.bootstrap_onboarding import (
    update_bootstrap_onboarding_state,
)
from kabot.agent.loop_core.message_runtime import process_message
from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.utils.workspace_templates import ensure_workspace_templates


def _build_loop(*, workspace: Path, session: SimpleNamespace, context_builder: MagicMock, response: str):
    return SimpleNamespace(
        workspace=workspace,
        _active_turn_id=None,
        runtime_performance=None,
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda content: (
                content,
                SimpleNamespace(
                    raw_directives=[],
                    think=False,
                    verbose=False,
                    elevated=False,
                    model=None,
                ),
            )
        ),
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: []),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value=response),
        _run_agent_loop=AsyncMock(return_value=response),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content=response)
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )


@pytest.mark.asyncio
async def test_process_message_bootstrap_onboarding_persists_identity_then_user_profile(tmp_path: Path):
    ensure_workspace_templates(tmp_path)
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "bootstrap"}]
    session = SimpleNamespace(metadata={})

    first_response = (
        "Locked in.\n\n"
        "I am now:\n"
        "- Name: Jarhed\n"
        "- Creature: your helper\n"
        "- Vibe: funny, to the point\n"
        "- Signature: ganas\n\n"
        "To finish setup, I just need two more things:\n"
        "1. What should I call you?\n"
        "2. Is your timezone still Asia/Jakarta?"
    )
    loop = _build_loop(
        workspace=tmp_path,
        session=session,
        context_builder=context_builder,
        response=first_response,
    )

    first_msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="1. jarhed\n2. your helper\n3. funny, to the point\n4. ganas",
    )
    await process_message(loop, first_msg)

    identity_text = (tmp_path / "IDENTITY.md").read_text(encoding="utf-8")
    user_text = (tmp_path / "USER.md").read_text(encoding="utf-8")

    assert "Jarhed" in identity_text
    assert "Your helper" in identity_text
    assert "Funny, to the point" in identity_text
    assert "Ganas" in identity_text
    assert "Maha Raja" not in user_text
    assert (tmp_path / "BOOTSTRAP.md").exists()
    assert session.metadata.get("bootstrap_onboarding", {}).get("stage") == "user"

    second_response = (
        "Locked in, Maha Raja.\n"
        "Timezone: Asia/Jakarta.\n\n"
        "I saved that to my profile too, so next chat will pick it up immediately."
    )
    loop._run_simple_response = AsyncMock(return_value=second_response)
    loop._run_agent_loop = AsyncMock(return_value=second_response)
    loop._finalize_session = AsyncMock(
        return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content=second_response)
    )

    second_msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="1. maha raja\n2. asia/jakarta",
    )
    await process_message(loop, second_msg)

    user_text = (tmp_path / "USER.md").read_text(encoding="utf-8")
    assert "Maha Raja" in user_text
    assert "Asia/Jakarta" in user_text
    assert not (tmp_path / "BOOTSTRAP.md").exists()
    assert session.metadata.get("bootstrap_onboarding", {}).get("stage") == "complete"


@pytest.mark.asyncio
async def test_process_message_bootstrap_onboarding_accepts_labeled_free_text_answers(tmp_path: Path):
    ensure_workspace_templates(tmp_path)
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "bootstrap"}]
    session = SimpleNamespace(
        metadata={
            "bootstrap_onboarding": {
                "stage": "user",
                "updated_at": time.time(),
                "assistant": {
                    "name": "Jarhed",
                    "creature": "Your helper",
                    "vibe": "Funny, to the point",
                    "emoji": "Ganas",
                },
            }
        }
    )

    response = "Saved to profile."
    loop = _build_loop(
        workspace=tmp_path,
        session=session,
        context_builder=context_builder,
        response=response,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="My name: Maha Raja\nTimezone: Asia/Jakarta",
    )
    await process_message(loop, msg)

    user_text = (tmp_path / "USER.md").read_text(encoding="utf-8")
    assert "Maha Raja" in user_text
    assert "Asia/Jakarta" in user_text
    assert session.metadata.get("bootstrap_onboarding", {}).get("stage") == "complete"


def test_update_bootstrap_onboarding_state_ignores_action_turns(tmp_path: Path):
    ensure_workspace_templates(tmp_path)
    session = SimpleNamespace(metadata={})
    loop = SimpleNamespace(workspace=tmp_path)

    msg = InboundMessage(
        channel="cli",
        sender_id="u1",
        chat_id="chat-1",
        content="ya pakai path desktop bot",
        metadata={"required_tool": "list_dir", "turn_category": "action"},
    )

    update_bootstrap_onboarding_state(
        loop,
        session,
        msg,
        "📄 tes.md",
        now_ts=time.time(),
    )

    identity_text = (tmp_path / "IDENTITY.md").read_text(encoding="utf-8")
    assert "Pakai path desktop bot" not in identity_text
    assert session.metadata.get("bootstrap_onboarding") is None
    assert (tmp_path / "BOOTSTRAP.md").exists()
