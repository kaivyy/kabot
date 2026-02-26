"""Tests for agent configuration schema."""

import time

import pytest

from kabot.config.schema import (
    AgentDefaults,
    AgentModelConfig,
    AgentsConfig,
    AuthProfile,
    Config,
    MemoryConfig,
    ProviderConfig,
    ProvidersConfig,
)


def test_agent_config_schema():
    """Test AgentConfig schema with all fields."""
    from kabot.config.schema import AgentConfig

    config = AgentConfig(
        id="work",
        name="Work Agent",
        model="openai/gpt-4o",
        workspace="~/.kabot/workspace-work"
    )
    assert config.id == "work"
    assert config.name == "Work Agent"
    assert config.model == "openai/gpt-4o"
    assert config.workspace == "~/.kabot/workspace-work"
    assert config.default is False


def test_agent_config_minimal():
    """Test AgentConfig with minimal required fields."""
    from kabot.config.schema import AgentConfig

    config = AgentConfig(id="personal")
    assert config.id == "personal"
    assert config.name == ""
    assert config.model is None
    assert config.workspace is None
    assert config.default is False


def test_agent_config_default_flag():
    """Test AgentConfig with default flag set."""
    from kabot.config.schema import AgentConfig

    config = AgentConfig(id="main", default=True)
    assert config.id == "main"
    assert config.default is True


def test_agents_config_with_list():
    """Test AgentsConfig with list of agents."""
    from kabot.config.schema import AgentConfig, AgentsConfig

    agents = AgentsConfig(
        agents=[
            AgentConfig(id="work", name="Work", model="openai/gpt-4o"),
            AgentConfig(id="personal", name="Personal", model="anthropic/claude-sonnet-4-5")
        ]
    )
    assert len(agents.agents) == 2
    assert agents.agents[0].id == "work"
    assert agents.agents[1].id == "personal"


def test_agents_config_empty_list():
    """Test AgentsConfig with empty list (default)."""
    from kabot.config.schema import AgentsConfig

    agents = AgentsConfig()
    assert len(agents.agents) == 0
    assert isinstance(agents.agents, list)


def test_provider_normalizes_openai_gpt53_codex_to_codex():
    cfg = Config(
        agents=AgentsConfig(defaults=AgentDefaults(model="openai/gpt-5.3-codex")),
        providers=ProvidersConfig(
            openai=ProviderConfig(api_key="sk-openai"),
            openai_codex=ProviderConfig(
                profiles={"default": AuthProfile(name="default", oauth_token="tok", token_type="oauth")},
                active_profile="default",
            ),
        ),
    )
    assert cfg.get_provider_name("openai/gpt-5.3-codex") == "openai-codex"


def test_provider_does_not_normalize_openai_gpt52_codex():
    cfg = Config(
        agents=AgentsConfig(defaults=AgentDefaults(model="openai/gpt-5.2-codex")),
        providers=ProvidersConfig(
            openai=ProviderConfig(api_key="sk-openai"),
            openai_codex=ProviderConfig(
                profiles={"default": AuthProfile(name="default", oauth_token="tok", token_type="oauth")},
                active_profile="default",
            ),
        ),
    )
    assert cfg.get_provider_name("openai/gpt-5.2-codex") == "openai"


def test_defaults_model_object_uses_primary_for_matching():
    cfg = Config(
        agents=AgentsConfig(
            defaults=AgentDefaults(
                model=AgentModelConfig(
                    primary="openai/gpt-5.3-codex",
                    fallbacks=["openai/gpt-5.2-codex"],
                )
            )
        ),
        providers=ProvidersConfig(
            openai=ProviderConfig(api_key="sk-openai"),
            openai_codex=ProviderConfig(
                profiles={"default": AuthProfile(name="default", oauth_token="tok", token_type="oauth")},
                active_profile="default",
            ),
        ),
    )
    assert cfg.get_provider_name() == "openai-codex"


def test_provider_match_accepts_setup_token_profile_credentials():
    cfg = Config(
        agents=AgentsConfig(defaults=AgentDefaults(model="anthropic/claude-sonnet-4-5")),
        providers=ProvidersConfig(
            anthropic=ProviderConfig(
                profiles={
                    "default": AuthProfile(
                        name="default",
                        setup_token="sk-ant-oat01-example",
                        token_type="token",
                    )
                },
                active_profile="default",
            ),
        ),
    )
    assert cfg.get_provider_name("anthropic/claude-sonnet-4-5") == "anthropic"


def test_provider_match_supports_mistral():
    cfg = Config(
        agents=AgentsConfig(defaults=AgentDefaults(model="mistral/mistral-large-latest")),
        providers=ProvidersConfig(
            mistral=ProviderConfig(
                api_key="mistral-key",
            ),
        ),
    )
    assert cfg.get_provider_name("mistral/mistral-large-latest") == "mistral"


def test_provider_match_supports_kilocode():
    cfg = Config(
        agents=AgentsConfig(defaults=AgentDefaults(model="kilocode/anthropic/claude-opus-4.6")),
        providers=ProvidersConfig(
            kilocode=ProviderConfig(
                api_key="kilo-key",
                api_base="https://api.kilo.ai/api/gateway/",
            ),
        ),
    )
    assert cfg.get_provider_name("kilocode/anthropic/claude-opus-4.6") == "kilocode"


def test_provider_match_supports_synthetic():
    cfg = Config(
        agents=AgentsConfig(defaults=AgentDefaults(model="synthetic/hf:MiniMaxAI/MiniMax-M2.1")),
        providers=ProvidersConfig(
            synthetic=ProviderConfig(
                api_key="synthetic-key",
                api_base="https://api.synthetic.new/anthropic",
            ),
        ),
    )
    assert cfg.get_provider_name("synthetic/hf:MiniMaxAI/MiniMax-M2.1") == "synthetic"


def test_provider_match_supports_cloudflare_ai_gateway():
    cfg = Config(
        agents=AgentsConfig(defaults=AgentDefaults(model="cloudflare-ai-gateway/claude-sonnet-4-5")),
        providers=ProvidersConfig(
            cloudflare_ai_gateway=ProviderConfig(
                api_key="cf-key",
                api_base="https://gateway.ai.cloudflare.com/v1/account/gateway/anthropic",
            ),
        ),
    )
    assert cfg.get_provider_name("cloudflare-ai-gateway/claude-sonnet-4-5") == "cloudflare-ai-gateway"


def test_get_api_key_returns_setup_token_from_active_profile():
    cfg = Config(
        agents=AgentsConfig(defaults=AgentDefaults(model="anthropic/claude-sonnet-4-5")),
        providers=ProvidersConfig(
            anthropic=ProviderConfig(
                profiles={
                    "default": AuthProfile(
                        name="default",
                        setup_token="sk-ant-oat01-example",
                        token_type="token",
                    )
                },
                active_profile="default",
            ),
        ),
    )
    assert cfg.get_api_key("anthropic/claude-sonnet-4-5") == "sk-ant-oat01-example"


@pytest.mark.asyncio
async def test_get_api_key_async_uses_default_model_provider_for_refresh(monkeypatch):
    cfg = Config(
        agents=AgentsConfig(
            defaults=AgentDefaults(
                model=AgentModelConfig(primary="openai-codex/gpt-5.3-codex")
            )
        ),
        providers=ProvidersConfig(
            openai_codex=ProviderConfig(
                profiles={
                    "default": AuthProfile(
                        name="default",
                        oauth_token="old-token",
                        refresh_token="refresh-token",
                        expires_at=1,
                        token_type="oauth",
                    )
                },
                active_profile="default",
            ),
        ),
    )

    called: dict[str, str] = {}

    class _DummyRefresh:
        async def refresh(self, provider: str, profile: AuthProfile):
            called["provider"] = provider
            updated = profile.model_copy()
            updated.oauth_token = "new-token"
            updated.expires_at = int(time.time() * 1000) + 3_600_000
            return updated

    monkeypatch.setattr("kabot.auth.refresh.TokenRefreshService", lambda: _DummyRefresh())

    token = await cfg.get_api_key_async()

    assert token == "new-token"
    assert called["provider"] == "openai-codex"


def test_config_has_memory_defaults():
    cfg = Config()
    assert cfg.memory.backend == "hybrid"
    assert cfg.memory.embedding_provider == "sentence"
    assert cfg.memory.enable_hybrid_search is True


def test_config_memory_can_be_overridden():
    cfg = Config(memory=MemoryConfig(backend="sqlite_only", embedding_provider="ollama"))
    assert cfg.memory.backend == "sqlite_only"
    assert cfg.memory.embedding_provider == "ollama"

