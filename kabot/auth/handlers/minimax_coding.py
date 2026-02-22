"""MiniMax Coding Plan subscription authentication handler."""

import os
from typing import Any, Dict

from rich.console import Console
from rich.prompt import Prompt

from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

console = Console()


class MiniMaxCodingHandler(AuthHandler):
    """Handler for MiniMax Coding Plan subscription authentication."""

    API_BASE = "https://api.minimax.chat/v1"

    @property
    def name(self) -> str:
        return "MiniMax Coding Plan (Subscription)"

    def authenticate(self) -> Dict[str, Any]:
        """Execute Coding Plan subscription authentication flow."""
        console.print("\n[bold]MiniMax Coding Plan Setup[/bold]")
        console.print("This requires a MiniMax Coding Plan subscription (unlimited usage).")
        console.print("Get your Coding Plan key from: https://platform.minimax.io/dashboard\n")

        # Check env var first
        env_key = os.environ.get("MINIMAX_CODING_API_KEY")
        if env_key:
            use_env = Prompt.ask(
                f"Found MINIMAX_CODING_API_KEY in environment ({env_key[:8]}...). Use this?",
                choices=["y", "n"],
                default="y"
            )
            if use_env == "y":
                return {
                    "providers": {
                        "minimax": {
                            "api_key": env_key,
                            "api_base": self.API_BASE,
                            "subscription_type": "coding_plan"
                        }
                    }
                }

        # Manual input
        api_key = secure_input("Enter MiniMax Coding Plan API Key")

        if not api_key:
            return None

        return {
            "providers": {
                "minimax": {
                    "api_key": api_key,
                    "api_base": self.API_BASE,
                    "subscription_type": "coding_plan"
                }
            }
        }
