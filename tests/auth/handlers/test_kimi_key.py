"""Tests for Kimi API Key handler."""
import pytest
from unittest.mock import patch


def test_kimi_key_handler_exists():
    """KimiKeyHandler class should exist."""
    from kabot.auth.handlers.kimi_key import KimiKeyHandler
    assert KimiKeyHandler is not None


def test_kimi_key_handler_has_name():
    """KimiKeyHandler should have name property."""
    from kabot.auth.handlers.kimi_key import KimiKeyHandler
    handler = KimiKeyHandler()
    assert handler.name == "Kimi (API Key)"


@patch('kabot.auth.handlers.kimi_key.secure_input')
def test_authenticate_returns_kimi_provider(mock_input):
    """authenticate() should return kimi provider structure."""
    with patch.dict('os.environ', {}, clear=True):
        mock_input.return_value = "kimi-test-key-123"

        from kabot.auth.handlers.kimi_key import KimiKeyHandler
        handler = KimiKeyHandler()
        result = handler.authenticate()

        assert result == {
            "providers": {
                "kimi": {
                    "api_key": "kimi-test-key-123",
                    "api_base": "https://api.moonshot.cn/v1"
                }
            }
        }
