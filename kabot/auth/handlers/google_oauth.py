"""Google Antigravity OAuth handler — PKCE + localhost callback.

Mirrors OpenClaw's extensions/google-antigravity-auth/index.ts.
Uses the same client_id, client_secret, scopes, and token endpoint.
"""

import asyncio
import base64
import hashlib
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Dict, Any, Optional
from urllib.parse import urlencode, urlparse, parse_qs

import httpx
from rich.console import Console
from rich.prompt import Prompt

from kabot.auth.handlers.base import AuthHandler

console = Console()

# ── OAuth constants (from OpenClaw google-antigravity-auth plugin) ──────────
GOOGLE_CLIENT_ID = (
    "1071006060591-tmhssin2h21lcre235vtolojh4g403ep"
    ".apps.googleusercontent.com"
)
GOOGLE_CLIENT_SECRET = "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"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo?alt=json"
REDIRECT_PORT = 51121
REDIRECT_PATH = "/oauth-callback"
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}{REDIRECT_PATH}"

SCOPES = " ".join([
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/cclog",
    "https://www.googleapis.com/auth/experimentsandconfigs",
])

RESPONSE_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Kabot Google OAuth</title></head>
<body style="font-family:system-ui;display:flex;justify-content:center;
align-items:center;height:100vh;margin:0;background:#1a1a2e;color:#e0e0e0">
<div style="text-align:center">
<h1 style="color:#00d4ff">✓ Authentication complete</h1>
<p>You can close this tab and return to the terminal.</p>
</div></body></html>"""


# ── PKCE helpers ────────────────────────────────────────────────────────────

def _generate_pkce() -> tuple:
    """Generate PKCE verifier + S256 challenge."""
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


# ── Callback server ────────────────────────────────────────────────────────

class _CallbackHandler(BaseHTTPRequestHandler):
    """Tiny HTTP handler that captures the OAuth callback."""

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != REDIRECT_PATH:
            self.send_response(404)
            self.end_headers()
            return

        qs = parse_qs(parsed.query)
        code = qs.get("code", [None])[0]
        state = qs.get("state", [None])[0]
        self.server._oauth_code = code    # type: ignore[attr-defined]
        self.server._oauth_state = state  # type: ignore[attr-defined]

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(RESPONSE_HTML.encode())

    def log_message(self, *_):
        pass  # suppress request logs


def _wait_for_callback(expected_state: str, timeout: int = 300) -> Optional[str]:
    """Start callback server and wait for Google's redirect."""
    try:
        server = HTTPServer(("127.0.0.1", REDIRECT_PORT), _CallbackHandler)
    except OSError:
        return None

    server._oauth_code = None   # type: ignore[attr-defined]
    server._oauth_state = None  # type: ignore[attr-defined]
    server.timeout = timeout

    thread = Thread(target=server.handle_request, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    try:
        server.server_close()
    except Exception:
        pass

    if server._oauth_state != expected_state:  # type: ignore[attr-defined]
        return None
    return server._oauth_code  # type: ignore[attr-defined]


# ── Token exchange ──────────────────────────────────────────────────────────

def _exchange_code(code: str, verifier: str) -> Dict[str, Any]:
    """Exchange authorization code for tokens."""
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI,
                "code_verifier": verifier,
            },
        )
        resp.raise_for_status()
        return resp.json()


def _fetch_user_email(access_token: str) -> Optional[str]:
    """Retrieve user email from Google userinfo."""
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code == 200:
                return resp.json().get("email")
    except Exception:
        pass
    return None


# ── Handler ─────────────────────────────────────────────────────────────────

class GoogleOAuthHandler(AuthHandler):
    """Handler for Google Antigravity OAuth (PKCE + localhost callback)."""

    @property
    def name(self) -> str:
        return "Google Gemini (OAuth)"

    def authenticate(self) -> Dict[str, Any]:
        console.print("\n[bold]Google Antigravity OAuth Setup[/bold]")
        console.print("This will authenticate via Google Cloud (Antigravity).\n")

        verifier, challenge = _generate_pkce()
        state = secrets.token_urlsafe(24)

        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

        # Try to open browser and start callback server
        console.print(f"[dim]Redirect URI: {REDIRECT_URI}[/dim]\n")

        try:
            webbrowser.open(auth_url)
            console.print("[green]→ Browser opened for Google sign-in[/green]")
            code = _wait_for_callback(state, timeout=300)
        except Exception:
            code = None

        # Fallback: manual URL paste (VPS / headless)
        if not code:
            console.print("\n[yellow]Could not detect callback automatically.[/yellow]")
            console.print("Open this URL in your browser:\n")
            console.print(f"[bold cyan]{auth_url}[/bold cyan]\n")
            console.print(
                "After signing in, paste the full redirect URL "
                "(starts with http://localhost:51121/oauth-callback?...):"
            )
            raw = Prompt.ask("Redirect URL")
            if raw:
                parsed = urlparse(raw.strip())
                qs = parse_qs(parsed.query)
                code = qs.get("code", [None])[0]
                cb_state = qs.get("state", [None])[0]
                if cb_state != state:
                    console.print("[red]✗ State mismatch — possible CSRF. Please retry.[/red]")
                    return None

        if not code:
            console.print("[red]✗ No authorization code received.[/red]")
            return None

        # Exchange code for tokens
        console.print("[dim]Exchanging code for tokens…[/dim]")
        try:
            token_data = _exchange_code(code, verifier)
        except httpx.HTTPStatusError as exc:
            console.print(f"[red]✗ Token exchange failed: {exc.response.text}[/red]")
            return None

        import time
        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token", "")
        expires_in = token_data.get("expires_in", 3600)  # Default 1 hour

        # Fetch user email
        email = _fetch_user_email(access_token)
        if email:
            console.print(f"[green]✓ Authenticated as {email}[/green]")
        else:
            console.print("[green]✓ Authentication successful[/green]")

        return {
            "providers": {
                "gemini": {
                    "oauth_token": access_token,
                    "refresh_token": refresh_token,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "expires_at": int(time.time() * 1000) + (expires_in * 1000),
                    "token_type": "oauth",
                    "email": email,
                }
            }
        }
