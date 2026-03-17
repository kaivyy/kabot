from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.cron_fallback_nlp import required_tool_for_query as cron_required_tool_for_query
from kabot.agent.loop_core.message_runtime import process_message
from kabot.agent.loop_core.message_runtime_parts.user_profile import infer_user_profile_updates
from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.utils.workspace_templates import ensure_workspace_templates


def _build_loop(
    *,
    workspace: Path,
    session: SimpleNamespace,
    history: list[dict[str, str]] | None = None,
    response: str = "ok",
    context_builder: MagicMock | None = None,
    memory: SimpleNamespace | None = None,
):
    if context_builder is None:
        context_builder = MagicMock()
        context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
        context_builder.consume_last_truncation_summary.return_value = None

    if memory is None:
        memory = SimpleNamespace(
            get_conversation_context=lambda _key, max_messages=30: list(history or []),
            remember_fact=AsyncMock(return_value=True),
        )

    return SimpleNamespace(
        workspace=workspace,
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        runtime_observability=None,
        _parse_approval_command=lambda _content: None,
        _parse_exec_approval_turn=lambda _content: None,
        _drain_pending_memory_writes=AsyncMock(return_value=0),
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
        memory=memory,
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False, turn_category="chat"))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(
            tool_names=["save_memory", "get_process_memory"],
            has=lambda name: name in {"save_memory", "get_process_memory"},
            get=lambda _name: None,
        ),
        _required_tool_for_query=lambda text: cron_required_tool_for_query(
            text,
            has_weather_tool=False,
            has_cron_tool=False,
            has_process_memory_tool=True,
            has_save_memory_tool=True,
        ),
        _run_simple_response=AsyncMock(return_value=response),
        _run_agent_loop=AsyncMock(return_value=response),
        _finalize_session=AsyncMock(
            side_effect=lambda _msg, _session, final_content: OutboundMessage(
                channel="telegram",
                chat_id="chat-1",
                content=str(final_content or ""),
            )
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
    )


def test_infer_user_profile_updates_is_english_first_and_skips_indonesian_parser_phrase():
    assert infer_user_profile_updates('call me "Maha Raja"') == {"address": "Maha Raja"}
    assert infer_user_profile_updates('panggil aku "Maha Raja"') == {}


@pytest.mark.asyncio
async def test_process_message_memory_commit_persists_user_address_and_routes_save_memory(tmp_path: Path):
    ensure_workspace_templates(tmp_path)
    session = SimpleNamespace(metadata={})
    remember_fact = AsyncMock(return_value=True)
    loop = _build_loop(
        workspace=tmp_path,
        session=session,
        response="Locked in. I'll remember that, Maha Raja.",
        memory=SimpleNamespace(
            get_conversation_context=lambda _key, max_messages=30: [],
            remember_fact=remember_fact,
        ),
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content='call me "Maha Raja" and remember that',
    )
    await process_message(loop, msg)

    assert msg.metadata.get("required_tool") == "save_memory"
    profile = session.metadata.get("user_profile") or {}
    assert profile.get("address") == "Maha Raja"
    user_text = (tmp_path / "USER.md").read_text(encoding="utf-8")
    assert "Maha Raja" in user_text
    assert remember_fact.await_count >= 1


@pytest.mark.asyncio
async def test_process_message_semantic_memory_commit_routes_save_memory_without_parser_phrase(tmp_path: Path):
    ensure_workspace_templates(tmp_path)
    session = SimpleNamespace(metadata={})
    remember_fact = AsyncMock(return_value=True)
    loop = _build_loop(
        workspace=tmp_path,
        session=session,
        response="Siap, nanti aku ingat itu.",
        memory=SimpleNamespace(
            get_conversation_context=lambda _key, max_messages=30: [],
            remember_fact=remember_fact,
        ),
    )
    loop.provider = SimpleNamespace(
        chat=AsyncMock(
            return_value=SimpleNamespace(content='{"memory_intent":"memory_commit"}')
        )
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="tolong simpan ini buat nanti",
    )
    await process_message(loop, msg)

    assert msg.metadata.get("required_tool") == "save_memory"


@pytest.mark.asyncio
async def test_process_message_call_me_preference_persists_profile_without_explicit_save_memory(tmp_path: Path):
    ensure_workspace_templates(tmp_path)
    session = SimpleNamespace(metadata={})
    loop = _build_loop(
        workspace=tmp_path,
        session=session,
        response="Siap, Maha Raja.",
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content='every time you reply, call me "Maha Raja"',
    )
    await process_message(loop, msg)

    profile = session.metadata.get("user_profile") or {}
    assert profile.get("address") == "Maha Raja"
    user_text = (tmp_path / "USER.md").read_text(encoding="utf-8")
    assert "Maha Raja" in user_text


@pytest.mark.asyncio
async def test_process_message_self_identity_recall_uses_profile_memory_context(tmp_path: Path):
    ensure_workspace_templates(tmp_path)
    captured: dict[str, str] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": captured["current_message"]}]

    session = SimpleNamespace(
        metadata={
            "user_profile": {
                "address": "Maha Raja",
                "updated_at": time.time(),
            }
        }
    )
    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None
    loop = _build_loop(
        workspace=tmp_path,
        session=session,
        response="Maha Raja",
        context_builder=context_builder,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="okay, so who am I",
    )
    response = await process_message(loop, msg)

    assert response is not None
    assert response.content == "Maha Raja"
    context_builder.build_messages.assert_called_once()
    assert "User prefers to be addressed as: Maha Raja" in captured["current_message"]
    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_message_semantic_memory_recall_in_user_language_injects_memory_context(tmp_path: Path):
    ensure_workspace_templates(tmp_path)
    captured: dict[str, str] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": captured["current_message"]}]

    async def _search_memory(*, query: str, session_id: str | None = None, limit: int = 5):
        return [
            {
                "role": "system",
                "content": "[decision] Kita sepakat fokus ke fitur memory hybrid penuh.",
            }
        ]

    session = SimpleNamespace(metadata={})
    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None
    loop = _build_loop(
        workspace=tmp_path,
        session=session,
        response="Kita sepakat fokus ke fitur memory hybrid penuh.",
        context_builder=context_builder,
        memory=SimpleNamespace(
            get_conversation_context=lambda _key, max_messages=30: [],
            search_memory=_search_memory,
            remember_fact=AsyncMock(return_value=True),
        ),
    )
    loop.provider = SimpleNamespace(
        chat=AsyncMock(
            return_value=SimpleNamespace(content='{"memory_intent":"memory_recall"}')
        )
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="apa keputusan kita tadi",
    )
    response = await process_message(loop, msg)

    assert response is not None
    assert "[decision] Kita sepakat fokus ke fitur memory hybrid penuh." in captured["current_message"]
    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_message_identity_recall_loads_history_when_profile_not_yet_persisted(tmp_path: Path):
    ensure_workspace_templates(tmp_path)
    captured: dict[str, str] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        return [
            {"role": "assistant", "content": 'If you ask who you are, I will answer: "Maha Raja".'},
            {"role": "user", "content": str(kwargs.get("current_message") or "")},
        ]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None
    session = SimpleNamespace(metadata={})
    loop = _build_loop(
        workspace=tmp_path,
        session=session,
        history=[{"role": "assistant", "content": 'If you ask who you are, I will answer: "Maha Raja".'}],
        response="Maha Raja",
        context_builder=context_builder,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="okay, so who am I",
    )
    await process_message(loop, msg)

    context_builder.build_messages.assert_called_once()
    assert "who am i" in captured["current_message"].lower()
