from typer.testing import CliRunner


def test_config_sets_token_mode_without_running_wizard(monkeypatch):
    from kabot.cli.commands import app
    from kabot.config.schema import Config

    runner = CliRunner()
    cfg = Config()
    cfg.runtime.performance.token_mode = "boros"
    saved: dict[str, Config] = {}

    monkeypatch.setattr("kabot.config.loader.load_config", lambda config_path=None: cfg)
    monkeypatch.setattr("kabot.config.loader.save_config", lambda updated, config_path=None: saved.update(config=updated))
    monkeypatch.setattr(
        "kabot.cli.commands.setup",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("setup should not run")),
    )

    result = runner.invoke(app, ["config", "--token-mode", "hemat"])

    assert result.exit_code == 0
    assert saved["config"].runtime.performance.token_mode == "hemat"
    assert "Runtime token mode set to HEMAT" in result.output


def test_config_token_saver_flag_toggles_mode(monkeypatch):
    from kabot.cli.commands import app
    from kabot.config.schema import Config

    runner = CliRunner()
    cfg = Config()
    cfg.runtime.performance.token_mode = "boros"
    saved: dict[str, Config] = {}

    monkeypatch.setattr("kabot.config.loader.load_config", lambda config_path=None: cfg)
    monkeypatch.setattr("kabot.config.loader.save_config", lambda updated, config_path=None: saved.update(config=updated))
    monkeypatch.setattr(
        "kabot.cli.commands.setup",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("setup should not run")),
    )

    result_on = runner.invoke(app, ["config", "--token-saver"])
    assert result_on.exit_code == 0
    assert saved["config"].runtime.performance.token_mode == "hemat"
    assert "Runtime token mode set to HEMAT" in result_on.output

    result_off = runner.invoke(app, ["config", "--no-token-saver"])
    assert result_off.exit_code == 0
    assert saved["config"].runtime.performance.token_mode == "boros"
    assert "Runtime token mode set to BOROS" in result_off.output


def test_config_rejects_invalid_token_mode(monkeypatch):
    from kabot.cli.commands import app
    from kabot.config.schema import Config

    runner = CliRunner()
    cfg = Config()

    monkeypatch.setattr("kabot.config.loader.load_config", lambda config_path=None: cfg)
    monkeypatch.setattr(
        "kabot.config.loader.save_config",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("save_config should not run")),
    )

    result = runner.invoke(app, ["config", "--token-mode", "agresif"])

    assert result.exit_code != 0
    assert "must be boros or hemat" in result.output.lower()
