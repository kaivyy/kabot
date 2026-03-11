"""Split from tests/agent/loop_core/test_message_runtime.py to keep test modules below 1000 lines.
Chunk 6: test_process_message_short_confirmation_action_phrase_uses_pending_intent_context .. test_process_message_persists_context_truncation_summary_and_passes_budget_hints.
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
async def test_process_message_short_confirmation_uses_pending_assistant_offer_context_for_chat():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "Kalau mau, aku bisa kasih juga versi angka hoki + jam bagus buat Gemini hari ini.",
                "profile": "CHAT",
                "kind": "assistant_offer",
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
        _run_simple_response=AsyncMock(return_value="2, 6, 8, 9"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="2, 6, 8, 9")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="ya")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    built = context_builder.build_messages.call_args.kwargs["current_message"]
    assert built.startswith("ya\n\n[Follow-up Context]\n")
    assert "[Offer Acceptance Note]" in built
    assert "accepting the assistant offer" in built.lower()
    assert "angka hoki + jam bagus buat Gemini hari ini" in built


@pytest.mark.asyncio
async def test_process_message_numeric_choice_uses_pending_assistant_offer_context_for_chat():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": (
                    "Jika Anda ingin, saya juga bisa menyesuaikan tingkat formalitasnya, misalnya:\n"
                    "1. Formal standar\n"
                    "2. Sangat formal\n"
                    "3. Formal tetapi tetap ramah\n"
                    "Silakan balas hanya angka: 1, 2, atau 3."
                ),
                "profile": "CHAT",
                "kind": "assistant_offer",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )

    captured_messages = {}

    async def _run_simple_response(_msg, messages):
        captured_messages["messages"] = messages
        return "Baik, saya akan gunakan formal standar."

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
        _run_simple_response=AsyncMock(side_effect=_run_simple_response),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(
                channel="telegram",
                chat_id="chat-1",
                content="Baik, saya akan gunakan formal standar.",
            )
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="1")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    current_message = context_builder.build_messages.call_args.kwargs["current_message"]
    assert current_message.startswith("1\n\n[Follow-up Context]\n")
    assert "1. formal standar" in current_message.lower()
    assert "silakan balas hanya angka" in current_message.lower()
    assert "[Selection Note]" in current_message
    assert "option 1" in current_message.lower()
    built = captured_messages["messages"][0]["content"]
    assert built == "ctx"


@pytest.mark.asyncio
async def test_process_message_user_supplied_multilingual_option_prompt_adds_strong_do_not_choose_note():
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
        _run_simple_response=AsyncMock(return_value="ok"),
        _run_agent_loop=AsyncMock(return_value="agent"),
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
        content="ถ้าคุณต้องการ ผมทำได้ 3 แบบ: 1) ทางการมาตรฐาน 2) ทางการมาก 3) ทางการแต่เป็นมิตร เลือกหนึ่งแบบ",
    )
    await process_message(loop, msg)

    current_message = captured_messages["current_message"]
    assert current_message.startswith("[User-Provided Option Prompt]\n")
    assert "[Context Note]" in current_message
    assert "should be treated as a quoted option list or draft" in current_message
    assert "Do not choose an option on the user's behalf" in current_message
    assert "ask for your recommendation" in current_message


@pytest.mark.asyncio
async def test_process_message_contextual_offer_question_uses_pending_assistant_offer_context():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": (
                    "Jika Anda mau, saya juga bisa menyesuaikan ke:\n"
                    "1. Formal profesional (kantor/bisnis)\n"
                    "2. Formal akademik\n"
                    "3. Formal layanan pelanggan (customer service)"
                ),
                "profile": "CHAT",
                "kind": "assistant_offer",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )

    captured_messages = {}

    async def _run_simple_response(_msg, messages):
        captured_messages["messages"] = messages
        return "Berikut contoh versi formal."

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
        _run_simple_response=AsyncMock(side_effect=_run_simple_response),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="Berikut contoh.")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="yang formal gimana")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    context_builder.build_messages.assert_called_once()
    current_message = context_builder.build_messages.call_args.kwargs["current_message"]
    assert current_message.startswith("yang formal gimana\n\n[Follow-up Context]\n")
    assert "formal akademik" in current_message.lower()
    assert "formal layanan pelanggan" in current_message.lower()
    built = captured_messages["messages"][0]["content"]
    assert built == "ctx"


@pytest.mark.asyncio
async def test_process_message_explicit_mcp_prompt_context_uses_full_context_builder():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
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
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _build_explicit_mcp_context_note=AsyncMock(
            return_value="[MCP Prompt Context]\n- Server: local\n- Prompt: briefing"
        ),
        _run_simple_response=AsyncMock(return_value="ok"),
        _run_agent_loop=AsyncMock(return_value="agent"),
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
        content="gunakan prompt briefing dari server local untuk bantu jawab",
    )
    await process_message(loop, msg)

    loop._build_explicit_mcp_context_note.assert_awaited_once()
    context_builder.build_messages.assert_called_once()
    kwargs = context_builder.build_messages.call_args.kwargs
    current_message = kwargs["current_message"]
    assert "[MCP Prompt Context]" in current_message
    assert "- Prompt: briefing" in current_message
    assert msg.metadata.get("mcp_context_mode") is True
    assert kwargs["budget_hints"]["mcp_context_mode"] is True


@pytest.mark.asyncio
async def test_process_message_explicit_mcp_resource_context_uses_full_context_builder():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
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
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: "stock",
        _build_explicit_mcp_context_note=AsyncMock(
            return_value="[MCP Resource Context]\n- Server: local\n- Resource: memory://field-guide"
        ),
        _run_simple_response=AsyncMock(return_value="ok"),
        _run_agent_loop=AsyncMock(return_value="agent"),
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
        content="baca resource memory://field-guide dari server local lalu jelaskan ringkas",
    )
    await process_message(loop, msg)

    loop._build_explicit_mcp_context_note.assert_awaited_once()
    context_builder.build_messages.assert_called_once()
    kwargs = context_builder.build_messages.call_args.kwargs
    current_message = kwargs["current_message"]
    assert "[MCP Resource Context]" in current_message
    assert "memory://field-guide" in current_message
    assert msg.metadata.get("mcp_context_mode") is True
    assert "required_tool" not in msg.metadata
    assert kwargs["budget_hints"]["mcp_context_mode"] is True


@pytest.mark.asyncio
async def test_process_message_option_ordinal_followup_uses_pending_assistant_offer_context():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": (
                    "Jika Anda ingin, saya juga bisa menyesuaikan tingkat formalitasnya, misalnya:\n"
                    "1. Formal standar\n"
                    "2. Sangat formal\n"
                    "3. Formal tetapi tetap ramah\n"
                    "Silakan balas hanya angka: 1, 2, atau 3."
                ),
                "profile": "CHAT",
                "kind": "assistant_offer",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )

    captured_messages = {}

    async def _run_simple_response(_msg, messages):
        captured_messages["messages"] = messages
        return "Berikut penjelasan opsi ketiga."

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
        _run_simple_response=AsyncMock(side_effect=_run_simple_response),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(
                channel="telegram",
                chat_id="chat-1",
                content="Berikut penjelasan opsi ketiga.",
            )
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

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    current_message = context_builder.build_messages.call_args.kwargs["current_message"]
    assert current_message.startswith("yang ketiga gimana\n\n[Follow-up Context]\n")
    assert "[Selection Note]" in current_message
    assert "option 3" in current_message.lower()


@pytest.mark.asyncio
async def test_process_message_multilingual_option_ordinal_followup_uses_pending_assistant_offer_context():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": (
                    "必要なら3つの文体を出せます。\n"
                    "1. 標準的に丁寧\n"
                    "2. とても丁寧\n"
                    "3. 丁寧だけどやわらかい\n"
                    "1つ選んでください。"
                ),
                "profile": "CHAT",
                "kind": "assistant_offer",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )

    captured_messages = {}

    async def _run_simple_response(_msg, messages):
        captured_messages["messages"] = messages
        return "了解です。2番を使います。"

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
        _run_simple_response=AsyncMock(side_effect=_run_simple_response),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="了解です。2番を使います。")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="2番")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    current_message = context_builder.build_messages.call_args.kwargs["current_message"]
    assert current_message.startswith("2番\n\n[Follow-up Context]\n")
    assert "[Selection Note]" in current_message
    assert "option 2" in current_message.lower()
    built = captured_messages["messages"][0]["content"]
    assert built == "ctx"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("assistant_text", "followup_text"),
    [
        ("好的，选择 2）非常正式。请把原文发给我。", "再简短一点"),
        ("とても丁寧な文体で進めます。原文を送ってください。", "もっと短く"),
        ("รับทราบครับ จะใช้สำนวนทางการมาก กรุณาส่งข้อความต้นฉบับ", "สั้นกว่านี้"),
    ],
)
async def test_process_message_multilingual_answer_reference_followup_uses_recent_assistant_history_context(
    assistant_text: str,
    followup_text: str,
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

    async def _run_simple_response(_msg, messages):
        captured_messages["messages"] = messages
        return "ok"

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
        _run_simple_response=AsyncMock(side_effect=_run_simple_response),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="ok")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content=followup_text)
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    current_message = captured_messages["current_message"]
    assert current_message.startswith(f"{followup_text}\n\n[Answer Reference Target]\n")
    assert assistant_text in current_message
    assert "[Answer Reference Context]\n" in current_message
    assert "[Grounded Answer Note]\n" in current_message
    assert "[Answer Reference Note]" in current_message


@pytest.mark.asyncio
async def test_process_message_answer_reference_followup_keeps_recent_answer_context_even_with_pending_assistant_offer():
    captured_messages = {}

    def _build_messages(**kwargs):
        captured_messages["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": "ctx"}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.consume_last_truncation_summary.return_value = None
    assistant_text = (
        "\u975e\u5e38\u597d\uff0c\u4ee5\u4e0b\u662f\u7b2c\u4e8c\u4e2a\u7248\u672c\uff08\u975e\u5e38\u6b63\u5f0f\uff09\uff1a"
    )
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "\u5982\u679c\u60a8\u9700\u8981\uff0c\u6211\u4e5f\u53ef\u4ee5\u518d\u63d0\u4f9b\u4e00\u4e2a\u201c\u6781\u7b80\u6b63\u5f0f\u7248\u201d\u3002",
                "profile": "CHAT",
                "kind": "assistant_offer",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )
    history = [{"role": "assistant", "content": assistant_text}]

    async def _run_simple_response(_msg, messages):
        captured_messages["messages"] = messages
        return "ok"

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
        _run_simple_response=AsyncMock(side_effect=_run_simple_response),
        _run_agent_loop=AsyncMock(return_value="agent"),
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
        content="\u518d\u7b80\u77ed\u4e00\u70b9",
    )
    await process_message(loop, msg)

    current_message = captured_messages.get("current_message") or str(
        captured_messages["messages"][0]["content"]
    )
    assert current_message.startswith("\u518d\u7b80\u77ed\u4e00\u70b9\n\n[Follow-up Context]\n")
    assert "[Offer Acceptance Note]" in current_message
    assert "[Answer Reference Context]" in current_message
    assert assistant_text in current_message
    assert "[Answer Reference Note]" in current_message


@pytest.mark.asyncio
async def test_process_message_short_new_question_does_not_reuse_unrelated_assistant_offer_context():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": (
                    "Jika Anda mau, saya juga bisa menyesuaikan ke:\n"
                    "1. Formal profesional\n"
                    "2. Formal akademik\n"
                    "3. Formal layanan pelanggan"
                ),
                "profile": "CHAT",
                "kind": "assistant_offer",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )

    captured_messages = {}

    async def _run_simple_response(_msg, messages):
        captured_messages["messages"] = messages
        return "Saya asisten yang siap membantu."

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
        _run_simple_response=AsyncMock(side_effect=_run_simple_response),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(
                channel="telegram",
                chat_id="chat-1",
                content="Saya asisten yang siap membantu.",
            )
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="siapa kamu")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    built = captured_messages["messages"][0]["content"]
    assert built == "siapa kamu"


@pytest.mark.asyncio
async def test_process_message_assistant_offer_followup_beats_stale_pending_weather_tool():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "weather",
                "source": "cuaca cilacap utara sekarang berapa",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "pending_followup_intent": {
                "text": "Kalau mau, aku bisa kasih paket darurat musim hujan yang murah buat disiapkan di tas.",
                "profile": "CHAT",
                "kind": "assistant_offer",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
        }
    )

    captured_messages = {}

    async def _run_simple_response(_msg, messages):
        captured_messages["messages"] = messages
        return "Ini paket darurat musim hujan yang murah."

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
        _run_simple_response=AsyncMock(side_effect=_run_simple_response),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(
                channel="telegram",
                chat_id="chat-1",
                content="Ini paket darurat musim hujan yang murah.",
            )
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="ya berikan")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    built = context_builder.build_messages.call_args.kwargs["current_message"]
    assert built.startswith("ya berikan\n\n[Follow-up Context]\n")
    assert "[Offer Acceptance Note]" in built
    assert "accepting the assistant offer" in built.lower()
    assert "paket darurat musim hujan" in built.lower()


@pytest.mark.asyncio
async def test_process_message_committed_action_offer_followup_beats_stale_last_tool_execution():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "last_tool_execution": {
                "tool": "get_system_info",
                "source": "cek spek pc saya",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "pending_followup_intent": {
                "text": "Aku akan buat file Excel jadwal lari 8 minggu kamu di workspace, lalu langsung kirim filenya ke chat ini.",
                "profile": "CHAT",
                "kind": "assistant_committed_action",
                "request_text": "buat file excel jadwal lari 8 minggu di workspace lalu kirim ke chat ini",
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
        tools=SimpleNamespace(tool_names=["get_system_info"], has=lambda name: name == "get_system_info"),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="Siap, saya akan buat file Excel-nya sekarang."),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(
                channel="telegram",
                chat_id="chat-1",
                content="Siap, saya akan buat file Excel-nya sekarang.",
            )
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="ya lakukan")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    built = context_builder.build_messages.call_args.kwargs["current_message"]
    assert built.startswith("ya lakukan\n\n[Committed Action Context]\n")
    assert "[Committed Action Note]" in built
    assert "follow through on the promised action now" in built.lower()
    assert "file excel jadwal lari 8 minggu" in built.lower()
    assert "cek spek pc saya" not in built.lower()
    assert "buat file excel jadwal lari 8 minggu di workspace" in built.lower()


@pytest.mark.asyncio
async def test_process_message_committed_action_followup_reuses_original_media_request_text():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "Saya akan generate gambar poster konsernya lalu kirim hasilnya.",
                "profile": "CHAT",
                "kind": "assistant_committed_action",
                "request_text": "buat gambar poster konser synthwave pakai imagen dengan nuansa neon",
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
        tools=SimpleNamespace(tool_names=["image_gen"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="oke buat sekarang")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    built = context_builder.build_messages.call_args.kwargs["current_message"]
    assert "[Committed Action Context]" in built
    assert "buat gambar poster konser synthwave pakai imagen" in built.lower()
    assert "generate gambar poster konsernya" in built.lower()
    assert msg.metadata.get("continuity_source") == "committed_action"
    assert msg.metadata.get("turn_category") == "contextual_action"


@pytest.mark.asyncio
async def test_process_message_committed_action_followup_with_arrow_key_controls_does_not_force_read_file():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": (
                    "Mantap, lanjut ya — aku akan upgrade game yang tadi dengan 4 fitur ini sekaligus:\n\n"
                    "1) 2-player mode (P1: W/S, P2: ↑/↓)\n"
                    "2) Mobile touch controls\n"
                    "3) Sound effects\n"
                    "4) Difficulty levels (Easy/Medium/Hard)\n\n"
                    "Aku akan edit file ping-pong/index.html, ping-pong/style.css, dan "
                    "ping-pong/game.js sekarang. Setelah itu aku kabarin kalau sudah selesai."
                ),
                "profile": "CHAT",
                "kind": "assistant_committed_action",
                "request_text": "yes continue",
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

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="yes continue")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("required_tool_query") is None
    built = context_builder.build_messages.call_args.kwargs["current_message"]
    assert "[Committed Action Context]" in built
    assert "ping-pong/index.html" in built
    assert "↑/↓" in built


@pytest.mark.asyncio
async def test_process_message_assistant_offer_followup_reuses_original_send_request_text():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "Kalau mau, saya bisa lanjut kirim file report.pdf ke chat ini.",
                "profile": "CHAT",
                "kind": "assistant_offer",
                "request_text": r"kirim file C:\Users\Arvy Kairi\Desktop\report.pdf ke chat ini",
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
        tools=SimpleNamespace(tool_names=["message"], has=lambda name: name == "message"),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="oke lanjut")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    built = context_builder.build_messages.call_args.kwargs["current_message"]
    assert "[Offer Acceptance Note]" in built
    assert "[Offer Request Context]" in built
    assert r"kirim file C:\Users\Arvy Kairi\Desktop\report.pdf ke chat ini".lower() in built.lower()
    assert msg.metadata.get("required_tool") == "message"
    assert msg.metadata.get("continuity_source") == "action_request"
    assert msg.metadata.get("requires_message_delivery") is True
    assert msg.metadata.get("turn_category") == "contextual_action"


@pytest.mark.asyncio
async def test_process_message_assistant_offer_followup_reuses_original_file_build_request_text():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "Kalau mau, saya bisa lanjut bikin file jadwal HM-nya dan kirim ke chat ini.",
                "profile": "CHAT",
                "kind": "assistant_offer",
                "request_text": "buat file .smoke_tmp/jadwal_hm.txt berisi TARGET PACE 7:00 lalu kirim ke chat ini",
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
        tools=SimpleNamespace(tool_names=["write_file", "message"], has=lambda name: name in {"write_file", "message"}),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="oke lanjut")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    built = context_builder.build_messages.call_args.kwargs["current_message"]
    assert "[Offer Request Context]" in built
    assert "buat file .smoke_tmp/jadwal_hm.txt" in built.lower()
    assert msg.metadata.get("required_tool") == "write_file"
    assert msg.metadata.get("continuity_source") == "action_request"
    assert msg.metadata.get("requires_message_delivery") is True
    assert msg.metadata.get("turn_category") == "contextual_action"


@pytest.mark.asyncio
async def test_process_message_assistant_offer_followup_promotes_coding_request_from_original_offer_context():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    context_builder.consume_last_truncation_summary.return_value = None
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "Kalau mau, saya bisa lanjut bikin landing page dan kirim screenshotnya.",
                "profile": "CHAT",
                "kind": "assistant_offer",
                "request_text": "buat website landing page KAIDUT tema dark style crypto lalu screenshot dan kirim ke chat ini",
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
        tools=SimpleNamespace(tool_names=["exec", "message"]),
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
    built = context_builder.build_messages.call_args.kwargs["current_message"]
    assert "[Offer Acceptance Note]" in built
    assert "[Offer Request Context]" in built
    assert "[Coding Build Note]" in built
    assert "buat website landing page kaidut" in built.lower()
    assert msg.metadata.get("route_profile") == "CODING"
    assert msg.metadata.get("continuity_source") == "coding_request"
    assert msg.metadata.get("requires_message_delivery") is True
    assert msg.metadata.get("turn_category") == "contextual_action"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        "buat file excel jadwal lari 8 minggu di workspace lalu kirim ke chat ini",
        "generate gambar poster produk pakai imagen dan simpan hasilnya di workspace",
        "buat video singkat promosi pakai nanobanana lalu export mp4",
    ],
)
async def test_process_message_generic_side_effect_requests_escalate_to_agent_loop(content: str):
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda text: (
                text,
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
        tools=SimpleNamespace(tool_names=["write_file", "image_gen", "exec"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content=content)
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    context_builder.build_messages.assert_called_once()
    built = context_builder.build_messages.call_args.kwargs["current_message"]
    assert content in built
    assert msg.metadata.get("turn_category") == "action"


@pytest.mark.asyncio
async def test_process_message_side_effect_request_beats_weak_read_file_parser_guess():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(metadata={})

    def _required_tool(text: str) -> str | None:
        normalized = (text or "").lower()
        if ".txt" in normalized or "file" in normalized:
            return "read_file"
        return None

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda text: (
                text,
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
        tools=SimpleNamespace(tool_names=["read_file", "write_file", "exec"]),
        _required_tool_for_query=_required_tool,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    content = "buat file .smoke_tmp/smoke_action_request.txt di workspace berisi HALO_KABOT"
    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content=content)
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    assert msg.metadata.get("required_tool") == "write_file"
    assert msg.metadata.get("required_tool_query") == content
    assert msg.metadata.get("continuity_source") == "action_request"
    assert msg.metadata.get("suppress_required_tool_inference") is True


@pytest.mark.asyncio
async def test_process_message_side_effect_request_infers_write_file_tool_when_path_is_explicit():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda text: (
                text,
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
        tools=SimpleNamespace(tool_names=["write_file", "read_file"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    content = "buat file .smoke_tmp/smoke_action_request.txt di workspace berisi HALO_KABOT"
    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content=content)
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") == "write_file"
    assert msg.metadata.get("required_tool_query") == content
    assert msg.metadata.get("continuity_source") == "action_request"


@pytest.mark.asyncio
async def test_process_message_side_effect_request_infers_image_gen_for_image_generation_prompt():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda text: (
                text,
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
        tools=SimpleNamespace(tool_names=["image_gen"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    content = "generate gambar poster produk pakai imagen dan simpan hasilnya di workspace"
    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content=content)
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") == "image_gen"
    assert msg.metadata.get("required_tool_query") == content


@pytest.mark.asyncio
async def test_process_message_coding_build_request_promotes_to_coding_route_without_crypto_tool_guess():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    context_builder.consume_last_truncation_summary.return_value = None
    session = SimpleNamespace(metadata={})

    def _required_tool(text: str) -> str | None:
        return "crypto" if "crypto" in (text or "").lower() else None

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda text: (
                text,
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
        tools=SimpleNamespace(tool_names=["crypto"]),
        _required_tool_for_query=_required_tool,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    content = "BUATKAN WEBSITE LANDING PAGE UNTUK PAYMENT GATEWAY, DENGAN TEMA DARK, STYLENYA SEPERTI WEBSITE CRYPTO"
    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content=content)
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("continuity_source") == "coding_request"
    assert msg.metadata.get("route_profile") == "CODING"
    current_message = context_builder.build_messages.call_args.kwargs["current_message"]
    assert "[Coding Build Note]" in current_message
    assert "landing page" in current_message.lower()


@pytest.mark.asyncio
async def test_process_message_side_effect_request_infers_message_for_explicit_send_file_prompt():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda text: (
                text,
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
        tools=SimpleNamespace(tool_names=["message"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    content = r"kirim file C:\Users\Arvy Kairi\Desktop\report.pdf ke chat ini"
    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content=content)
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") == "message"
    assert msg.metadata.get("required_tool_query") == content
    assert msg.metadata.get("requires_message_delivery") is True


@pytest.mark.asyncio
async def test_process_message_committed_coding_action_followup_promotes_to_coding_route():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    context_builder.consume_last_truncation_summary.return_value = None
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "Aku akan bikin landing page KAIDUT lalu ambil screenshot dan kirim ke chat ini.",
                "profile": "CHAT",
                "kind": "assistant_committed_action",
                "request_text": "buat website landing page KAIDUT tema dark style crypto lalu screenshot dan kirim ke chat ini",
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
            parse=lambda text: (
                text,
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

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="YA")
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("continuity_source") == "committed_coding_action"
    assert msg.metadata.get("route_profile") == "CODING"
    current_message = context_builder.build_messages.call_args.kwargs["current_message"]
    assert "[Committed Action Context]" in current_message
    assert "[Coding Build Note]" in current_message
    assert "landing page kaidut" in current_message.lower()
    assert msg.metadata.get("requires_message_delivery") is True


@pytest.mark.asyncio
async def test_process_message_coding_build_request_marks_delivery_required_for_shorthand_ss_kirim_sini():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
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
            parse=lambda text: (
                text,
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

    content = "NAMA BRAND: KAIDUT. CTA WA: 08888888. LANJUT BIKIN WEBSITE LANDING PAGE NYA DAN SS KIRIM SINI"
    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content=content)
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("continuity_source") == "coding_request"
    assert msg.metadata.get("route_profile") == "CODING"
    assert msg.metadata.get("requires_message_delivery") is True
    current_message = context_builder.build_messages.call_args.kwargs["current_message"]
    assert "[Coding Build Note]" in current_message


@pytest.mark.asyncio
async def test_process_message_find_then_send_file_request_stays_ai_driven_and_marks_delivery_required():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda text: (
                text,
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
        tools=SimpleNamespace(tool_names=["find_files", "message"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    content = "cari file report.pdf di workspace lalu kirim ke chat ini"
    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content=content)
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("continuity_source") == "action_request"
    assert msg.metadata.get("requires_message_delivery") is True


@pytest.mark.asyncio
async def test_process_message_create_then_send_file_request_prefers_write_file_and_marks_delivery_required():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda text: (
                text,
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
        tools=SimpleNamespace(tool_names=["write_file", "message"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    content = "buat file .smoke_tmp/report.txt berisi HALO lalu kirim ke chat ini"
    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content=content)
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") == "write_file"
    assert msg.metadata.get("required_tool_query") == content
    assert msg.metadata.get("requires_message_delivery") is True


@pytest.mark.asyncio
async def test_process_message_generate_then_send_image_request_prefers_image_gen_and_marks_delivery_required():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda text: (
                text,
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
        tools=SimpleNamespace(tool_names=["image_gen", "message"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    content = "generate gambar poster kopi pakai imagen lalu kirim ke chat ini"
    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content=content)
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") == "image_gen"
    assert msg.metadata.get("required_tool_query") == content
    assert msg.metadata.get("requires_message_delivery") is True


@pytest.mark.asyncio
async def test_process_message_side_effect_request_infers_registered_media_mcp_tool():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda text: (
                text,
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
        tools=SimpleNamespace(tool_names=["mcp__nanobanana__generate_video"]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    content = "buat video singkat promosi pakai nanobanana lalu export mp4"
    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content=content)
    await process_message(loop, msg)

    loop._run_agent_loop.assert_awaited_once()
    assert msg.metadata.get("required_tool") == "mcp__nanobanana__generate_video"
    assert msg.metadata.get("required_tool_query") == content


@pytest.mark.asyncio
async def test_process_message_assistant_offer_followup_does_not_infer_cron_from_offer_text():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "If you want, I can give you a more specific Gemini day plan in 60 seconds.",
                "profile": "CHAT",
                "kind": "assistant_offer",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )

    captured_messages = {}

    async def _run_simple_response(_msg, messages):
        captured_messages["messages"] = messages
        return "Morning: focus. Afternoon: flex. Night: reset."

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
        _required_tool_for_query=lambda text: "cron" if "seconds" in (text or "").lower() else None,
        _run_simple_response=AsyncMock(side_effect=_run_simple_response),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="Morning: focus.")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="yeah")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    built = context_builder.build_messages.call_args.kwargs["current_message"]
    assert built.startswith("yeah\n\n[Follow-up Context]\n")
    assert "[Offer Acceptance Note]" in built
    assert "accepting the assistant offer" in built.lower()
    assert "gemini day plan in 60 seconds" in built.lower()


@pytest.mark.asyncio
async def test_process_message_generic_plan_followup_does_not_infer_stale_stock_history():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(metadata={})

    def _required_tool(text: str) -> str | None:
        normalized = (text or "").lower()
        if "saham" in normalized or "stock" in normalized or "apple" in normalized or "aapl" in normalized:
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
        memory=SimpleNamespace(
            get_conversation_context=lambda _key, max_messages=30: [
                {"role": "user", "content": "kalau saham apple berapa sekarang"},
                {
                    "role": "assistant",
                    "content": (
                        "Kalau kamu mau, aku bisa lanjut bikin rencana entry-exit 3 skenario "
                        "(breakout, pullback, dan invalidation) lengkap angka levelnya."
                    ),
                },
            ]
        ),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=_required_tool,
        _run_simple_response=AsyncMock(return_value="Baik, saya lanjutkan rencananya."),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(
                channel="telegram",
                chat_id="chat-1",
                content="Baik, saya lanjutkan rencananya.",
            )
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="lanjut rencana")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    context_builder.build_messages.assert_called_once()


@pytest.mark.asyncio
async def test_process_message_stock_offer_followup_uses_pending_assistant_offer_context():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "ctx"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": (
                    "Kalau kamu mau, aku bisa lanjut bikin rencana entry-exit 3 skenario "
                    "(breakout, pullback, dan invalidation) lengkap angka levelnya."
                ),
                "profile": "CHAT",
                "kind": "assistant_offer",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "pending_followup_tool": {
                "tool": "stock",
                "source": "kalau saham apple berapa sekarang",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
        }
    )

    captured_messages = {}

    async def _run_simple_response(_msg, messages):
        captured_messages["messages"] = messages
        return "Baik, saya lanjutkan rencana entry-exit."

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
        _required_tool_for_query=lambda text: "stock" if "apple" in (text or "").lower() else None,
        _run_simple_response=AsyncMock(side_effect=_run_simple_response),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(
                channel="telegram",
                chat_id="chat-1",
                content="Baik, saya lanjutkan rencana entry-exit.",
            )
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="ya lanjut")
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    context_builder.build_messages.assert_called_once()
    current_message = context_builder.build_messages.call_args.kwargs["current_message"]
    assert current_message.startswith("ya lanjut\n\n[Follow-up Context]\n")
    assert "[Offer Acceptance Note]" in current_message
    assert "accepting the assistant offer" in current_message.lower()
    assert "entry-exit 3 skenario" in current_message.lower()
    built = captured_messages["messages"][0]["content"]
    assert built == "ctx"

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
