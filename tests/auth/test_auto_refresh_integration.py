# tests/auth/test_auto_refresh_integration.py
import time
from unittest.mock import AsyncMock, patch

import pytest

from kabot.config.schema import AuthProfile, Config, ProviderConfig


@pytest.mark.asyncio
async def test_get_api_key_auto_refreshes():
    """get_api_key_async should auto-refresh expired OAuth tokens."""
    config = Config()
    config.providers.openai = ProviderConfig(
        profiles={
            "default": AuthProfile(
                name="default",
                oauth_token="expired",
                refresh_token="valid_refresh",
                expires_at=int(time.time() * 1000) - 60_000,
                token_type="oauth",
                client_id="app_test",
            )
        },
        active_profile="default"
    )

    mock_refresh = AsyncMock(return_value=AuthProfile(
        name="default",
        oauth_token="new_token",
        refresh_token="new_refresh",
        expires_at=int(time.time() * 1000) + 3600_000,
        token_type="oauth",
    ))

    with patch("kabot.auth.refresh.TokenRefreshService.refresh", mock_refresh):
        key = await config.get_api_key_async("openai/gpt-4o")

    assert key == "new_token"
    mock_refresh.assert_called_once()

@pytest.mark.asyncio
async def test_get_api_key_async_no_refresh_for_valid():
    """get_api_key_async should not refresh valid tokens."""
    config = Config()
    config.providers.openai = ProviderConfig(
        profiles={
            "default": AuthProfile(
                name="default",
                oauth_token="valid_token",
                expires_at=int(time.time() * 1000) + 3600_000,
                token_type="oauth",
            )
        },
        active_profile="default"
    )

    key = await config.get_api_key_async("openai/gpt-4o")
    assert key == "valid_token"
