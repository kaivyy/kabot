import asyncio
import re
import webbrowser
from typing import Optional
from urllib.parse import parse_qs, urlparse

from rich.console import Console
from rich.prompt import Prompt

from kabot.auth.oauth_callback import OAuthCallbackServer
from kabot.utils.environment import detect_runtime_environment

console = Console()

def parse_redirect_url(input_text: str) -> Optional[str]:
    """
    Extract authorization code from a full URL if provided,
    otherwise return the input as-is (assuming it's the raw code).
    """
    input_text = input_text.strip()
    if input_text.startswith("http"):
        try:
            parsed = urlparse(input_text)
            params = parse_qs(parsed.query)
            # Try 'code' (standard) or 'token'
            code = params.get('code') or params.get('token')
            if code:
                return code[0]
        except Exception:
            pass
    return input_text

def is_vps() -> bool:
    """
    Detect if running in a VPS/Headless environment.
    Uses centralized runtime environment detection.
    """
    env = detect_runtime_environment()
    return env.is_vps or env.is_headless

def open_browser(url: str):
    """
    Open a URL in the browser if local, or print it if on VPS.
    """
    if is_vps():
        console.print(f"\n[bold yellow]Please open this URL in your browser:[/bold yellow]\n{url}\n")
    else:
        console.print(f"Opening browser to: {url}")
        try:
            webbrowser.open(url)
        except Exception:
            # Fallback if browser opening fails
            console.print(f"\n[bold yellow]Could not open browser. Please open this URL:[/bold yellow]\n{url}\n")

def secure_input(prompt_text: str) -> str:
    """
    Securely prompt for input (masks characters).
    """
    return Prompt.ask(prompt_text, password=True)

def run_oauth_flow(auth_url: str, port: int = 8765) -> Optional[str]:
    """
    Run OAuth flow: open browser, start callback server, return token.

    Works in both local and VPS environments.

    Args:
        auth_url: OAuth authorization URL (without state/redirect_uri)
        port: Local server port (default 8765)

    Returns:
        OAuth token/code
    """
    server = OAuthCallbackServer(port=port)
    # Generate full URL with state and redirect_uri early
    full_url = server.get_auth_url(auth_url, {})

    if is_vps():
        # VPS mode: Manual flow
        console.print("\n[bold yellow]VPS Environment Detected[/bold yellow]")
        console.print("\n[bold]1. Please open this URL in your browser:[/bold]")
        console.print(f"[cyan]{full_url}[/cyan]")
        console.print("\n[bold]2. Complete the login and you will reach a 'Site Can't Be Reached' page.[/bold]")
        console.print("[bold]3. Copy the ENTIRE URL from your browser's address bar and paste it below.[/bold]")

        raw_input = secure_input("\nPaste the Redirect URL or Code")
        token = parse_redirect_url(raw_input)
        return token
    else:
        # Local mode: Automatic flow
        console.print("[dim]Opening browser for authentication...[/dim]")
        try:
            webbrowser.open(full_url)
        except Exception:
            console.print(f"\n[yellow]Failed to open browser automatically. Please open:[/yellow]\n{full_url}\n")

        # Start callback server
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            token = loop.run_until_complete(server.start_and_wait())
            return token
        except TimeoutError:
            console.print("[red]OAuth flow timed out.[/red]")
            return None
        finally:
            loop.close()
def validate_api_key(key: str, pattern: str = None) -> bool:
    """
    Validate API key format.

    Args:
        key: API key to validate
        pattern: Optional regex pattern to match

    Returns:
        True if valid, False otherwise
    """
    if not key or len(key) < 10:
        return False

    if pattern:
        return bool(re.match(pattern, key))

    return True
