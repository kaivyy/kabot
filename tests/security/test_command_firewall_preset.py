import yaml

from kabot.security.command_firewall import ApprovalDecision, CommandFirewall


def test_balanced_preset_respects_explicit_policy(tmp_path):
    config_path = tmp_path / "command_approvals.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(
            {
                "policy": "deny",
                "allowlist": [{"pattern": "git status", "description": "safe"}],
                "denylist": [],
            },
            f,
        )

    firewall = CommandFirewall(config_path, preset="balanced")
    assert firewall.check_command("git status") == ApprovalDecision.DENY


def test_compat_preset_promotes_ask_to_allowlist(tmp_path):
    config_path = tmp_path / "command_approvals.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(
            {
                "policy": "ask",
                "allowlist": [{"pattern": "git status", "description": "safe"}],
                "denylist": [],
            },
            f,
        )

    firewall = CommandFirewall(config_path, preset="compat")
    assert firewall.check_command("git status") == ApprovalDecision.ALLOW
    assert firewall.check_command("rm -rf /tmp") == ApprovalDecision.ASK


def test_preset_never_relaxes_fail_safe_deny(tmp_path):
    config_path = tmp_path / "command_approvals.yaml"
    config_path.write_text("not valid yaml: {{{", encoding="utf-8")

    firewall = CommandFirewall(config_path, preset="compat")
    assert firewall.check_command("ls") == ApprovalDecision.DENY

