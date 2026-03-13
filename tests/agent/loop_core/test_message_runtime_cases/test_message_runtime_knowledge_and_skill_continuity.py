import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.loop_core.message_runtime import process_message
from kabot.bus.events import InboundMessage, OutboundMessage


@pytest.mark.asyncio
@pytest.mark.parametrize("followup_text", ["just explain", "use English", "don't use web search"])
async def test_process_message_web_search_setup_hint_followups_demote_back_to_grounded_answer_mode(
    followup_text: str,
):
    captured: dict[str, str] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": captured["current_message"]}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "web_search",
                "source": "can you explain about earth? what is earth or something, everything you know about earth",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "last_tool_context": {
                "tool": "web_search",
                "source": "can you explain about earth? what is earth or something, everything you know about earth",
                "updated_at": time.time(),
            },
        }
    )

    history = [
        {
            "role": "assistant",
            "content": (
                "web_search needs a search API key. Configure BRAVE_API_KEY, "
                "PERPLEXITY_API_KEY, XAI_API_KEY, or KIMI_API_KEY/MOONSHOT_API_KEY in "
                "tools.web.search or your environment. For direct page fetches, use web_fetch."
            ),
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

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content=followup_text,
    )
    await process_message(loop, msg)

    assert msg.metadata.get("required_tool") is None
    assert "earth" in captured["current_message"].lower()
    assert "web search" in captured["current_message"].lower()
    assert session.metadata.get("pending_followup_tool") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "followup_text",
    ["struktur skillsnya gimana", "flow skillnya gimana", "template skillnya dong"],
)
async def test_process_message_skill_structure_followups_keep_skill_creator_lane(
    followup_text: str,
):
    captured: dict[str, str] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        captured["skill_names"] = ",".join(kwargs.get("skill_names") or [])
        return [{"role": "user", "content": captured["current_message"]}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    session = SimpleNamespace(
        metadata={
            "skill_creation_flow": {
                "request_text": "buat skill baru untuk EV monitor",
                "stage": "discovery",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
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

    assert "skill-creator" in captured["skill_names"]
    assert "[Skill Workflow]" in captured["current_message"]
    assert "buat skill baru untuk EV monitor" in captured["current_message"]
    assert msg.metadata.get("skill_creation_guard", {}).get("active") is True
