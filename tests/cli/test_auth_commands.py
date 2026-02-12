"""Tests for auth CLI commands."""
import pytest
from typer.testing import CliRunner
from unittest.mock import patch


@pytest.fixture
def runner():
    return CliRunner()


def test_auth_login_command_exists(runner):
    """auth login command should exist."""
    from kabot.cli.commands import app
    result = runner.invoke(app, ["auth", "login", "--help"])
    assert result.exit_code == 0
    assert "Login to a provider" in result.output


def test_auth_methods_command_exists(runner):
    """auth methods command should exist."""
    from kabot.cli.commands import app
    result = runner.invoke(app, ["auth", "methods", "--help"])
    assert result.exit_code == 0


def test_auth_login_accepts_method_option(runner):
    """auth login should accept --method option."""
    from kabot.cli.commands import app
    result = runner.invoke(app, ["auth", "login", "--help"])
    assert "--method" in result.output or "-m" in result.output


def test_auth_methods_with_valid_provider(runner):
    """auth methods should show methods for valid provider."""
    from kabot.cli.commands import app
    result = runner.invoke(app, ["auth", "methods", "openai"])
    assert result.exit_code == 0
    assert "API Key" in result.output


def test_auth_methods_with_invalid_provider(runner):
    """auth methods should error for invalid provider."""
    from kabot.cli.commands import app
    result = runner.invoke(app, ["auth", "methods", "invalid_provider"])
    assert result.exit_code == 1
    assert "not found" in result.output
