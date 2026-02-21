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
