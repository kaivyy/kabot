"""Split from tests/agent/loop_core/test_message_runtime.py to keep test modules below 1000 lines.
Chunk 5: test_process_message_explicit_skill_reference_suppresses_conflicting_weather_inference .. test_should_store_followup_intent_for_short_live_research_query.
"""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import kabot.agent.loop_core.message_runtime as message_runtime_module
from kabot.agent.loop_core.message_runtime import (
    process_message,
)
from kabot.bus.events import InboundMessage, OutboundMessage


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
async def test_process_message_simple_chat_offer_response_stores_pending_followup_offer_intent():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "chat"}]
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
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(
            return_value=(
                "Gemini untuk hari ini bagus buat komunikasi. "
                "Kalau mau, aku bisa kasih juga versi angka hoki + jam bagus buat Gemini hari ini."
            )
        ),
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
        content="zodiak gw gemini, jadi hari ini gimana",
    )
    await process_message(loop, msg)

    assert session.metadata["pending_followup_intent"]["text"] == (
        "kalau mau, aku bisa kasih juga versi angka hoki + jam bagus buat gemini hari ini."
    )
    assert session.metadata["pending_followup_intent"]["profile"] == "CHAT"
    assert session.metadata["pending_followup_intent"]["kind"] == "assistant_offer"


@pytest.mark.asyncio
async def test_process_message_simple_chat_offer_response_stores_numbered_choice_block():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
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
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(
            return_value=(
                "Tentu. Mulai sekarang saya akan menggunakan gaya bahasa formal.\n"
                "Jika Anda ingin, saya juga bisa menyesuaikan tingkat formalitasnya, misalnya:\n"
                "1. Formal standar\n"
                "2. Sangat formal\n"
                "3. Formal tetapi tetap ramah\n"
                "Silakan balas hanya angka: 1, 2, atau 3."
            )
        ),
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
        content="dari semua template chat jadikan formal",
    )
    await process_message(loop, msg)

    assert session.metadata["pending_followup_intent"]["text"] == (
        "jika anda ingin, saya juga bisa menyesuaikan tingkat formalitasnya, misalnya: "
        "1. formal standar 2. sangat formal 3. formal tetapi tetap ramah "
        "silakan balas hanya angka: 1, 2, atau 3."
    )
    assert session.metadata["pending_followup_intent"]["profile"] == "CHAT"
    assert session.metadata["pending_followup_intent"]["kind"] == "assistant_offer"


@pytest.mark.asyncio
async def test_process_message_simple_chat_offer_response_stores_inline_numbered_choice_prompt():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
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
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(
            return_value="Siap, mau format yang mana? Balas angka aja: 1 (ringkas), 2 (detail), atau 3 (tabel)."
        ),
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
        content="ubah format jawaban",
    )
    await process_message(loop, msg)

    assert session.metadata["pending_followup_intent"]["text"] == (
        "siap, mau format yang mana? balas angka aja: 1 (ringkas), 2 (detail), atau 3 (tabel)."
    )
    assert session.metadata["pending_followup_intent"]["profile"] == "CHAT"
    assert session.metadata["pending_followup_intent"]["kind"] == "assistant_offer"


@pytest.mark.asyncio
async def test_process_message_simple_chat_offer_response_stores_inline_choice_question_prompt():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
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
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(
            return_value="Siap, aku tunggu pilihanmu. Mau yang 1) ringkas, 2) detail, atau 3) tabel?"
        ),
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
        content="ubah format jawaban",
    )
    await process_message(loop, msg)

    assert session.metadata["pending_followup_intent"]["text"] == (
        "siap, aku tunggu pilihanmu. mau yang 1) ringkas, 2) detail, atau 3) tabel?"
    )
    assert session.metadata["pending_followup_intent"]["profile"] == "CHAT"
    assert session.metadata["pending_followup_intent"]["kind"] == "assistant_offer"


@pytest.mark.asyncio
async def test_process_message_user_supplied_option_prompt_adds_grounding_note():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
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
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="Boleh, silakan pilih 1, 2, atau 3."),
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
        content="Kalau mau, aku bisa kasih 3 opsi: 1) ringkas 2) detail 3) tabel. Pilih satu ya.",
    )
    await process_message(loop, msg)

    effective_content = str(msg.metadata.get("effective_content") or "")
    assert effective_content.startswith("[User-Provided Option Prompt]\n")
    assert "should be treated as a quoted option list or draft" in effective_content
    assert "Do not choose an option on the user's behalf" in effective_content

@pytest.mark.asyncio
async def test_process_message_direct_tool_fast_path_skips_full_context_build():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "cek ram"}]
    route_mock = AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))

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
            route=route_mock
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
    route_mock.assert_not_awaited()
    assert msg.metadata.get("route_profile") == "GENERAL"
    assert msg.metadata.get("route_complex") is True

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
