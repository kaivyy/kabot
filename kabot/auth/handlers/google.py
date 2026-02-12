from typing import Dict, Any
import os
from rich.prompt import Prompt
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

class GoogleHandler(AuthHandler):
    @property
    def name(self) -> str:
        return "Google Gemini"

    def authenticate(self) -> Dict[str, Any]:
        print("\n[bold]Google Gemini Setup[/bold]")
        print("Get your API key from: https://aistudio.google.com/app/apikey")

        # Check for existing env var
        env_key = os.environ.get("GEMINI_API_KEY")
        if env_key:
            use_env = Prompt.ask(f"Found GEMINI_API_KEY in environment ({env_key[:8]}...). Use this?", choices=["y", "n"], default="y")
            if use_env == "y":
                return {"providers": {"gemini": {"api_key": env_key}}}

        api_key = secure_input("Enter Gemini API Key")
        return {"providers": {"gemini": {"api_key": api_key}}}
