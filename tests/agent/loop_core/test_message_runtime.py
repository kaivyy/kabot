from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.loop_core.message_runtime import (
    process_isolated,
    process_message,
    process_system_message,
)
from kabot.bus.events import InboundMessage, OutboundMessage


@pytest.mark.asyncio
async def test_process_message_uses_routed_context_builder():
    routed_context = MagicMock()
    routed_context.build_messages.return_value = [{"role": "user", "content": "halo"}]
    default_context = MagicMock()

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=None,
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=SimpleNamespace(metadata={})),
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
        context=default_context,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="ok"),
        _run_agent_loop=AsyncMock(return_value="ok"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="ok")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="halo")
    response = await process_message(loop, msg)

    assert response is not None
    routed_context.build_messages.assert_called_once()
    default_context.build_messages.assert_not_called()


@pytest.mark.asyncio
async def test_process_system_message_uses_origin_routed_context_builder():
    routed_context = MagicMock()
    routed_context.build_messages.return_value = [{"role": "user", "content": "cron ping"}]

    session = MagicMock()
    session.get_history.return_value = []

    cron_tool = SimpleNamespace(set_context=MagicMock())

    loop = SimpleNamespace(
        sessions=SimpleNamespace(get_or_create=MagicMock(return_value=session), save=MagicMock()),
        tools=SimpleNamespace(get=lambda name: cron_tool if name in {"message", "spawn", "cron"} else None),
        _resolve_context_for_channel_chat=MagicMock(return_value=routed_context),
        _run_agent_loop=AsyncMock(return_value="done"),
        context=MagicMock(),
    )

    msg = InboundMessage(
        channel="system",
        sender_id="system",
        chat_id="telegram:8086618307",
        content="[System] Cron job executed",
    )

    response = await process_system_message(loop, msg)

    assert response is not None
    assert response.channel == "telegram"
    assert response.chat_id == "8086618307"
    loop._resolve_context_for_channel_chat.assert_called_once_with("telegram", "8086618307")
    routed_context.build_messages.assert_called_once()
    loop.context.build_messages.assert_not_called()


@pytest.mark.asyncio
async def test_process_isolated_uses_routed_context_builder():
    routed_context = MagicMock()
    routed_context.build_messages.return_value = [{"role": "user", "content": "isolated"}]

    loop = SimpleNamespace(
        tools=SimpleNamespace(get=lambda _name: None, tool_names=[]),
        _resolve_context_for_channel_chat=MagicMock(return_value=routed_context),
        _run_agent_loop=AsyncMock(return_value="done"),
        sessions=SimpleNamespace(get_or_create=MagicMock(return_value=SimpleNamespace())),
        context=MagicMock(),
    )

    result = await process_isolated(loop, "isolated task", channel="telegram", chat_id="chat-1", job_id="job-1")

    assert result == "done"
    loop._resolve_context_for_channel_chat.assert_called_once_with("telegram", "chat-1")
    routed_context.build_messages.assert_called_once()
    loop.context.build_messages.assert_not_called()
