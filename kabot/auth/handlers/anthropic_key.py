"""Anthropic API Key authentication handler."""

import os
from typing import Any, Dict

from rich.console import Console
from rich.prompt import Prompt

from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

console = Console()


class AnthropicKeyHandler(AuthHandler):
    """Handler for Anthropic API Key authentication."""

    @property
    def name(self) -> str:
        return "Anthropic (API Key)"

    def authenticate(self) -> Dict[str, Any]:
        """Execute API key authentication flow."""
        console.print("\n[bold]Anthropic API Key Setup[/bold]")
        console.print("Get your API key from: https://console.anthropic.com/settings/keys\n")

        # Check env var first
        env_key = os.environ.get("ANTHROPIC_API_KEY")
        if env_key:
            use_env = Prompt.ask(
                f"Found ANTHROPIC_API_KEY in environment ({env_key[:8]}...). Use this?",
                choices=["y", "n"],
                default="y"
            )
            if use_env == "y":
                return {"providers": {"anthropic": {"api_key": env_key}}}

        # Manual input
        api_key = secure_input("Enter Anthropic API Key")

        if not api_key:
            return None

        return {"providers": {"anthropic": {"api_key": api_key}}}
