from typing import Dict, Any
import os
from rich.prompt import Prompt
from kabot.auth.handlers.base import AuthHandler

class OllamaHandler(AuthHandler):
    @property
    def name(self) -> str:
        return "Ollama (Local)"

    def authenticate(self) -> Dict[str, Any]:
        print("\n[bold]Ollama Setup[/bold]")
        print("Ensure Ollama is running (default: http://localhost:11434)")

        default_url = "http://localhost:11434"

        # Check environment
        env_host = os.environ.get("OLLAMA_HOST")
        if env_host:
            default_url = env_host

        base_url = Prompt.ask("Enter Ollama Base URL", default=default_url)

        # Ollama doesn't strictly need an API key for local use, but our schema might require the field.
        # We'll use "ollama" as a placeholder if needed, or empty string.
        return {
            "providers": {
                "vllm": { # Mapping to vllm/local provider in config
                    "api_base": base_url,
                    "api_key": "ollama"
                }
            }
        }
