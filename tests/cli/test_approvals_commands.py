"""Tests for approvals CLI command surface."""

from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


def test_approvals_status_command_exists(runner):
    from kabot.cli.commands import app

    result = runner.invoke(app, ["approvals", "status", "--help"])
    assert result.exit_code == 0


def test_approvals_audit_command_exists(runner):
    from kabot.cli.commands import app

    result = runner.invoke(app, ["approvals", "audit", "--help"])
    assert result.exit_code == 0


def test_approvals_status_and_allow_work_with_custom_config(runner, tmp_path: Path):
    from kabot.cli.commands import app

    cfg = tmp_path / "approvals.yaml"

    status = runner.invoke(app, ["approvals", "status", "--config", str(cfg)])
    assert status.exit_code == 0
    assert "policy" in status.output.lower()

    allow = runner.invoke(
        app,
        [
            "approvals",
            "allow",
            "echo *",
            "--description",
            "allow echo",
            "--config",
            str(cfg),
        ],
    )
    assert allow.exit_code == 0
    assert "added allowlist pattern" in allow.output.lower()


def test_approvals_scoped_add_list_and_remove(runner, tmp_path: Path):
    from kabot.cli.commands import app

    cfg = tmp_path / "approvals.yaml"

    add = runner.invoke(
        app,
        [
            "approvals",
            "scoped-add",
            "--name",
            "telegram-deny",
            "--policy",
            "deny",
            "--scope",
            "channel=telegram",
            "--scope",
            "tool=exec",
            "--config",
            str(cfg),
        ],
    )
    assert add.exit_code == 0
    assert "added scoped policy" in add.output.lower()

    listing = runner.invoke(app, ["approvals", "scoped-list", "--config", str(cfg)])
    assert listing.exit_code == 0
    assert "telegram-deny" in listing.output
    assert "channel=telegram" in listing.output

    remove = runner.invoke(
        app,
        ["approvals", "scoped-remove", "telegram-deny", "--config", str(cfg)],
    )
    assert remove.exit_code == 0
    assert "removed scoped policy" in remove.output.lower()


def test_approvals_scoped_add_rejects_invalid_scope_key(runner, tmp_path: Path):
    from kabot.cli.commands import app

    cfg = tmp_path / "approvals.yaml"
    result = runner.invoke(
        app,
        [
            "approvals",
            "scoped-add",
            "--name",
            "bad",
            "--policy",
            "deny",
            "--scope",
            "invalid_scope=value",
            "--config",
            str(cfg),
        ],
    )
    assert result.exit_code == 1
    assert "invalid scope key" in result.output.lower()
