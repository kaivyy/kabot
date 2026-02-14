"""Generic API Key authentication handlers."""

from typing import Dict, Any, Optional
import os
from rich.prompt import Prompt
from rich.console import Console
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

console = Console()


class SimpleKeyHandler(AuthHandler):
    """Base handler for simple API Key authentication."""

    def __init__(self, provider_id: str, provider_name: str, env_var: str, help_url: str):
        self.provider_id = provider_id
        self._name = provider_name
        self.env_var = env_var
        self.help_url = help_url

    @property
    def name(self) -> str:
        return f"{self._name} (API Key)"

    def authenticate(self) -> Dict[str, Any]:
        """Execute API key authentication flow."""
        console.print(f"\n[bold]{self._name} API Key Setup[/bold]")
        console.print(f"Get your API key from: [link={self.help_url}]{self.help_url}[/link]\n")

        # Check env var first
        env_key = os.environ.get(self.env_var)
        if env_key:
            use_env = Prompt.ask(
                f"Found {self.env_var} in environment ({env_key[:8]}...). Use this?",
                choices=["y", "n"],
                default="y"
            )
            if use_env == "y":
                return {"providers": {self.provider_id: {"api_key": env_key}}}

        # Manual input
        api_key = secure_input(f"Enter {self._name} API Key")

        if not api_key:
            return None

        # Build config fragment (handle nested structures if needed, but usually flat under provider)
        return {"providers": {self.provider_id: {"api_key": api_key}}}


class DeepSeekKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "deepseek",
            "DeepSeek",
            "DEEPSEEK_API_KEY",
            "https://platform.deepseek.com/api_keys"
        )


class GroqKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "groq",
            "Groq",
            "GROQ_API_KEY",
            "https://console.groq.com/keys"
        )


class OpenRouterKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "openrouter",
            "OpenRouter",
            "OPENROUTER_API_KEY",
            "https://openrouter.ai/keys"
        )


class ZhipuKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "zhipu",
            "Zhipu AI (GLM)",
            "ZHIPUAI_API_KEY",
            "https://open.bigmodel.cn/usercenter/apikeys"
        )


class DashScopeKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "dashscope",
            "DashScope (Qwen)",
            "DASHSCOPE_API_KEY",
            "https://dashscope.console.aliyun.com/apiKey"
        )


class AiHubMixKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "aihubmix",
            "AIHubMix",
            "AIHUBMIX_API_KEY",
            "https://aihubmix.com/"
        )


class LettaKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "letta",
            "Letta",
            "LETTA_API_KEY",
            "http://localhost:8283"
        )

    def authenticate(self) -> Dict[str, Any]:
        """Override to also ask for API Base."""
        data = super().authenticate()
        if not data:
            return None
            
        # Also ask for API Base since mostly self-hosted
        api_base = Prompt.ask("Enter Letta API Base URL", default="http://localhost:8283")
        data["providers"]["letta"]["api_base"] = api_base
        return data


class VLLMHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "vllm",
            "vLLM",
            "VLLM_API_KEY",
            "http://localhost:8000"
        )

    def authenticate(self) -> Dict[str, Any]:
        """Override to ask for API Base."""
        console.print(f"\n[bold]{self._name} Setup[/bold]")
        
        api_base = Prompt.ask("Enter vLLM API Base URL", default="http://localhost:8000/v1")
        api_key = secure_input("Enter API Key (optional)") or "EMPTY"
        
        return {
            "providers": {
                "vllm": {
                    "api_key": api_key,
                    "api_base": api_base
                }
            }
        }
