# tests/auth/test_refresh.py
import time
from unittest.mock import AsyncMock, patch

import pytest

from kabot.auth.refresh import TokenRefreshService
from kabot.config.schema import AuthProfile


@pytest.mark.asyncio
async def test_refresh_expired_openai_token():
    profile = AuthProfile(
        name="test",
        oauth_token="expired_token",
        refresh_token="valid_refresh",
        expires_at=int(time.time() * 1000) - 60_000,  # Expired
        token_type="oauth",
        client_id="app_EMoamEEZ73f0CkXaXp7hrann",
    )

    mock_response = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "expires_in": 3600,
    }

    service = TokenRefreshService()
    with patch("kabot.auth.refresh._call_token_endpoint", new_callable=AsyncMock, return_value=mock_response):
        result = await service.refresh("openai", profile)

    assert result is not None
    assert result.oauth_token == "new_access_token"
    assert result.refresh_token == "new_refresh_token"
    assert result.expires_at > int(time.time() * 1000)

@pytest.mark.asyncio
async def test_no_refresh_for_valid_token():
    profile = AuthProfile(
        name="valid",
        oauth_token="still_good",
        expires_at=int(time.time() * 1000) + 3600_000,
        token_type="oauth",
    )
    service = TokenRefreshService()
    result = await service.refresh("openai", profile)
    assert result is None  # No refresh needed

@pytest.mark.asyncio
async def test_no_refresh_for_api_key():
    profile = AuthProfile(name="key", api_key="sk-abc")
    service = TokenRefreshService()
    result = await service.refresh("openai", profile)
    assert result is None


@pytest.mark.asyncio
async def test_do_refresh_supports_openai_codex_provider_alias():
    profile = AuthProfile(
        name="codex",
        oauth_token="expired_token",
        refresh_token="valid_refresh",
        expires_at=int(time.time() * 1000) - 60_000,
        token_type="oauth",
        client_id="app_EMoamEEZ73f0CkXaXp7hrann",
    )

    mock_response = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "expires_in": 3600,
    }

    service = TokenRefreshService()
    with patch("kabot.auth.refresh._call_token_endpoint", new_callable=AsyncMock, return_value=mock_response) as mock_call:
        result = await service._do_refresh("openai-codex", profile)

    assert result is not None
    assert result.oauth_token == "new_access_token"
    assert result.refresh_token == "new_refresh_token"
    assert result.expires_at > int(time.time() * 1000)
    mock_call.assert_awaited_once()


@pytest.mark.asyncio
async def test_do_refresh_supports_qwen_portal_provider_alias():
    profile = AuthProfile(
        name="qwen",
        oauth_token="expired_token",
        refresh_token="valid_refresh",
        expires_at=int(time.time() * 1000) - 60_000,
        token_type="oauth",
        client_id="f0304373b74a44d2b584a3fb70ca9e56",
    )

    mock_response = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "expires_in": 3600,
    }

    service = TokenRefreshService()
    with patch("kabot.auth.refresh._call_token_endpoint", new_callable=AsyncMock, return_value=mock_response) as mock_call:
        result = await service._do_refresh("qwen-portal", profile)

    assert result is not None
    assert result.oauth_token == "new_access_token"
    assert result.refresh_token == "new_refresh_token"
    assert result.expires_at > int(time.time() * 1000)
    mock_call.assert_awaited_once()


@pytest.mark.asyncio
async def test_do_refresh_supports_gemini_provider_name():
    profile = AuthProfile(
        name="gemini",
        oauth_token="expired_token",
        refresh_token="valid_refresh",
        expires_at=int(time.time() * 1000) - 60_000,
        token_type="oauth",
        client_id="google-client",
    )

    mock_response = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "expires_in": 3600,
    }

    service = TokenRefreshService()
    with patch("kabot.auth.refresh._call_token_endpoint", new_callable=AsyncMock, return_value=mock_response) as mock_call:
        result = await service._do_refresh("gemini", profile)

    assert result is not None
    assert result.oauth_token == "new_access_token"
    assert result.refresh_token == "new_refresh_token"
    assert result.expires_at > int(time.time() * 1000)
    mock_call.assert_awaited_once()


@pytest.mark.asyncio
async def test_do_refresh_includes_client_secret_when_present():
    profile = AuthProfile(
        name="google-oauth",
        oauth_token="expired_token",
        refresh_token="valid_refresh",
        expires_at=int(time.time() * 1000) - 60_000,
        token_type="oauth",
        client_id="google-client",
        client_secret="google-secret",
    )

    captured: dict = {}

    async def _fake_call(url: str, data: dict):
        captured["url"] = url
        captured["data"] = data
        return {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
        }

    service = TokenRefreshService()
    with patch("kabot.auth.refresh._call_token_endpoint", new_callable=AsyncMock, side_effect=_fake_call):
        result = await service._do_refresh("gemini", profile)

    assert result is not None
    assert captured["data"]["client_secret"] == "google-secret"
