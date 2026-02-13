from typing import Dict, Any
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import run_oauth_flow

class MiniMaxOAuthHandler(AuthHandler):
    """Handler for MiniMax Portal OAuth login."""

    def authenticate(self) -> Dict[str, Any]:
        # MiniMax portal auth URL
        auth_url = "https://api.minimax.io/oauth/authorize"
        
        # This will handle PC vs VPS, Port detection, and Smart URL parsing automatically
        token = run_oauth_flow(auth_url)
        
        if not token:
            return {}

        return {
            "providers": {
                "minimax": {
                    "oauth_token": token
                }
            }
        }
