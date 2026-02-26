"""Test that setup wizard includes a Memory configuration option."""


def test_memory_in_advanced_menu_options():
    """Memory should appear in the advanced menu options list."""
    from kabot.cli.setup_wizard import SetupWizard
    wizard = SetupWizard()
    wizard.setup_mode = "advanced"
    options = wizard._main_menu_option_values()
    assert "memory" in options


def test_memory_in_simple_menu_options():
    """Memory should appear in the simple menu options list."""
    from kabot.cli.setup_wizard import SetupWizard
    wizard = SetupWizard()
    wizard.setup_mode = "simple"
    options = wizard._main_menu_option_values()
    assert "memory" in options


def test_configure_memory_updates_backend_without_crash(monkeypatch):
    """Memory config flow should persist backend selection without import errors."""
    from kabot.cli.setup_wizard import SetupWizard, ClackUI

    wizard = SetupWizard()
    saved = {}

    monkeypatch.setattr("kabot.config.loader.save_config", lambda cfg: saved.setdefault("cfg", cfg))
    monkeypatch.setattr(ClackUI, "section_start", lambda *_: None)
    monkeypatch.setattr(ClackUI, "section_end", lambda *_: None)
    monkeypatch.setattr(ClackUI, "clack_select", lambda *_, **__: "sqlite_only")
    monkeypatch.setattr(wizard, "_save_setup_state", lambda *_, **__: None)

    wizard._configure_memory()

    assert wizard.config.memory.backend == "sqlite_only"
    assert saved["cfg"] is wizard.config


def test_configure_memory_sets_embedding_provider_for_hybrid(monkeypatch):
    """Hybrid backend should prompt and store embedding provider selection."""
    from kabot.cli.setup_wizard import SetupWizard, ClackUI

    wizard = SetupWizard()
    saved = {}
    picks = iter(["hybrid", "ollama"])

    monkeypatch.setattr("kabot.config.loader.save_config", lambda cfg: saved.setdefault("cfg", cfg))
    monkeypatch.setattr(ClackUI, "section_start", lambda *_: None)
    monkeypatch.setattr(ClackUI, "section_end", lambda *_: None)
    monkeypatch.setattr(ClackUI, "clack_select", lambda *_, **__: next(picks))
    monkeypatch.setattr(wizard, "_save_setup_state", lambda *_, **__: None)

    wizard._configure_memory()

    assert wizard.config.memory.backend == "hybrid"
    assert wizard.config.memory.embedding_provider == "ollama"
    assert saved["cfg"] is wizard.config
