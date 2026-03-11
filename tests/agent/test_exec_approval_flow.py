"""Tests for explicit exec approval flow in AgentLoop."""

import shutil
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.loop import AgentLoop
from kabot.agent.tools.shell import ExecTool
from kabot.bus.events import InboundMessage, OutboundMessage


def _make_case_dir() -> Path:
    root = Path.cwd() / ".tmp-test-exec-approval-flow"
    root.mkdir(parents=True, exist_ok=True)
    case_dir = root / f"case-{uuid.uuid4().hex[:8]}"
    case_dir.mkdir(parents=True, exist_ok=True)
    return case_dir


def test_parse_approval_command_supports_approve_and_deny():
    assert AgentLoop._parse_approval_command("/approve") == ("approve", None)
    assert AgentLoop._parse_approval_command("/approve abc123") == ("approve", "abc123")
    assert AgentLoop._parse_approval_command("/deny xyz789") == ("deny", "xyz789")
    assert AgentLoop._parse_approval_command("hello world") is None


@pytest.mark.asyncio
async def test_process_pending_exec_approval_runs_approved_command():
    loop = AgentLoop.__new__(AgentLoop)
    session = MagicMock()
    msg = InboundMessage(
        channel="cli",
        sender_id="user",
        chat_id="direct",
        content="/approve abc123",
        _session_key="cli:direct",
    )

    exec_tool = MagicMock()
    exec_tool.consume_pending_approval.return_value = {
        "id": "abc123",
        "command": "echo ok",
        "working_dir": ".",
    }
    exec_tool.execute = AsyncMock(return_value="ok")
    exec_tool.clear_pending_approval.return_value = False

    loop.tools = MagicMock()
    loop.tools.get.return_value = exec_tool
    loop._init_session = AsyncMock(return_value=session)
    loop._finalize_session = AsyncMock(
        return_value=OutboundMessage(channel="cli", chat_id="direct", content="ok")
    )

    result = await loop._process_pending_exec_approval(msg, action="approve", approval_id="abc123")

    exec_tool.consume_pending_approval.assert_called_once_with("cli:direct", "abc123")
    exec_tool.execute.assert_awaited_once()
    assert result.content == "ok"


@pytest.mark.asyncio
async def test_process_pending_exec_approval_denies_pending_command():
    loop = AgentLoop.__new__(AgentLoop)
    session = MagicMock()
    msg = InboundMessage(
        channel="telegram",
        sender_id="user",
        chat_id="123",
        content="/deny abc123",
        _session_key="telegram:123",
    )

    exec_tool = MagicMock()
    exec_tool.clear_pending_approval.return_value = True
    exec_tool.consume_pending_approval.return_value = None

    loop.tools = MagicMock()
    loop.tools.get.return_value = exec_tool
    loop._init_session = AsyncMock(return_value=session)
    loop._finalize_session = AsyncMock(
        return_value=OutboundMessage(
            channel="telegram",
            chat_id="123",
            content="Pending command approval denied.",
        )
    )

    result = await loop._process_pending_exec_approval(msg, action="deny", approval_id="abc123")

    exec_tool.clear_pending_approval.assert_called_once_with("telegram:123", "abc123")
    assert result.content == "Pending command approval denied."


@pytest.mark.asyncio
async def test_process_pending_exec_approval_uses_persisted_pending_entry_from_fresh_exec_tool():
    case_dir = _make_case_dir()
    try:
        config_path = case_dir / "command_approvals.yaml"
        first_tool = ExecTool(timeout=5, firewall_config_path=config_path, auto_approve=False)
        approval_id = first_tool.set_pending_approval("cli:direct", "echo persisted", working_dir=str(case_dir))

        loop = AgentLoop.__new__(AgentLoop)
        session = MagicMock()
        msg = InboundMessage(
            channel="cli",
            sender_id="user",
            chat_id="direct",
            content=f"/approve {approval_id}",
            _session_key="cli:direct",
        )

        fresh_tool = ExecTool(timeout=5, firewall_config_path=config_path, auto_approve=False)
        fresh_tool.execute = AsyncMock(return_value="persisted-ok")

        loop.tools = MagicMock()
        loop.tools.get.return_value = fresh_tool
        loop._init_session = AsyncMock(return_value=session)
        loop._finalize_session = AsyncMock(
            return_value=OutboundMessage(channel="cli", chat_id="direct", content="persisted-ok")
        )

        result = await loop._process_pending_exec_approval(msg, action="approve", approval_id=approval_id)

        fresh_tool.execute.assert_awaited_once()
        assert result.content == "persisted-ok"
        assert fresh_tool.get_pending_approval("cli:direct") is None
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)
