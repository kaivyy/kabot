"""Tests for OAuth callback server."""

import pytest

from kabot.auth.oauth_callback import OAuthCallbackServer


def test_server_initialization():
    """Server should initialize with default or specified port."""
    server = OAuthCallbackServer(port=1234)
    assert server.port == 1234
    assert server.state is not None
    assert len(server.state) > 20


def test_get_auth_url():
    """get_auth_url should build correct URL with state and redirect_uri."""
    server = OAuthCallbackServer(port=8765)
    base_url = "https://auth.example.com/authorize"
    params = {"client_id": "test-client", "scope": "test"}

    url = server.get_auth_url(base_url, params)

    assert base_url in url
    assert "state=" in url
    assert server.state in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8765%2Fcallback" in url


@pytest.mark.asyncio
async def test_handle_callback_success():
    """handle_callback should extract code/token and return success HTML."""
    server = OAuthCallbackServer()

    # Mock request
    from unittest.mock import MagicMock
    request = MagicMock()
    request.query = {
        "state": server.state,
        "code": "test-code-123"
    }

    response = await server.handle_callback(request)

    assert server.token == "test-code-123"
    assert response.status == 200
    assert "Authentication Successful" in response.text


@pytest.mark.asyncio
async def test_handle_callback_state_mismatch():
    """handle_callback should return 400 on state mismatch."""
    server = OAuthCallbackServer()

    from unittest.mock import MagicMock
    request = MagicMock()
    request.query = {
        "state": "wrong-state",
        "code": "test-code"
    }

    response = await server.handle_callback(request)

    assert response.status == 400
    assert "Invalid state" in response.text
    assert server.token is None
