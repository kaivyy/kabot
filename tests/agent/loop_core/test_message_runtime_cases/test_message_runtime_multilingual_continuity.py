from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.loop_core.message_runtime import process_message
from kabot.bus.events import InboundMessage, OutboundMessage


@pytest.mark.asyncio
async def test_process_message_action_route_injects_session_continuity_note_for_multilingual_followup():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "working_directory": r"C:\Users\Arvy Kairi\Desktop\bot",
            "delivery_route": {
                "channel": "telegram",
                "chat_id": "chat-1",
                "thread_id": "55",
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
            route=AsyncMock(
                return_value=SimpleNamespace(
                    profile="GENERAL",
                    is_complex=True,
                    turn_category="action",
                )
            )
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=["message", "list_dir", "read_file"]),
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
        content="このチャットに tes.md を送って",
    )

    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    current_message = context_builder.build_messages.call_args.kwargs["current_message"]
    assert "[System Note: Session continuity context]" in current_message
    assert r"C:\Users\Arvy Kairi\Desktop\bot" in current_message
    assert '"channel": "telegram"' in current_message
    assert "Do not rely on fixed language-specific keywords" in current_message


@pytest.mark.asyncio
async def test_process_message_project_inspection_turn_injects_grounded_filesystem_note():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "working_directory": r"C:\Users\Arvy Kairi\Desktop\bot\openclaw",
            "delivery_route": {
                "channel": "telegram",
                "chat_id": "chat-1",
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
            route=AsyncMock(
                return_value=SimpleNamespace(
                    profile="GENERAL",
                    is_complex=True,
                    turn_category="action",
                    grounding_mode="filesystem_inspection",
                )
            )
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=["message", "list_dir", "read_file", "find_files"]),
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
        content="openclaw フォルダをちゃんと見て、これは何のアプリか説明して",
    )

    await process_message(loop, msg)

    current_message = context_builder.build_messages.call_args.kwargs["current_message"]
    assert "[System Note: Grounded filesystem inspection]" in current_message
    assert r"C:\Users\Arvy Kairi\Desktop\bot\openclaw" in current_message
    assert "Start with list_dir, read_file, find_files, or exec" in current_message
    assert msg.metadata.get("requires_grounded_filesystem_inspection") is True
    assert msg.metadata.get("route_grounding_mode") == "filesystem_inspection"
