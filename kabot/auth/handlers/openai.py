from typing import Dict, Any
import os
from rich.prompt import Prompt
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

class OpenAIHandler(AuthHandler):
    @property
    def name(self) -> str:
        return "OpenAI"

    def authenticate(self) -> Dict[str, Any]:
        print("\n[bold]OpenAI Setup[/bold]")
        print("Get your API key from: https://platform.openai.com/api-keys")

        # Check for existing env var
        env_key = os.environ.get("OPENAI_API_KEY")
        if env_key:
            use_env = Prompt.ask(f"Found OPENAI_API_KEY in environment ({env_key[:8]}...). Use this?", choices=["y", "n"], default="y")
            if use_env == "y":
                return {"providers": {"openai": {"api_key": env_key}}}

        api_key = secure_input("Enter OpenAI API Key")
        return {"providers": {"openai": {"api_key": api_key}}}
