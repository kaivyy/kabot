"""Tests for OAuth flow utilities."""
from unittest.mock import MagicMock, patch

from kabot.auth.utils import run_oauth_flow


@patch('kabot.auth.utils.is_vps')
@patch('kabot.auth.utils.secure_input')
def test_run_oauth_flow_vps(mock_input, mock_is_vps):
    """run_oauth_flow in VPS mode should prompt for manual input."""
    mock_is_vps.return_value = True
    mock_input.return_value = "manual-token-123"

    result = run_oauth_flow("https://example.com/auth")

    assert result == "manual-token-123"
    mock_input.assert_called_once()


@patch('kabot.auth.utils.is_vps')
@patch('kabot.auth.utils.webbrowser.open')
@patch('kabot.auth.utils.OAuthCallbackServer')
def test_run_oauth_flow_local(mock_server_cls, mock_browser, mock_is_vps):
    """run_oauth_flow in local mode should open browser and start server."""
    mock_is_vps.return_value = False

    # Mock server instance
    mock_server = MagicMock()
    mock_server.get_auth_url.return_value = "https://example.com/auth?full=1"

    # Create an actual coroutine for start_and_wait
    async def mock_start_and_wait():
        return "auto-token-456"

    mock_server.start_and_wait = mock_start_and_wait
    mock_server_cls.return_value = mock_server

    result = run_oauth_flow("https://example.com/auth")

    assert result == "auto-token-456"
    mock_browser.assert_called_once_with("https://example.com/auth?full=1")
