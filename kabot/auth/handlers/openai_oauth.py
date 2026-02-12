"""OpenAI OAuth authentication handler."""

from typing import Dict, Any
from rich.console import Console
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import run_oauth_flow

console = Console()


class OpenAIOAuthHandler(AuthHandler):
    """Handler for OpenAI OAuth authentication (ChatGPT subscription)."""

    @property
    def name(self) -> str:
        return "OpenAI (OAuth)"

    def authenticate(self) -> Dict[str, Any]:
        """Execute OAuth authentication flow."""
        console.print("\n[bold]OpenAI OAuth Setup[/bold]")
        console.print("This requires a ChatGPT subscription.\n")

        # Build base authorization URL
        # NOTE: Using placeholder URL as per design document
        auth_url = "https://auth.openai.com/authorize"
        
        params = {
            "client_id": "kabot-openai",
            "response_type": "code",
            "scope": "openid profile email",
        }

        # Build full URL with state and redirect_uri via utility
        # run_oauth_flow handles the server and browser
        token = run_oauth_flow(auth_url)

        if not token:
            return None

        return {"providers": {"openai": {"oauth_token": token}}}
