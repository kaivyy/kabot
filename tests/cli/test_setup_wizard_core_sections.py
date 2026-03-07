from __future__ import annotations

from pathlib import Path

from kabot.cli.setup_wizard import SetupWizard


def test_main_menu_disambiguates_skills_and_native_google():
    wizard = SetupWizard()

    choices = wizard._main_menu_choices()
    labels = {choice.value: str(choice.title) for choice in choices}

    assert labels["skills"] == "Skills (Configure & Install Plans)"
    assert labels["google"] == "Google Suite (Native Auth, no npm)"


def test_configure_workspace_back_from_action_menu(monkeypatch):
    wizard = SetupWizard()
    original_workspace = wizard.config.agents.defaults.workspace

    monkeypatch.setattr("kabot.cli.wizard.sections.core.ClackUI.clack_select", lambda *_, **__: None)
    monkeypatch.setattr(
        "kabot.cli.wizard.sections.core.Prompt.ask",
        lambda *_, **__: (_ for _ in ()).throw(AssertionError("Prompt.ask should not be called")),
    )
    monkeypatch.setattr(wizard, "_save_setup_state", lambda *_, **__: None)

    wizard._configure_workspace()

    assert wizard.config.agents.defaults.workspace == original_workspace


def test_configure_workspace_supports_back_keyword(monkeypatch):
    wizard = SetupWizard()
    original_workspace = wizard.config.agents.defaults.workspace

    monkeypatch.setattr("kabot.cli.wizard.sections.core.ClackUI.clack_select", lambda *_, **__: "set")
    monkeypatch.setattr("kabot.cli.wizard.sections.core.Prompt.ask", lambda *_, **__: "back")
    monkeypatch.setattr(wizard, "_save_setup_state", lambda *_, **__: None)

    wizard._configure_workspace()

    assert wizard.config.agents.defaults.workspace == original_workspace


def test_configure_google_back_before_auth_flow(monkeypatch):
    wizard = SetupWizard()

    monkeypatch.setattr("kabot.cli.wizard.sections.core.ClackUI.clack_select", lambda *_, **__: None)
    monkeypatch.setattr(
        "kabot.auth.google_auth.GoogleAuthManager",
        lambda: (_ for _ in ()).throw(AssertionError("GoogleAuthManager should not be constructed")),
    )

    wizard._configure_google()


def test_configure_google_explains_native_no_npm(monkeypatch, capsys):
    wizard = SetupWizard()

    monkeypatch.setattr("kabot.cli.wizard.sections.core.ClackUI.clack_select", lambda *_, **__: None)

    wizard._configure_google()

    output = capsys.readouterr().out
    assert "Setup native Google Suite integration" in output
    assert "No npm, Node.js skill install, or gog setup is required here." in output


def test_configure_google_keep_existing_credentials_returns_without_path_prompt(monkeypatch):
    wizard = SetupWizard()

    class _DummyTokenPath:
        def exists(self) -> bool:
            return True

    class _DummyGoogleAuthManager:
        def __init__(self):
            self.token_path = _DummyTokenPath()
            self.credentials_path = Path("unused-google-credentials.json")

        def get_credentials(self):
            raise AssertionError("get_credentials should not run when keeping existing credentials")

    selections = iter(["auth", "keep"])

    monkeypatch.setattr(
        "kabot.cli.wizard.sections.core.ClackUI.clack_select",
        lambda *_, **__: next(selections),
    )
    monkeypatch.setattr("kabot.auth.google_auth.GoogleAuthManager", _DummyGoogleAuthManager)
    monkeypatch.setattr(
        "kabot.cli.wizard.sections.core.questionary.path",
        lambda *_, **__: (_ for _ in ()).throw(AssertionError("questionary.path should not be called")),
    )

    wizard._configure_google()


def test_configure_workspace_auto_creates_bootstrap_templates(monkeypatch, tmp_path):
    wizard = SetupWizard()
    target_workspace = tmp_path / "workspace-auto"

    monkeypatch.setattr("kabot.cli.wizard.sections.core.ClackUI.clack_select", lambda *_, **__: "set")
    monkeypatch.setattr("kabot.cli.wizard.sections.core.Prompt.ask", lambda *_, **__: str(target_workspace))
    monkeypatch.setattr(wizard, "_save_setup_state", lambda *_, **__: None)
    monkeypatch.setattr(wizard, "_load_setup_state", lambda: {"user_selections": {}})
    monkeypatch.setattr(wizard, "_write_setup_state", lambda _state: None)

    wizard._configure_workspace()

    assert (target_workspace / "AGENTS.md").exists()
    assert (target_workspace / "SOUL.md").exists()
    assert (target_workspace / "USER.md").exists()
    assert (target_workspace / "memory" / "MEMORY.md").exists()
