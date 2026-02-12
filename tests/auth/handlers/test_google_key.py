"""Tests for Google API Key handler."""
import pytest
from unittest.mock import patch


def test_google_key_handler_exists():
    """GoogleKeyHandler class should exist."""
    from kabot.auth.handlers.google_key import GoogleKeyHandler
    assert GoogleKeyHandler is not None


def test_google_key_handler_has_name():
    """GoogleKeyHandler should have name property."""
    from kabot.auth.handlers.google_key import GoogleKeyHandler
    handler = GoogleKeyHandler()
    assert handler.name == "Google Gemini (API Key)"


@patch('kabot.auth.handlers.google_key.secure_input')
def test_authenticate_returns_gemini_provider(mock_input):
    """authenticate() should return 'gemini' provider key."""
    with patch.dict('os.environ', {}, clear=True):
        mock_input.return_value = "AIza-test123"

        from kabot.auth.handlers.google_key import GoogleKeyHandler
        handler = GoogleKeyHandler()
        result = handler.authenticate()

        # Note: Uses 'gemini' as provider key for config compatibility
        assert result == {"providers": {"gemini": {"api_key": "AIza-test123"}}}
