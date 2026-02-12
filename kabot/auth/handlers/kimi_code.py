"""Kimi Code subscription authentication handler."""

from typing import Dict, Any
import os
from rich.prompt import Prompt
from rich.console import Console
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

console = Console()


class KimiCodeHandler(AuthHandler):
    """Handler for Kimi Code subscription authentication."""

    API_BASE = "https://api.moonshot.cn/v1"

    @property
    def name(self) -> str:
        return "Kimi Code (Subscription)"

    def authenticate(self) -> Dict[str, Any]:
        """Execute Kimi Code subscription authentication flow."""
        console.print("\n[bold]Kimi Code Subscription Setup[/bold]")
        console.print("This requires a Kimi Code subscription plan.")
        console.print("Get your subscription key from: https://platform.moonshot.cn/console/api-keys\n")

        # Check env var first
        env_key = os.environ.get("KIMI_CODE_API_KEY")
        if env_key:
            use_env = Prompt.ask(
                f"Found KIMI_CODE_API_KEY in environment ({env_key[:8]}...). Use this?",
                choices=["y", "n"],
                default="y"
            )
            if use_env == "y":
                return {
                    "providers": {
                        "kimi": {
                            "api_key": env_key,
                            "api_base": self.API_BASE,
                            "subscription_type": "kimi_code"
                        }
                    }
                }

        # Manual input
        api_key = secure_input("Enter Kimi Code API Key")

        if not api_key:
            return None

        return {
            "providers": {
                "kimi": {
                    "api_key": api_key,
                    "api_base": self.API_BASE,
                    "subscription_type": "kimi_code"
                }
            }
        }
