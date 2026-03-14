"""Split from tests/agent/loop_core/test_message_runtime.py to keep test modules below 1000 lines.
Chunk 2: test_process_message_uses_pending_followup_tool_without_keyword_dependency .. test_process_message_file_context_followup_reuses_last_file_path_for_llm_note.
"""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.loop_core.message_runtime import (
    process_message,
)
from kabot.bus.events import InboundMessage, OutboundMessage


@pytest.mark.asyncio
async def test_process_message_uses_pending_followup_tool_without_keyword_dependency():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "terusin dong"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "web_search",
                "source": "berita terbaru 2026 sekarang",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="terusin dong")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    context_builder.build_messages.assert_not_called()

@pytest.mark.asyncio
async def test_process_message_abort_shortcut_clears_pending_followups_and_skips_execution():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "stop"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "weather",
                "source": "cuaca purwokerto",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "pending_followup_intent": {
                "text": "carikan berita terbaru",
                "profile": "RESEARCH",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: True),
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
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="stopped")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="STOP ACTION!!!")
    response = await process_message(loop, msg)

    assert response is not None
    loop._run_agent_loop.assert_not_called()
    loop._run_simple_response.assert_not_called()
    context_builder.build_messages.assert_not_called()
    assert "pending_followup_tool" not in session.metadata
    assert "pending_followup_intent" not in session.metadata
    finalized_text = loop._finalize_session.await_args.args[2]
    assert "stopped" in finalized_text.lower() or "hentikan" in finalized_text.lower()

@pytest.mark.asyncio
async def test_process_message_expired_pending_followup_tool_is_ignored():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "lanjut dong"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "web_search",
                "source": "berita terbaru 2026 sekarang",
                "updated_at": time.time() - 1000,
                "expires_at": time.time() - 1,
            }
        }
    )

    loop = SimpleNamespace(
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
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="lanjut dong")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert "pending_followup_tool" not in session.metadata

@pytest.mark.asyncio
async def test_process_message_explicit_tool_query_overrides_pending_followup_tool_context():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "kalau suhu cilacap berapa sekarang"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "web_search",
                "source": "berita terbaru 2026 sekarang",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )

    def _required_tool(text: str) -> str | None:
        normalized = (text or "").lower()
        if "suhu" in normalized or "cuaca" in normalized:
            return "weather"
        if "berita" in normalized:
            return "web_search"
        return None

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=_required_tool,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="kalau suhu cilacap berapa sekarang",
    )
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    assert msg.metadata.get("required_tool") == "weather"
    assert msg.metadata.get("required_tool_query") == "kalau suhu cilacap berapa sekarang"
    assert session.metadata["pending_followup_tool"]["tool"] == "weather"

@pytest.mark.asyncio
async def test_process_message_short_followup_does_not_force_pending_cron_after_user_acknowledgement():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "oke makasih ya"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "cron",
                "source": "ingatkan pukul 21.25 buka hp",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="oke makasih ya")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None
    assert "pending_followup_tool" not in session.metadata

@pytest.mark.asyncio
async def test_process_message_short_greeting_does_not_force_pending_cron_followup():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "halo"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "cron",
                "source": "ingatkan pukul 21.25 buka hp",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="halo")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None
    assert "pending_followup_tool" not in session.metadata

@pytest.mark.asyncio
async def test_process_message_non_action_feedback_does_not_force_pending_tool_followup():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "stop bahas saham"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "stock",
                "source": "cek harga bbri bbca bmri",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="stop bahas saham")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None
    assert "pending_followup_tool" not in session.metadata

@pytest.mark.asyncio
async def test_process_message_runtime_feedback_like_kok_lama_does_not_force_pending_tool_followup():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "kok lama"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "stock",
                "source": "cek harga saham apple",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="kok lama")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None
    assert "pending_followup_tool" not in session.metadata

@pytest.mark.asyncio
async def test_process_message_explicit_file_path_request_clears_stale_system_info_followup():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [
        {
            "role": "user",
            "content": r"C:\Users\Arvy Kairi\.kabot\workspace\landing_hacker.html font pada web ini",
        }
    ]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "get_system_info",
                "source": "cek spek pc sekarang",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content=r"C:\Users\Arvy Kairi\.kabot\workspace\landing_hacker.html font pada web ini",
    )
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None
    assert "pending_followup_tool" not in session.metadata

@pytest.mark.asyncio
async def test_process_message_large_file_scan_request_clears_stale_cleanup_followup():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [
        {
            "role": "user",
            "content": "cari file/folder yang ukurannya besar, karena ssd 256gb sisanya cuma 18gb an",
        }
    ]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "cleanup_system",
                "source": "cleanup pc sekarang",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="cari file/folder yang ukurannya besar, karena ssd 256gb sisanya cuma 18gb an",
    )
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None
    assert "pending_followup_tool" not in session.metadata

@pytest.mark.asyncio
async def test_process_message_explicit_file_path_adds_file_analysis_note_for_llm():
    captured: dict[str, str] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": captured["current_message"]}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=True))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=["read_file"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content=r"C:\Users\Arvy Kairi\.kabot\workspace\landing_hacker.html font pada web ini",
    )
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert "[System Note: Explicit file reference]" in captured["current_message"]
    assert "landing_hacker.html" in captured["current_message"]
    assert msg.metadata.get("required_tool") == "read_file"
    assert "landing_hacker.html" in str(msg.metadata.get("required_tool_query") or "")

@pytest.mark.asyncio
async def test_process_message_explicit_file_path_stores_last_file_context():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "x"}]
    context_builder.consume_last_truncation_summary.return_value = None
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=True))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=["read_file"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content=r"C:\Users\Arvy Kairi\.kabot\workspace\landing_hacker.html font pada web ini",
    )
    await process_message(loop, msg)

    last_ctx = session.metadata.get("last_tool_context")
    assert isinstance(last_ctx, dict)
    assert last_ctx.get("tool") == "read_file"
    assert "landing_hacker.html" in str(last_ctx.get("path") or "")
    assert msg.metadata.get("file_analysis_mode") is True

@pytest.mark.asyncio
async def test_process_message_file_context_followup_reuses_last_file_path_for_llm_note():
    captured: dict[str, str] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": captured["current_message"]}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None
    session = SimpleNamespace(
        metadata={
            "last_tool_context": {
                "tool": "read_file",
                "path": r"C:\Users\Arvy Kairi\.kabot\workspace\landing_hacker.html",
                "source": r"c:\users\arvy kairi\.kabot\workspace\landing_hacker.html font pada web ini",
                "updated_at": time.time(),
            }
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=True))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=["read_file"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="buka html ini",
    )
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert "[System Note: Explicit file reference]" in captured["current_message"]
    assert "landing_hacker.html" in captured["current_message"]
    assert msg.metadata.get("required_tool") == "read_file"
