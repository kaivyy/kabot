import os
import subprocess
import sys
from pathlib import Path

from kabot.cli import (
    commands,
    commands_agent_command,
    commands_approvals,
    commands_gateway,
    commands_mcp,
    commands_models_auth,
    commands_provider_runtime,
    commands_setup,
    commands_system,
)


def test_commands_reexports_new_command_modules():
    assert commands.setup is commands_setup.setup
    assert commands.skills_install is commands_setup.skills_install
    assert commands._make_provider is commands_provider_runtime._make_provider
    assert commands._wire_cli_exec_approval is commands_provider_runtime._wire_cli_exec_approval
    assert commands.gateway is commands_gateway.gateway
    assert commands.agent is commands_agent_command.agent
    assert commands.auth_list is commands_models_auth.auth_list
    assert commands.mcp_status is commands_mcp.mcp_status
    assert commands.approvals_status is commands_approvals.approvals_status
    assert commands.cron_list is commands_system.cron_list
    assert commands.plugins_cmd is commands_system.plugins_cmd


def test_agent_command_has_exec_approval_wiring_in_function_globals():
    assert "_wire_cli_exec_approval" in commands.agent.__globals__
    assert (
        commands.agent.__globals__["_wire_cli_exec_approval"]
        is commands_provider_runtime._wire_cli_exec_approval
    )


def test_agent_command_keeps_cli_runtime_helpers_in_function_globals():
    assert "_collect_cli_delivery_job_ids" in commands.agent.__globals__
    assert "_next_cli_reminder_delay_seconds" in commands.agent.__globals__
    assert "_save_history" in commands.agent.__globals__


def test_models_info_keeps_panel_dependency_available():
    assert "Panel" in commands_models_auth.models_info.__globals__


def test_python_module_invocation_of_commands_help_does_not_hit_circular_import():
    repo_root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root)
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        [sys.executable, "-m", "kabot.cli.commands", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert "Usage" in result.stdout
