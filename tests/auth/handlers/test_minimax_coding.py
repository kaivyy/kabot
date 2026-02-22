"""Tests for MiniMax Coding Plan handler."""
from unittest.mock import patch


def test_minimax_coding_handler_exists():
    """MiniMaxCodingHandler class should exist."""
    from kabot.auth.handlers.minimax_coding import MiniMaxCodingHandler
    assert MiniMaxCodingHandler is not None


def test_minimax_coding_handler_has_name():
    """MiniMaxCodingHandler should have name property."""
    from kabot.auth.handlers.minimax_coding import MiniMaxCodingHandler
    handler = MiniMaxCodingHandler()
    assert handler.name == "MiniMax Coding Plan (Subscription)"


@patch('kabot.auth.handlers.minimax_coding.secure_input')
def test_authenticate_includes_subscription_type(mock_input):
    """authenticate() should include subscription_type field."""
    with patch.dict('os.environ', {}, clear=True):
        mock_input.return_value = "minimax-coding-key-123"

        from kabot.auth.handlers.minimax_coding import MiniMaxCodingHandler
        handler = MiniMaxCodingHandler()
        result = handler.authenticate()

        assert result["providers"]["minimax"]["subscription_type"] == "coding_plan"
