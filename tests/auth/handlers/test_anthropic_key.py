"""Tests for Anthropic API Key handler."""
import pytest
from unittest.mock import patch


def test_anthropic_key_handler_exists():
    """AnthropicKeyHandler class should exist."""
    from kabot.auth.handlers.anthropic_key import AnthropicKeyHandler
    assert AnthropicKeyHandler is not None


def test_anthropic_key_handler_has_name():
    """AnthropicKeyHandler should have name property."""
    from kabot.auth.handlers.anthropic_key import AnthropicKeyHandler
    handler = AnthropicKeyHandler()
    assert handler.name == "Anthropic (API Key)"


@patch('kabot.auth.handlers.anthropic_key.secure_input')
def test_authenticate_returns_correct_structure(mock_input):
    """authenticate() should return correct provider structure."""
    with patch.dict('os.environ', {}, clear=True):
        mock_input.return_value = "sk-ant-test123"

        from kabot.auth.handlers.anthropic_key import AnthropicKeyHandler
        handler = AnthropicKeyHandler()
        result = handler.authenticate()

        assert result == {"providers": {"anthropic": {"api_key": "sk-ant-test123"}}}
