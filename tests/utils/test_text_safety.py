from kabot.utils.text_safety import ensure_utf8_text


def test_ensure_utf8_text_preserves_valid_text():
    value = "hello ✅"
    out = ensure_utf8_text(value)

    assert out == value
    out.encode("utf-8")


def test_ensure_utf8_text_replaces_unpaired_surrogate():
    out = ensure_utf8_text("bad \ud83d text")

    out.encode("utf-8")
    assert "\ud83d" not in out
