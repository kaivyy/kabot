from kabot.cli.commands import _make_provider
from kabot.config.schema import (
    AgentDefaults,
    AgentModelConfig,
    AgentsConfig,
    AuthProfile,
    Config,
    ProviderConfig,
    ProvidersConfig,
)


def test_make_provider_supports_agent_model_config_and_merges_fallbacks(monkeypatch):
    captured: dict[str, object] = {}

    class _DummyProvider:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("kabot.providers.litellm_provider.LiteLLMProvider", _DummyProvider)

    cfg = Config(
        agents=AgentsConfig(
            defaults=AgentDefaults(
                model=AgentModelConfig(
                    primary="openai-codex/gpt-5.3-codex",
                    fallbacks=["openai/gpt-5.2-codex"],
                )
            )
        ),
        providers=ProvidersConfig(
            openai_codex=ProviderConfig(
                fallbacks=["openai/gpt-4o-mini"],
                profiles={
                    "default": AuthProfile(
                        name="default",
                        oauth_token="oauth-token",
                        token_type="oauth",
                    )
                },
                active_profile="default",
            )
        ),
    )

    _make_provider(cfg)

    assert captured["default_model"] == "openai-codex/gpt-5.3-codex"
    assert captured["api_key"] == "oauth-token"
    assert captured["fallbacks"] == [
        "openai/gpt-5.2-codex",
        "openai/gpt-4o-mini",
    ]


def test_make_provider_auto_adds_groq_fallback_when_chain_empty_and_groq_credentials_exist(monkeypatch):
    captured: dict[str, object] = {}

    class _DummyProvider:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("kabot.providers.litellm_provider.LiteLLMProvider", _DummyProvider)

    cfg = Config(
        agents=AgentsConfig(
            defaults=AgentDefaults(model="openai-codex/gpt-5.3-codex")
        ),
        providers=ProvidersConfig(
            openai_codex=ProviderConfig(
                profiles={
                    "default": AuthProfile(
                        name="default",
                        oauth_token="oauth-token",
                        token_type="oauth",
                    )
                },
                active_profile="default",
            ),
            groq=ProviderConfig(api_key="groq-key"),
        ),
    )

    _make_provider(cfg)

    assert captured["default_model"] == "openai-codex/gpt-5.3-codex"
    assert captured["fallbacks"] == [
        "groq/meta-llama/llama-4-scout-17b-16e-instruct",
    ]
    assert captured["provider_api_keys"]["openai-codex"] == "oauth-token"
    assert captured["provider_api_keys"]["groq"] == "groq-key"


def test_make_provider_does_not_auto_add_groq_fallback_when_non_openai_primary(monkeypatch):
    captured: dict[str, object] = {}

    class _DummyProvider:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("kabot.providers.litellm_provider.LiteLLMProvider", _DummyProvider)

    cfg = Config(
        agents=AgentsConfig(
            defaults=AgentDefaults(model="anthropic/claude-3-5-sonnet-20241022")
        ),
        providers=ProvidersConfig(
            anthropic=ProviderConfig(api_key="anthropic-key"),
            groq=ProviderConfig(api_key="groq-key"),
        ),
    )

    _make_provider(cfg)

    assert captured["default_model"] == "anthropic/claude-3-5-sonnet-20241022"
    assert captured["fallbacks"] == []


def test_make_provider_does_not_auto_add_groq_fallback_without_groq_credentials(monkeypatch):
    captured: dict[str, object] = {}

    class _DummyProvider:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("kabot.providers.litellm_provider.LiteLLMProvider", _DummyProvider)

    cfg = Config(
        agents=AgentsConfig(
            defaults=AgentDefaults(model="openai-codex/gpt-5.3-codex")
        ),
        providers=ProvidersConfig(
            openai_codex=ProviderConfig(
                profiles={
                    "default": AuthProfile(
                        name="default",
                        oauth_token="oauth-token",
                        token_type="oauth",
                    )
                },
                active_profile="default",
            ),
            groq=ProviderConfig(api_key=""),
        ),
    )

    _make_provider(cfg)

    assert captured["default_model"] == "openai-codex/gpt-5.3-codex"
    assert captured["fallbacks"] == []
