"""Tests for doctor CLI command surface."""

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


def test_doctor_command_exposes_bootstrap_sync_flag(runner):
    from kabot.cli.commands import app

    result = runner.invoke(app, ["doctor", "--help"])
    assert result.exit_code == 0
    assert "--bootstrap-sync" in result.output

