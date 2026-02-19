"""Tests for explicit exec approval flow in AgentLoop."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from kabot.agent.loop import AgentLoop
from kabot.bus.events import InboundMessage, OutboundMessage


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
