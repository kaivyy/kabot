"""SetupWizard section methods: model_auth."""

from __future__ import annotations

from typing import Optional

from rich.console import Console

console = Console()

def _sync_provider_credentials_from_disk(self) -> None:
    """Merge provider credentials saved by AuthManager into in-memory wizard config."""
    try:
        from kabot.cli import setup_wizard as setup_wizard_module

        disk_config = setup_wizard_module.load_config()
        self.config.providers = disk_config.providers.model_copy(deep=True)
    except Exception as e:
        console.print(f"|  [yellow]Warning: Could not sync provider credentials: {e}[/yellow]")

def _provider_has_credentials(self, provider_config) -> bool:
    """Check whether a provider config has any API key/OAuth credentials."""
    if not provider_config:
        return False
    if provider_config.api_key or getattr(provider_config, "setup_token", None):
        return True
    if provider_config.active_profile in provider_config.profiles:
        active = provider_config.profiles[provider_config.active_profile]
        if active.api_key or active.oauth_token or active.setup_token:
            return True
    for profile in provider_config.profiles.values():
        if profile.api_key or profile.oauth_token or profile.setup_token:
            return True
    return False

def _provider_config_key_for_auth(self, provider_id: str) -> Optional[str]:
    """Map auth provider IDs to config provider field names."""
    provider_mapping = {
        "openai": "openai",
        "anthropic": "anthropic",
        "google": "gemini",
        "ollama": "vllm",
        "groq": "groq",
        "kimi": "moonshot",
        "minimax": "minimax",
        "mistral": "mistral",
        "kilocode": "kilocode",
        "together": "together",
        "venice": "venice",
        "huggingface": "huggingface",
        "qianfan": "qianfan",
        "nvidia": "nvidia",
        "xai": "xai",
        "cerebras": "cerebras",
        "opencode": "opencode",
        "xiaomi": "xiaomi",
        "volcengine": "volcengine",
        "byteplus": "byteplus",
        "synthetic": "synthetic",
        "cloudflare-ai-gateway": "cloudflare_ai_gateway",
        "vercel-ai-gateway": "vercel_ai_gateway",
        "openrouter": "openrouter",
        "aihubmix": "aihubmix",
        "deepseek": "deepseek",
        "zhipu": "zhipu",
        "dashscope": "dashscope",
        "vllm": "vllm",
        "letta": "letta",
    }
    return provider_mapping.get(provider_id)

def _provider_has_saved_credentials(self, provider_id: str) -> bool:
    """Return True when provider already has usable API key/OAuth in config."""
    # OpenAI login may store OAuth in openai_codex profile.
    if provider_id == "openai":
        openai_cfg = getattr(self.config.providers, "openai", None)
        codex_cfg = getattr(self.config.providers, "openai_codex", None)
        return self._provider_has_credentials(openai_cfg) or self._provider_has_credentials(codex_cfg)

    config_key = self._provider_config_key_for_auth(provider_id)
    if not config_key:
        return False
    provider_cfg = getattr(self.config.providers, config_key, None)
    return self._provider_has_credentials(provider_cfg)

def _providers_with_saved_credentials(self) -> list[str]:
    """Return auth provider ids that currently have saved credentials."""
    from kabot.auth.menu import AUTH_PROVIDERS

    return [provider_id for provider_id in AUTH_PROVIDERS if self._provider_has_saved_credentials(provider_id)]

def _model_allowed_by_provider_credentials(self, model_id: str, allowed_provider_ids: list[str]) -> bool:
    """Return True when model_id belongs to any authenticated provider scope."""
    if not allowed_provider_ids:
        return True
    return any(self._model_matches_provider(model_id, provider_id) for provider_id in allowed_provider_ids)

def _current_model_display(self) -> str:
    """Return concise current primary model label for UI."""
    current = self.config.agents.defaults.model
    primary = getattr(current, "primary", None)
    if isinstance(primary, str) and primary.strip():
        return primary
    return str(current)

def _provider_model_prefixes(self, provider_id: str) -> list[str]:
    """Map auth provider IDs to model ID prefixes used in the registry."""
    mapping = {
        "openai": ["openai", "openai-codex"],
        "anthropic": ["anthropic"],
        "google": ["google", "google-gemini-cli"],
        "ollama": ["ollama", "vllm"],
        "groq": ["groq"],
        "kimi": ["moonshot", "kimi-coding"],
        "minimax": ["minimax", "minimax-portal"],
        "mistral": ["mistral"],
        "kilocode": ["kilocode"],
        "together": ["together"],
        "venice": ["venice"],
        "huggingface": ["huggingface"],
        "qianfan": ["qianfan"],
        "nvidia": ["nvidia"],
        "xai": ["xai", "x-ai"],
        "cerebras": ["cerebras"],
        "opencode": ["opencode"],
        "xiaomi": ["xiaomi"],
        "volcengine": ["volcengine", "volcengine-plan"],
        "byteplus": ["byteplus", "byteplus-plan"],
        "synthetic": ["synthetic"],
        "cloudflare-ai-gateway": ["cloudflare-ai-gateway"],
        "vercel-ai-gateway": ["vercel-ai-gateway"],
        "deepseek": ["deepseek"],
        "zhipu": ["zai", "zhipu", "z-ai"],
        "dashscope": ["qwen-portal", "dashscope"],
        "openrouter": ["openrouter"],
        "aihubmix": ["aihubmix"],
        "letta": ["letta"],
        "vllm": ["vllm", "ollama"],
    }
    return mapping.get(provider_id, [provider_id])

def _model_matches_provider(self, model_id: str, provider_id: Optional[str]) -> bool:
    """Return True if model belongs to the selected provider scope."""
    if not provider_id:
        return True

    model_lower = (model_id or "").lower().strip()
    for prefix in self._provider_model_prefixes(provider_id):
        if model_lower.startswith(f"{prefix.lower()}/"):
            return True
    return False

def _normalize_scoped_manual_model_input(self, user_input: str, provider_id: Optional[str]) -> str:
    """Normalize manual model input when picker is scoped to a provider."""
    value = (user_input or "").strip()
    if not value or not provider_id:
        return value

    provider_prefix = f"{provider_id.lower()}/"
    if value.lower().startswith(provider_prefix):
        return value

    # Allow vendor/model style input inside provider-scoped picker.
    if "/" in value:
        return f"{provider_id}/{value}"

    return value

def _build_model_chain_from_provider_selections(
    self,
    provider_models: dict[str, str],
    provider_order: list[str],
) -> list[str]:
    """Build ordered model chain from user selections (primary -> fallbacks)."""
    chain: list[str] = []
    seen: set[str] = set()

    for provider_id in provider_order:
        model_id = str(provider_models.get(provider_id, "")).strip()
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        chain.append(model_id)

    for provider_id, model_id_raw in provider_models.items():
        if provider_id in provider_order:
            continue
        model_id = str(model_id_raw).strip()
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        chain.append(model_id)

    return chain

def _apply_model_chain_from_provider_selections(
    self,
    provider_models: dict[str, str],
    provider_order: list[str],
) -> bool:
    """Apply selected provider-model chain to config without hardcoded fallbacks."""
    from kabot.config.schema import AgentModelConfig

    chain = self._build_model_chain_from_provider_selections(provider_models, provider_order)
    if not chain:
        return False

    primary = chain[0]
    fallbacks = chain[1:]
    current = self.config.agents.defaults.model

    if isinstance(current, AgentModelConfig):
        if current.primary == primary and list(current.fallbacks or []) == fallbacks:
            return False
    elif current == primary and not fallbacks:
        return False

    self.config.agents.defaults.model = AgentModelConfig(primary=primary, fallbacks=fallbacks)
    return True

def _apply_post_login_defaults(self, provider_id: str) -> bool:
    """
    Legacy hook retained for compatibility.

    Hardcoded default/fallback injection is intentionally disabled.
    """
    return False

def _recommended_auto_model_chain(self) -> list[str]:
    """Return chain based on wizard user selections, not hardcoded provider defaults."""
    state = self._load_setup_state()
    user_selections = state.get("user_selections", {})
    provider_models = user_selections.get("provider_models", {}) or {}
    provider_order = user_selections.get("provider_model_order", []) or []
    if not isinstance(provider_models, dict) or not isinstance(provider_order, list):
        return []
    return self._build_model_chain_from_provider_selections(provider_models, provider_order)

def _apply_auto_default_model_chain(self) -> bool:
    """Apply selection-based chain if available (no static fallback model list)."""
    state = self._load_setup_state()
    user_selections = state.get("user_selections", {})
    provider_models = user_selections.get("provider_models", {}) or {}
    provider_order = user_selections.get("provider_model_order", []) or []
    if not isinstance(provider_models, dict) or not isinstance(provider_order, list):
        return False
    return self._apply_model_chain_from_provider_selections(provider_models, provider_order)

def _show_auto_model_chain_summary(self, updated: bool) -> None:
    """Render concise summary for user-selected model chain."""
    from kabot.config.schema import AgentModelConfig

    model = self.config.agents.defaults.model
    if isinstance(model, AgentModelConfig):
        primary = model.primary
        fallbacks = list(model.fallbacks or [])
    else:
        primary = str(model)
        fallbacks = []

    status = "updated" if updated else "kept"
    console.print(f"|  [green]Model chain {status} from user selections.[/green]")
    console.print(f"|  primary: [cyan]{primary}[/cyan]")
    if fallbacks:
        console.print(f"|  fallbacks: [dim]{', '.join(fallbacks)}[/dim]")
