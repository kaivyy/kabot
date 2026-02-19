"""Tests for Google Gemini CLI OAuth handler."""

from kabot.auth.manager import AuthManager


def test_google_gemini_cli_handler_has_name():
    """GoogleGeminiCLIHandler should implement required name property."""
    from kabot.auth.handlers.google_gemini_cli import GoogleGeminiCLIHandler

    handler = GoogleGeminiCLIHandler()
    assert handler.name == "Google Gemini CLI OAuth"


def test_auth_manager_loads_google_gemini_cli_handler():
    """AuthManager should be able to instantiate google/gemini_cli handler."""
    manager = AuthManager()
    handler = manager._load_handler("google", "gemini_cli")
    assert handler.__class__.__name__ == "GoogleGeminiCLIHandler"
