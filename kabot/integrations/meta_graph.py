"""Meta Graph API client."""

from __future__ import annotations

from typing import Any

import httpx


class MetaGraphClient:
    """Minimal async client for Meta Graph endpoints."""

    def __init__(
        self,
        access_token: str,
        api_base: str = "https://graph.facebook.com/v21.0",
        timeout: float = 30.0,
    ) -> None:
        self.access_token = (access_token or "").strip()
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout

    async def request(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send request to Meta Graph API and return JSON."""
        if not self.access_token:
            raise ValueError("Meta access token is missing")

        normalized = "/" + path.lstrip("/")

        # Threads endpoints use a different host and API version
        if "threads" in normalized:
            url = f"https://graph.threads.net/v1.0{normalized}"
            # Threads API requires access_token in the payload/query instead of just Auth header for some endpoints
            payload["access_token"] = self.access_token
        else:
            url = f"{self.api_base}{normalized}"

        headers = {"Authorization": f"Bearer {self.access_token}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if "threads" in normalized:
                # Threads requires application/x-www-form-urlencoded
                response = await client.request(method=method, url=url, data=payload)
            else:
                # Regular Meta API uses JSON
                response = await client.request(method=method, url=url, json=payload, headers=headers)

        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        if response.status_code >= 400:
            message = data.get("error", data)
            raise RuntimeError(f"Meta Graph API error ({response.status_code}): {message}")

        if isinstance(data, dict):
            return data

        return {"data": data}
