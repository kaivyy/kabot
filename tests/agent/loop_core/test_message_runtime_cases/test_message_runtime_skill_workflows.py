"""Split from tests/agent/loop_core/test_message_runtime.py to keep test modules below 1000 lines.
Chunk 4: test_process_message_non_confirmation_short_turn_does_not_reuse_pending_stock_tool .. test_process_message_multilingual_skill_update_request_suppresses_conflicting_weather_inference.
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
async def test_process_message_non_confirmation_short_turn_does_not_reuse_pending_stock_tool():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [
        {"role": "user", "content": "gaperlu web search langsung buka aja"}
    ]
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

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="gaperlu web search langsung buka aja",
    )
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None
    assert "pending_followup_tool" not in session.metadata

@pytest.mark.asyncio
async def test_process_message_non_confirmation_short_turn_does_not_reuse_pending_stock_intent():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [
        {"role": "user", "content": "gaperlu web search langsung buka aja"}
    ]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "cek harga saham bbri bbca bmri",
                "profile": "GENERAL",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )

    def _required_tool(text: str) -> str | None:
        normalized = (text or "").lower()
        if "saham" in normalized or "stock" in normalized:
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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: []),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=_required_tool,
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
        content="gaperlu web search langsung buka aja",
    )
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None
    assert "pending_followup_intent" not in session.metadata

@pytest.mark.asyncio
async def test_process_message_closing_ack_does_not_infer_cron_from_recent_history():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "oke makasih ya"}]
    session = SimpleNamespace(metadata={})

    def _required_tool(text: str) -> str | None:
        normalized = (text or "").lower()
        if "ingatkan" in normalized:
            return "cron"
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
        memory=SimpleNamespace(
            get_conversation_context=lambda _key, max_messages=30: [
                {"role": "user", "content": "ingatkan pukul 21.25 buka hp"},
                {"role": "assistant", "content": "Siap, reminder aktif."},
            ]
        ),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=_required_tool,
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

@pytest.mark.asyncio
async def test_process_message_short_followup_uses_pending_non_tool_intent_context():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ya"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "buat skill creator untuk telegram",
                "profile": "GENERAL",
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

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="ya lanjut")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    context_builder.build_messages.assert_called_once()
    built_message = context_builder.build_messages.call_args.kwargs.get("current_message", "")
    assert "[Follow-up Context]" in built_message
    assert "buat skill creator untuk telegram" in built_message

@pytest.mark.asyncio
async def test_process_message_skill_creation_request_forces_skill_creator_context():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "skill"}]
    session = SimpleNamespace(metadata={})

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
        content="buat kemampuan baru buat kabot",
    )
    await process_message(loop, msg)

    kwargs = context_builder.build_messages.call_args.kwargs
    assert "skill-creator" in (kwargs.get("skill_names") or [])
    built_message = kwargs.get("current_message", "")
    assert "[Skill Workflow]" in built_message
    assert "Do not create files yet" in built_message

@pytest.mark.asyncio
async def test_process_message_skill_creation_followup_keeps_workflow_note():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "skill"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "buat skill baru untuk Threads API",
                "profile": "GENERAL",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "skill_creation_flow": {
                "request_text": "buat skill baru untuk Threads API",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
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

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="ya lanjut")
    await process_message(loop, msg)

    kwargs = context_builder.build_messages.call_args.kwargs
    assert "skill-creator" in (kwargs.get("skill_names") or [])
    built_message = kwargs.get("current_message", "")
    assert "[Skill Workflow]" in built_message
    assert "[Follow-up Context]" in built_message

@pytest.mark.asyncio
async def test_process_message_skill_creation_discovery_answers_keep_workflow_active():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "skill"}]
    session = SimpleNamespace(
        metadata={
            "skill_creation_flow": {
                "request_text": "buat skills untuk cek runtime vps dengan lengkap",
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
        content="1. a,b,c,d\n2. c\n3. a\n4. b",
    )
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    kwargs = context_builder.build_messages.call_args.kwargs
    assert "skill-creator" in (kwargs.get("skill_names") or [])
    built_message = kwargs.get("current_message", "")
    assert built_message.startswith("1. a,b,c,d\n2. c\n3. a\n4. b\n\n[Follow-up Context]\n")
    assert "buat skills untuk cek runtime vps dengan lengkap" in built_message.lower()
    assert "[Skill Workflow]" in built_message
    assert "Do not create files yet" not in built_message
    assert msg.metadata.get("skill_creation_guard", {}).get("stage") == "discovery"


@pytest.mark.asyncio
async def test_process_message_skill_creation_plan_response_promotes_flow_to_planning():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "skill"}]
    session = SimpleNamespace(metadata={})

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
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(
            return_value=(
                "Berikut plan saya:\n"
                "- <workspace>/skills/meta-threads/SKILL.md\n"
                "- <workspace>/skills/meta-threads/scripts/main.py\n"
                "Setuju?"
            )
        ),
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
        content="buat skill baru untuk Threads API",
        metadata={},
    )
    await process_message(loop, msg)

    flow = session.metadata.get("skill_creation_flow")
    assert isinstance(flow, dict)
    assert flow.get("stage") == "planning"

@pytest.mark.asyncio
async def test_process_message_skill_creation_approval_turn_sets_approved_guard():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "skill"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "buat skill baru untuk Threads API",
                "profile": "GENERAL",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "skill_creation_flow": {
                "request_text": "buat skill baru untuk Threads API",
                "stage": "planning",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
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
        _run_agent_loop=AsyncMock(return_value="Baik, saya implementasikan sesuai plan."),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="oke lanjut", metadata={})
    await process_message(loop, msg)

    kwargs = context_builder.build_messages.call_args.kwargs
    built_message = kwargs.get("current_message", "")
    assert "explicitly approved the plan" in built_message
    assert msg.metadata.get("skill_creation_guard", {}).get("approved") is True
    assert session.metadata.get("skill_creation_flow", {}).get("stage") == "approved"

@pytest.mark.asyncio
async def test_process_message_skill_creation_followup_keeps_existing_approved_stage():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "skill"}]
    session = SimpleNamespace(
        metadata={
            "skill_creation_flow": {
                "request_text": "buat skills untuk cek runtime vps dengan lengkap",
                "stage": "approved",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
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

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="lanjut", metadata={})
    await process_message(loop, msg)

    kwargs = context_builder.build_messages.call_args.kwargs
    built_message = kwargs.get("current_message", "")
    assert "explicitly approved the plan" in built_message
    assert msg.metadata.get("skill_creation_guard", {}).get("approved") is True
    assert session.metadata.get("skill_creation_flow", {}).get("stage") == "approved"


@pytest.mark.asyncio
@pytest.mark.parametrize("followup_text", ["lanjut pakai skillnya", "lanjut", "lanj"])
async def test_process_message_existing_created_skill_followup_loads_created_skill_instead_of_creator(
    followup_text: str,
):
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "skill"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": (
                    "Kalau kamu mau, langkah berikutnya saya bisa langsung pakai skill ini "
                    "untuk cek runtime server saat ini dan kirim hasilnya."
                ),
                "profile": "CHAT",
                "kind": "assistant_offer",
                "request_text": "buat skills untuk cek runtime vps dengan lengkap",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "skill_creation_flow": {
                "request_text": "buat skills untuk cek runtime vps dengan lengkap",
                "stage": "approved",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
        }
    )
    history = [
        {
            "role": "assistant",
            "content": (
                "Berhasil, skill-nya sudah saya buat di:\n\n"
                "/root/.kabot/workspace-telegram_main/skills/cek-runtime-vps/SKILL.md"
            ),
        }
    ]

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
        metadata={},
    )
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    kwargs = context_builder.build_messages.call_args.kwargs
    built_message = kwargs.get("current_message", "")
    assert "cek-runtime-vps" in (kwargs.get("skill_names") or [])
    assert "[Existing Skill Note]" in built_message
    assert "use that existing skill now" in built_message.lower()
    assert "[Skill Workflow]" not in built_message
    assert msg.metadata.get("skill_creation_guard") is None
    assert session.metadata.get("skill_creation_flow") is None


@pytest.mark.asyncio
async def test_process_message_existing_runtime_skill_followup_infers_server_monitor_tool():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "skill"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": (
                    "Kalau kamu mau, langkah berikutnya saya bisa langsung pakai skill ini "
                    "untuk cek runtime server saat ini dan kirim hasilnya."
                ),
                "profile": "CHAT",
                "kind": "assistant_offer",
                "request_text": "buat skills untuk cek runtime vps dengan lengkap",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "skill_creation_flow": {
                "request_text": "buat skills untuk cek runtime vps dengan lengkap",
                "stage": "approved",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
        }
    )
    history = [
        {
            "role": "assistant",
            "content": (
                "Berhasil, skill-nya sudah saya buat di:\n\n"
                "/root/.kabot/workspace-telegram_main/skills/cek-runtime-vps/SKILL.md"
            ),
        }
    ]

    def _required_tool_for_query(text: str) -> str | None:
        normalized = str(text or "").lower()
        if "runtime server" in normalized or "cek server" in normalized or "status server" in normalized:
            return "server_monitor"
        return None

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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda _name: _name == "server_monitor"),
        _required_tool_for_query=_required_tool_for_query,
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
        content="lanjut",
        metadata={},
    )
    await process_message(loop, msg)

    assert msg.metadata.get("required_tool") == "server_monitor"
    assert "runtime server" in str(msg.metadata.get("required_tool_query") or "").lower()


@pytest.mark.asyncio
async def test_process_message_existing_runtime_skill_followup_stores_runtime_request_text_for_next_offer():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "skill"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": (
                    "Kalau kamu mau, langkah berikutnya saya bisa langsung pakai skill ini "
                    "untuk cek runtime server saat ini dan kirim hasilnya."
                ),
                "profile": "CHAT",
                "kind": "assistant_offer",
                "request_text": "buat skills untuk cek runtime vps dengan lengkap",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "skill_creation_flow": {
                "request_text": "buat skills untuk cek runtime vps dengan lengkap",
                "stage": "approved",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
        }
    )
    history = [
        {
            "role": "assistant",
            "content": (
                "Berhasil, skill-nya sudah saya buat di:\n\n"
                "/root/.kabot/workspace-telegram_main/skills/cek-runtime-vps/SKILL.md"
            ),
        }
    ]

    def _required_tool_for_query(text: str) -> str | None:
        normalized = str(text or "").lower()
        if "runtime server" in normalized or "cek server" in normalized or "status server" in normalized:
            return "server_monitor"
        return None

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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda _name: _name == "server_monitor"),
        _required_tool_for_query=_required_tool_for_query,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(
            return_value="Kalau mau, saya bisa lanjut cek status live server sekarang."
        ),
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
        content="lanjut",
        metadata={},
    )
    await process_message(loop, msg)

    stored = session.metadata.get("pending_followup_intent") or {}
    assert stored.get("kind") == "assistant_offer"
    assert "runtime server" in str(stored.get("request_text") or "").lower()
    assert "buat skills" not in str(stored.get("request_text") or "").lower()


@pytest.mark.asyncio
async def test_process_message_skill_install_request_forces_skill_installer_workflow():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "skill install"}]
    session = SimpleNamespace(metadata={})

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
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="Saya bisa cek repo, target install, dan trust mode dulu."),
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
        content="tolong install skill dari github repo owner/repo",
    )
    await process_message(loop, msg)

    kwargs = context_builder.build_messages.call_args.kwargs
    assert "skill-installer" in (kwargs.get("skill_names") or [])
    built_message = kwargs.get("current_message", "")
    assert "[Skill Workflow]" in built_message
    assert "installing or updating an external Kabot skill" in built_message
    assert session.metadata.get("skill_creation_flow", {}).get("kind") == "install"
    assert msg.metadata.get("skill_creation_guard", {}).get("kind") == "install"

@pytest.mark.asyncio
async def test_process_message_skill_install_request_suppresses_conflicting_tool_inference():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "skill install"}]
    session = SimpleNamespace(metadata={})

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
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: "stock",
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="Saya cek repo dulu."),
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
        content="install a skill from github repo owner/repo for Threads integration",
    )
    await process_message(loop, msg)

    kwargs = context_builder.build_messages.call_args.kwargs
    assert "skill-installer" in (kwargs.get("skill_names") or [])
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None
    assert msg.metadata.get("suppress_required_tool_inference") is True

@pytest.mark.asyncio
async def test_process_message_skill_install_approval_turn_sets_approved_guard():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "skill install"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "tolong install skill dari github repo owner/repo",
                "profile": "GENERAL",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "skill_creation_flow": {
                "request_text": "tolong install skill dari github repo owner/repo",
                "stage": "planning",
                "kind": "install",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
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
        _run_agent_loop=AsyncMock(return_value="Baik, saya lanjut install sesuai plan."),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="oke lanjut", metadata={})
    await process_message(loop, msg)

    kwargs = context_builder.build_messages.call_args.kwargs
    built_message = kwargs.get("current_message", "")
    assert "explicitly approved the plan" in built_message
    assert "skill-installer" in (kwargs.get("skill_names") or [])
    assert msg.metadata.get("skill_creation_guard", {}).get("approved") is True
    assert msg.metadata.get("skill_creation_guard", {}).get("kind") == "install"
    assert session.metadata.get("skill_creation_flow", {}).get("stage") == "approved"

@pytest.mark.asyncio
async def test_process_message_skill_update_request_suppresses_conflicting_weather_inference():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "skill update"}]
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
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: "weather",
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="Saya cek skill cuacanya dulu."),
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
        content="Please update the weather skill so it can also check UV index",
    )
    await process_message(loop, msg)

    kwargs = context_builder.build_messages.call_args.kwargs
    assert "skill-creator" in (kwargs.get("skill_names") or [])
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None
    assert msg.metadata.get("suppress_required_tool_inference") is True

@pytest.mark.asyncio
async def test_process_message_multilingual_skill_update_request_suppresses_conflicting_weather_inference():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "skill update"}]

    prompts = (
        "天気スキルを更新してUV indexも見られるようにして",
        "ช่วยอัปเดตสกิลอากาศให้เช็กค่า UV index ได้ด้วย",
    )

    for prompt in prompts:
        session = SimpleNamespace(metadata={})
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
                route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
            ),
            _resolve_context_for_message=lambda _msg: context_builder,
            context=context_builder,
            tools=SimpleNamespace(tool_names=[]),
            _required_tool_for_query=lambda _text: "weather",
            _run_simple_response=AsyncMock(return_value="simple"),
            _run_agent_loop=AsyncMock(return_value="Saya cek skill cuacanya dulu."),
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
            content=prompt,
        )
        await process_message(loop, msg)

        kwargs = context_builder.build_messages.call_args.kwargs
        assert "skill-creator" in (kwargs.get("skill_names") or [])
        assert msg.metadata.get("required_tool") is None
        assert msg.metadata.get("required_tool_query") is None
        assert msg.metadata.get("suppress_required_tool_inference") is True
