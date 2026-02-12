from typing import Dict, Any
import os
from rich.prompt import Prompt
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

class AnthropicHandler(AuthHandler):
    @property
    def name(self) -> str:
        return "Anthropic"

    def authenticate(self) -> Dict[str, Any]:
        print("\n[bold]Anthropic Setup[/bold]")
        print("Get your API key from: https://console.anthropic.com/settings/keys")

        # Check for existing env var
        env_key = os.environ.get("ANTHROPIC_API_KEY")
        if env_key:
            use_env = Prompt.ask(f"Found ANTHROPIC_API_KEY in environment ({env_key[:8]}...). Use this?", choices=["y", "n"], default="y")
            if use_env == "y":
                return {"providers": {"anthropic": {"api_key": env_key}}}

        api_key = secure_input("Enter Anthropic API Key")
        return {"providers": {"anthropic": {"api_key": api_key}}}
