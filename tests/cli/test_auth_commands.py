"""Tests for auth CLI commands."""

import pytest
from typer.testing import CliRunner


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


def test_auth_methods_accepts_openai_codex_alias(runner):
    """auth methods should accept openai-codex alias and show openai methods."""
    from kabot.cli.commands import app
    result = runner.invoke(app, ["auth", "methods", "openai-codex"])
    assert result.exit_code == 0
    assert "OpenAI" in result.output
    assert "Browser Login (OAuth)" in result.output


def test_auth_methods_accepts_gemini_alias(runner):
    """auth methods should accept gemini alias and show google methods."""
    from kabot.cli.commands import app
    result = runner.invoke(app, ["auth", "methods", "gemini"])
    assert result.exit_code == 0
    assert "Google Gemini" in result.output
    assert "Browser Login (OAuth)" in result.output


def test_auth_methods_accepts_moonshot_alias(runner):
    """auth methods should accept moonshot alias and show kimi methods."""
    from kabot.cli.commands import app
    result = runner.invoke(app, ["auth", "methods", "moonshot"])
    assert result.exit_code == 0
    assert "Kimi (Moonshot AI)" in result.output


def test_auth_methods_accepts_vllm_alias(runner):
    """auth methods should accept vllm alias and show ollama methods."""
    from kabot.cli.commands import app
    result = runner.invoke(app, ["auth", "methods", "vllm"])
    assert result.exit_code == 0
    assert "Ollama" in result.output


def test_auth_methods_with_invalid_provider(runner):
    """auth methods should error for invalid provider."""
    from kabot.cli.commands import app
    result = runner.invoke(app, ["auth", "methods", "invalid_provider"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_auth_parity_command_exists(runner):
    """auth parity command should exist and return success."""
    from kabot.cli.commands import app

    result = runner.invoke(app, ["auth", "parity"])
    assert result.exit_code == 0
