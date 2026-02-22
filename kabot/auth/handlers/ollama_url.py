"""Ollama URL configuration handler."""

import os
from typing import Any, Dict

from rich.console import Console
from rich.prompt import Prompt

from kabot.auth.handlers.base import AuthHandler

console = Console()


class OllamaURLHandler(AuthHandler):
    """Handler for Ollama local server configuration."""

    @property
    def name(self) -> str:
        return "Ollama (Local)"

    def authenticate(self) -> Dict[str, Any]:
        """Configure Ollama server URL."""
        console.print("\n[bold]Ollama Setup[/bold]")
        console.print("Ensure Ollama is running (default: http://localhost:11434)\n")

        default_url = "http://localhost:11434"

        # Check environment
        env_host = os.environ.get("OLLAMA_HOST")
        if env_host:
            default_url = env_host

        base_url = Prompt.ask("Enter Ollama Base URL", default=default_url)

        return {
            "providers": {
                "vllm": {
                    "api_base": base_url,
                    "api_key": "ollama"
                }
            }
        }
