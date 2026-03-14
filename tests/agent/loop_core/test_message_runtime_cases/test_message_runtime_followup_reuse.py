"""Split from tests/agent/loop_core/test_message_runtime.py to keep test modules below 1000 lines.
Chunk 3: test_process_message_file_context_followup_uses_recent_history_when_session_context_missing .. test_process_message_explicit_file_request_does_not_force_pending_intent_followup.
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
async def test_process_message_file_context_followup_uses_recent_history_when_session_context_missing():
    captured: dict[str, str] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": captured["current_message"]}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None
    session = SimpleNamespace(metadata={})
    history = [
        {
            "role": "user",
            "content": r"C:\Users\Arvy Kairi\.kabot\workspace\landing_hacker.html font pada web ini",
        }
    ]

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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
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
    last_ctx = session.metadata.get("last_tool_context")
    assert isinstance(last_ctx, dict)
    assert last_ctx.get("tool") == "read_file"
    assert "landing_hacker.html" in str(last_ctx.get("path") or "")

@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("followup_text", "history_text"),
    [
        ("这个文件的字体是什么", r"C:\Users\Arvy Kairi\.kabot\workspace\landing_hacker.html 这个网页用的是什么字体"),
        ("このファイルのフォントは？", r"C:\Users\Arvy Kairi\.kabot\workspace\landing_hacker.html このサイトのフォントは何？"),
        ("ฟอนต์ในไฟล์นี้คืออะไร", r"C:\Users\Arvy Kairi\.kabot\workspace\landing_hacker.html เว็บนี้ใช้ฟอนต์อะไร"),
    ],
)
async def test_process_message_multilingual_file_context_followup_uses_recent_history(
    followup_text: str,
    history_text: str,
):
    captured: dict[str, str] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": captured["current_message"]}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None
    session = SimpleNamespace(metadata={})
    history = [{"role": "user", "content": history_text}]

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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
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
        content=followup_text,
    )
    await process_message(loop, msg)

    assert msg.metadata.get("required_tool") == "read_file"
    assert "landing_hacker.html" in str(msg.metadata.get("required_tool_query") or "")
    assert "[System Note: Explicit file reference]" in captured["current_message"]

@pytest.mark.asyncio
async def test_process_message_short_weather_followup_question_uses_pending_weather_context():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "berangin apa ga?"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "weather",
                "source": "suhu bandung sekarang berapa",
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
        tools=SimpleNamespace(
            tool_names=["weather"],
            has=lambda name: name == "weather",
        ),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="berangin apa ga?")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    assert msg.metadata.get("required_tool") == "weather"
    assert "bandung" in str(msg.metadata.get("required_tool_query", "")).lower()
    assert "berangin" in str(msg.metadata.get("required_tool_query", "")).lower()

@pytest.mark.asyncio
async def test_process_message_weather_tool_detected_from_raw_followup_still_enriches_pending_location_context():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "berangin apa ga?"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "weather",
                "source": "suhu bandung sekarang berapa",
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
        tools=SimpleNamespace(
            tool_names=["weather"],
            has=lambda name: name == "weather",
        ),
        _required_tool_for_query=lambda text: "weather" if "berangin" in str(text or "").lower() else None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="berangin apa ga?")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") == "weather"
    assert "bandung" in str(msg.metadata.get("required_tool_query", "")).lower()
    assert "berangin" in str(msg.metadata.get("required_tool_query", "")).lower()


@pytest.mark.asyncio
async def test_process_message_weather_forecast_followup_reuses_recent_weather_location():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "prediksi 3-6 jam ke depan"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "weather",
                "source": "cuaca cilacap sekarang",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "last_tool_context": {
                "tool": "weather",
                "location": "Cilacap",
                "source": "cuaca cilacap sekarang",
                "updated_at": time.time(),
            },
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
        tools=SimpleNamespace(tool_names=["weather"]),
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
        content="prediksi 3-6 jam ke depan",
    )
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") == "weather"
    assert "cilacap" in str(msg.metadata.get("required_tool_query", "")).lower()
    assert "prediksi" in str(msg.metadata.get("required_tool_query", "")).lower()


@pytest.mark.asyncio
async def test_process_message_weather_forecast_followup_survives_recent_answer_reference_when_last_tool_context_is_weather():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "prediksi 3-6 jam ke depan"}]
    session = SimpleNamespace(
        metadata={
            "last_tool_context": {
                "tool": "weather",
                "location": "Cilacap",
                "source": "cuaca cilacap sekarang",
                "updated_at": time.time(),
            },
        }
    )

    conversation_history = [
        {"role": "assistant", "content": "Iya, 27.6C di Cilacap itu termasuk lumayan panas buat aktivitas luar rumah."}
    ]

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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: conversation_history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=["weather"]),
        _required_tool_for_query=lambda text: "weather" if "prediksi" in str(text or "").lower() else None,
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
        content="prediksi 3-6 jam ke depan",
    )
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") == "weather"
    assert "cilacap" in str(msg.metadata.get("required_tool_query", "")).lower()
    assert "prediksi" in str(msg.metadata.get("required_tool_query", "")).lower()
    assert msg.metadata.get("continuity_source") != "answer_reference"


@pytest.mark.asyncio
async def test_process_message_weather_forecast_followup_beats_cron_parser_when_weather_context_is_grounded():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "prediksi 3-6 jam ke depan"}]
    session = SimpleNamespace(
        metadata={
            "last_tool_context": {
                "tool": "weather",
                "location": "Cilacap",
                "source": "cuaca cilacap sekarang",
                "updated_at": time.time(),
            },
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
        tools=SimpleNamespace(tool_names=["weather"]),
        _required_tool_for_query=lambda text: "cron" if "prediksi" in str(text or "").lower() else None,
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
        content="prediksi 3-6 jam ke depan",
    )
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") == "weather"
    assert "cilacap" in str(msg.metadata.get("required_tool_query", "")).lower()
    assert "prediksi" in str(msg.metadata.get("required_tool_query", "")).lower()

@pytest.mark.asyncio
async def test_process_message_stock_tool_detected_from_raw_followup_still_enriches_pending_symbol_context():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "jadikan idr harganya"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "stock",
                "source": "MSFT",
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
        tools=SimpleNamespace(
            tool_names=["stock"],
            has=lambda name: name == "stock",
        ),
        _required_tool_for_query=lambda text: "stock" if "idr" in str(text or "").lower() else None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="jadikan idr harganya")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") == "stock"
    assert "msft" in str(msg.metadata.get("required_tool_query", "")).lower()
    assert "idr" in str(msg.metadata.get("required_tool_query", "")).lower()


@pytest.mark.asyncio
async def test_process_message_stock_trend_followup_uses_recent_stock_context_for_analysis():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "trend nya naik?"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "stock",
                "source": "kalau saham apple berapa sekarang",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "last_tool_context": {
                "tool": "stock",
                "symbol": "AAPL",
                "source": "apple",
                "updated_at": time.time(),
            },
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
        tools=SimpleNamespace(
            tool_names=["stock", "stock_analysis"],
            has=lambda name: name in {"stock", "stock_analysis"},
        ),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="trend nya naik?")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") == "stock_analysis"
    assert "apple" in str(msg.metadata.get("required_tool_query", "")).lower()
    assert "trend" in str(msg.metadata.get("required_tool_query", "")).lower()


@pytest.mark.asyncio
async def test_process_message_contextual_stock_followup_keeps_analysis_intent_from_recent_user_query():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "Buatkan 3 skenario trading AAPL: breakout, pullback, invalidation",
                "profile": "GENERAL",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "pending_followup_tool": {
                "tool": "stock",
                "source": "AAPL",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
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
        tools=SimpleNamespace(
            tool_names=["stock", "stock_analysis"],
            has=lambda name: name in {"stock", "stock_analysis"},
        ),
        _required_tool_for_query=lambda text: (
            "stock_analysis"
            if "breakout" in str(text or "").lower()
            else ("stock" if "aapl" in str(text or "").lower() else None)
        ),
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="lanjut yang tadi")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") == "stock_analysis"
    assert "breakout" in str(msg.metadata.get("required_tool_query", "")).lower()


@pytest.mark.asyncio
async def test_process_message_referential_stock_followup_uses_context_instead_of_reinvoking_tool():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "Buatkan 3 skenario trading AAPL: breakout, pullback, invalidation",
                "profile": "GENERAL",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "pending_followup_tool": {
                "tool": "stock_analysis",
                "source": "Buatkan 3 skenario trading AAPL: breakout, pullback, invalidation",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
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
        _required_tool_for_query=lambda text: (
            "stock_analysis" if "breakout" in str(text or "").lower() else None
        ),
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="yang kedua")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    effective_content = str(msg.metadata.get("effective_content") or "")
    assert effective_content.startswith("yang kedua\n\n[Follow-up Context]\n")
    assert "breakout, pullback, invalidation" in effective_content.lower()


@pytest.mark.asyncio
async def test_process_message_hostile_feedback_does_not_reuse_stale_stock_followup():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "Buatkan 3 skenario trading AAPL: breakout, pullback, invalidation",
                "profile": "GENERAL",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "pending_followup_tool": {
                "tool": "stock_analysis",
                "source": "Buatkan 3 skenario trading AAPL: breakout, pullback, invalidation",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
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
        _required_tool_for_query=lambda text: (
            "stock_analysis" if "breakout" in str(text or "").lower() else None
        ),
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="tolol")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert "pending_followup_tool" not in session.metadata
    current_message = context_builder.build_messages.call_args.kwargs["current_message"]
    assert current_message.startswith("tolol")
    assert "[Feedback Note]" in current_message
    assert "do not joke" in current_message.lower()


@pytest.mark.asyncio
async def test_process_message_short_number_followup_reuses_recent_assistant_option_prompt_from_history():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    history = [
        {
            "role": "assistant",
            "content": "Siap, aku tunggu pilihanmu. Mau yang 1) ringkas, 2) detail, atau 3) tabel?",
        }
    ]
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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="detail"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="2")
    await process_message(loop, msg)

    effective_content = str(msg.metadata.get("effective_content") or "")
    assert "[Follow-up Context]" in effective_content
    assert "mau yang 1) ringkas, 2) detail, atau 3) tabel?" in effective_content.lower()


@pytest.mark.asyncio
async def test_process_message_option_ordinal_followup_reuses_recent_assistant_prompt_from_history():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    history = [
        {"role": "assistant", "content": "Siap, aku tunggu pilihanmu. Mau yang 1) ringkas, 2) detail, atau 3) tabel?"},
        {"role": "user", "content": "2"},
        {"role": "assistant", "content": "Siap, aku jelaskan versi detail."},
    ]
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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="tabel"),
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
        content="yang ketiga gimana",
    )
    await process_message(loop, msg)

    effective_content = str(msg.metadata.get("effective_content") or "")
    assert "[Follow-up Context]" in effective_content
    assert "[Selection Note]" in effective_content
    assert "option 3" in effective_content.lower()


@pytest.mark.asyncio
async def test_process_message_chinese_option_followup_reuses_recent_multiline_prompt_from_history():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    history = [
        {
            "role": "assistant",
            "content": (
                "\u5f53\u7136\u53ef\u4ee5\uff5e\n"
                "\u4f60\u53ef\u4ee5\u76f4\u63a5\u9009\u4e00\u4e2a\u7f16\u53f7\u5c31\u597d\uff1a\n"
                "1\uff09\u6b63\u5f0f\u6807\u51c6\n"
                "2\uff09\u975e\u5e38\u6b63\u5f0f\n"
                "3\uff09\u6b63\u5f0f\u4f46\u53cb\u597d\n"
                "\u5982\u679c\u4f60\u4e0d\u786e\u5b9a\uff0c\u6211\u4e5f\u53ef\u4ee5\u5148\u544a\u8bc9\u4f60\u8fd9\u4e09\u4e2a\u7248\u672c\u5404\u81ea\u9002\u5408\u4ec0\u4e48\u573a\u666f\u3002"
            ),
        }
    ]
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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="\u597d\u7684\uff0c\u6211\u7528\u7b2c\u4e8c\u79cd\u98ce\u683c\u3002"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="\u7b2c\u4e8c\u4e2a")
    await process_message(loop, msg)

    effective_content = str(msg.metadata.get("effective_content") or "")
    assert "[Follow-up Context]" in effective_content
    assert "\u4f60\u53ef\u4ee5\u76f4\u63a5\u9009\u4e00\u4e2a\u7f16\u53f7\u5c31\u597d" in effective_content
    assert "2\uff09\u975e\u5e38\u6b63\u5f0f" in effective_content
    assert "[Selection Note]" in effective_content
    assert "option 2" in effective_content.lower()

@pytest.mark.asyncio
async def test_process_message_meta_feedback_does_not_reuse_pending_stock_followup():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "kok lama"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "stock",
                "source": "MSFT",
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

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="kok lama")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None
    assert "pending_followup_tool" not in session.metadata

@pytest.mark.asyncio
async def test_process_message_short_confirmation_ignores_stale_pending_stock_when_tool_unavailable():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ya bagus"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "stock",
                "source": "BBRI",
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
        tools=SimpleNamespace(tool_names=["weather"], has=lambda name: name == "weather"),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="ya bagus")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None


@pytest.mark.asyncio
async def test_process_message_drops_unavailable_required_tool_selected_by_parser():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ya tolong ingat itu"}]
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
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=["weather"], has=lambda name: name == "weather"),
        _required_tool_for_query=lambda _text: "stock",
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="ya tolong ingat itu")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None


@pytest.mark.asyncio
async def test_process_message_advice_request_does_not_force_weather_from_keyword_only_parser():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [
        {"role": "user", "content": "sunscreen yang bagus buat cuaca panas apa ya?"}
    ]
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
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda text: "weather" if "panas" in str(text or "").lower() else None,
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
        content="sunscreen yang bagus buat cuaca panas apa ya?",
    )
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None

@pytest.mark.asyncio
async def test_process_message_stock_idr_followup_uses_structured_last_tool_context_without_pending_tool():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "jadikan idr harganya"}]
    session = SimpleNamespace(
        metadata={
            "last_tool_context": {
                "tool": "stock",
                "symbol": "MSFT",
                "entity": "Microsoft",
                "currency": "USD",
                "quote_price": 410.68,
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
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(
            tool_names=["stock"],
            has=lambda name: name == "stock",
        ),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="jadikan idr harganya")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    assert msg.metadata.get("required_tool") == "stock"
    assert "msft" in str(msg.metadata.get("required_tool_query", "")).lower()
    assert "idr" in str(msg.metadata.get("required_tool_query", "")).lower()

@pytest.mark.asyncio
async def test_process_message_weather_context_beats_update_keyword_overlap():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [
        {"role": "user", "content": "cek update real time kondisi cuaca kecepatan angin arah angin di bandung"}
    ]
    session = SimpleNamespace(
        metadata={
            "last_tool_context": {
                "tool": "weather",
                "location": "bandung",
                "source": "suhu bandung sekarang berapa",
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
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(
            tool_names=["weather", "check_update"],
            has=lambda name: name in {"weather", "check_update"},
        ),
        _required_tool_for_query=lambda text: "check_update" if "update" in str(text or "").lower() else None,
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
        content="cek update real time kondisi cuaca kecepatan angin arah angin di bandung",
    )
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    assert msg.metadata.get("required_tool") == "weather"
    assert "bandung" in str(msg.metadata.get("required_tool_query", "")).lower()
    assert "angin" in str(msg.metadata.get("required_tool_query", "")).lower()

@pytest.mark.asyncio
async def test_process_message_multilingual_weather_followup_uses_last_location_context():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "风大吗？"}]
    session = SimpleNamespace(
        metadata={
            "last_tool_context": {
                "tool": "weather",
                "location": "北京",
                "source": "北京今天天气怎么样？",
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
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(
            tool_names=["weather"],
            has=lambda name: name == "weather",
        ),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="风大吗？")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    assert msg.metadata.get("required_tool") == "weather"
    assert "北京" in str(msg.metadata.get("required_tool_query", ""))

@pytest.mark.asyncio
async def test_process_message_weather_metric_interpretation_followup_keeps_ai_driven_reply():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "kecepatan angin 4.4km/h?"}]
    session = SimpleNamespace(
        metadata={
            "last_tool_context": {
                "tool": "weather",
                "location": "Cilacap",
                "source": "cuaca cilacap sekarang",
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
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: "weather",
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
        content="kecepatan angin 4.4km/h?",
    )
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None


@pytest.mark.asyncio
async def test_process_message_explicit_file_request_does_not_force_pending_tool_followup():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "baca file config.json"}]
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

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="baca file config.json")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None
    assert "pending_followup_tool" not in session.metadata

@pytest.mark.asyncio
async def test_process_message_config_question_does_not_force_pending_tool_followup():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "di config ada model apa saja"}]
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

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="di config ada model apa saja")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None
    assert "pending_followup_tool" not in session.metadata

@pytest.mark.asyncio
async def test_process_message_explicit_file_request_does_not_force_pending_intent_followup():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "baca file config.json"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "carikan berita perang iran terbaru 2026 sekarang",
                "profile": "RESEARCH",
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

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="baca file config.json")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None
    assert "pending_followup_intent" not in session.metadata


@pytest.mark.asyncio
async def test_process_message_list_dir_context_followup_reuses_last_directory_state():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "terus folder bot ada apa aja, 5 item aja"}]
    session = SimpleNamespace(
        metadata={
            "last_tool_context": {
                "tool": "list_dir",
                "path": r"C:\Users\Arvy Kairi\Desktop",
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
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda name: name == "list_dir"),
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
        content="terus folder bot ada apa aja, 5 item aja",
    )
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    assert msg.metadata.get("required_tool") == "list_dir"
    assert msg.metadata.get("required_tool_query") == "terus folder bot ada apa aja, 5 item aja"


@pytest.mark.asyncio
async def test_process_message_short_followup_reuses_last_tool_execution_for_mcp_tool():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "cek lagi dong"}]
    session = SimpleNamespace(
        metadata={
            "last_tool_execution": {
                "tool": "mcp__yahoo_finance__quote",
                "source": "^jkse",
                "args": {"symbol": "^JKSE"},
                "result_preview": '{"symbol":"^JKSE","price":7210.31}',
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
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda _name: False),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="cek lagi dong")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    assert msg.metadata.get("required_tool") == "mcp__yahoo_finance__quote"
    assert msg.metadata.get("required_tool_query") == "^jkse"


@pytest.mark.asyncio
async def test_process_message_explicit_new_request_does_not_reuse_last_tool_execution():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "baca file config.json"}]
    session = SimpleNamespace(
        metadata={
            "last_tool_execution": {
                "tool": "mcp__yahoo_finance__quote",
                "source": "^jkse",
                "args": {"symbol": "^JKSE"},
                "result_preview": '{"symbol":"^JKSE","price":7210.31}',
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
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda _name: False),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="baca file config.json")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None


@pytest.mark.asyncio
async def test_process_message_answer_reference_beats_last_tool_execution_context():
    captured_messages = {}

    def _build_messages(**kwargs):
        captured_messages["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": "ctx"}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None
    assistant_text = "Yang saya maksud: angin 4.4 km/h itu tergolong pelan."
    session = SimpleNamespace(
        metadata={
            "last_tool_execution": {
                "tool": "mcp__yahoo_finance__quote",
                "source": "^jkse",
                "args": {"symbol": "^JKSE"},
                "result_preview": '{"symbol":"^JKSE","price":7210.31}',
                "updated_at": time.time(),
            }
        }
    )
    history = [{"role": "assistant", "content": assistant_text}]

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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda _name: False),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="maksudnya apa itu")
    await process_message(loop, msg)

    loop._run_simple_response.assert_not_called()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("continuity_source") == "answer_reference"
    current_message = captured_messages.get("current_message") or str(msg.metadata.get("effective_content") or "")
    assert current_message.startswith("maksudnya apa itu\n\n[Answer Reference Target]\n")
    assert "[Grounded Answer Note]\n" in current_message
    assert "[Answer Reference Context]\n" in current_message
    assert assistant_text in current_message


@pytest.mark.asyncio
async def test_process_message_plain_apa_itu_reuses_recent_assistant_answer_context():
    captured_messages = {}

    def _build_messages(**kwargs):
        captured_messages["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": "ctx"}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None
    assistant_text = (
        "Skill ini akan cek uptime, load, RAM, disk, network, dan service penting di VPS Linux."
    )
    session = SimpleNamespace(metadata={})
    history = [{"role": "assistant", "content": assistant_text}]

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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda _name: False),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="apa itu")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("continuity_source") == "answer_reference"
    current_message = captured_messages.get("current_message") or str(msg.metadata.get("effective_content") or "")
    assert current_message.startswith("apa itu\n\n[Answer Reference Target]\n")
    assert "[Answer Reference Context]\n" in current_message
    assert assistant_text in current_message


@pytest.mark.asyncio
async def test_process_message_last_tool_execution_beats_recent_user_intent_for_short_followup():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "cek lagi dong"}]
    session = SimpleNamespace(
        metadata={
            "last_tool_execution": {
                "tool": "mcp__yahoo_finance__quote",
                "source": "^jkse",
                "args": {"symbol": "^JKSE"},
                "result_preview": '{"symbol":"^JKSE","price":7210.31}',
                "updated_at": time.time(),
            }
        }
    )
    history = [{"role": "user", "content": "kalau saham apple berapa sekarang"}]

    def _required_tool(text: str) -> str | None:
        normalized = str(text or "").lower()
        if "apple" in normalized or "saham" in normalized or "stock" in normalized:
            return "stock"
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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda _name: False),
        _required_tool_for_query=_required_tool,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="cek lagi dong")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    assert msg.metadata.get("required_tool") == "mcp__yahoo_finance__quote"
    assert msg.metadata.get("required_tool_query") == "^jkse"
    assert msg.metadata.get("continuity_source") == "tool_execution"


@pytest.mark.asyncio
async def test_process_message_short_contextual_followup_does_not_reuse_last_stock_execution():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "kenapa lagi"}]
    session = SimpleNamespace(
        metadata={
            "last_tool_execution": {
                "tool": "stock",
                "source": "BBRI",
                "args": {"symbol": "BBRI"},
                "result_preview": "[STOCK] BBRI ...",
                "updated_at": time.time(),
            }
        }
    )
    history = [{"role": "user", "content": "harga bbri sekarang"}]

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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=["stock"], has=lambda name: name == "stock"),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="kenapa lagi")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None


@pytest.mark.asyncio
async def test_process_message_recent_user_intent_beats_weak_parser_guess_on_low_information_followup():
    captured = {}

    def _build_messages(**kwargs):
        captured["skill_names"] = kwargs.get("skill_names")
        return [{"role": "user", "content": "update dong"}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    session = SimpleNamespace(metadata={})
    history = [{"role": "user", "content": "cek suhu cilacap sekarang"}]

    def _required_tool(text: str) -> str | None:
        normalized = str(text or "").lower()
        if "update" in normalized:
            return "check_update"
        if "suhu" in normalized or "cuaca" in normalized:
            return "weather"
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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=["weather", "check_update"], has=lambda name: name in {"weather", "check_update"}),
        _required_tool_for_query=_required_tool,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="update dong")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    assert msg.metadata.get("required_tool") == "weather"
    assert msg.metadata.get("required_tool_query") == "cek suhu cilacap sekarang"
    assert msg.metadata.get("continuity_source") == "user_intent"
    assert msg.metadata.get("forced_skill_names") == ["weather"]
    assert msg.metadata.get("suppress_required_tool_inference") is True
    assert captured.get("skill_names") == ["weather"]


@pytest.mark.asyncio
async def test_process_message_explicit_weather_query_marks_parser_continuity_source():
    captured = {}

    def _build_messages(**kwargs):
        captured["skill_names"] = kwargs.get("skill_names")
        return [{"role": "user", "content": "cek suhu cilacap sekarang"}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    session = SimpleNamespace(metadata={})

    def _required_tool(text: str) -> str | None:
        normalized = str(text or "").lower()
        if "suhu" in normalized or "cuaca" in normalized:
            return "weather"
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
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=["weather"], has=lambda name: name == "weather"),
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
        content="cek suhu cilacap sekarang",
    )
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    assert msg.metadata.get("required_tool") == "weather"
    assert msg.metadata.get("continuity_source") == "parser"
    assert msg.metadata.get("forced_skill_names") == ["weather"]
    assert msg.metadata.get("suppress_required_tool_inference") is True
    assert captured.get("skill_names") == ["weather"]


@pytest.mark.asyncio
async def test_process_message_contextual_followup_reuses_recent_assistant_answer_topic():
    captured_messages = {}

    def _build_messages(**kwargs):
        captured_messages["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": "ctx"}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None
    assistant_text = (
        "Untuk perjalanan di Cilacap sekarang, paling aman pilih pakaian ringan, "
        "bawa payung kecil, dan tetap siap kalau mendung menebal."
    )
    session = SimpleNamespace(metadata={})
    history = [{"role": "assistant", "content": assistant_text}]

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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda _name: False),
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
        content="kalau untuk bepergian bagaimana",
    )
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("continuity_source") == "answer_reference"
    current_message = captured_messages["current_message"]
    assert current_message.startswith("kalau untuk bepergian bagaimana\n\n[Answer Reference Target]\n")
    assert "[Grounded Answer Note]\n" in current_message
    assert "[Answer Reference Context]\n" in current_message
    assert assistant_text in current_message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("followup_text", "assistant_text"),
    (
        (
            "\u7b2c\u4e8c\u4e2a\u662f\u4ec0\u4e48\uff1f\u7b80\u77ed\u56de\u7b54\u3002",
            "\U0001f4c1 .basetemp\n\U0001f4c1 .claude\n\U0001f4c4 .dockerignore",
        ),
        (
            "\u0e02\u0e49\u0e2d\u0e17\u0e35\u0e48\u0e2a\u0e2d\u0e07\u0e04\u0e37\u0e2d\u0e2d\u0e30\u0e44\u0e23 \u0e15\u0e2d\u0e1a\u0e2a\u0e31\u0e49\u0e19\u0e46",
            "\U0001f4c1 .basetemp\n\U0001f4c1 .claude\n\U0001f4c4 .dockerignore",
        ),
    ),
)
async def test_process_message_multilingual_option_reference_followup_reuses_recent_assistant_answer(
    followup_text: str,
    assistant_text: str,
):
    captured_messages = {}

    def _build_messages(**kwargs):
        captured_messages["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": "ctx"}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None
    session = SimpleNamespace(metadata={})
    history = [{"role": "assistant", "content": assistant_text}]

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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda _name: False),
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
        content=followup_text,
    )
    await process_message(loop, msg)

    loop._run_simple_response.assert_not_called()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("continuity_source") == "answer_reference"
    current_message = captured_messages.get("current_message") or str(msg.metadata.get("effective_content") or "")
    assert "[Answer Reference Target]\n" in current_message
    assert "[Answer Reference Context]\n" in current_message
    assert "[Referenced Item Context]\n" in current_message
    assert "[Grounded Answer Note]\n" in current_message
    assert "[Selection Note]\n" in current_message
    assert "option 2" in current_message.lower()
    assert "\U0001f4c1 .claude" in current_message
    assert assistant_text in current_message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("followup_text", "assistant_text", "pending_intent_text"),
    (
        (
            "\u0e02\u0e49\u0e2d\u0e17\u0e35\u0e48\u0e2a\u0e2d\u0e07\u0e04\u0e37\u0e2d\u0e2d\u0e30\u0e44\u0e23 \u0e15\u0e2d\u0e1a\u0e2a\u0e31\u0e49\u0e19\u0e46",
            "\U0001f4c1 .basetemp\n\U0001f4c1 .claude\n\U0001f4c4 .dockerignore",
            "tampilkan 3 item pertama dari folder c:\\users\\arvy kairi\\desktop\\bot\\kabot",
        ),
        (
            "\u305d\u308c\u3063\u3066\u3069\u3046\u3044\u3046\u610f\u5473\uff1f\u4e00\u884c\u3060\u3051\u3002",
            "halo-mcp-konteks",
            "gunakan tool mcp.local_echo.echo dengan argumen text='halo-mcp-konteks' lalu tampilkan hasilnya saja.",
        ),
    ),
)
async def test_process_message_answer_reference_ignores_stale_pending_intent_context(
    followup_text: str,
    assistant_text: str,
    pending_intent_text: str,
):
    captured_messages = {}

    def _build_messages(**kwargs):
        captured_messages["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": "ctx"}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None
    now_ts = time.time()
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": pending_intent_text,
                "profile": "GENERAL",
                "updated_at": now_ts,
                "expires_at": now_ts + 60,
            }
        }
    )
    history = [{"role": "assistant", "content": assistant_text}]

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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda _name: False),
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
        content=followup_text,
    )
    await process_message(loop, msg)

    assert msg.metadata.get("continuity_source") == "answer_reference"
    effective_content = str(msg.metadata.get("effective_content") or "")
    assert "[Follow-up Context]\n" not in effective_content


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("followup_text", "assistant_text"),
    (
        (
            "\u7b2c\u4e8c\u4e2a\u662f\u4ec0\u4e48\uff1f\u7b80\u77ed\u56de\u7b54\u3002",
            "\U0001f4c1 .basetemp\n\U0001f4c1 .claude\n\U0001f4c4 .dockerignore",
        ),
        (
            "\u0e02\u0e49\u0e2d\u0e17\u0e35\u0e48\u0e2a\u0e2d\u0e07\u0e04\u0e37\u0e2d\u0e2d\u0e30\u0e44\u0e23 \u0e15\u0e2d\u0e1a\u0e2a\u0e31\u0e49\u0e19\u0e46",
            "\U0001f4c1 .basetemp\n\U0001f4c1 .claude\n\U0001f4c4 .dockerignore",
        ),
    ),
)
async def test_process_message_answer_reference_selection_followup_can_fast_reply_from_target(
    followup_text: str,
    assistant_text: str,
):
    session = SimpleNamespace(metadata={})
    history = [{"role": "assistant", "content": assistant_text}]
    captured = {}

    async def _finalize(_msg, _session, final_content):
        captured["final_content"] = str(final_content or "")
        return OutboundMessage(channel="telegram", chat_id="chat-1", content=str(final_content or ""))

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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: MagicMock(),
        context=MagicMock(),
        tools=SimpleNamespace(tool_names=[], has=lambda _name: False),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(side_effect=_finalize),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content=followup_text)
    await process_message(loop, msg)

    loop._run_simple_response.assert_not_called()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("continuity_source") == "answer_reference"
    assert ".claude" in captured["final_content"]
    assert ".basetemp" not in captured["final_content"]
    assert ".dockerignore" not in captured["final_content"]


@pytest.mark.asyncio
async def test_process_message_answer_reference_meaning_followup_can_fast_reply_from_target():
    session = SimpleNamespace(metadata={})
    history = [{"role": "assistant", "content": "halo-mcp-konteks"}]
    captured = {}

    async def _finalize(_msg, _session, final_content):
        captured["final_content"] = str(final_content or "")
        return OutboundMessage(channel="telegram", chat_id="chat-1", content=str(final_content or ""))

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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: MagicMock(),
        context=MagicMock(),
        tools=SimpleNamespace(tool_names=[], has=lambda _name: False),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(side_effect=_finalize),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="\u305d\u308c\u3063\u3066\u3069\u3046\u3044\u3046\u610f\u5473\uff1f\u4e00\u884c\u3060\u3051\u3002",
    )
    await process_message(loop, msg)

    loop._run_simple_response.assert_not_called()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("continuity_source") == "answer_reference"
    assert "halo-mcp-konteks" in captured["final_content"]
    assert "\u305d\u308c\u3063\u3066\u3069\u3046\u3044\u3046\u610f\u5473" not in captured["final_content"]


@pytest.mark.asyncio
async def test_process_message_answer_reference_selection_beats_list_dir_followup_fallback():
    session = SimpleNamespace(
        metadata={
            "last_tool_context": {
                "tool": "list_dir",
                "path": r"C:\Users\Arvy Kairi\Desktop\bot\kabot",
                "updated_at": time.time(),
            }
        }
    )
    history = [{"role": "assistant", "content": "\U0001f4c1 .basetemp\n\U0001f4c1 .claude\n\U0001f4c4 .dockerignore"}]
    captured = {}

    async def _finalize(_msg, _session, final_content):
        captured["final_content"] = str(final_content or "")
        return OutboundMessage(channel="telegram", chat_id="chat-1", content=str(final_content or ""))

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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: MagicMock(),
        context=MagicMock(),
        tools=SimpleNamespace(tool_names=["list_dir"], has=lambda name: name == "list_dir"),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(side_effect=_finalize),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="\u0e02\u0e49\u0e2d\u0e17\u0e35\u0e48\u0e2a\u0e2d\u0e07\u0e04\u0e37\u0e2d\u0e2d\u0e30\u0e44\u0e23 \u0e15\u0e2d\u0e1a\u0e2a\u0e31\u0e49\u0e19\u0e46",
    )
    await process_message(loop, msg)

    loop._run_agent_loop.assert_not_called()
    loop._run_simple_response.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("continuity_source") == "answer_reference"
    assert ".claude" in captured["final_content"]
    assert ".basetemp" not in captured["final_content"]


@pytest.mark.asyncio
async def test_process_message_memory_recall_uses_relevant_memory_facts_over_stale_tool_state():
    captured_messages = {}

    def _build_messages(**kwargs):
        captured_messages["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": "ctx"}]

    async def _search_memory(*, query: str, session_id: str | None = None, limit: int = 5):
        return [
            {
                "content": "[preference] The saved preference code is MEM-42.",
                "metadata": {"category": "preference"},
            }
        ]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None
    now_ts = time.time()
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "stock",
                "source": "cek saham apple sekarang",
                "updated_at": now_ts,
                "expires_at": now_ts + 60,
            }
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=False),
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
        memory=SimpleNamespace(
            get_conversation_context=lambda _key, max_messages=30: [],
            search_memory=_search_memory,
        ),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False, turn_category="chat"))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda _name: False),
        _required_tool_for_query=lambda text: "stock" if "code" in str(text or "").lower() else None,
        _run_simple_response=AsyncMock(return_value="MEM-42"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="MEM-42")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="what is my preference code?",
    )
    await process_message(loop, msg)

    loop._run_agent_loop.assert_not_called()
    loop._run_simple_response.assert_awaited_once()
    assert msg.metadata.get("required_tool") is None
    assert "memory_facts" in list(msg.metadata.get("layered_context_sources") or [])
    current_message = captured_messages["current_message"]
    assert "[Relevant Memory Facts]\n" in current_message
    assert "MEM-42" in current_message
    assert "[Memory Recall Note]\n" in current_message


@pytest.mark.asyncio
async def test_process_message_memory_recall_prioritizes_user_profile_and_skips_query_echo():
    captured_messages = {}

    def _build_messages(**kwargs):
        captured_messages["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": "ctx"}]

    async def _search_memory(*, query: str, session_id: str | None = None, limit: int = 5):
        return [
            {
                "role": "user",
                "content": "what do you remember about me",
            },
            {
                "role": "system",
                "content": "[preference] If the user asks \"who am I?\", answer: Maha Raja.",
            },
        ]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None
    session = SimpleNamespace(
        metadata={
            "user_profile": {
                "address": "Maha Raja",
                "self_identity_answer": "Maha Raja",
            }
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=False),
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
        memory=SimpleNamespace(
            get_conversation_context=lambda _key, max_messages=30: [],
            search_memory=_search_memory,
        ),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False, turn_category="chat"))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda _name: False),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="Maha Raja"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="Maha Raja")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="what do you remember about me",
    )
    await process_message(loop, msg)

    current_message = captured_messages["current_message"]
    assert "User prefers to be addressed as: Maha Raja" in current_message
    assert "[preference] If the user asks \"who am I?\", answer: Maha Raja." in current_message
    assert "\n- what do you remember about me\n" not in current_message


@pytest.mark.asyncio
async def test_process_message_complex_turn_includes_relevant_learned_execution_hints():
    captured_messages = {}

    def _build_messages(**kwargs):
        captured_messages["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": "ctx"}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=False),
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
        memory=SimpleNamespace(
            get_conversation_context=lambda _key, max_messages=30: [],
            get_recent_lessons=lambda limit=8, task_type="complex": [
                {
                    "trigger": "send screenshot file to chat",
                    "guardrail": "Only claim screenshot delivery after message(files=...) succeeds.",
                },
                {
                    "trigger": "stock price lookup",
                    "guardrail": "Verify the symbol before quoting a price.",
                },
            ],
        ),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CODING", is_complex=True, turn_category="action"))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda _name: False),
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
        content="bikin landing page lalu screenshot dan kirim ke chat ini",
    )
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    current_message = captured_messages["current_message"]
    assert "[Learned Execution Hints]\n" in current_message
    assert "screenshot delivery" in current_message.lower()
    assert "Verify the symbol before quoting a price." not in current_message
    assert "learned_hints" in list(msg.metadata.get("layered_context_sources") or [])


@pytest.mark.asyncio
async def test_process_message_explicit_send_file_request_keeps_message_tool_over_list_dir_followup_context():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "kirim file tes.md kesini"}]
    session = SimpleNamespace(
        metadata={
            "last_tool_context": {
                "tool": "list_dir",
                "path": r"C:\\Users\\Arvy Kairi\\Desktop\\bot",
                "source": r"C:\\Users\\Arvy Kairi\\Desktop\\bot",
                "updated_at": time.time(),
            },
            "last_navigated_path": r"C:\\Users\\Arvy Kairi\\Desktop\\bot",
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
        tools=SimpleNamespace(
            tool_names=["message", "list_dir"],
            has=lambda name: name in {"message", "list_dir"},
        ),
        _required_tool_for_query=lambda _text: "message",
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="kirim file tes.md kesini")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") == "message"


@pytest.mark.asyncio
async def test_process_message_bare_send_file_request_keeps_message_tool_over_list_dir_followup_context():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "kirim file tes.md"}]
    session = SimpleNamespace(
        metadata={
            "last_tool_context": {
                "tool": "list_dir",
                "path": r"C:\\Users\\Arvy Kairi\\Desktop\\bot",
                "source": r"C:\\Users\\Arvy Kairi\\Desktop\\bot",
                "updated_at": time.time(),
            },
            "last_navigated_path": r"C:\\Users\\Arvy Kairi\\Desktop\\bot",
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
        tools=SimpleNamespace(
            tool_names=["message", "list_dir"],
            has=lambda name: name in {"message", "list_dir"},
        ),
        _required_tool_for_query=lambda _text: "message",
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="kirim file tes.md")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") == "message"
