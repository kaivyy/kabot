"""Tests for env-check command."""

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


def test_env_check_command_exists(runner):
    from kabot.cli.commands import app

    result = runner.invoke(app, ["env-check", "--help"])
    assert result.exit_code == 0


def test_env_check_outputs_recommended_mode(runner):
    from kabot.cli.commands import app

    result = runner.invoke(app, ["env-check"])
    assert result.exit_code == 0
    assert "recommended gateway mode" in result.output.lower()
