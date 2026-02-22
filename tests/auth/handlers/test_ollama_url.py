"""Tests for Ollama URL handler."""
from unittest.mock import patch


def test_ollama_url_handler_exists():
    """OllamaURLHandler class should exist."""
    from kabot.auth.handlers.ollama_url import OllamaURLHandler
    assert OllamaURLHandler is not None


def test_ollama_url_handler_has_name():
    """OllamaURLHandler should have name property."""
    from kabot.auth.handlers.ollama_url import OllamaURLHandler
    handler = OllamaURLHandler()
    assert handler.name == "Ollama (Local)"


@patch('kabot.auth.handlers.ollama_url.Prompt.ask')
def test_authenticate_returns_vllm_provider(mock_prompt):
    """authenticate() should return 'vllm' provider with api_base."""
    with patch.dict('os.environ', {}, clear=True):
        mock_prompt.return_value = "http://localhost:11434"

        from kabot.auth.handlers.ollama_url import OllamaURLHandler
        handler = OllamaURLHandler()
        result = handler.authenticate()

        assert result == {
            "providers": {
                "vllm": {
                    "api_base": "http://localhost:11434",
                    "api_key": "ollama"
                }
            }
        }
