import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.loop_core.message_runtime import process_message, process_system_message
from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.session.manager import Session, SessionManager


@pytest.mark.asyncio
async def test_process_message_command_response_uses_session_finalize_path():
    session = SimpleNamespace(metadata={})
    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_observability=None,
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(
            is_command=lambda _content: True,
            route=AsyncMock(return_value="Command handled."),
        ),
        _init_session=AsyncMock(return_value=session),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="Command handled.")
        ),
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="/status",
    )
    response = await process_message(loop, msg)

    assert response is not None
    loop._init_session.assert_awaited_once_with(msg)
    loop._finalize_session.assert_awaited_once_with(msg, session, "Command handled.")


@pytest.mark.asyncio
async def test_process_message_drains_pending_memory_before_loading_history_for_followup():
    history_rows: list[dict[str, str]] = []
    assistant_text = (
        "Untuk perjalanan di Cilacap sekarang, paling aman pilih pakaian ringan, "
        "bawa payung kecil, dan tetap siap kalau mendung menebal."
    )
    captured_messages: dict[str, str] = {}

    async def _flush_pending_memory(*, max_wait_ms: int = 250) -> int:
        await asyncio.sleep(0)
        history_rows.append({"role": "assistant", "content": assistant_text})
        return 1

    def _build_messages(**kwargs):
        captured_messages["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": captured_messages["current_message"]}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        runtime_observability=None,
        _parse_approval_command=lambda _content: None,
        _drain_pending_memory_writes=AsyncMock(side_effect=_flush_pending_memory),
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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: list(history_rows)),
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
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="kalau untuk bepergian bagaimana",
    )
    await process_message(loop, msg)

    loop._drain_pending_memory_writes.assert_awaited_once()
    assert msg.metadata.get("continuity_source") == "answer_reference"
    assert assistant_text in captured_messages["current_message"]


@pytest.mark.asyncio
async def test_process_message_contextual_answer_reference_beats_stale_pending_user_intent():
    assistant_text = (
        "Untuk perjalanan di Cilacap sekarang, paling aman pilih pakaian ringan, "
        "bawa payung kecil, dan tetap siap kalau mendung menebal."
    )
    captured_messages: dict[str, str] = {}
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "weather",
                "source": "cuaca cilacap sekarang bagaimana",
                "updated_at": 1_773_232_800.0,
                "expires_at": 1_773_233_100.0,
            },
            "pending_followup_intent": {
                "text": "cuaca cilacap sekarang bagaimana",
                "profile": "GENERAL",
                "updated_at": 1_773_232_800.0,
                "expires_at": 1_773_233_100.0,
            }
        }
    )

    def _build_messages(**kwargs):
        captured_messages["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": captured_messages["current_message"]}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        runtime_observability=None,
        _parse_approval_command=lambda _content: None,
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
        memory=SimpleNamespace(
            get_conversation_context=lambda _key, max_messages=30: [
                {"role": "assistant", "content": assistant_text}
            ]
        ),
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
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="kalau untuk bepergian bagaimana",
    )
    await process_message(loop, msg)

    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("continuity_source") == "answer_reference"
    assert assistant_text in captured_messages["current_message"]


@pytest.mark.asyncio
async def test_process_system_message_persists_origin_turn_into_memory_backend():
    routed_context = MagicMock()
    routed_context.build_messages.return_value = [{"role": "user", "content": "cron ping"}]

    session = MagicMock()
    session.get_history.return_value = []
    memory = SimpleNamespace(
        create_session=MagicMock(),
        add_message=AsyncMock(),
    )

    contextual_tools: dict[str, Any] = {
        name: SimpleNamespace(set_context=MagicMock())
        for name in {"message", "spawn", "cron"}
    }

    loop = SimpleNamespace(
        runtime_performance=SimpleNamespace(fast_first_response=False),
        runtime_observability=None,
        memory=memory,
        sessions=SimpleNamespace(get_or_create=MagicMock(return_value=session), save=MagicMock()),
        tools=SimpleNamespace(get=lambda name: contextual_tools.get(name)),
        _resolve_context_for_channel_chat=MagicMock(return_value=routed_context),
        _run_agent_loop=AsyncMock(return_value="done"),
        context=MagicMock(),
        last_usage=None,
    )

    msg = InboundMessage(
        channel="system",
        sender_id="cron",
        chat_id="telegram:chat-1",
        content="Reminder: HM workout starts in 5 minutes.",
    )

    response = await process_system_message(loop, msg)

    assert response is not None
    assert response.channel == "telegram"
    assert response.chat_id == "chat-1"
    memory.create_session.assert_called_once_with("telegram:chat-1", "telegram", "chat-1", "cron")
    memory.add_message.assert_has_awaits(
        [
            (( "telegram:chat-1", "user", "[System: cron] Reminder: HM workout starts in 5 minutes."),),
            (( "telegram:chat-1", "assistant", "done"),),
        ]
    )


@pytest.mark.asyncio
async def test_process_message_memory_recall_followup_bypasses_fast_simple_context():
    captured_messages: dict[str, list[dict[str, str]]] = {}
    context_builder = MagicMock()
    context_builder.consume_last_truncation_summary.return_value = None

    def _build_messages(**kwargs):
        messages = [
            {"role": "system", "content": "ctx"},
            *list(kwargs.get("history") or []),
            {"role": "user", "content": str(kwargs.get("current_message") or "")},
        ]
        captured_messages["messages"] = messages
        return messages

    context_builder.build_messages.side_effect = _build_messages
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        runtime_observability=None,
        _parse_approval_command=lambda _content: None,
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
        memory=SimpleNamespace(
            get_conversation_context=lambda _key, max_messages=30: [
                {"role": "assistant", "content": "好的，我会记住偏好代码 MEMZH-314。"}
            ]
        ),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda _name: False),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="MEMZH-314"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="MEMZH-314")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="我刚才让你记住的代码是什么？只回答代码。",
    )
    response = await process_message(loop, msg)

    assert response is not None
    context_builder.build_messages.assert_called_once()
    assert any(item.get("role") == "assistant" for item in captured_messages["messages"])


@pytest.mark.asyncio
async def test_process_message_falls_back_to_durable_session_snapshot_when_memory_is_empty(tmp_path):
    manager = SessionManager(tmp_path)
    original = Session(
        key="telegram:chat-9",
        metadata={
            "durable_history": [
                {"role": "user", "content": "cuaca cilacap sekarang bagaimana"},
                {
                    "role": "assistant",
                    "content": "Sekarang berawan, paling aman pakai baju ringan dan bawa payung kecil.",
                },
            ]
        },
    )
    manager.save(original)
    restored = manager.get_or_create("telegram:chat-9")
    restored.messages = []

    captured_history: dict[str, list[dict[str, str]]] = {}
    context_builder = MagicMock()
    context_builder.consume_last_truncation_summary.return_value = None

    def _build_messages(**kwargs):
        captured_history["history"] = list(kwargs.get("history") or [])
        return [{"role": "user", "content": str(kwargs.get("current_message") or "")}]

    context_builder.build_messages.side_effect = _build_messages

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=False),
        runtime_observability=None,
        _parse_approval_command=lambda _content: None,
        _drain_pending_memory_writes=AsyncMock(return_value=0),
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=restored),
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
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False, turn_category="chat"))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda _name: False),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-9", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-9",
        content="kalau untuk bepergian bagaimana",
        _session_key="telegram:chat-9",
    )

    response = await process_message(loop, msg)

    assert response is not None
    assert captured_history["history"] == [
        {"role": "user", "content": "cuaca cilacap sekarang bagaimana"},
        {
            "role": "assistant",
            "content": "Sekarang berawan, paling aman pakai baju ringan dan bawa payung kecil.",
        },
    ]
