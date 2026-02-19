"""Focused ASK-mode behavior tests for ExecTool."""

import shutil
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from kabot.agent.tools.shell import ExecTool


def _make_case_dir() -> Path:
    root = Path.cwd() / ".tmp-test-shell-firewall"
    root.mkdir(parents=True, exist_ok=True)
    case_dir = root / f"case-{uuid.uuid4().hex[:8]}"
    case_dir.mkdir(parents=True, exist_ok=True)
    return case_dir


@pytest.mark.asyncio
async def test_ask_mode_blocks_command_without_auto_approve():
    case_dir = _make_case_dir()
    try:
        config_path = case_dir / "command_approvals.yaml"
        tool = ExecTool(timeout=5, firewall_config_path=config_path, auto_approve=False)

        with patch("asyncio.create_subprocess_shell") as mock_subprocess:
            result = await tool.execute("echo hello")
            assert "requires approval" in result.lower()
            mock_subprocess.assert_not_called()
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_ask_mode_callback_allow_once_executes_command():
    case_dir = _make_case_dir()
    try:
        config_path = case_dir / "command_approvals.yaml"
        tool = ExecTool(
            timeout=5,
            firewall_config_path=config_path,
            auto_approve=False,
            approval_callback=lambda *_: "allow_once",
        )

        with patch("asyncio.create_subprocess_shell") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"ok", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            result = await tool.execute("echo hello", _session_key="cli:direct")
            assert "ok" in result
            mock_subprocess.assert_called_once()
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_ask_mode_stores_pending_approval_for_session():
    case_dir = _make_case_dir()
    try:
        config_path = case_dir / "command_approvals.yaml"
        tool = ExecTool(timeout=5, firewall_config_path=config_path, auto_approve=False)

        result = await tool.execute("echo hello", _session_key="cli:direct")
        assert "approval id" in result.lower()
        assert "/approve" in result

        pending = tool.get_pending_approval("cli:direct")
        assert pending is not None
        assert pending["command"] == "echo hello"
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_pending_approval_can_be_consumed_and_executed():
    case_dir = _make_case_dir()
    try:
        config_path = case_dir / "command_approvals.yaml"
        tool = ExecTool(timeout=5, firewall_config_path=config_path, auto_approve=False)

        tool.set_pending_approval("cli:direct", "echo approved")
        pending = tool.consume_pending_approval("cli:direct")
        assert pending is not None
        assert tool.get_pending_approval("cli:direct") is None

        with patch("asyncio.create_subprocess_shell") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"approved", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            result = await tool.execute(
                pending["command"],
                _session_key="cli:direct",
                _approved_by_user=True,
            )
            assert "approved" in result
            mock_subprocess.assert_called_once()
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_ask_mode_respects_scoped_channel_policy():
    case_dir = _make_case_dir()
    try:
        config_path = case_dir / "command_approvals.yaml"
        config_path.write_text(
            """policy: ask
allowlist: []
denylist: []
scoped_policies:
  - name: telegram-exec-deny
    scope:
      channel: telegram
      tool: exec
    policy: deny
"""
        )

        tool = ExecTool(timeout=5, firewall_config_path=config_path, auto_approve=False)
        denied = await tool.execute("echo hello", _session_key="telegram:1", _channel="telegram")
        assert "blocked by security policy" in denied.lower()

        asked = await tool.execute("echo hello", _session_key="cli:direct", _channel="cli")
        assert "requires approval" in asked.lower()
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_ask_mode_respects_scoped_identity_policy():
    case_dir = _make_case_dir()
    try:
        config_path = case_dir / "command_approvals.yaml"
        config_path.write_text(
            """policy: ask
allowlist: []
denylist: []
scoped_policies:
  - name: account-guard
    scope:
      account_id: acct-1
      thread_id: ops-*
      peer_kind: group
      tool: exec
    policy: deny
"""
        )

        tool = ExecTool(timeout=5, firewall_config_path=config_path, auto_approve=False)

        denied = await tool.execute(
            "echo hello",
            _session_key="cli:direct",
            _channel="cli",
            _account_id="acct-1",
            _thread_id="ops-main",
            _peer_kind="group",
        )
        assert "blocked by security policy" in denied.lower()

        asked = await tool.execute(
            "echo hello",
            _session_key="cli:direct",
            _channel="cli",
            _account_id="acct-2",
            _thread_id="ops-main",
            _peer_kind="group",
        )
        assert "requires approval" in asked.lower()
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)
