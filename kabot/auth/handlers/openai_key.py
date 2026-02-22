"""OpenAI API Key authentication handler."""

import os
from typing import Any, Dict

from rich.console import Console
from rich.prompt import Prompt

from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

console = Console()


class OpenAIKeyHandler(AuthHandler):
    """Handler for OpenAI API Key authentication."""

    @property
    def name(self) -> str:
        return "OpenAI (API Key)"

    def authenticate(self) -> Dict[str, Any]:
        """Execute API key authentication flow."""
        console.print("\n[bold]OpenAI API Key Setup[/bold]")
        console.print("Get your API key from: https://platform.openai.com/api-keys\n")

        # Check env var first
        env_key = os.environ.get("OPENAI_API_KEY")
        if env_key:
            use_env = Prompt.ask(
                f"Found OPENAI_API_KEY in environment ({env_key[:8]}...). Use this?",
                choices=["y", "n"],
                default="y"
            )
            if use_env == "y":
                return {"providers": {"openai": {"api_key": env_key}}}

        # Manual input
        api_key = secure_input("Enter OpenAI API Key")

        if not api_key:
            return None

        return {"providers": {"openai": {"api_key": api_key}}}
