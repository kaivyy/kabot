"""Tests for cron CLI command parity."""

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


def test_cron_status_command_exists(runner):
    """cron status command should exist."""
    from kabot.cli.commands import app

    result = runner.invoke(app, ["cron", "status", "--help"])
    assert result.exit_code == 0
    assert "status" in result.output.lower()


def test_cron_update_command_exists(runner):
    """cron update command should exist."""
    from kabot.cli.commands import app

    result = runner.invoke(app, ["cron", "update", "--help"])
    assert result.exit_code == 0
    assert "--message" in result.output


def test_cron_runs_command_exists(runner):
    """cron runs command should exist."""
    from kabot.cli.commands import app

    result = runner.invoke(app, ["cron", "runs", "--help"])
    assert result.exit_code == 0
    assert "history" in result.output.lower() or "run" in result.output.lower()
