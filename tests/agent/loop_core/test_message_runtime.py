import asyncio
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
        tools=SimpleNamespace(tool_names=[]),
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
    routed_context.build_messages.assert_not_called()
    sent_messages = loop._run_simple_response.await_args.args[1]
    assert sent_messages == [{"role": "user", "content": "halo"}]


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

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
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

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
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
        content=r"C:\Users\Arvy Kairi\.kabot\workspace\landing_hacker.html font pada web ini",
    )
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert "[System Note: Explicit file reference]" in captured["current_message"]
    assert "landing_hacker.html" in captured["current_message"]


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
        tools=SimpleNamespace(tool_names=[]),
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
        tools=SimpleNamespace(tool_names=[]),
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
        tools=SimpleNamespace(tool_names=[]),
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

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="风大吗？")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    assert msg.metadata.get("required_tool") == "weather"
    assert "北京" in str(msg.metadata.get("required_tool_query", ""))


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


@pytest.mark.asyncio
async def test_process_message_explicit_skill_reference_suppresses_conflicting_weather_inference():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [
        {"role": "system", "content": "ctx with Auto-Selected Skills"},
        {"role": "user", "content": "Please use the weather skill for this request"},
    ]
    context_builder.skills = SimpleNamespace(match_skills=lambda _msg, _profile: ["weather"])

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
        content="Please use the weather skill for this request",
    )
    await process_message(loop, msg)

    context_builder.build_messages.assert_called_once()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None
    assert msg.metadata.get("suppress_required_tool_inference") is True


@pytest.mark.asyncio
async def test_process_message_multilingual_explicit_skill_reference_suppresses_second_pass_tool_inference():
    prompts_and_skills = (
        ("请用 apple-reminders 技能处理这个请求。", ["apple-reminders"]),
        ("ช่วยใช้สกิล weather กับงานนี้หน่อย", ["weather"]),
        ("writing-plans スキルを使ってこの依頼を手伝って", ["writing-plans"]),
    )

    for prompt, matched_skills in prompts_and_skills:
        context_builder = MagicMock()
        context_builder.build_messages.return_value = [
            {"role": "system", "content": "ctx with Auto-Selected Skills"},
            {"role": "user", "content": prompt},
        ]
        context_builder.skills = SimpleNamespace(
            match_skills=lambda _msg, _profile, _skills=matched_skills: list(_skills)
        )

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
            content=prompt,
        )
        await process_message(loop, msg)

        assert msg.metadata.get("required_tool") is None
        assert msg.metadata.get("required_tool_query") is None
        assert msg.metadata.get("suppress_required_tool_inference") is True


@pytest.mark.asyncio
async def test_process_message_skill_approval_turn_emits_approved_status(monkeypatch):
    published = []
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

    def _fake_t(key: str, locale: str | None = None, text: str | None = None, **kwargs) -> str:
        return f"<{key}>"

    monkeypatch.setattr("kabot.agent.loop_core.message_runtime.t", _fake_t)

    async def _publish(msg):
        published.append(msg)

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
        bus=SimpleNamespace(publish_outbound=AsyncMock(side_effect=_publish)),
        channel_manager=SimpleNamespace(channel_uses_mutable_status_lane=lambda _name: True),
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="oke lanjut", metadata={})
    await process_message(loop, msg)

    statuses = [m for m in published if (m.metadata or {}).get("type") == "status_update"]
    phases = [(m.metadata or {}).get("phase") for m in statuses]
    contents = [m.content for m in statuses]
    assert "approved" in phases
    assert "<runtime.status.approved>" in contents


@pytest.mark.asyncio
async def test_process_message_plain_chat_does_not_store_pending_followup_intent():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "chat"}]
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
        content="aku lagi santai sambil denger musik di rumah nih",
    )
    await process_message(loop, msg)

    assert "pending_followup_intent" not in session.metadata


@pytest.mark.asyncio
async def test_process_message_direct_tool_fast_path_skips_full_context_build():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "cek ram"}]

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
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: "get_process_memory",
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="raw-ram-result"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="raw-ram-result")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="cek ram sekarang")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    context_builder.build_messages.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_check_update_fast_path_skips_full_context_build():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "cek update kabot"}]

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
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: "check_update",
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="raw-update-result"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="raw-update-result")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="cek update kabot sekarang")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    context_builder.build_messages.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_research_route_defaults_to_web_search_fast_path():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "berita terbaru 2026 sekarang"}]

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
            route=AsyncMock(return_value=SimpleNamespace(profile="RESEARCH", is_complex=True))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda name: name == "web_search"),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="web-result"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="web-result")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="berita terbaru 2026 sekarang",
    )
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    context_builder.build_messages.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_simple_route_emits_status_phases():
    published: list[OutboundMessage] = []

    async def _publish(msg: OutboundMessage) -> None:
        published.append(msg)

    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "oke"}]

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
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="ok"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="ok")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
        bus=SimpleNamespace(publish_outbound=AsyncMock(side_effect=_publish)),
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="oke")
    await process_message(loop, msg)

    statuses = [m for m in published if m.metadata.get("type") == "status_update"]
    phases = [m.metadata.get("phase") for m in statuses]
    assert "queued" in phases
    assert "thinking" in phases
    assert "done" in phases
    context_builder.build_messages.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_queue_merge_notice_in_queued_status():
    published: list[OutboundMessage] = []

    async def _publish(msg: OutboundMessage) -> None:
        published.append(msg)

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
        _resolve_context_for_message=lambda _msg: MagicMock(),
        context=MagicMock(),
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="ok"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="ok")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
        bus=SimpleNamespace(publish_outbound=AsyncMock(side_effect=_publish)),
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="hello",
        metadata={"queue": {"dropped_count": 2, "dropped_preview": ["older 1", "older 2"]}},
    )
    await process_message(loop, msg)

    queued = next(
        (m.content for m in published if m.metadata.get("type") == "status_update" and m.metadata.get("phase") == "queued"),
        "",
    )
    assert "Merged 2 queued message(s)." in queued


@pytest.mark.asyncio
async def test_process_message_status_text_comes_from_i18n_translator(monkeypatch):
    published: list[OutboundMessage] = []

    async def _publish(msg: OutboundMessage) -> None:
        published.append(msg)

    def _fake_t(key: str, text: str | None = None, **kwargs) -> str:
        if "count" in kwargs:
            return f"<{key}:{kwargs['count']}>"
        return f"<{key}>"

    monkeypatch.setattr(message_runtime_module, "t", _fake_t)

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
        _resolve_context_for_message=lambda _msg: MagicMock(),
        context=MagicMock(),
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="ok"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="ok")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
        bus=SimpleNamespace(publish_outbound=AsyncMock(side_effect=_publish)),
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="hello",
        metadata={"queue": {"dropped_count": 2, "dropped_preview": ["older 1"]}},
    )
    await process_message(loop, msg)

    queued = next(
        m.content for m in published if m.metadata.get("type") == "status_update" and m.metadata.get("phase") == "queued"
    )
    thinking = next(
        m.content for m in published if m.metadata.get("type") == "status_update" and m.metadata.get("phase") == "thinking"
    )
    done = next(
        m.content for m in published if m.metadata.get("type") == "status_update" and m.metadata.get("phase") == "done"
    )

    assert "<runtime.status.queued>" in queued
    assert "<runtime.status.queued_merged:2>" in queued
    assert thinking == "<runtime.status.thinking>"
    assert done == "<runtime.status.done>"


@pytest.mark.asyncio
async def test_process_message_emits_keepalive_updates_for_long_running_turn(monkeypatch):
    published: list[OutboundMessage] = []

    async def _publish(msg: OutboundMessage) -> None:
        published.append(msg)

    async def _slow_simple(_msg, _messages):
        await asyncio.sleep(0.06)
        return "ok"

    monkeypatch.setattr(message_runtime_module, "_KEEPALIVE_INITIAL_DELAY_SECONDS", 0.01, raising=False)
    monkeypatch.setattr(message_runtime_module, "_KEEPALIVE_INTERVAL_SECONDS", 0.01, raising=False)

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
        _resolve_context_for_message=lambda _msg: MagicMock(),
        context=MagicMock(),
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(side_effect=_slow_simple),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="ok")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
        bus=SimpleNamespace(publish_outbound=AsyncMock(side_effect=_publish)),
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="please check quickly")
    await process_message(loop, msg)

    keepalive_updates = [
        item
        for item in published
        if (item.metadata or {}).get("type") == "status_update"
        and bool((item.metadata or {}).get("keepalive", False))
    ]
    assert keepalive_updates


@pytest.mark.asyncio
async def test_process_message_skips_keepalive_updates_for_non_passthrough_channel(monkeypatch):
    published: list[OutboundMessage] = []

    async def _publish(msg: OutboundMessage) -> None:
        published.append(msg)

    async def _slow_simple(_msg, _messages):
        await asyncio.sleep(0.06)
        return "ok"

    monkeypatch.setattr(message_runtime_module, "_KEEPALIVE_INITIAL_DELAY_SECONDS", 0.01, raising=False)
    monkeypatch.setattr(message_runtime_module, "_KEEPALIVE_INTERVAL_SECONDS", 0.01, raising=False)

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
        _resolve_context_for_message=lambda _msg: MagicMock(),
        context=MagicMock(),
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(side_effect=_slow_simple),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="slack", chat_id="chat-1", content="ok")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
        bus=SimpleNamespace(publish_outbound=AsyncMock(side_effect=_publish)),
    )

    msg = InboundMessage(channel="slack", sender_id="u1", chat_id="chat-1", content="please check quickly")
    await process_message(loop, msg)

    keepalive_updates = [
        item
        for item in published
        if (item.metadata or {}).get("type") == "status_update"
        and bool((item.metadata or {}).get("keepalive", False))
    ]
    assert not keepalive_updates


@pytest.mark.asyncio
async def test_process_message_non_mutable_channel_emits_minimal_status_phases(monkeypatch):
    published: list[OutboundMessage] = []

    async def _publish(msg: OutboundMessage) -> None:
        published.append(msg)

    async def _slow_simple(_msg, _messages):
        await asyncio.sleep(0.05)
        return "ok"

    monkeypatch.setattr(message_runtime_module, "_KEEPALIVE_INITIAL_DELAY_SECONDS", 0.01, raising=False)
    monkeypatch.setattr(message_runtime_module, "_KEEPALIVE_INTERVAL_SECONDS", 0.01, raising=False)

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
        _resolve_context_for_message=lambda _msg: MagicMock(),
        context=MagicMock(),
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(side_effect=_slow_simple),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="whatsapp", chat_id="chat-1", content="ok")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
        bus=SimpleNamespace(publish_outbound=AsyncMock(side_effect=_publish)),
    )

    msg = InboundMessage(channel="whatsapp", sender_id="u1", chat_id="chat-1", content="cek status")
    await process_message(loop, msg)

    phases = [
        (item.metadata or {}).get("phase")
        for item in published
        if (item.metadata or {}).get("type") == "status_update"
    ]
    assert "queued" in phases
    assert "thinking" not in phases
    assert "done" not in phases


def test_should_store_followup_intent_for_short_live_research_query():
    assert message_runtime_module._should_store_followup_intent("berita terbaru 2026 sekarang")
    assert message_runtime_module._should_store_followup_intent("latest headlines 2026 now")


@pytest.mark.asyncio
async def test_process_message_short_confirmation_action_phrase_uses_pending_intent_context():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ambil sekarang"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "berita terbaru 2026 sekarang",
                "profile": "RESEARCH",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )

    def _required_tool(text: str) -> str | None:
        q = (text or "").lower()
        if "berita" in q or "news" in q:
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

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="ambil sekarang")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    context_builder.build_messages.assert_not_called()
    assert msg.metadata.get("required_tool") == "web_search"
    assert msg.metadata.get("required_tool_query") == "berita terbaru 2026 sekarang"


@pytest.mark.asyncio
async def test_process_message_persists_context_truncation_summary_and_passes_budget_hints():
    remember_fact = AsyncMock(return_value=True)
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "halo"}]
    context_builder.consume_last_truncation_summary.return_value = {
        "summary": "Earlier user asked for stock and weather details in one thread.",
        "dropped_count": 6,
    }

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=False, token_mode="hemat"),
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
            get_conversation_context=lambda _key, max_messages=30: [],
            remember_fact=remember_fact,
        ),
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

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="halo")
    await process_message(loop, msg)

    context_builder.build_messages.assert_called_once()
    kwargs = context_builder.build_messages.call_args.kwargs
    assert isinstance(kwargs.get("budget_hints"), dict)
    assert kwargs["budget_hints"]["token_mode"] == "hemat"
    remember_fact.assert_awaited_once()
