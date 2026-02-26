from pathlib import Path

from kabot.cli.setup_wizard import SetupWizard


def test_configure_gateway_invalid_port_keeps_previous_value(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()
    wizard.config.gateway.port = 18790

    selects = iter(["loopback", "none"])
    monkeypatch.setattr(
        "kabot.cli.setup_wizard.ClackUI.clack_select",
        lambda *args, **kwargs: next(selects),
    )
    monkeypatch.setattr("kabot.cli.setup_wizard.Prompt.ask", lambda *args, **kwargs: "not-a-port")
    monkeypatch.setattr("kabot.cli.setup_wizard.Confirm.ask", lambda *args, **kwargs: False)

    wizard._configure_gateway()

    assert wizard.config.gateway.port == 18790
    assert wizard.config.gateway.auth_token == ""


def test_configure_gateway_can_enable_hsts(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()

    selects = iter(["local", "none"])
    monkeypatch.setattr(
        "kabot.cli.setup_wizard.ClackUI.clack_select",
        lambda *args, **kwargs: next(selects),
    )

    prompt_answers = iter(["18888", "max-age=86400; includeSubDomains"])
    monkeypatch.setattr("kabot.cli.setup_wizard.Prompt.ask", lambda *args, **kwargs: next(prompt_answers))

    confirm_answers = iter([False, True])  # tailscale, hsts enabled
    monkeypatch.setattr("kabot.cli.setup_wizard.Confirm.ask", lambda *args, **kwargs: next(confirm_answers))

    wizard._configure_gateway()

    assert wizard.config.gateway.port == 18888
    assert wizard.config.gateway.http.security_headers.strict_transport_security is True
    assert (
        wizard.config.gateway.http.security_headers.strict_transport_security_value
        == "max-age=86400; includeSubDomains"
    )


def test_configure_gateway_back_on_bind_exits_without_prompts(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()
    original = wizard.config.gateway.model_copy(deep=True)

    monkeypatch.setattr("kabot.cli.setup_wizard.ClackUI.clack_select", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "kabot.cli.setup_wizard.Prompt.ask",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Prompt.ask should not be called")),
    )
    monkeypatch.setattr(
        "kabot.cli.setup_wizard.Confirm.ask",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Confirm.ask should not be called")),
    )

    wizard._configure_gateway()

    assert wizard.config.gateway.port == original.port
    assert wizard.config.gateway.auth_token == original.auth_token
    assert wizard.config.gateway.host == original.host


def test_configure_gateway_back_on_auth_keeps_existing_token(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()
    wizard.config.gateway.auth_token = "existing-token"

    selects = iter(["loopback", None])
    monkeypatch.setattr(
        "kabot.cli.setup_wizard.ClackUI.clack_select",
        lambda *args, **kwargs: next(selects),
    )

    prompt_answers = iter(["18790"])
    monkeypatch.setattr("kabot.cli.setup_wizard.Prompt.ask", lambda *args, **kwargs: next(prompt_answers))
    monkeypatch.setattr("kabot.cli.setup_wizard.Confirm.ask", lambda *args, **kwargs: False)

    wizard._configure_gateway()

    assert wizard.config.gateway.auth_token == "existing-token"
