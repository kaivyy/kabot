import json
import shutil
from pathlib import Path

from kabot.cli.setup_wizard import SetupWizard
from kabot.config.schema import AgentModelConfig, AuthProfile


def test_openai_codex_default_model_order():
    wizard = SetupWizard()
    wizard.config.agents.defaults.model = "openai/gpt-4o"
    wizard.config.providers.openai_codex.profiles["default"] = AuthProfile(
        name="default",
        oauth_token="tok",
        token_type="oauth",
    )
    wizard.config.providers.openai_codex.active_profile = "default"

    changed = wizard._apply_post_login_defaults("openai")

    assert changed is True
    assert isinstance(wizard.config.agents.defaults.model, AgentModelConfig)
    assert wizard.config.agents.defaults.model.primary == "openai-codex/gpt-5.3-codex"
    assert wizard.config.agents.defaults.model.fallbacks == [
        "openai/gpt-5.2-codex",
        "openai/gpt-4o-mini",
    ]


def test_openai_codex_default_does_not_override_non_openai_model():
    wizard = SetupWizard()
    wizard.config.agents.defaults.model = "anthropic/claude-3-5-sonnet-20241022"
    wizard.config.providers.openai_codex.profiles["default"] = AuthProfile(
        name="default",
        oauth_token="tok",
        token_type="oauth",
    )
    wizard.config.providers.openai_codex.active_profile = "default"

    changed = wizard._apply_post_login_defaults("openai")

    assert changed is False
    assert wizard.config.agents.defaults.model == "anthropic/claude-3-5-sonnet-20241022"


def test_provider_has_credentials_accepts_setup_token():
    wizard = SetupWizard()
    wizard.config.providers.anthropic.profiles["default"] = AuthProfile(
        name="default",
        setup_token="sk-ant-oat01-example",
        token_type="token",
    )
    wizard.config.providers.anthropic.active_profile = "default"

    assert wizard._provider_has_credentials(wizard.config.providers.anthropic) is True


def test_sync_provider_credentials_from_disk_preserves_unsaved_config(monkeypatch):
    wizard = SetupWizard()
    wizard.config.agents.defaults.workspace = "~/my-local-workspace"

    disk_config = wizard.config.model_copy(deep=True)
    disk_config.providers.openai_codex.profiles["default"] = AuthProfile(
        name="default",
        oauth_token="tok",
        token_type="oauth",
    )
    disk_config.providers.openai_codex.active_profile = "default"

    monkeypatch.setattr("kabot.cli.setup_wizard.load_config", lambda: disk_config)

    wizard._sync_provider_credentials_from_disk()

    assert wizard.config.agents.defaults.workspace == "~/my-local-workspace"
    assert wizard.config.providers.openai_codex.profiles["default"].oauth_token == "tok"


def test_save_setup_state_serializes_agent_model_config(monkeypatch):
    test_home = Path.cwd() / ".tmp-test-home-setup-wizard"
    if test_home.exists():
        shutil.rmtree(test_home)
    test_home.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: test_home)

    wizard = SetupWizard()
    model_config = AgentModelConfig(
        primary="openai-codex/gpt-5.3-codex",
        fallbacks=["openai/gpt-5.2-codex"],
    )

    wizard._save_setup_state("auth", completed=True, default_model=model_config)

    state_file = test_home / ".kabot" / "setup-state.json"
    state = json.loads(state_file.read_text())

    assert state["sections"]["auth"]["default_model"]["primary"] == "openai-codex/gpt-5.3-codex"
    assert state["sections"]["auth"]["default_model"]["fallbacks"] == ["openai/gpt-5.2-codex"]
    shutil.rmtree(test_home, ignore_errors=True)
