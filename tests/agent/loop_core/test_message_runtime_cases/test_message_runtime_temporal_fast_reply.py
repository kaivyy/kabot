from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import kabot.agent.loop_core.message_runtime as message_runtime_module
from kabot.agent.loop_core.message_runtime import process_message
from kabot.agent.loop_core.message_runtime_parts.temporal import build_temporal_fast_reply
from kabot.bus.events import InboundMessage, OutboundMessage


def _fixed_wib_now() -> datetime:
    return datetime(2026, 3, 9, 14, 5, tzinfo=timezone(timedelta(hours=7)))


@pytest.mark.parametrize(
    ("query", "semantic_intent", "expected_fragment"),
    [
        ("what day is it?", "day_today", "Monday"),
        ("what day is it tomorrow?", "day_tomorrow", "Tuesday"),
        ("what day was it yesterday?", "day_yesterday", "Sunday"),
        ("what day one week from now?", "day_next_week", "Monday"),
    ],
)
def test_build_temporal_fast_reply_handles_semantic_intents(
    query,
    semantic_intent,
    expected_fragment,
):
    reply = build_temporal_fast_reply(
        query,
        now_local=_fixed_wib_now(),
        semantic_intent=semantic_intent,
    )

    assert reply is not None
    assert expected_fragment in reply


def test_build_temporal_fast_reply_ignores_non_question_feedback():
    reply = build_temporal_fast_reply(
        "it's monday already, why was this not stored in memory",
        now_local=_fixed_wib_now(),
    )

    assert reply is None


def test_build_temporal_fast_reply_prioritizes_semantic_day_intent():
    reply = build_temporal_fast_reply(
        "what day is it? answer briefly and use WIB.",
        now_local=_fixed_wib_now(),
        semantic_intent="day_today",
    )

    assert reply == "Today is Monday."


def test_build_temporal_fast_reply_no_longer_uses_keyword_parser_fallback():
    reply = build_temporal_fast_reply(
        "what day is it?",
        now_local=_fixed_wib_now(),
    )

    assert reply is None


def test_build_temporal_fast_reply_accepts_semantic_intent_override():
    reply = build_temporal_fast_reply(
        "lanjut",
        now_local=_fixed_wib_now(),
        semantic_intent="time_now",
    )

    assert reply is not None
    assert "14:05" in reply


@pytest.mark.asyncio
async def test_process_message_temporal_fast_reply_skips_context_and_llm(monkeypatch):
    routed_context = MagicMock()
    routed_context.build_messages.return_value = [{"role": "user", "content": "hari apa sekarang"}]
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
        _resolve_context_for_message=lambda _msg: routed_context,
        context=routed_context,
        tools=SimpleNamespace(tool_names=["read_file"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="llm-should-not-run"),
        _run_agent_loop=AsyncMock(return_value="agent-should-not-run"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="Today is Monday.")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
        bus=None,
        channel_manager=None,
    )

    monkeypatch.setattr(
        message_runtime_module,
        "build_temporal_fast_reply",
        lambda text, *, locale=None, now_local=None, semantic_intent=None: "Today is Monday.",
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="what day is it?")
    response = await process_message(loop, msg)

    assert response is not None
    assert response.content == "Today is Monday."
    routed_context.build_messages.assert_not_called()
    loop._run_simple_response.assert_not_awaited()
    loop._run_agent_loop.assert_not_awaited()
