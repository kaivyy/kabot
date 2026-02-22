"""Tests for model validator."""


def test_validate_format_valid():
    from kabot.cli.model_validator import validate_format
    assert validate_format("openai/gpt-4o")


def test_validate_format_invalid():
    from kabot.cli.model_validator import validate_format
    assert not validate_format("gpt-4o")


def test_resolve_alias():
    from kabot.cli.model_validator import resolve_alias
    assert resolve_alias("codex") == "openai/gpt-5.1-codex"
    assert resolve_alias("sonnet") == "anthropic/claude-3-5-sonnet-20241022"
    assert resolve_alias("invalid") is None
