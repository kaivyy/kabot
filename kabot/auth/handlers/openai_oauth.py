"""OpenAI OAuth authentication handler using PKCE (S256).

Uses the same public client_id as OpenAI Codex CLI to authenticate
users with their ChatGPT subscription via browser login.
"""

import secrets
import hashlib
import base64
import asyncio
import webbrowser
from typing import Dict, Any, Optional
from urllib.parse import urlencode, urlparse, parse_qs

import httpx
from aiohttp import web
from rich.console import Console
from rich.prompt import Prompt

from kabot.auth.handlers.base import AuthHandler
from kabot.utils.environment import detect_runtime_environment

console = Console()

# ── OpenAI OAuth Constants (from Codex CLI public client) ──
OPENAI_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
OPENAI_AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
OPENAI_TOKEN_URL = "https://auth.openai.com/oauth/token"
CALLBACK_PORT = 1455
CALLBACK_PATH = "/auth/callback"
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"
SCOPES = "openid profile email offline_access"


def _generate_pkce() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _is_headless() -> bool:
    """Detect headless/VPS environment."""
    return detect_runtime_environment().is_headless


def _parse_callback_input(raw: str, expected_state: str) -> Optional[Dict[str, str]]:
    """Extract code and state from a pasted URL or raw code."""
    raw = raw.strip()
    if not raw:
        return None

    def _extract_from_params(params: Dict[str, list[str]]) -> Optional[Dict[str, str]]:
        code = (params.get("code") or [None])[0]
        state = (params.get("state") or [None])[0]
        if code:
            return {"code": code, "state": state or expected_state}
        return None

    try:
        parsed = urlparse(raw)
        # Standard callback query: ?code=...&state=...
        query_match = _extract_from_params(parse_qs(parsed.query))
        if query_match:
            return query_match

        # Manual paste can include fragment callback:
        # http://localhost:1455/auth/callback#code=...&state=...
        if parsed.fragment:
            fragment_match = _extract_from_params(parse_qs(parsed.fragment))
            if fragment_match:
                return fragment_match
    except Exception:
        pass

    # Raw query string fallback: "code=...&state=..."
    if "code=" in raw:
        raw_params = raw.lstrip("?#")
        query_match = _extract_from_params(parse_qs(raw_params))
        if query_match:
            return query_match

    # Compatibility fallback: "<code>#<state>"
    if "#" in raw and "://" not in raw:
        code, state = raw.split("#", 1)
        if code:
            return {"code": code, "state": state or expected_state}

    # Treat as raw code
    return {"code": raw, "state": expected_state}


async def _exchange_code(code: str, verifier: str) -> Dict[str, Any]:
    """Exchange authorization code + verifier for access/refresh tokens."""
    body = {
        "grant_type": "authorization_code",
        "client_id": OPENAI_CLIENT_ID,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            OPENAI_TOKEN_URL,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()


async def _wait_for_callback(state: str, timeout: int = 300) -> Optional[str]:
    """Start local HTTP server and wait for callback with auth code."""
    result: Dict[str, Optional[str]] = {"code": None}

    async def handle(request: web.Request) -> web.Response:
        received_state = request.query.get("state")
        if received_state != state:
            return web.Response(text="Invalid state (CSRF)", status=400)
        code = request.query.get("code")
        if not code:
            return web.Response(text="Missing code", status=400)
        result["code"] = code
        html = (
            "<!doctype html><html><body>"
            "<h2>✓ Authentication Successful</h2>"
            "<p>You can close this window and return to the terminal.</p>"
            "</body></html>"
        )
        return web.Response(text=html, content_type="text/html")

    app = web.Application()
    app.router.add_get(CALLBACK_PATH, handle)
    runner = web.AppRunner(app)
    await runner.setup()

    try:
        site = web.TCPSite(runner, "localhost", CALLBACK_PORT)
        await site.start()
    except OSError as e:
        await runner.cleanup()
        raise RuntimeError(
            f"Port {CALLBACK_PORT} is busy. Close any other app using it."
        ) from e

    console.print(f"[dim]Waiting for OAuth callback on port {CALLBACK_PORT}...[/dim]")

    try:
        for _ in range(timeout):
            if result["code"]:
                return result["code"]
            await asyncio.sleep(1)
        return None
    finally:
        await runner.cleanup()


class OpenAIOAuthHandler(AuthHandler):
    """Handler for OpenAI OAuth authentication (ChatGPT subscription, PKCE)."""

    @property
    def name(self) -> str:
        return "OpenAI (OAuth)"

    def authenticate(self) -> Dict[str, Any]:
        """Execute PKCE OAuth authentication flow."""
        console.print("\n[bold]OpenAI Codex OAuth Setup[/bold]")
        console.print("This uses your ChatGPT subscription.\n")

        verifier, challenge = _generate_pkce()
        state = secrets.token_urlsafe(24)

        params = {
            "response_type": "code",
            "client_id": OPENAI_CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "originator": "kabot",
        }
        auth_url = f"{OPENAI_AUTHORIZE_URL}?{urlencode(params)}"

        if _is_headless():
            return self._headless_flow(auth_url, state, verifier)
        else:
            return self._local_flow(auth_url, state, verifier)

    def _local_flow(self, auth_url: str, state: str, verifier: str) -> Optional[Dict[str, Any]]:
        """Browser-based flow for local machines."""
        console.print("[dim]Opening browser for authentication...[/dim]")
        try:
            webbrowser.open(auth_url)
        except Exception:
            console.print(
                f"\n[yellow]Could not open browser. Please open:[/yellow]\n{auth_url}\n"
            )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            code = loop.run_until_complete(_wait_for_callback(state))
        except Exception as e:
            console.print(f"[red]Callback error: {e}[/red]")
            # Fallback to manual paste
            return self._headless_flow(auth_url, state, verifier)
        finally:
            loop.close()

        if not code:
            console.print("[red]OAuth timed out. Falling back to manual paste...[/red]")
            return self._headless_flow(auth_url, state, verifier)

        return self._exchange_and_return(code, verifier)

    def _headless_flow(self, auth_url: str, state: str, verifier: str) -> Optional[Dict[str, Any]]:
        """Manual paste flow for VPS/headless environments."""
        console.print("\n[bold yellow]VPS / Headless Mode[/bold yellow]")
        console.print("\n[bold]1.[/bold] Open this URL in your browser:")
        console.print(f"[cyan]{auth_url}[/cyan]")
        console.print("\n[bold]2.[/bold] Complete the login.")
        console.print("[bold]3.[/bold] Copy the ENTIRE redirect URL and paste below.")
        console.print("[dim](Even if it says 'Site Can't Be Reached', the URL still has the code.)[/dim]\n")

        raw = Prompt.ask("Paste the Redirect URL or Code", password=True)
        parsed = _parse_callback_input(raw, state)

        if not parsed or not parsed.get("code"):
            console.print("[red]No authorization code found in input.[/red]")
            return None

        if parsed.get("state") and parsed["state"] != state:
            console.print("[red]State mismatch. Please retry login.[/red]")
            return None

        return self._exchange_and_return(parsed["code"], verifier)

    def _exchange_and_return(self, code: str, verifier: str) -> Optional[Dict[str, Any]]:
        """Exchange auth code for tokens and return credential dict."""
        console.print("[dim]Exchanging code for tokens...[/dim]")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            tokens = loop.run_until_complete(_exchange_code(code, verifier))
        except Exception as e:
            console.print(f"[red]Token exchange failed: {e}[/red]")
            return None
        finally:
            loop.close()

        import time
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in", 3600)  # Default 1 hour

        if not access_token:
            console.print("[red]No access_token returned by OpenAI.[/red]")
            return None

        console.print("[green]✓ OpenAI OAuth authentication successful![/green]")

        return {
            "providers": {
                "openai_codex": {
                    "oauth_token": access_token,
                    "refresh_token": refresh_token,
                    "client_id": OPENAI_CLIENT_ID,
                    "expires_at": int(time.time() * 1000) + (expires_in * 1000),
                    "token_type": "oauth",
                }
            }
        }
