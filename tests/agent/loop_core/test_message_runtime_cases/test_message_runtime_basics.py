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
    assert session.metadata.get("runtime_locale") == "id"

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
    assert session.metadata.get("input_locale") == "id"


def test_resolve_runtime_locale_honors_explicit_runtime_locale_override():
    session = SimpleNamespace(metadata={})
    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="tolong cek cuaca sekarang",
        metadata={"runtime_locale": "id"},
    )

    resolved = message_runtime_module._resolve_runtime_locale(session, msg, msg.content)

    assert resolved == "id"
    assert session.metadata.get("runtime_locale") == "id"
    assert session.metadata.get("input_locale") == "id"

def test_short_context_followup_does_not_misclassify_substantive_cjk_query():
    assert message_runtime_module._is_short_context_followup("\u5929\u6c14\u5317\u4eac\u73b0\u5728\u600e\u4e48\u6837") is False
    assert message_runtime_module._is_short_context_followup("\u662f") is True

def test_followup_helpers_detect_acknowledgement_without_hardcoded_wordlist():
    assert message_runtime_module._is_low_information_turn("oke makasih ya", max_tokens=6, max_chars=64)
    assert message_runtime_module._looks_like_short_confirmation("oke makasih ya")
    assert message_runtime_module._is_short_context_followup("oke makasih ya")
    assert message_runtime_module._looks_like_short_confirmation("saranmu apa") is False


def test_extract_assistant_followup_offer_text_supports_multilingual_offer_phrases():
    assert (
        message_runtime_module._extract_assistant_followup_offer_text(
            "Kalau mau, aku bisa kasih juga versi angka hoki + jam bagus buat Gemini hari ini."
        )
        == "Kalau mau, aku bisa kasih juga versi angka hoki + jam bagus buat Gemini hari ini."
    )
    assert (
        message_runtime_module._extract_assistant_followup_offer_text(
            "If you'd like, I can also give you lucky numbers and best hours for Gemini today."
        )
        == "If you'd like, I can also give you lucky numbers and best hours for Gemini today."
    )
    assert message_runtime_module._extract_assistant_followup_offer_text(
        "Tolong beri tahu apa yang ingin Anda saya berikan?"
    ) is None


def test_extract_explicit_mcp_tool_name_maps_alias_to_api_safe_name():
    assert (
        message_runtime_module._extract_explicit_mcp_tool_name(
            "Gunakan tool mcp.local_echo.echo dengan argumen text='halo'."
        )
        == "mcp__local_echo__echo"
    )


def test_extract_assistant_followup_offer_text_supports_polite_indonesian_offer_phrase():
    assert (
        message_runtime_module._extract_assistant_followup_offer_text(
            "Tentu. Mulai sekarang saya akan menggunakan gaya bahasa formal. "
            "Jika Anda ingin, saya juga bisa menyesuaikan tingkat formalitasnya "
            "(misalnya: sangat resmi, profesional, atau semi-formal)."
        )
        == "Jika Anda ingin, saya juga bisa menyesuaikan tingkat formalitasnya "
        "(misalnya: sangat resmi, profesional, atau semi-formal)."
    )


def test_extract_assistant_followup_offer_text_supports_action_oriented_offer_phrase():
    text = "Kalau kamu mau, aku lanjut cek harga IHSG real-time sekarang pakai simbol ^JKSE."
    assert message_runtime_module._extract_assistant_followup_offer_text(text) == text


def test_extract_assistant_followup_offer_text_supports_committed_action_promise():
    text = (
        "Bisa banget. Aku akan buat file Excel jadwal lari 8 minggu kamu di workspace, "
        "lalu langsung kirim filenya ke chat ini."
    )
    assert (
        message_runtime_module._extract_assistant_followup_offer_text(text)
        == "Aku akan buat file Excel jadwal lari 8 minggu kamu di workspace, lalu langsung kirim filenya ke chat ini."
    )


def test_extract_assistant_followup_offer_text_preserves_numbered_choice_block():
    assert (
        message_runtime_module._extract_assistant_followup_offer_text(
            "Tentu. Mulai sekarang saya akan menggunakan gaya bahasa formal.\n"
            "Jika Anda ingin, saya juga bisa menyesuaikan tingkat formalitasnya, misalnya:\n"
            "1. Formal standar\n"
            "2. Sangat formal\n"
            "3. Formal tetapi tetap ramah\n"
            "Silakan balas hanya angka: 1, 2, atau 3."
        )
        == "Jika Anda ingin, saya juga bisa menyesuaikan tingkat formalitasnya, misalnya:\n"
        "1. Formal standar\n"
        "2. Sangat formal\n"
        "3. Formal tetapi tetap ramah\n"
        "Silakan balas hanya angka: 1, 2, atau 3."
    )


def test_extract_assistant_followup_offer_text_supports_pure_numbered_choice_prompt():
    assert (
        message_runtime_module._extract_assistant_followup_offer_text(
            "Tentu! Berikut 3 opsi tingkat formalitas:\n"
            "1. Santai\n"
            "2. Semi-formal\n"
            "3. Formal\n"
            "Silakan balas hanya dengan angka: 1, 2, atau 3."
        )
        == "Tentu! Berikut 3 opsi tingkat formalitas:\n"
        "1. Santai\n"
        "2. Semi-formal\n"
        "3. Formal\n"
        "Silakan balas hanya dengan angka: 1, 2, atau 3."
    )


def test_extract_assistant_followup_offer_text_supports_inline_numbered_choice_prompt():
    assert (
        message_runtime_module._extract_assistant_followup_offer_text(
            "Siap, mau format yang mana? Balas angka aja: 1 (ringkas), 2 (detail), atau 3 (tabel)."
        )
        == "Siap, mau format yang mana? Balas angka aja: 1 (ringkas), 2 (detail), atau 3 (tabel)."
    )


def test_extract_assistant_followup_offer_text_supports_inline_choice_question_prompt():
    assert (
        message_runtime_module._extract_assistant_followup_offer_text(
            "Siap, aku tunggu pilihanmu. Mau yang 1) ringkas, 2) detail, atau 3) tabel?"
        )
        == "Siap, aku tunggu pilihanmu. Mau yang 1) ringkas, 2) detail, atau 3) tabel?"
    )


def test_extract_user_supplied_option_prompt_text_detects_inline_numbered_choices():
    assert (
        message_runtime_module._extract_user_supplied_option_prompt_text(
            "Kalau mau, aku bisa kasih 3 opsi: 1) ringkas 2) detail 3) tabel. Pilih satu ya."
        )
        == "Kalau mau, aku bisa kasih 3 opsi: 1) ringkas 2) detail 3) tabel. Pilih satu ya."
    )


def test_extract_assistant_followup_offer_text_preserves_multiline_chinese_choice_block():
    text = (
        "\u5f53\u7136\u53ef\u4ee5\uff5e\n"
        "\u4f60\u53ef\u4ee5\u76f4\u63a5\u9009\u4e00\u4e2a\u7f16\u53f7\u5c31\u597d\uff1a\n"
        "1\uff09\u6b63\u5f0f\u6807\u51c6\n"
        "2\uff09\u975e\u5e38\u6b63\u5f0f\n"
        "3\uff09\u6b63\u5f0f\u4f46\u53cb\u597d\n"
        "\u5982\u679c\u4f60\u4e0d\u786e\u5b9a\uff0c\u6211\u4e5f\u53ef\u4ee5\u5148\u544a\u8bc9\u4f60\u8fd9\u4e09\u4e2a\u7248\u672c\u5404\u81ea\u9002\u5408\u4ec0\u4e48\u573a\u666f\u3002"
    )

    assert (
        message_runtime_module._extract_assistant_followup_offer_text(text)
        == "\u4f60\u53ef\u4ee5\u76f4\u63a5\u9009\u4e00\u4e2a\u7f16\u53f7\u5c31\u597d\uff1a\n1\uff09\u6b63\u5f0f\u6807\u51c6\n2\uff09\u975e\u5e38\u6b63\u5f0f\n3\uff09\u6b63\u5f0f\u4f46\u53cb\u597d"
    )


def test_extract_user_supplied_option_prompt_text_detects_multilingual_inline_choices():
    assert (
        message_runtime_module._extract_user_supplied_option_prompt_text(
            "\u5982\u679c\u4f60\u613f\u610f\uff0c\u6211\u53ef\u4ee5\u7ed9\u4f60\u4e09\u4e2a\u7248\u672c\uff1a1\uff09\u6b63\u5f0f\u6807\u51c6 2\uff09\u975e\u5e38\u6b63\u5f0f 3\uff09\u6b63\u5f0f\u4f46\u53cb\u597d\u3002\u9009\u4e00\u4e2a\u3002"
        )
        == "\u5982\u679c\u4f60\u613f\u610f\uff0c\u6211\u53ef\u4ee5\u7ed9\u4f60\u4e09\u4e2a\u7248\u672c\uff1a1\uff09\u6b63\u5f0f\u6807\u51c6 2\uff09\u975e\u5e38\u6b63\u5f0f 3\uff09\u6b63\u5f0f\u4f46\u53cb\u597d\u3002\u9009\u4e00\u4e2a\u3002"
    )
    assert (
        message_runtime_module._extract_user_supplied_option_prompt_text(
            "\u5fc5\u8981\u306a\u30893\u3064\u306e\u6587\u4f53\u3092\u51fa\u305b\u307e\u3059\u30021) \u6a19\u6e96\u7684\u306b\u4e01\u5be7 2) \u3068\u3066\u3082\u4e01\u5be7 3) \u4e01\u5be7\u3060\u3051\u3069\u3084\u308f\u3089\u304b\u3044\u30021\u3064\u9078\u3093\u3067\u304f\u3060\u3055\u3044\u3002"
        )
        == "\u5fc5\u8981\u306a\u30893\u3064\u306e\u6587\u4f53\u3092\u51fa\u305b\u307e\u3059\u30021) \u6a19\u6e96\u7684\u306b\u4e01\u5be7 2) \u3068\u3066\u3082\u4e01\u5be7 3) \u4e01\u5be7\u3060\u3051\u3069\u3084\u308f\u3089\u304b\u3044\u30021\u3064\u9078\u3093\u3067\u304f\u3060\u3055\u3044\u3002"
    )
    assert (
        message_runtime_module._extract_user_supplied_option_prompt_text(
            "\u0e16\u0e49\u0e32\u0e04\u0e38\u0e13\u0e15\u0e49\u0e2d\u0e07\u0e01\u0e32\u0e23 \u0e1c\u0e21\u0e17\u0e33\u0e44\u0e14\u0e49 3 \u0e41\u0e1a\u0e1a: 1) \u0e17\u0e32\u0e07\u0e01\u0e32\u0e23\u0e21\u0e32\u0e15\u0e23\u0e10\u0e32\u0e19 2) \u0e17\u0e32\u0e07\u0e01\u0e32\u0e23\u0e21\u0e32\u0e01 3) \u0e17\u0e32\u0e07\u0e01\u0e32\u0e23\u0e41\u0e15\u0e48\u0e40\u0e1b\u0e47\u0e19\u0e21\u0e34\u0e15\u0e23 \u0e40\u0e25\u0e37\u0e2d\u0e01\u0e2b\u0e19\u0e36\u0e48\u0e07\u0e41\u0e1a\u0e1a"
        )
        == "\u0e16\u0e49\u0e32\u0e04\u0e38\u0e13\u0e15\u0e49\u0e2d\u0e07\u0e01\u0e32\u0e23 \u0e1c\u0e21\u0e17\u0e33\u0e44\u0e14\u0e49 3 \u0e41\u0e1a\u0e1a: 1) \u0e17\u0e32\u0e07\u0e01\u0e32\u0e23\u0e21\u0e32\u0e15\u0e23\u0e10\u0e32\u0e19 2) \u0e17\u0e32\u0e07\u0e01\u0e32\u0e23\u0e21\u0e32\u0e01 3) \u0e17\u0e32\u0e07\u0e01\u0e32\u0e23\u0e41\u0e15\u0e48\u0e40\u0e1b\u0e47\u0e19\u0e21\u0e34\u0e15\u0e23 \u0e40\u0e25\u0e37\u0e2d\u0e01\u0e2b\u0e19\u0e36\u0e48\u0e07\u0e41\u0e1a\u0e1a"
    )


def test_extract_user_supplied_option_prompt_text_ignores_explicit_pick_for_me_requests():
    assert (
        message_runtime_module._extract_user_supplied_option_prompt_text(
            "Kalau mau, aku bisa kasih 3 opsi: 1) ringkas 2) detail 3) tabel. Menurutmu pilih yang mana?"
        )
        is None
    )


def test_infer_recent_assistant_option_prompt_from_history_prefers_latest_choice_prompt():
    history = [
        {"role": "assistant", "content": "Ini jawaban biasa."},
        {
            "role": "assistant",
            "content": "Siap, aku tunggu pilihanmu. Mau yang 1) ringkas, 2) detail, atau 3) tabel?",
        },
    ]

    assert (
        message_runtime_module._infer_recent_assistant_option_prompt_from_history(history)
        == "Siap, aku tunggu pilihanmu. Mau yang 1) ringkas, 2) detail, atau 3) tabel?"
    )


def test_extract_option_selection_reference_supports_numeric_and_ordinal_followups():
    assert message_runtime_module._extract_option_selection_reference("2") == "2"
    assert message_runtime_module._extract_option_selection_reference("nomor 3") == "3"
    assert message_runtime_module._extract_option_selection_reference("yang ketiga gimana") == "3"
    assert message_runtime_module._extract_option_selection_reference("the second one") == "2"
    assert (
        message_runtime_module._extract_option_selection_reference(
            "\u7b2c\u4e8c\u4e2a\u662f\u4ec0\u4e48\uff1f\u7b80\u77ed\u56de\u7b54\u3002"
        )
        == "2"
    )
    assert message_runtime_module._extract_option_selection_reference("\u7b2c\u4e8c\u4e2a") == "2"
    assert message_runtime_module._extract_option_selection_reference("2\u756a") == "2"
    assert message_runtime_module._extract_option_selection_reference("\u0e02\u0e49\u0e2d 2") == "2"
    assert message_runtime_module._extract_option_selection_reference("yang formal gimana") is None
    assert (
        message_runtime_module._extract_option_selection_reference(
            "\u0e02\u0e49\u0e2d\u0e17\u0e35\u0e48\u0e2a\u0e2d\u0e07\u0e04\u0e37\u0e2d\u0e2d\u0e30\u0e44\u0e23 \u0e15\u0e2d\u0e1a\u0e2a\u0e31\u0e49\u0e19\u0e46"
        )
        == "2"
    )


def test_contextual_followup_request_supports_option_ordinal_references():
    assert message_runtime_module._looks_like_contextual_followup_request("yang ketiga gimana")
    assert message_runtime_module._looks_like_contextual_followup_request("nomor 3")
    assert message_runtime_module._looks_like_contextual_followup_request("the second one")
    assert message_runtime_module._looks_like_contextual_followup_request(
        "\u7b2c\u4e8c\u4e2a\u662f\u4ec0\u4e48\uff1f\u7b80\u77ed\u56de\u7b54\u3002"
    )
    assert message_runtime_module._looks_like_contextual_followup_request("\u7b2c\u4e8c\u4e2a")
    assert message_runtime_module._looks_like_contextual_followup_request("2\u756a")
    assert message_runtime_module._looks_like_contextual_followup_request("\u0e02\u0e49\u0e2d 2")
    assert message_runtime_module._looks_like_contextual_followup_request(
        "\u0e02\u0e49\u0e2d\u0e17\u0e35\u0e48\u0e2a\u0e2d\u0e07\u0e04\u0e37\u0e2d\u0e2d\u0e30\u0e44\u0e23 \u0e15\u0e2d\u0e1a\u0e2a\u0e31\u0e49\u0e19\u0e46"
    )
    assert message_runtime_module._looks_like_contextual_followup_request("maksudnya apa itu") is False
    assert message_runtime_module._looks_like_contextual_followup_request("trend nya naik?") is False


def test_answer_reference_followup_only_latches_explicit_answer_item_references():
    assert message_runtime_module._looks_like_answer_reference_followup("yang kedua")
    assert message_runtime_module._looks_like_answer_reference_followup("yang ketiga gimana")
    assert message_runtime_module._looks_like_answer_reference_followup(
        "\u7b2c\u4e8c\u4e2a\u662f\u4ec0\u4e48\uff1f\u7b80\u77ed\u56de\u7b54\u3002"
    )
    assert message_runtime_module._looks_like_answer_reference_followup(
        "\u0e02\u0e49\u0e2d\u0e17\u0e35\u0e48\u0e2a\u0e2d\u0e07\u0e04\u0e37\u0e2d\u0e2d\u0e30\u0e44\u0e23 \u0e15\u0e2d\u0e1a\u0e2a\u0e31\u0e49\u0e19\u0e46"
    )
    assert message_runtime_module._looks_like_answer_reference_followup("coba ulang versi singkat") is False
    assert message_runtime_module._looks_like_answer_reference_followup("ulang dari awal") is False
    assert message_runtime_module._looks_like_answer_reference_followup("maksudnya apa itu") is False
    assert message_runtime_module._looks_like_answer_reference_followup("\u518d\u7b80\u77ed\u4e00\u70b9") is False
    assert message_runtime_module._looks_like_answer_reference_followup("\u8fd9\u662f\u4ec0\u4e48\u610f\u601d") is False
    assert message_runtime_module._looks_like_answer_reference_followup("\u3082\u3063\u3068\u77ed\u304f") is False
    assert message_runtime_module._looks_like_answer_reference_followup("\u305d\u308c\u3069\u3046\u3044\u3046\u610f\u5473") is False
    assert message_runtime_module._looks_like_answer_reference_followup("\u0e2a\u0e31\u0e49\u0e19\u0e01\u0e27\u0e48\u0e32\u0e19\u0e35\u0e49") is False
    assert message_runtime_module._looks_like_answer_reference_followup("\u0e2b\u0e21\u0e32\u0e22\u0e04\u0e27\u0e32\u0e21\u0e27\u0e48\u0e32\u0e44\u0e07") is False
    assert message_runtime_module._looks_like_answer_reference_followup("lanjut yang tadi") is False


def test_non_action_meta_feedback_detects_short_hostile_feedback():
    assert message_runtime_module._looks_like_non_action_meta_feedback("tolol")
    assert message_runtime_module._looks_like_non_action_meta_feedback("goblok jawab apa loh")
    assert message_runtime_module._looks_like_non_action_meta_feedback("cek lagi dong") is False

def test_filesystem_location_query_helper_supports_multilingual_phrases():
    assert message_runtime_module._looks_like_filesystem_location_query("lokasimu sekarang dimana")
    assert message_runtime_module._looks_like_filesystem_location_query("\u4f60\u73b0\u5728\u5728\u54ea\u4e2a\u6587\u4ef6\u5939")
    assert message_runtime_module._looks_like_filesystem_location_query("\u4eca\u3069\u306e\u30d5\u30a9\u30eb\u30c0\u306b\u3044\u308b")
    assert message_runtime_module._looks_like_filesystem_location_query("\u0e15\u0e2d\u0e19\u0e19\u0e35\u0e49\u0e04\u0e38\u0e13\u0e2d\u0e22\u0e39\u0e48\u0e42\u0e1f\u0e25\u0e40\u0e14\u0e2d\u0e23\u0e4c\u0e44\u0e2b\u0e19")
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
    assert msg.metadata.get("turn_category") == "chat"


@pytest.mark.asyncio
async def test_process_message_memory_commit_followup_bypasses_fast_simple_context():
    routed_context = MagicMock()
    routed_context.build_messages.return_value = [
        {"role": "system", "content": "# Memory\n## Long-term Memory\nUse WIB (UTC+7)."},
        {"role": "assistant", "content": "Say 'save it' and I'll commit it to memory."},
        {"role": "user", "content": "save it"},
    ]
    routed_context.skills = SimpleNamespace(
        match_skills=lambda _msg, _profile: [],
    )

    history = [
        {"role": "assistant", "content": "Say 'save it' and I'll commit it to memory."},
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
    _run_simple_response=AsyncMock(return_value="Done, I saved it."),
    _run_agent_loop=AsyncMock(return_value="ok"),
    _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="Done, I saved it.")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(channel="telegram", sender_id="u1", chat_id="chat-1", content="save it")
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
