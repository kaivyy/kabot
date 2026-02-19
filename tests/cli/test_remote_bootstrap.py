"""Tests for remote bootstrap CLI command."""

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


def test_remote_bootstrap_command_exists(runner):
    from kabot.cli.commands import app

    result = runner.invoke(app, ["remote-bootstrap", "--help"])
    assert result.exit_code == 0


def test_remote_bootstrap_dry_run_linux_systemd(runner):
    from kabot.cli.commands import app

    result = runner.invoke(
        app,
        [
            "remote-bootstrap",
            "--platform",
            "linux",
            "--service",
            "systemd",
            "--dry-run",
            "--no-healthcheck",
        ],
    )
    assert result.exit_code == 0
    assert "systemctl --user enable kabot" in result.output
    assert "doctor --fix" in result.output.lower()


def test_remote_bootstrap_dry_run_windows(runner):
    from kabot.cli.commands import app

    result = runner.invoke(
        app,
        [
            "remote-bootstrap",
            "--platform",
            "windows",
            "--service",
            "windows",
            "--dry-run",
            "--no-healthcheck",
        ],
    )
    assert result.exit_code == 0
    assert "install-kabot-service.ps1" in result.output


def test_remote_bootstrap_dry_run_termux(runner):
    from kabot.cli.commands import app

    result = runner.invoke(
        app,
        [
            "remote-bootstrap",
            "--platform",
            "termux",
            "--service",
            "auto",
            "--dry-run",
            "--no-healthcheck",
        ],
    )
    assert result.exit_code == 0
    assert "termux-services" in result.output.lower()


def test_remote_bootstrap_apply_windows_uses_task_scheduler(runner, monkeypatch):
    from kabot.cli.commands import app

    called = {"install": False}

    def _fake_install_windows_task_service(*args, **kwargs):  # noqa: ANN002, ANN003
        called["install"] = True
        return True, "ok"

    monkeypatch.setattr("kabot.core.daemon.install_windows_task_service", _fake_install_windows_task_service)

    result = runner.invoke(
        app,
        [
            "remote-bootstrap",
            "--platform",
            "windows",
            "--service",
            "windows",
            "--apply",
            "--no-healthcheck",
        ],
    )

    assert result.exit_code == 0
    assert called["install"] is True
