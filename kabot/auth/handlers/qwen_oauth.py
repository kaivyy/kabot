"""Qwen Portal OAuth handler — device code flow.

Mirrors OpenClaw's extensions/qwen-portal-auth/oauth.ts.
Uses device code grant: user gets a code, opens URL in browser to approve,
Kabot polls the token endpoint until approved.
"""

import hashlib
import secrets
import time
import base64
import webbrowser
from typing import Dict, Any, Optional
from urllib.parse import urlencode

import httpx
from rich.console import Console
from rich.prompt import Prompt

from kabot.auth.handlers.base import AuthHandler

console = Console()

# ── OAuth constants (from OpenClaw qwen-portal-auth plugin) ────────────────
QWEN_CLIENT_ID = "f0304373b74a44d2b584a3fb70ca9e56"
QWEN_BASE_URL = "https://chat.qwen.ai"
QWEN_DEVICE_CODE_URL = f"{QWEN_BASE_URL}/api/v1/oauth2/device/code"
QWEN_TOKEN_URL = f"{QWEN_BASE_URL}/api/v1/oauth2/token"
QWEN_SCOPE = "openid profile email model.completion"
QWEN_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
QWEN_API_BASE = "https://portal.qwen.ai/v1"


# ── PKCE helper ─────────────────────────────────────────────────────────────

def _generate_pkce() -> tuple:
    """Generate PKCE verifier + S256 challenge."""
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


# ── Device code flow ────────────────────────────────────────────────────────

def _request_device_code(challenge: str) -> Dict[str, Any]:
    """Request a device code from Qwen's OAuth endpoint."""
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            QWEN_DEVICE_CODE_URL,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={
                "client_id": QWEN_CLIENT_ID,
                "scope": QWEN_SCOPE,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if not data.get("device_code") or not data.get("user_code"):
        raise RuntimeError(
            data.get("error", "Qwen device code request returned incomplete data")
        )
    return data


def _poll_token(device_code: str, verifier: str) -> Optional[Dict[str, Any]]:
    """Poll Qwen's token endpoint once. Returns token data or None if pending."""
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            QWEN_TOKEN_URL,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={
                "grant_type": QWEN_GRANT_TYPE,
                "client_id": QWEN_CLIENT_ID,
                "device_code": device_code,
                "code_verifier": verifier,
            },
        )

    if not resp.is_success:
        try:
            err = resp.json()
        except Exception:
            return None
        error_code = err.get("error", "")
        if error_code in ("authorization_pending", "slow_down"):
            return None
        raise RuntimeError(
            err.get("error_description", err.get("error", resp.text))
        )

    data = resp.json()
    if not data.get("access_token") or not data.get("refresh_token"):
        return None
    return data


# ── Handler ─────────────────────────────────────────────────────────────────

class QwenOAuthHandler(AuthHandler):
    """Handler for Qwen Portal OAuth (device code flow)."""

    @property
    def name(self) -> str:
        return "Qwen (OAuth)"

    def authenticate(self) -> Dict[str, Any]:
        console.print("\n[bold]Qwen Portal OAuth Setup[/bold]")
        console.print("This will authenticate via Qwen's device code flow.\n")

        # Generate PKCE
        verifier, challenge = _generate_pkce()

        # Request device code
        console.print("[dim]Requesting device code…[/dim]")
        try:
            device_data = _request_device_code(challenge)
        except Exception as exc:
            console.print(f"[red]✗ Failed to get device code: {exc}[/red]")
            return {}

        user_code = device_data["user_code"]
        verification_uri = device_data.get(
            "verification_uri_complete",
            device_data.get("verification_uri", ""),
        )
        device_code = device_data["device_code"]
        expires_in = device_data.get("expires_in", 300)
        poll_interval = device_data.get("interval", 2)

        # Show user code and verification URL
        console.print(f"\n[bold cyan]Your code: {user_code}[/bold cyan]")
        console.print(f"[bold]Open this URL to approve:[/bold]")
        console.print(f"[link={verification_uri}]{verification_uri}[/link]\n")

        # Try to open browser
        try:
            webbrowser.open(verification_uri)
            console.print("[green]→ Browser opened[/green]")
        except Exception:
            console.print("[yellow]Could not open browser. Please open the URL manually.[/yellow]")

        # Poll for approval
        console.print("[dim]Waiting for approval…[/dim]")
        start = time.time()
        interval = poll_interval

        while (time.time() - start) < expires_in:
            time.sleep(interval)

            try:
                token_data = _poll_token(device_code, verifier)
            except RuntimeError as exc:
                console.print(f"[red]✗ Qwen OAuth failed: {exc}[/red]")
                return {}

            if token_data:
                access_token = token_data["access_token"]
                refresh_token = token_data["refresh_token"]
                expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
                resource_url = token_data.get("resource_url", "")

                console.print("[green]✓ Qwen OAuth approved![/green]")

                api_base = resource_url if resource_url else QWEN_API_BASE
                # Normalize base URL
                if not api_base.endswith("/v1"):
                    api_base = api_base.rstrip("/") + "/v1"

                return {
                    "providers": {
                        "qwen": {
                            "oauth_token": access_token,
                            "refresh_token": refresh_token,
                            "client_id": QWEN_CLIENT_ID,
                            "expires_at": int(time.time() * 1000) + (expires_in * 1000),
                            "token_type": "oauth",
                            "api_base": api_base,
                        }
                    }
                }

            # Back-off slightly
            interval = min(interval * 1.2, 10)

        console.print("[red]✗ Timed out waiting for Qwen OAuth approval.[/red]")
        return {}
