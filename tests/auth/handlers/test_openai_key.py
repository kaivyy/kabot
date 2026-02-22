"""Tests for OpenAI API Key handler."""
from unittest.mock import patch


def test_openai_key_handler_exists():
    """OpenAIKeyHandler class should exist."""
    from kabot.auth.handlers.openai_key import OpenAIKeyHandler
    assert OpenAIKeyHandler is not None


def test_openai_key_handler_has_name():
    """OpenAIKeyHandler should have name property."""
    from kabot.auth.handlers.openai_key import OpenAIKeyHandler
    handler = OpenAIKeyHandler()
    assert handler.name == "OpenAI (API Key)"


def test_openai_key_handler_inherits_base():
    """OpenAIKeyHandler should inherit from AuthHandler."""
    from kabot.auth.handlers.base import AuthHandler
    from kabot.auth.handlers.openai_key import OpenAIKeyHandler
    assert issubclass(OpenAIKeyHandler, AuthHandler)


@patch('kabot.auth.handlers.openai_key.secure_input')
def test_authenticate_with_manual_input(mock_input):
    """authenticate() should return api_key from manual input."""
    with patch.dict('os.environ', {}, clear=True):
        mock_input.return_value = "sk-test123456789"

        from kabot.auth.handlers.openai_key import OpenAIKeyHandler
        handler = OpenAIKeyHandler()
        result = handler.authenticate()

        assert result == {"providers": {"openai": {"api_key": "sk-test123456789"}}}


@patch('kabot.auth.handlers.openai_key.Prompt.ask')
def test_authenticate_uses_env_var_when_accepted(mock_prompt):
    """authenticate() should use env var when user accepts."""
    with patch.dict('os.environ', {"OPENAI_API_KEY": "sk-env-key-12345"}):
        mock_prompt.return_value = "y"

        from kabot.auth.handlers.openai_key import OpenAIKeyHandler
        handler = OpenAIKeyHandler()
        result = handler.authenticate()

        assert result == {"providers": {"openai": {"api_key": "sk-env-key-12345"}}}
