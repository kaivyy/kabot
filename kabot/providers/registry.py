"""
Provider Registry — single source of truth for LLM provider metadata.
"""

from __future__ import annotations

import importlib
import pkgutil
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from kabot.providers.models import ModelMetadata, ModelPricing


@dataclass(frozen=True)
class ProviderSpec:
    # identity
    name: str                       # config field name, e.g. "dashscope"
    keywords: tuple[str, ...]       # model-name keywords for matching (lowercase)
    env_key: str                    # LiteLLM env var, e.g. "DASHSCOPE_API_KEY"
    display_name: str = ""          # shown in `kabot status`

    # model prefixing
    litellm_prefix: str = ""                 # "dashscope" → model becomes "dashscope/{model}"
    skip_prefixes: tuple[str, ...] = ()      # don't prefix if model already starts with these 

    # extra env vars
    env_extras: tuple[tuple[str, str], ...] = ()

    # gateway / local detection
    is_gateway: bool = False
    is_local: bool = False
    detect_by_key_prefix: str = ""
    detect_by_base_keyword: str = ""
    default_api_base: str = ""

    # gateway behavior
    strip_model_prefix: bool = False

    # per-model param overrides
    model_overrides: tuple[tuple[str, dict[str, Any]], ...] = ()

    @property
    def label(self) -> str:
        return self.display_name or self.name.title()


class ModelRegistry:
    """Central registry for all AI models and their metadata."""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ModelRegistry, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db=None):
        if self._initialized:
            return
        self._models: Dict[str, ModelMetadata] = {}
        self._aliases: Dict[str, str] = {} # Alias -> Full ID
        self._db = db
        self._initialized = True
        self.load_catalog()
        if self._db:
            self.load_scanned_models()
        self.load_plugins()

    def register_alias(self, alias: str, model_id: str):
        """Register a model alias."""
        self._aliases[alias] = model_id

    def resolve_alias(self, alias: str) -> Optional[str]:
        """Resolve an alias to its full model ID. Returns None if not found."""
        return self._aliases.get(alias)

    def get_all_aliases(self) -> Dict[str, str]:
        """Get all registered aliases. Returns a copy to prevent external modification."""
        return self._aliases.copy()

    def resolve(self, name: str, user_aliases: Optional[Dict[str, str]] = None) -> str:
        """
        Resolve a name (alias, short ID, or full ID) to a full model ID.
        
        Priority:
        1. User-defined aliases (from config)
        2. Registry aliases (from plugins/catalog)
        3. Registry short ID lookup
        4. Return as-is (Full ID or unknown)
        """
        # 1. User aliases
        if user_aliases and name in user_aliases:
            return user_aliases[name]
            
        # 2. Registry aliases
        if name in self._aliases:
            return self._aliases[name]
            
        # 3. Registry short ID
        model = self.get_model(name)
        if model:
            return model.id
            
        # 4. Fallback
        return name

    def load_catalog(self):
        """Load the static catalog into the registry."""
        try:
            from kabot.providers.catalog import populate_registry
            populate_registry(self)
        except ImportError:
            pass

    def load_scanned_models(self):
        """Load scanned models from the database."""
        if not self._db:
            return
        
        scanned = self._db.get_scanned_models()
        for m in scanned:
            metadata = ModelMetadata(
                id=m["id"],
                name=m["name"],
                provider=m["provider"],
                context_window=m["context_window"],
                max_output=m["max_output"],
                pricing=ModelPricing(
                    input_1m=m["pricing_input"],
                    output_1m=m["pricing_output"]
                ),
                capabilities=m["capabilities"],
                is_premium=bool(m["is_premium"])
            )
            self.register(metadata)

    def load_plugins(self):
        """Automatically discover and load plugins from kabot.providers.plugins."""
        import kabot.providers.plugins as plugins_pkg
        
        # Get the path to the plugins package
        pkg_path = os.path.dirname(plugins_pkg.__file__)
        
        for _, name, is_pkg in pkgutil.iter_modules([pkg_path]):
            if is_pkg:
                module_name = f"kabot.providers.plugins.{name}"
                try:
                    module = importlib.import_module(module_name)
                    # Look for a register function in the plugin
                    if hasattr(module, "register"):
                        module.register(self)
                except Exception as e:
                    # Log error or handle gracefully
                    pass

    def register(self, metadata: ModelMetadata):
        """Register a new model."""
        self._models[metadata.id] = metadata

    def get_model(self, model_id: str) -> Optional[ModelMetadata]:
        """Retrieve model metadata by ID."""
        # Try full ID first
        if model_id in self._models:
            return self._models[model_id]
        
        # Try short ID (e.g. "gpt-4o" matches "openai/gpt-4o")
        for metadata in self._models.values():
            if metadata.short_id == model_id:
                return metadata
        return None

    def list_models(self) -> List[ModelMetadata]:
        """Return a list of all registered models."""
        return list(self._models.values())

    def get_providers(self) -> Dict[str, int]:
        """Return a dictionary of provider names and their model counts."""
        providers = {}
        for m in self._models.values():
            providers[m.provider] = providers.get(m.provider, 0) + 1
        return providers

    def clear(self):
        """Clear all registered models."""
        self._models = {}


# ---------------------------------------------------------------------------
# PROVIDERS — the registry. Order = priority.
# ---------------------------------------------------------------------------

PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        name="openrouter",
        keywords=("openrouter",),
        env_key="OPENROUTER_API_KEY",
        display_name="OpenRouter",
        litellm_prefix="openrouter",
        is_gateway=True,
        detect_by_key_prefix="sk-or-",
        detect_by_base_keyword="openrouter",
        default_api_base="https://openrouter.ai/api/v1",
    ),
    ProviderSpec(
        name="aihubmix",
        keywords=("aihubmix",),
        env_key="OPENAI_API_KEY",
        display_name="AiHubMix",
        litellm_prefix="openai",
        is_gateway=True,
        detect_by_base_keyword="aihubmix",
        default_api_base="https://aihubmix.com/v1",
        strip_model_prefix=True,
    ),
    ProviderSpec(
        name="anthropic",
        keywords=("anthropic", "claude"),
        env_key="ANTHROPIC_API_KEY",
        display_name="Anthropic",
    ),
    ProviderSpec(
        name="openai",
        keywords=("openai", "gpt"),
        env_key="OPENAI_API_KEY",
        display_name="OpenAI",
    ),
    ProviderSpec(
        name="deepseek",
        keywords=("deepseek",),
        env_key="DEEPSEEK_API_KEY",
        display_name="DeepSeek",
        litellm_prefix="deepseek",
        skip_prefixes=("deepseek/",),
    ),
    ProviderSpec(
        name="gemini",
        keywords=("gemini",),
        env_key="GEMINI_API_KEY",
        display_name="Gemini",
        litellm_prefix="gemini",
        skip_prefixes=("gemini/",),
    ),
    ProviderSpec(
        name="zhipu",
        keywords=("zhipu", "glm", "zai"),
        env_key="ZAI_API_KEY",
        display_name="Zhipu AI",
        litellm_prefix="zai",
        skip_prefixes=("zhipu/", "zai/", "openrouter/", "hosted_vllm/"),
        env_extras=(("ZHIPUAI_API_KEY", "{api_key}"),),
    ),
    ProviderSpec(
        name="dashscope",
        keywords=("qwen", "dashscope"),
        env_key="DASHSCOPE_API_KEY",
        display_name="DashScope",
        litellm_prefix="dashscope",
        skip_prefixes=("dashscope/", "openrouter/"),
    ),
    ProviderSpec(
        name="moonshot",
        keywords=("moonshot", "kimi"),
        env_key="MOONSHOT_API_KEY",
        display_name="Moonshot",
        litellm_prefix="moonshot",
        skip_prefixes=("moonshot/", "openrouter/"),
        env_extras=(("MOONSHOT_API_BASE", "{api_base}"),),
        default_api_base="https://api.moonshot.ai/v1",
        model_overrides=(("kimi-k2.5", {"temperature": 1.0}),),
    ),
    ProviderSpec(
        name="minimax",
        keywords=("minimax", "abab"),
        env_key="MINIMAX_API_KEY",
        display_name="MiniMax",
        litellm_prefix="minimax",
        skip_prefixes=("minimax/", "openrouter/"),
        env_extras=(("MINIMAX_API_BASE", "{api_base}"),),
        default_api_base="https://api.minimax.chat/v1",
    ),
    ProviderSpec(
        name="letta",
        keywords=("letta",),
        env_key="LETTA_API_KEY",
        display_name="Letta",
        is_gateway=True,
        is_local=True,
        detect_by_base_keyword="letta",
        default_api_base="http://localhost:8283",
    ),
    ProviderSpec(
        name="vllm",
        keywords=("vllm",),
        env_key="HOSTED_VLLM_API_KEY",
        display_name="vLLM/Local",
        litellm_prefix="hosted_vllm",
        is_local=True,
    ),
    ProviderSpec(
        name="groq",
        keywords=("groq",),
        env_key="GROQ_API_KEY",
        display_name="Groq",
        litellm_prefix="groq",
        skip_prefixes=("groq/",),
    ),
)


def find_by_model(model: str) -> ProviderSpec | None:
    model_lower = model.lower()
    for spec in PROVIDERS:
        if spec.is_gateway or spec.is_local:
            continue
        if any(kw in model_lower for kw in spec.keywords):
            return spec
    return None


def find_gateway(
    provider_name: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
) -> ProviderSpec | None:
    if provider_name:
        spec = find_by_name(provider_name)
        if spec and (spec.is_gateway or spec.is_local):
            return spec
    for spec in PROVIDERS:
        if spec.detect_by_key_prefix and api_key and api_key.startswith(spec.detect_by_key_prefix):
            return spec
        if spec.detect_by_base_keyword and api_base and spec.detect_by_base_keyword in api_base:
            return spec
    return None


def find_by_name(name: str) -> ProviderSpec | None:
    for spec in PROVIDERS:
        if spec.name == name:
            return spec
    return None
