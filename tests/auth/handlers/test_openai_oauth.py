"""Tests for OpenAI OAuth handler."""
import pytest
from unittest.mock import patch


def test_openai_oauth_handler_exists():
    """OpenAIOAuthHandler class should exist."""
    from kabot.auth.handlers.openai_oauth import OpenAIOAuthHandler
    assert OpenAIOAuthHandler is not None


def test_openai_oauth_handler_has_name():
    """OpenAIOAuthHandler should have name property."""
    from kabot.auth.handlers.openai_oauth import OpenAIOAuthHandler
    handler = OpenAIOAuthHandler()
    assert handler.name == "OpenAI (OAuth)"


@patch('kabot.auth.handlers.openai_oauth.run_oauth_flow')
def test_authenticate_returns_oauth_token(mock_flow):
    """authenticate() should return oauth_token structure."""
    mock_flow.return_value = "openai-test-token-123"

    from kabot.auth.handlers.openai_oauth import OpenAIOAuthHandler
    handler = OpenAIOAuthHandler()
    result = handler.authenticate()

    assert result == {"providers": {"openai": {"oauth_token": "openai-test-token-123"}}}
