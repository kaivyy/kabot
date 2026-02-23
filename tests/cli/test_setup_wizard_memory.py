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
