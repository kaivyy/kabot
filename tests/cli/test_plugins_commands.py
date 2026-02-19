"""Tests for plugins CLI lifecycle commands."""

from pathlib import Path

import pytest
from typer.testing import CliRunner


def _write_dynamic_plugin(root: Path, plugin_id: str, version: str = "1.0.0") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "plugin.json").write_text(
        (
            "{\n"
            f'  "id": "{plugin_id}",\n'
            f'  "name": "{plugin_id.title()}",\n'
            f'  "version": "{version}",\n'
            '  "description": "test plugin",\n'
            '  "entry_point": "main.py"\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    (root / "main.py").write_text("def register(registry=None, hooks=None):\n    return None\n", encoding="utf-8")


@pytest.fixture
def runner():
    return CliRunner()


def test_plugins_install_list_disable_enable_remove(runner, monkeypatch, tmp_path):
    from kabot.cli.commands import app
    from kabot.config.schema import Config

    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")

    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    source = tmp_path / "plugin-src"
    _write_dynamic_plugin(source, "demo_plugin")

    result_install = runner.invoke(app, ["plugins", "install", "--source", str(source)])
    assert result_install.exit_code == 0
    assert "Installed plugin" in result_install.output

    result_list = runner.invoke(app, ["plugins", "list"])
    assert result_list.exit_code == 0
    assert "Installed Plugins" in result_list.output
    assert "Total: 1 plugin(s)" in result_list.output

    result_disable = runner.invoke(app, ["plugins", "disable", "--target", "demo_plugin"])
    assert result_disable.exit_code == 0

    result_enable = runner.invoke(app, ["plugins", "enable", "--target", "demo_plugin"])
    assert result_enable.exit_code == 0

    result_remove = runner.invoke(app, ["plugins", "remove", "--target", "demo_plugin", "--yes"])
    assert result_remove.exit_code == 0
    assert "Removed plugin" in result_remove.output


def test_plugins_doctor_action_exists(runner):
    from kabot.cli.commands import app

    result = runner.invoke(app, ["plugins", "--help"])
    assert result.exit_code == 0
    assert "doctor" in result.output.lower()


def test_plugins_install_from_git_supports_ref(runner, monkeypatch, tmp_path):
    from kabot.cli.commands import app
    from kabot.config.schema import Config

    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")
    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)

    captured = {}

    def _fake_install_from_git(self, url, ref=None, target_name=None, overwrite=False):  # noqa: ANN001
        captured["url"] = url
        captured["ref"] = ref
        return "git_plugin"

    monkeypatch.setattr("kabot.plugins.manager.PluginManager.install_from_git", _fake_install_from_git)
    result = runner.invoke(
        app,
        ["plugins", "install", "--git", "https://example.com/repo.git", "--ref", "v1.2.3"],
    )

    assert result.exit_code == 0
    assert captured["url"] == "https://example.com/repo.git"
    assert captured["ref"] == "v1.2.3"


def test_plugins_scaffold_command(runner, monkeypatch, tmp_path):
    from kabot.cli.commands import app
    from kabot.config.schema import Config

    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")
    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)

    result = runner.invoke(app, ["plugins", "scaffold", "--target", "meta_bridge"])
    assert result.exit_code == 0
    assert "Scaffolded plugin" in result.output
