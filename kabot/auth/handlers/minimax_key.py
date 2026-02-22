"""MiniMax API Key authentication handler."""

import os
from typing import Any, Dict

from rich.console import Console
from rich.prompt import Prompt

from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

console = Console()


class MiniMaxKeyHandler(AuthHandler):
    """Handler for MiniMax general API Key authentication (pay-as-you-go)."""

    API_BASE = "https://api.minimax.chat/v1"

    @property
    def name(self) -> str:
        return "MiniMax (API Key)"

    def authenticate(self) -> Dict[str, Any]:
        """Execute API key authentication flow."""
        console.print("\n[bold]MiniMax API Key Setup[/bold]")
        console.print("Get your API key from: https://platform.minimax.io/dashboard\n")

        # Check env var first
        env_key = os.environ.get("MINIMAX_API_KEY")
        if env_key:
            use_env = Prompt.ask(
                f"Found MINIMAX_API_KEY in environment ({env_key[:8]}...). Use this?",
                choices=["y", "n"],
                default="y"
            )
            if use_env == "y":
                return {
                    "providers": {
                        "minimax": {
                            "api_key": env_key,
                            "api_base": self.API_BASE
                        }
                    }
                }

        # Manual input
        api_key = secure_input("Enter MiniMax API Key")

        if not api_key:
            return None

        return {
            "providers": {
                "minimax": {
                    "api_key": api_key,
                    "api_base": self.API_BASE
                }
            }
        }
