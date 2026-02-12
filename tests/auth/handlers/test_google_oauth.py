"""Tests for Google OAuth handler."""
import pytest
from unittest.mock import patch


def test_google_oauth_handler_exists():
    """GoogleOAuthHandler class should exist."""
    from kabot.auth.handlers.google_oauth import GoogleOAuthHandler
    assert GoogleOAuthHandler is not None


def test_google_oauth_handler_has_name():
    """GoogleOAuthHandler should have name property."""
    from kabot.auth.handlers.google_oauth import GoogleOAuthHandler
    handler = GoogleOAuthHandler()
    assert handler.name == "Google Gemini (OAuth)"


@patch('kabot.auth.handlers.google_oauth.run_oauth_flow')
def test_authenticate_returns_gemini_oauth_token(mock_flow):
    """authenticate() should return gemini provider with oauth_token."""
    mock_flow.return_value = "google-test-token-123"

    from kabot.auth.handlers.google_oauth import GoogleOAuthHandler
    handler = GoogleOAuthHandler()
    result = handler.authenticate()

    # Note: Uses 'gemini' as provider key for config compatibility
    assert result == {"providers": {"gemini": {"oauth_token": "google-test-token-123"}}}
