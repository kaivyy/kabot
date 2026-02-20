from pathlib import Path

from kabot.cli.setup_wizard import SetupWizard


def test_set_openclaw_freedom_mode_enables_unrestricted_profile(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()

    wizard._set_openclaw_freedom_mode(True)

    assert wizard.config.tools.exec.auto_approve is True
    assert wizard.config.tools.restrict_to_workspace is False
    assert wizard.config.integrations.http_guard.enabled is False
    assert wizard.config.integrations.http_guard.block_private_networks is False
    assert wizard.config.integrations.http_guard.deny_hosts == []


def test_set_openclaw_freedom_mode_off_restores_safe_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()
    wizard._set_openclaw_freedom_mode(True)

    wizard._set_openclaw_freedom_mode(False)

    assert wizard.config.tools.exec.auto_approve is False
    assert wizard.config.integrations.http_guard.enabled is True
    assert wizard.config.integrations.http_guard.block_private_networks is True
    assert "127.0.0.1" in wizard.config.integrations.http_guard.deny_hosts


def test_setup_wizard_simple_mode_hides_advanced_sections(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()
    wizard._set_setup_mode("simple")

    options = wizard._main_menu_option_values()
    assert "workspace" in options
    assert "model" in options
    assert "channels" in options
    assert "gateway" not in options
    assert "doctor" not in options
    assert "logging" not in options


def test_setup_wizard_advanced_mode_shows_full_sections(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()
    wizard._set_setup_mode("advanced")

    options = wizard._main_menu_option_values()
    assert "gateway" in options
    assert "doctor" in options
    assert "logging" in options
