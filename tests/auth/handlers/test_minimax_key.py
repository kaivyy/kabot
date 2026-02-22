"""Tests for MiniMax API Key handler."""
from unittest.mock import patch


def test_minimax_key_handler_exists():
    """MiniMaxKeyHandler class should exist."""
    from kabot.auth.handlers.minimax_key import MiniMaxKeyHandler
    assert MiniMaxKeyHandler is not None


def test_minimax_key_handler_has_name():
    """MiniMaxKeyHandler should have name property."""
    from kabot.auth.handlers.minimax_key import MiniMaxKeyHandler
    handler = MiniMaxKeyHandler()
    assert handler.name == "MiniMax (API Key)"


@patch('kabot.auth.handlers.minimax_key.secure_input')
def test_authenticate_returns_minimax_provider(mock_input):
    """authenticate() should return minimax provider structure."""
    with patch.dict('os.environ', {}, clear=True):
        mock_input.return_value = "minimax-test-key-123"

        from kabot.auth.handlers.minimax_key import MiniMaxKeyHandler
        handler = MiniMaxKeyHandler()
        result = handler.authenticate()

        assert result == {
            "providers": {
                "minimax": {
                    "api_key": "minimax-test-key-123",
                    "api_base": "https://api.minimax.chat/v1"
                }
            }
        }
