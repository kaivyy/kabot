"""Kimi (Moonshot AI) API Key authentication handler.

Supports both international (.ai) and China (.cn) endpoints,
matching OpenClaw's moonshot-api-key and moonshot-api-key-cn options.
"""

from typing import Dict, Any
import os
from rich.prompt import Prompt
from rich.console import Console
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

console = Console()

# Moonshot API endpoints (from OpenClaw onboard-auth.models.ts)
ENDPOINTS = {
    "international": "https://api.moonshot.ai/v1",
    "china": "https://api.moonshot.cn/v1",
}


class KimiKeyHandler(AuthHandler):
    """Handler for Kimi general API Key authentication."""

    @property
    def name(self) -> str:
        return "Kimi (API Key)"

    def authenticate(self) -> Dict[str, Any]:
        """Execute API key authentication flow."""
        console.print("\n[bold]Kimi (Moonshot AI) API Key Setup[/bold]")
        console.print("Get your API key from: https://platform.moonshot.cn/console/api-keys\n")

        # Endpoint selection
        region = Prompt.ask(
            "Select endpoint",
            choices=["international", "china"],
            default="international",
        )
        api_base = ENDPOINTS[region]
        console.print(f"[dim]Using endpoint: {api_base}[/dim]\n")

        # Check env var first
        env_key = os.environ.get("MOONSHOT_API_KEY") or os.environ.get("KIMI_API_KEY")
        if env_key:
            use_env = Prompt.ask(
                f"Found Moonshot API key in environment ({env_key[:8]}...). Use this?",
                choices=["y", "n"],
                default="y"
            )
            if use_env == "y":
                return {
                    "providers": {
                        "moonshot": {
                            "api_key": env_key,
                            "api_base": api_base,
                        }
                    }
                }

        # Manual input
        api_key = secure_input("Enter Moonshot API Key")

        if not api_key:
            return None

        return {
            "providers": {
                "moonshot": {
                    "api_key": api_key,
                    "api_base": api_base,
                }
            }
        }
