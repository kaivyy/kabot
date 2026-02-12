import os
import webbrowser
import asyncio
import re
from typing import Optional
from rich.prompt import Prompt
from rich.console import Console
from kabot.auth.oauth_callback import OAuthCallbackServer

console = Console()

def is_vps() -> bool:
    """
    Detect if running in a VPS/Headless environment.
    Checks for SSH environment variables or CI flags.
    """
    # Common indicators of SSH sessions
    ssh_client = os.environ.get("SSH_CLIENT")
    ssh_tty = os.environ.get("SSH_TTY")

    # Common indicators of CI/CD environments
    ci = os.environ.get("CI")

    # Check if running in Docker (optional, but often correlates with headless)
    is_docker = os.path.exists("/.dockerenv")

    return any([ssh_client, ssh_tty, ci, is_docker])

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
    if is_vps():
        # VPS mode: Manual flow
        console.print("\n[yellow]VPS Environment Detected[/yellow]")
        console.print("\n[bold]Please open this URL in your browser:[/bold]")
        console.print(f"[cyan]{auth_url}[/cyan]\n")

        token = secure_input("Paste the authorization code/token")
        return token
    else:
        # Local mode: Automatic flow
        server = OAuthCallbackServer(port=port)
        
        # Build full URL with server instance (includes state)
        full_url = server.get_auth_url(auth_url, {})
        
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
