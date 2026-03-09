from kabot.utils.text_safety import ensure_utf8_text, repair_common_mojibake_text


def test_ensure_utf8_text_preserves_valid_text():
    value = "hello ✅"
    out = ensure_utf8_text(value)

    assert out == value
    out.encode("utf-8")


def test_ensure_utf8_text_replaces_unpaired_surrogate():
    out = ensure_utf8_text("bad \ud83d text")

    out.encode("utf-8")
    assert "\ud83d" not in out


def test_repair_common_mojibake_text_restores_utf8_garbled_prompt():
    original = "请用 weather 技能处理这个请求。"
    garbled = original.encode("utf-8").decode("latin1")

    repaired = repair_common_mojibake_text(garbled)

    assert repaired == original


def test_repair_common_mojibake_text_keeps_clean_unicode_unchanged():
    original = "デスクトップのbotフォルダを見せて"

    repaired = repair_common_mojibake_text(original)

    assert repaired == original
