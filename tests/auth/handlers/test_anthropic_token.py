"""Tests for Anthropic Setup Token handler."""
from unittest.mock import patch


def test_anthropic_token_handler_exists():
    """AnthropicTokenHandler class should exist."""
    from kabot.auth.handlers.anthropic_token import AnthropicTokenHandler
    assert AnthropicTokenHandler is not None


def test_anthropic_token_handler_has_name():
    """AnthropicTokenHandler should have name property."""
    from kabot.auth.handlers.anthropic_token import AnthropicTokenHandler
    handler = AnthropicTokenHandler()
    assert handler.name == "Anthropic (Setup Token)"


@patch('kabot.auth.handlers.anthropic_token.secure_input')
def test_authenticate_returns_anthropic_token(mock_input):
    """authenticate() should return anthropic provider with setup_token."""
    with patch.dict('os.environ', {}, clear=True):
        mock_input.return_value = "ant-setup-token-123"

        from kabot.auth.handlers.anthropic_token import AnthropicTokenHandler
        handler = AnthropicTokenHandler()
        result = handler.authenticate()

        assert result == {"providers": {"anthropic": {"setup_token": "ant-setup-token-123"}}}
