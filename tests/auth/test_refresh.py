# tests/auth/test_refresh.py
import pytest
import time
from unittest.mock import AsyncMock, patch
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
