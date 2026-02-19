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
