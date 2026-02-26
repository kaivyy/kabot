"""Generic API Key authentication handlers."""

import os
from typing import Any, Dict

from rich.console import Console
from rich.prompt import Prompt

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
        console.print("[dim]Paste key and press Enter. Input is visible.[/dim]")
        api_key = (Prompt.ask(f"Enter {self._name} API Key", password=False) or "").strip()

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


class MistralKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "mistral",
            "Mistral",
            "MISTRAL_API_KEY",
            "https://console.mistral.ai/api-keys"
        )


class KiloCodeKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "kilocode",
            "Kilo Gateway",
            "KILOCODE_API_KEY",
            "https://app.kilo.ai"
        )


class TogetherKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "together",
            "Together AI",
            "TOGETHER_API_KEY",
            "https://api.together.xyz/settings/api-keys"
        )


class VeniceKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "venice",
            "Venice AI",
            "VENICE_API_KEY",
            "https://venice.ai"
        )


class HuggingFaceKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "huggingface",
            "Hugging Face",
            "HF_TOKEN",
            "https://huggingface.co/settings/tokens"
        )


class QianfanKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "qianfan",
            "Qianfan",
            "QIANFAN_API_KEY",
            "https://console.bce.baidu.com/qianfan/ais/console/apiKey"
        )


class NvidiaKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "nvidia",
            "NVIDIA",
            "NVIDIA_API_KEY",
            "https://catalog.ngc.nvidia.com/"
        )


class XAIKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "xai",
            "xAI",
            "XAI_API_KEY",
            "https://x.ai"
        )


class CerebrasKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "cerebras",
            "Cerebras",
            "CEREBRAS_API_KEY",
            "https://inference.cerebras.ai"
        )


class OpenCodeKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "opencode",
            "OpenCode Zen",
            "OPENCODE_API_KEY",
            "https://opencode.ai"
        )


class XiaomiKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "xiaomi",
            "Xiaomi MiMo",
            "XIAOMI_API_KEY",
            "https://platform.xiaomimimo.com/#/console/api-keys"
        )


class VolcengineKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "volcengine",
            "Volcano Engine",
            "VOLCANO_ENGINE_API_KEY",
            "https://console.volcengine.com/ark"
        )


class BytePlusKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "byteplus",
            "BytePlus",
            "BYTEPLUS_API_KEY",
            "https://console.byteplus.com/ark"
        )


class SyntheticKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "synthetic",
            "Synthetic",
            "SYNTHETIC_API_KEY",
            "https://api.synthetic.new/"
        )


class CloudflareAIGatewayKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "cloudflare-ai-gateway",
            "Cloudflare AI Gateway",
            "CLOUDFLARE_AI_GATEWAY_API_KEY",
            "https://dash.cloudflare.com/"
        )

    def authenticate(self) -> Dict[str, Any]:
        """Ask API key plus account/gateway IDs to build API base URL."""
        data = super().authenticate()
        if not data:
            return None

        account_id = Prompt.ask("Enter Cloudflare Account ID", default="").strip()
        gateway_id = Prompt.ask("Enter Cloudflare Gateway ID", default="").strip()
        if account_id and gateway_id:
            api_base = f"https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/anthropic"
            data["providers"]["cloudflare-ai-gateway"]["api_base"] = api_base
        return data


class VercelAIGatewayKeyHandler(SimpleKeyHandler):
    def __init__(self):
        super().__init__(
            "vercel-ai-gateway",
            "Vercel AI Gateway",
            "AI_GATEWAY_API_KEY",
            "https://vercel.com/ai-gateway"
        )

    def authenticate(self) -> Dict[str, Any]:
        """Ask API key and optionally override API base URL."""
        data = super().authenticate()
        if not data:
            return None

        api_base = Prompt.ask(
            "Enter Vercel AI Gateway API Base URL",
            default="https://ai-gateway.vercel.sh/v1"
        ).strip()
        if api_base:
            data["providers"]["vercel-ai-gateway"]["api_base"] = api_base
        return data


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

