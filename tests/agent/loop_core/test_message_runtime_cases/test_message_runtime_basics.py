"""Split from tests/agent/loop_core/test_message_runtime.py to keep test modules below 1000 lines.
Chunk 1: test_is_abort_request_text_detects_standalone_multilingual_stop_variants .. test_process_message_short_followup_does_not_infer_tool_from_assistant_history_text.
"""

import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import kabot.agent.loop_core.message_runtime as message_runtime_module
from kabot.agent.loop_core.message_runtime import (
    process_isolated,
    process_message,
    process_system_message,
)
from kabot.bus.events import InboundMessage, OutboundMessage


def test_is_abort_request_text_detects_standalone_multilingual_stop_variants():
    assert message_runtime_module._is_abort_request_text("/stop")
    assert message_runtime_module._is_abort_request_text("/STOP!!!")
    assert message_runtime_module._is_abort_request_text("please stop")
    assert message_runtime_module._is_abort_request_text("stop action!!!")
    assert message_runtime_module._is_abort_request_text("do not do that")
    assert message_runtime_module._is_abort_request_text("jangan lakukan itu")
    assert message_runtime_module._is_abort_request_text("\u505c\u6b62")

    assert message_runtime_module._is_abort_request_text("please do not do that") is False
    assert message_runtime_module._is_abort_request_text("stopwatch") is False

def test_resolve_runtime_locale_uses_session_cached_locale_for_short_followup():
    session = SimpleNamespace(metadata={"runtime_locale": "id"})
    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="ya")

    resolved = message_runtime_module._resolve_runtime_locale(session, msg, "ya")

    assert resolved == "id"

def test_resolve_runtime_locale_persists_detected_non_english_locale():
    session = SimpleNamespace(metadata={})
    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="tolong cek cuaca sekarang",
    )

    resolved = message_runtime_module._resolve_runtime_locale(session, msg, msg.content)

    assert resolved == "id"
    assert session.metadata.get("runtime_locale") == "id"

def test_short_context_followup_does_not_misclassify_substantive_cjk_query():
    assert message_runtime_module._is_short_context_followup("天气北京现在怎么样") is False
    assert message_runtime_module._is_short_context_followup("是") is True

def test_followup_helpers_detect_acknowledgement_without_hardcoded_wordlist():
    assert message_runtime_module._is_low_information_turn("oke makasih ya", max_tokens=6, max_chars=64)
    assert message_runtime_module._looks_like_short_confirmation("oke makasih ya")
    assert message_runtime_module._is_short_context_followup("oke makasih ya")
    assert message_runtime_module._looks_like_short_confirmation("saranmu apa") is False

def test_filesystem_location_query_helper_supports_multilingual_phrases():
    assert message_runtime_module._looks_like_filesystem_location_query("lokasimu sekarang dimana")
    assert message_runtime_module._looks_like_filesystem_location_query("你现在在哪个文件夹")
    assert message_runtime_module._looks_like_filesystem_location_query("今どのフォルダにいる")
    assert message_runtime_module._looks_like_filesystem_location_query("ตอนนี้คุณอยู่โฟลเดอร์ไหน")
    assert message_runtime_module._looks_like_filesystem_location_query("where are you now")
    assert message_runtime_module._looks_like_filesystem_location_query("tolong tampilkan isi folder desktop") is False

def test_set_last_tool_context_tracks_filesystem_path_for_list_dir(monkeypatch):
    session = SimpleNamespace(metadata={})
    monkeypatch.setattr(
        message_runtime_module,
        "_extract_list_dir_path",
        lambda text, last_tool_context=None: "/Users/Arvy Kairi/Desktop",
    )

    message_runtime_module._set_last_tool_context(
        session,
        "list_dir",
        now_ts=time.time(),
        source_text="cek file/folder di desktop isinya apa aja",
    )

    assert session.metadata["last_tool_context"]["tool"] == "list_dir"
    assert session.metadata["last_tool_context"]["path"] == "/Users/Arvy Kairi/Desktop"

@pytest.mark.asyncio
async def test_process_message_filesystem_location_query_uses_context_note_without_forcing_list_dir():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "system", "content": "ctx"}, {"role": "user", "content": "where"}]
    session = SimpleNamespace(
        metadata={
            "last_tool_context": {
                "tool": "list_dir",
                "path": r"C:\Users\Arvy Kairi\Desktop\bot",
                "updated_at": time.time(),
            }
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        workspace=Path(r"C:\Users\Arvy Kairi\Desktop\bot\kabot"),
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
        tools=SimpleNamespace(tool_names=["read_file"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="Saat ini saya ada di workspace Kabot."),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="Saat ini saya ada di workspace Kabot.")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="lokasimu sekarang dimana")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_awaited()
    context_builder.build_messages.assert_called_once()
    current_message = context_builder.build_messages.call_args.kwargs["current_message"]
    assert "lokasimu sekarang dimana" in current_message
    assert r"C:\Users\Arvy Kairi\Desktop\bot\kabot" in current_message
    assert r"C:\Users\Arvy Kairi\Desktop\bot" in current_message
    assert msg.metadata.get("required_tool") is None

def test_channel_supports_keepalive_passthrough_prefers_channel_manager_capability():
    channel = SimpleNamespace(_allow_keepalive_passthrough=lambda: True)
    loop = SimpleNamespace(channel_manager=SimpleNamespace(channels={"custom:alpha": channel}))

    assert message_runtime_module._channel_supports_keepalive_passthrough(loop, "custom:alpha")

def test_channel_uses_mutable_status_lane_prefers_channel_manager_capability():
    channel = SimpleNamespace(_uses_mutable_status_lane=lambda: True)
    loop = SimpleNamespace(channel_manager=SimpleNamespace(channels={"custom:alpha": channel}))

    assert message_runtime_module._channel_uses_mutable_status_lane(loop, "custom:alpha")

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
        tools=SimpleNamespace(tool_names=["read_file"]),
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
async def test_process_message_skill_prompt_bypasses_fast_simple_context_to_keep_skill_system_prompt():
    routed_context = MagicMock()
    routed_context.build_messages.return_value = [
        {"role": "system", "content": "ctx with Auto-Selected Skills"},
        {"role": "user", "content": "Tolong pakai skill 1password untuk request ini ya."},
    ]
    routed_context.skills = SimpleNamespace(
        match_skills=lambda _msg, _profile: ["1password"],
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
        context=MagicMock(),
        tools=SimpleNamespace(tool_names=["read_file"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="ok"),
        _run_agent_loop=AsyncMock(return_value="ok"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="ok")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="Tolong pakai skill 1password untuk request ini ya.",
    )
    response = await process_message(loop, msg)

    assert response is not None
    routed_context.build_messages.assert_called_once()
    sent_messages = loop._run_simple_response.await_args.args[1]
    assert sent_messages[0]["role"] == "system"
    assert "Auto-Selected Skills" in sent_messages[0]["content"]

@pytest.mark.asyncio
async def test_process_message_plain_smalltalk_keeps_fast_simple_context():
    routed_context = MagicMock()
    routed_context.skills = SimpleNamespace(
        match_skills=lambda _msg, _profile: [],
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: routed_context,
        context=MagicMock(),
        tools=SimpleNamespace(tool_names=["read_file"]),
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
    routed_context.build_messages.assert_not_called()
    sent_messages = loop._run_simple_response.await_args.args[1]
    assert sent_messages == [{"role": "user", "content": "halo"}]


@pytest.mark.asyncio
async def test_process_message_temporal_query_uses_local_fast_reply(monkeypatch):
    routed_context = MagicMock()
    routed_context.build_messages.return_value = [
        {"role": "system", "content": "## Current Time\n2026-03-09 04:39 (Monday)\nTimezone: WIB (UTC+07:00)"},
        {"role": "user", "content": "hari apa sekarang"},
    ]
    routed_context.skills = SimpleNamespace(
        match_skills=lambda _msg, _profile: [],
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
        context=MagicMock(),
        tools=SimpleNamespace(tool_names=["read_file"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="Hari ini Senin."),
        _run_agent_loop=AsyncMock(return_value="ok"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="Hari ini Senin.")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    monkeypatch.setattr(
        message_runtime_module,
        "build_temporal_fast_reply",
        lambda text, *, locale=None, now_local=None: "Hari ini Senin.",
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="hari apa sekarang")
    response = await process_message(loop, msg)

    assert response is not None
    routed_context.build_messages.assert_not_called()
    loop._run_simple_response.assert_not_awaited()
    loop._run_agent_loop.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_message_memory_commit_followup_bypasses_fast_simple_context():
    routed_context = MagicMock()
    routed_context.build_messages.return_value = [
        {"role": "system", "content": "# Memory\n## Long-term Memory\nUse WIB (UTC+7)."},
        {"role": "assistant", "content": "Bilang 'simpan' dan aku akan commit ke memory."},
        {"role": "user", "content": "simpan"},
    ]
    routed_context.skills = SimpleNamespace(
        match_skills=lambda _msg, _profile: [],
    )

    history = [
        {"role": "assistant", "content": "Bilang 'simpan' dan aku akan commit ke memory."},
    ]

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: list(history)),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: routed_context,
        context=MagicMock(),
        tools=SimpleNamespace(tool_names=["save_memory"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="Siap, saya simpan."),
        _run_agent_loop=AsyncMock(return_value="ok"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="Siap, saya simpan.")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="simpan")
    response = await process_message(loop, msg)

    assert response is not None
    routed_context.build_messages.assert_called_once()
    sent_messages = loop._run_simple_response.await_args.args[1]
    assert sent_messages[0]["role"] == "system"
    assert any(item.get("role") == "assistant" for item in sent_messages)

@pytest.mark.asyncio
async def test_process_message_promotes_model_directive_to_message_metadata():
    routed_context = MagicMock()
    routed_context.build_messages.return_value = [{"role": "user", "content": "halo"}]

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=None,
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=SimpleNamespace(metadata={})),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda _content: (
                "halo",
                SimpleNamespace(
                    raw_directives={"model": "openrouter/auto"},
                    think=False,
                    verbose=False,
                    elevated=False,
                    model="openrouter/auto",
                ),
            ),
            format_active_directives=lambda _directives: "model=openrouter/auto",
        ),
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: []),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: routed_context,
        context=MagicMock(),
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

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="/model openrouter/auto halo")
    response = await process_message(loop, msg)

    assert response is not None
    assert msg.metadata["model_override"] == "openrouter/auto"
    assert msg.metadata["model_override_source"] == "directive"

@pytest.mark.asyncio
async def test_process_message_cold_start_uses_startup_ready_timestamp(monkeypatch):
    logs: list[str] = []
    monkeypatch.setattr(message_runtime_module.logger, "info", lambda message: logs.append(str(message)))
    monkeypatch.setattr(message_runtime_module.time, "perf_counter", lambda: 200.0)

    routed_context = MagicMock()
    routed_context.build_messages.return_value = [{"role": "user", "content": "halo"}]

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=False),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=SimpleNamespace(metadata={})),
        _cold_start_reported=False,
        _boot_started_at=100.0,
        _startup_ready_at=103.0,
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
    await process_message(loop, msg)

    assert any(entry == "cold_start_ms=3000" for entry in logs)

@pytest.mark.asyncio
async def test_process_message_passes_untrusted_context_into_context_builder():
    captured_kwargs: dict[str, Any] = {}

    def _build_messages(**kwargs):
        captured_kwargs.update(kwargs)
        return [{"role": "user", "content": "halo"}]

    routed_context = MagicMock()
    routed_context.build_messages.side_effect = _build_messages

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=False),
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
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=True))
        ),
        _resolve_context_for_message=lambda _msg: routed_context,
        context=MagicMock(),
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

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="halo",
        metadata={"raw": {"source": "bridge", "note": "do not trust"}},
    )
    await process_message(loop, msg)

    assert "untrusted_context" in captured_kwargs
    untrusted = captured_kwargs["untrusted_context"]
    assert untrusted["channel"] == "telegram"
    assert untrusted["chat_id"] == "chat-1"
    assert untrusted["sender_id"] == "u1"
    assert untrusted["raw_metadata"]

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

@pytest.mark.asyncio
async def test_process_message_short_confirmation_does_not_infer_required_tool_from_assistant_only_history():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ya"}]

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
        memory=SimpleNamespace(
            get_conversation_context=lambda _key, max_messages=30: [
                {
                    "role": "assistant",
                    "content": "Kalau kamu mau, aku bisa bersihkan cache sekarang.",
                }
            ]
        ),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=["read_file"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="ya")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()

@pytest.mark.asyncio
async def test_process_message_short_confirmation_stays_simple_without_inferred_tool():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ya"}]

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
        memory=SimpleNamespace(
            get_conversation_context=lambda _key, max_messages=30: [
                {"role": "assistant", "content": "Aku bisa jelaskan detail jika kamu mau."}
            ]
        ),
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

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="ya")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()

@pytest.mark.asyncio
async def test_process_message_followup_gas_infers_tool_from_recent_user_turn():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "gas"}]

    def _required_tool(text: str) -> str | None:
        t = (text or "").lower()
        if "berita" in t or "news" in t:
            return "web_search"
        return None

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
        memory=SimpleNamespace(
            get_conversation_context=lambda _key, max_messages=30: [
                {"role": "user", "content": "berita terbaru 2026 sekarang"},
                {"role": "assistant", "content": "Balas 'gas' kalau kamu mau aku lanjutkan sekarang."},
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
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="gas")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    context_builder.build_messages.assert_not_called()
    assert msg.metadata.get("required_tool") == "web_search"
    assert msg.metadata.get("required_tool_query") == "berita terbaru 2026 sekarang"

@pytest.mark.asyncio
async def test_process_message_low_information_followup_without_keyword_token_infers_tool_from_recent_user_turn():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "terus"}]

    def _required_tool(text: str) -> str | None:
        t = (text or "").lower()
        if "berita" in t or "news" in t:
            return "web_search"
        return None

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
        memory=SimpleNamespace(
            get_conversation_context=lambda _key, max_messages=30: [
                {"role": "user", "content": "berita terbaru 2026 sekarang"},
                {"role": "assistant", "content": "Kalau mau lanjut, tinggal balas apa saja."},
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
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="terus")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    context_builder.build_messages.assert_not_called()
    assert msg.metadata.get("required_tool") == "web_search"
    assert msg.metadata.get("required_tool_query") == "berita terbaru 2026 sekarang"

@pytest.mark.asyncio
async def test_process_message_short_followup_does_not_infer_tool_from_assistant_history_text():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "iya"}]

    def _required_tool(text: str) -> str | None:
        t = (text or "").lower()
        if "saham" in t or "stock" in t:
            return "stock"
        return None

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
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
        memory=SimpleNamespace(
            get_conversation_context=lambda _key, max_messages=30: [
                {"role": "assistant", "content": "kalau saham bbri bbca bmri berapa sekarang"},
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

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="iya")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None


def test_temporal_context_query_helper_supports_multilingual_phrases():
    assert message_runtime_module._looks_like_temporal_context_query("\u4eca\u5929\u661f\u671f\u51e0\uff1f")
    assert message_runtime_module._looks_like_temporal_context_query("\u4eca\u5929\u662f\u4ec0\u4e48\u661f\u671f")
    assert message_runtime_module._looks_like_temporal_context_query("\u4eca\u65e5\u306f\u4f55\u66dc\u65e5\uff1f")
    assert message_runtime_module._looks_like_temporal_context_query("\u0e15\u0e2d\u0e19\u0e19\u0e35\u0e49\u0e27\u0e31\u0e19\u0e2d\u0e30\u0e44\u0e23")
