"""Google OAuth authentication handler."""

from typing import Dict, Any
from rich.console import Console
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import run_oauth_flow

console = Console()


class GoogleOAuthHandler(AuthHandler):
    """Handler for Google OAuth authentication (Google Gemini)."""

    @property
    def name(self) -> str:
        return "Google Gemini (OAuth)"

    def authenticate(self) -> Dict[str, Any]:
        """Execute Google OAuth authentication flow."""
        console.print("\n[bold]Google OAuth Setup[/bold]")
        console.print("This will connect Kabot to your Google account.\n")

        # Build Google authorization URL
        # NOTE: Using placeholder URL as per design document
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        
        params = {
            "client_id": "kabot-google",
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/generative-language",
            "access_type": "offline",
            "prompt": "consent"
        }

        # Build full URL and handle flow via utility
        token = run_oauth_flow(auth_url)

        if not token:
            return None

        # Note: Uses 'gemini' as provider key for config compatibility
        return {"providers": {"gemini": {"oauth_token": token}}}
