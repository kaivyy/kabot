"""OAuth token auto-refresh service."""

import time
from typing import Optional

import httpx
from loguru import logger

from kabot.config.schema import AuthProfile

# Provider-specific token endpoints
_TOKEN_ENDPOINTS = {
    "openai": "https://auth.openai.com/oauth/token",
    "openai-codex": "https://auth.openai.com/oauth/token",
    "openai_codex": "https://auth.openai.com/oauth/token",
    "google": "https://oauth2.googleapis.com/token",
    "gemini": "https://oauth2.googleapis.com/token",
    "minimax": "https://api.minimax.chat/v1/oauth/token",
    "dashscope": "https://auth.aliyun.com/oauth/token",
    "qwen-portal": "https://chat.qwen.ai/api/v1/oauth2/token",
    "qwen_portal": "https://chat.qwen.ai/api/v1/oauth2/token",
}

# Buffer: refresh 5 minutes before actual expiry
REFRESH_BUFFER_MS = 5 * 60 * 1000


async def _call_token_endpoint(url: str, data: dict) -> dict:
    """Call an OAuth token endpoint."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            url, data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()


class TokenRefreshService:
    """Automatically refresh expired OAuth tokens with file locking for multi-process safety."""

    async def refresh(
        self, provider: str, profile: AuthProfile
    ) -> Optional[AuthProfile]:
        """Refresh an expired token. Returns updated profile or None if no refresh needed."""
        # API keys never need refresh
        if profile.token_type != "oauth" or not profile.refresh_token:
            return None

        # Check if token is expired or close to expiry
        if profile.expires_at and not self._needs_refresh(profile.expires_at):
            return None

        # Cross-process file locking to prevent race conditions in multi-instance deployments
        from pathlib import Path

        from filelock import FileLock

        lock_path = Path.home() / ".kabot" / "auth.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        lock = FileLock(str(lock_path), timeout=10)

        try:
            # Acquire file lock (blocking, but with timeout)
            with lock:
                # Double-check after acquiring lock (another process might have refreshed)
                if profile.expires_at and not self._needs_refresh(profile.expires_at):
                    return None

                return await self._do_refresh(provider, profile)
        except Exception as e:
            logger.warning(f"Could not acquire auth lock or refresh failed: {e}")
            # Best-effort fallback: refresh without lock if lock cannot be acquired.
            return await self._do_refresh(provider, profile)

    def _needs_refresh(self, expires_at: int) -> bool:
        """Check if token needs refresh (expired or within buffer)."""
        now_ms = int(time.time() * 1000)
        return now_ms >= (expires_at - REFRESH_BUFFER_MS)

    async def _do_refresh(
        self, provider: str, profile: AuthProfile
    ) -> Optional[AuthProfile]:
        """Execute the token refresh."""
        token_url = _TOKEN_ENDPOINTS.get(provider)
        if not token_url:
            logger.warning(f"No token endpoint for provider: {provider}")
            return None

        try:
            data = {
                "grant_type": "refresh_token",
                "refresh_token": profile.refresh_token,
            }
            if profile.client_id:
                data["client_id"] = profile.client_id
            if profile.client_secret:
                data["client_secret"] = profile.client_secret

            result = await _call_token_endpoint(token_url, data)

            now_ms = int(time.time() * 1000)
            expires_in = result.get("expires_in", 3600)

            # Return updated profile
            updated = profile.model_copy()
            updated.oauth_token = result["access_token"]
            updated.refresh_token = result.get("refresh_token", profile.refresh_token)
            updated.expires_at = now_ms + (expires_in * 1000)

            logger.info(f"Refreshed OAuth token for {provider} (expires in {expires_in}s)")
            return updated

        except Exception as e:
            logger.error(f"OAuth refresh failed for {provider}: {e}")
            return None
