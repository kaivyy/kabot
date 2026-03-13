from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

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
        "Sip, kebentuk.\n\n"
        "Aku sekarang:\n"
        "- Nama: Jarhed\n"
        "- Peran: pembantu kamu\n"
        "- Gaya: lucu, to the point\n"
        "- Signature: ganas\n\n"
        "Biar beres total, tinggal 2 hal:\n"
        "1. Aku panggil kamu siapa?\n"
        "2. Timezone kamu tetap Asia/Jakarta kan?"
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
        content="1. jarhed\n2. pembantu saya\n3. lucu, to the point\n4. ganas",
    )
    await process_message(loop, first_msg)

    identity_text = (tmp_path / "IDENTITY.md").read_text(encoding="utf-8")
    user_text = (tmp_path / "USER.md").read_text(encoding="utf-8")

    assert "Jarhed" in identity_text
    assert "Pembantu saya" in identity_text
    assert "Lucu, to the point" in identity_text
    assert "Ganas" in identity_text
    assert "Maha Raja" not in user_text
    assert (tmp_path / "BOOTSTRAP.md").exists()
    assert session.metadata.get("bootstrap_onboarding", {}).get("stage") == "user"

    second_response = (
        "Siap, Maha Raja.\n"
        "Timezone: Asia/Jakarta.\n\n"
        "Udah aku simpan ke profil juga, jadi next chat aku langsung nyambung."
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
        content="1. maha raja\n2. ya jakarta",
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
                    "creature": "Pembantu saya",
                    "vibe": "Lucu, to the point",
                    "emoji": "Ganas",
                },
            }
        }
    )

    response = "Siap, aku simpan ke profil."
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
        content="Nama saya: Maha Raja\nTimezone: WIB",
    )
    await process_message(loop, msg)

    user_text = (tmp_path / "USER.md").read_text(encoding="utf-8")
    assert "Maha Raja" in user_text
    assert "Asia/Jakarta" in user_text
    assert session.metadata.get("bootstrap_onboarding", {}).get("stage") == "complete"
