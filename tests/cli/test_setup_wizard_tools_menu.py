from __future__ import annotations

from kabot.cli.setup_wizard import SetupWizard


def test_configure_tools_back_from_main_menu(monkeypatch):
    wizard = SetupWizard()
    original = wizard.config.model_copy(deep=True)

    monkeypatch.setattr(
        "kabot.cli.wizard.sections.tools_gateway_skills.ClackUI.clack_select",
        lambda *_, **__: None,
    )
    monkeypatch.setattr(
        "kabot.cli.wizard.sections.tools_gateway_skills.Prompt.ask",
        lambda *_, **__: (_ for _ in ()).throw(AssertionError("Prompt.ask should not be called")),
    )
    monkeypatch.setattr(
        "kabot.cli.wizard.sections.tools_gateway_skills.Confirm.ask",
        lambda *_, **__: (_ for _ in ()).throw(AssertionError("Confirm.ask should not be called")),
    )
    monkeypatch.setattr(wizard, "_save_setup_state", lambda *_, **__: None)

    wizard._configure_tools()

    assert wizard.config.tools.web.search.api_key == original.tools.web.search.api_key
    assert wizard.config.tools.web.search.max_results == original.tools.web.search.max_results
    assert wizard.config.tools.exec.timeout == original.tools.exec.timeout


def test_configure_tools_advanced_menu_sets_only_selected_key(monkeypatch):
    wizard = SetupWizard()
    wizard.config.tools.web.search.perplexity_api_key = ""
    wizard.config.tools.web.search.kimi_api_key = ""
    wizard.config.tools.web.search.xai_api_key = ""
    wizard.config.tools.web.fetch.firecrawl_api_key = ""
    wizard.config.tools.web.search.provider = "brave"

    picks = iter(
        [
            "advanced",
            "perplexity_key",
            None,  # Back from advanced submenu
            None,  # Back from tools menu
        ]
    )

    monkeypatch.setattr(
        "kabot.cli.wizard.sections.tools_gateway_skills.ClackUI.clack_select",
        lambda *_, **__: next(picks),
    )
    monkeypatch.setattr(
        "kabot.cli.wizard.sections.tools_gateway_skills.Prompt.ask",
        lambda *_, **__: "pplx_test_key",
    )
    monkeypatch.setattr(
        "kabot.cli.wizard.sections.tools_gateway_skills.Confirm.ask",
        lambda *_, **__: (_ for _ in ()).throw(AssertionError("Confirm.ask should not be called in this flow")),
    )
    monkeypatch.setattr(wizard, "_save_setup_state", lambda *_, **__: None)

    wizard._configure_tools()

    assert wizard.config.tools.web.search.perplexity_api_key == "pplx_test_key"
    assert wizard.config.tools.web.search.provider == "perplexity"
    assert wizard.config.tools.web.search.kimi_api_key == ""
    assert wizard.config.tools.web.search.xai_api_key == ""
    assert wizard.config.tools.web.fetch.firecrawl_api_key == ""


def test_configure_tools_runtime_mode_sets_hemat(monkeypatch):
    wizard = SetupWizard()
    wizard.config.runtime.performance.token_mode = "boros"

    picks = iter(
        [
            "runtime_mode",
            "hemat",
            None,  # Back from tools menu
        ]
    )

    monkeypatch.setattr(
        "kabot.cli.wizard.sections.tools_gateway_skills.ClackUI.clack_select",
        lambda *_, **__: next(picks),
    )
    monkeypatch.setattr(
        "kabot.cli.wizard.sections.tools_gateway_skills.Prompt.ask",
        lambda *_, **__: (_ for _ in ()).throw(AssertionError("Prompt.ask should not be called in this flow")),
    )
    monkeypatch.setattr(
        "kabot.cli.wizard.sections.tools_gateway_skills.Confirm.ask",
        lambda *_, **__: (_ for _ in ()).throw(AssertionError("Confirm.ask should not be called in this flow")),
    )
    monkeypatch.setattr(wizard, "_save_setup_state", lambda *_, **__: None)

    wizard._configure_tools()

    assert wizard.config.runtime.performance.token_mode == "hemat"
