"""Tests for Kimi Code subscription handler."""
from unittest.mock import patch


def test_kimi_code_handler_exists():
    """KimiCodeHandler class should exist."""
    from kabot.auth.handlers.kimi_code import KimiCodeHandler
    assert KimiCodeHandler is not None


def test_kimi_code_handler_has_name():
    """KimiCodeHandler should have name property."""
    from kabot.auth.handlers.kimi_code import KimiCodeHandler
    handler = KimiCodeHandler()
    assert handler.name == "Kimi Code (Subscription)"


@patch('kabot.auth.handlers.kimi_code.secure_input')
def test_authenticate_uses_code_api_base(mock_input):
    """authenticate() should use Kimi Code specific API base."""
    with patch.dict('os.environ', {}, clear=True):
        mock_input.return_value = "kimi-code-key-123"

        from kabot.auth.handlers.kimi_code import KimiCodeHandler
        handler = KimiCodeHandler()
        result = handler.authenticate()

        # Kimi Code uses different API base for coding features
        assert result["providers"]["moonshot"]["api_base"] == "https://api.moonshot.cn/v1"
        assert result["providers"]["moonshot"]["subscription_type"] == "kimi_code"
