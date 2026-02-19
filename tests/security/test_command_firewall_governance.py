"""Tests for advanced approval governance in CommandFirewall."""

import json
from pathlib import Path

import yaml

from kabot.security.command_firewall import ApprovalDecision, CommandFirewall


def _write_config(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f)


def test_scoped_policy_can_override_global_policy(tmp_path):
    config_path = tmp_path / "command_approvals.yaml"
    _write_config(
        config_path,
        {
            "policy": "ask",
            "allowlist": [],
            "denylist": [],
            "scoped_policies": [
                {
                    "name": "telegram-exec-deny",
                    "scope": {"channel": "telegram", "tool": "exec"},
                    "policy": "deny",
                },
                {
                    "name": "cli-exec-allow-echo",
                    "scope": {"channel": "cli", "tool": "exec"},
                    "policy": "allowlist",
                    "allowlist": [{"pattern": "echo *", "description": "echo only"}],
                },
            ],
        },
    )
    firewall = CommandFirewall(config_path)

    assert (
        firewall.check_command(
            "echo hello",
            context={"channel": "telegram", "tool": "exec"},
        )
        == ApprovalDecision.DENY
    )
    assert (
        firewall.check_command(
            "echo hello",
            context={"channel": "cli", "tool": "exec"},
        )
        == ApprovalDecision.ALLOW
    )
    assert (
        firewall.check_command(
            "echo hello",
            context={"channel": "discord", "tool": "exec"},
        )
        == ApprovalDecision.ASK
    )


def test_scoped_policy_supports_agent_specific_rules(tmp_path):
    config_path = tmp_path / "command_approvals.yaml"
    _write_config(
        config_path,
        {
            "policy": "ask",
            "allowlist": [],
            "denylist": [],
            "scoped_policies": [
                {
                    "name": "analyst-can-read-git",
                    "scope": {"agent_id": "analyst", "tool": "exec"},
                    "policy": "allowlist",
                    "allowlist": [{"pattern": "git status", "description": "safe"}],
                }
            ],
        },
    )
    firewall = CommandFirewall(config_path)

    assert (
        firewall.check_command(
            "git status",
            context={"agent_id": "analyst", "tool": "exec"},
        )
        == ApprovalDecision.ALLOW
    )
    assert (
        firewall.check_command(
            "git status",
            context={"agent_id": "coder", "tool": "exec"},
        )
        == ApprovalDecision.ASK
    )


def test_firewall_writes_audit_log_and_can_read_recent_entries(tmp_path):
    config_path = tmp_path / "command_approvals.yaml"
    _write_config(
        config_path,
        {
            "policy": "ask",
            "allowlist": [],
            "denylist": [{"pattern": "rm -rf *", "description": "dangerous"}],
        },
    )
    firewall = CommandFirewall(config_path)

    firewall.check_command("echo hello", context={"channel": "cli", "tool": "exec"})
    firewall.check_command("rm -rf /", context={"channel": "telegram", "tool": "exec"})

    assert firewall.audit_log_path.exists()

    entries = firewall.get_recent_audit(limit=10)
    assert len(entries) >= 2
    assert any(e["command"] == "echo hello" for e in entries)
    assert any(e["decision"] == "deny" for e in entries)

    telegram_entries = firewall.get_recent_audit(limit=10, channel="telegram")
    assert all(e.get("context", {}).get("channel") == "telegram" for e in telegram_entries)

    with open(firewall.audit_log_path, "r") as f:
        first_line = f.readline().strip()
    payload = json.loads(first_line)
    assert "decision" in payload
    assert "command" in payload


def test_scoped_policy_supports_identity_scope_fields_with_wildcards(tmp_path):
    config_path = tmp_path / "command_approvals.yaml"
    _write_config(
        config_path,
        {
            "policy": "ask",
            "allowlist": [],
            "denylist": [],
            "scoped_policies": [
                {
                    "name": "account-thread-guard",
                    "scope": {
                        "account_id": "acct-123",
                        "thread_id": "ops-*",
                        "peer_kind": "group",
                    },
                    "policy": "deny",
                }
            ],
        },
    )
    firewall = CommandFirewall(config_path)

    assert (
        firewall.check_command(
            "echo deploy",
            context={
                "account_id": "acct-123",
                "thread_id": "ops-incident",
                "peer_kind": "group",
                "tool": "exec",
            },
        )
        == ApprovalDecision.DENY
    )
    assert (
        firewall.check_command(
            "echo deploy",
            context={
                "account_id": "acct-123",
                "thread_id": "random-thread",
                "peer_kind": "group",
                "tool": "exec",
            },
        )
        == ApprovalDecision.ASK
    )
