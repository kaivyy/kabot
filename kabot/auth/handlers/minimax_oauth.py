"""MiniMax Portal OAuth handler — device code flow (Global + CN).

Mirrors OpenClaw's extensions/minimax-portal-auth/oauth.ts.
Uses device code grant with region selection: Global (api.minimax.io)
or China (api.minimaxi.com). Same client_id for both regions.
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

# ── OAuth constants (from OpenClaw minimax-portal-auth plugin) ─────────────
MINIMAX_CLIENT_ID = "78257093-7e40-4613-99e0-527b14b39113"
MINIMAX_SCOPE = "group_id profile model.completion"
MINIMAX_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:user_code"

REGIONS = {
    "global": {
        "label": "Global (api.minimax.io)",
        "base_url": "https://api.minimax.io",
        "api_base": "https://api.minimax.io/anthropic",
    },
    "cn": {
        "label": "China (api.minimaxi.com)",
        "base_url": "https://api.minimaxi.com",
        "api_base": "https://api.minimaxi.com/anthropic",
    },
}


# ── PKCE helper ─────────────────────────────────────────────────────────────

def _generate_pkce() -> tuple:
    """Generate PKCE verifier + S256 challenge + state."""
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    state = secrets.token_urlsafe(16)
    return verifier, challenge, state


# ── Device code flow ────────────────────────────────────────────────────────

def _request_user_code(
    challenge: str, state: str, base_url: str
) -> Dict[str, Any]:
    """Request a user code from MiniMax's OAuth endpoint."""
    code_url = f"{base_url}/oauth/code"
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            code_url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={
                "response_type": "code",
                "client_id": MINIMAX_CLIENT_ID,
                "scope": MINIMAX_SCOPE,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": state,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if not data.get("user_code") or not data.get("verification_uri"):
        raise RuntimeError(
            data.get("error", "MiniMax OAuth returned incomplete data")
        )

    # Verify state
    if data.get("state") != state:
        raise RuntimeError("MiniMax OAuth state mismatch — possible CSRF attack")

    return data


def _poll_token(
    user_code: str, verifier: str, base_url: str
) -> Optional[Dict[str, Any]]:
    """Poll MiniMax's token endpoint once. Returns token data or None if pending."""
    token_url = f"{base_url}/oauth/token"
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            token_url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={
                "grant_type": MINIMAX_GRANT_TYPE,
                "client_id": MINIMAX_CLIENT_ID,
                "user_code": user_code,
                "code_verifier": verifier,
            },
        )

    try:
        data = resp.json()
    except Exception:
        return None

    if not resp.is_success:
        error_msg = (
            data.get("base_resp", {}).get("status_msg", "")
            or resp.text
        )
        if error_msg:
            raise RuntimeError(f"MiniMax OAuth error: {error_msg}")
        return None

    status = data.get("status", "")
    if status == "error":
        raise RuntimeError("MiniMax OAuth: server returned an error")

    if status != "success":
        return None  # Still pending

    if (
        not data.get("access_token")
        or not data.get("refresh_token")
        or not data.get("expired_in")
    ):
        return None

    return data


# ── Handler ─────────────────────────────────────────────────────────────────

class MiniMaxOAuthHandler(AuthHandler):
    """Handler for MiniMax Portal OAuth (device code, Global + CN)."""

    @property
    def name(self) -> str:
        return "MiniMax (OAuth)"

    def authenticate(self) -> Dict[str, Any]:
        console.print("\n[bold]MiniMax Portal OAuth Setup[/bold]")
        console.print("This will authenticate via MiniMax's device code flow.\n")

        # Region selection
        region = Prompt.ask(
            "Select region",
            choices=["global", "cn"],
            default="global",
        )
        region_cfg = REGIONS[region]
        base_url = region_cfg["base_url"]

        # Generate PKCE + state
        verifier, challenge, state = _generate_pkce()

        # Request user code
        console.print(f"[dim]Requesting device code ({region_cfg['label']})…[/dim]")
        try:
            code_data = _request_user_code(challenge, state, base_url)
        except Exception as exc:
            console.print(f"[red]✗ Failed to get user code: {exc}[/red]")
            return {}

        user_code = code_data["user_code"]
        verification_uri = code_data["verification_uri"]
        expires_at = code_data.get("expired_in", int(time.time()) + 300)
        poll_interval = code_data.get("interval", 2)

        # Show user code and URL
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
        interval = poll_interval

        while time.time() < expires_at:
            time.sleep(interval)

            try:
                token_data = _poll_token(user_code, verifier, base_url)
            except RuntimeError as exc:
                console.print(f"[red]✗ MiniMax OAuth failed: {exc}[/red]")
                return {}

            if token_data:
                access_token = token_data["access_token"]
                refresh_token = token_data["refresh_token"]
                expires_in = token_data.get("expired_in", 3600)  # Default 1 hour
                resource_url = token_data.get("resource_url", "")
                notification = token_data.get("notification_message", "")

                if notification:
                    console.print(f"[yellow]{notification}[/yellow]")

                console.print("[green]✓ MiniMax OAuth approved![/green]")

                api_base = resource_url if resource_url else region_cfg["api_base"]

                return {
                    "providers": {
                        "minimax": {
                            "oauth_token": access_token,
                            "refresh_token": refresh_token,
                            "client_id": MINIMAX_CLIENT_ID,
                            "expires_at": int(time.time() * 1000) + (expires_in * 1000),
                            "token_type": "oauth",
                            "api_base": api_base,
                            "region": region,
                        }
                    }
                }

            # Back-off slightly
            interval = min(interval * 1.5, 10)

        console.print("[red]✗ Timed out waiting for MiniMax OAuth approval.[/red]")
        return {}
