from kabot.cli.commands import _terminal_safe


def test_terminal_safe_replaces_unencodable_characters_for_cp1252():
    text = "Halo 👋 — chat works ✅"
    safe = _terminal_safe(text, encoding="cp1252")
    assert "?" in safe


def test_terminal_safe_keeps_ascii_unchanged():
    text = "hello test openai codex"
    safe = _terminal_safe(text, encoding="cp1252")
    assert safe == text
