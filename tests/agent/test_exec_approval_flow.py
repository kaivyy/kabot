"""Tests for conversational exec approval flow in AgentLoop."""

import shutil
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.loop import AgentLoop
from kabot.agent.loop_core.message_runtime import process_message
from kabot.agent.tools.shell import ExecTool
from kabot.bus.events import InboundMessage, OutboundMessage


def _make_case_dir() -> Path:
    root = Path.cwd() / ".tmp-test-exec-approval-flow"
    root.mkdir(parents=True, exist_ok=True)
    case_dir = root / f"case-{uuid.uuid4().hex[:8]}"
    case_dir.mkdir(parents=True, exist_ok=True)
    return case_dir


def test_parse_exec_approval_turn_supports_natural_language_acceptance_and_denial():
    assert AgentLoop._parse_exec_approval_turn("ya jalankan sekarang") == "approve"
    assert AgentLoop._parse_exec_approval_turn("oke lanjut eksekusi") == "approve"
    assert AgentLoop._parse_exec_approval_turn("jangan jalankan") == "deny"
    assert AgentLoop._parse_exec_approval_turn("batal aja") == "deny"
    assert AgentLoop._parse_exec_approval_turn("halo dulu") is None


@pytest.mark.asyncio
async def test_process_pending_exec_approval_runs_approved_command():
    loop = AgentLoop.__new__(AgentLoop)
    session = MagicMock()
    msg = InboundMessage(
        channel="cli",
        sender_id="user",
        chat_id="direct",
        content="ya jalankan sekarang",
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
        content="jangan jalankan",
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
            content="oke lanjut eksekusi",
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


@pytest.mark.asyncio
async def test_process_message_executes_pending_command_from_natural_language_approval_turn():
    case_dir = _make_case_dir()
    try:
        config_path = case_dir / "command_approvals.yaml"
        exec_tool = ExecTool(timeout=5, firewall_config_path=config_path, auto_approve=False)
        approval_id = exec_tool.set_pending_approval("cli:direct", "echo from-chat", working_dir=str(case_dir))
        exec_tool.execute = AsyncMock(return_value="from-chat-ok")

        loop = AgentLoop.__new__(AgentLoop)
        session = MagicMock(metadata={})
        loop.tools = MagicMock()
        loop.tools.get.return_value = exec_tool
        loop.command_router = MagicMock()
        loop.command_router.is_command.return_value = False
        loop._init_session = AsyncMock(return_value=session)
        loop._finalize_session = AsyncMock(
            return_value=OutboundMessage(channel="cli", chat_id="direct", content="from-chat-ok")
        )
        loop.runtime_performance = MagicMock(fast_first_response=False)
        loop._cold_start_reported = True
        loop.directive_parser = MagicMock(
            parse=lambda content: (
                content,
                MagicMock(raw_directives=[], think=False, verbose=False, elevated=False, model=None),
            )
        )
        loop.memory = MagicMock(get_conversation_context=lambda _key, max_messages=30: [])
        loop.router = MagicMock(route=AsyncMock(return_value=MagicMock(profile="CHAT", is_complex=False)))
        loop._resolve_context_for_message = lambda _msg: MagicMock(
            build_messages=lambda **_kwargs: [{"role": "user", "content": "ctx"}],
            consume_last_truncation_summary=lambda: None,
        )
        loop.context = loop._resolve_context_for_message(None)
        loop._required_tool_for_query = lambda _text: None
        loop._run_simple_response = AsyncMock(return_value="simple")
        loop._run_agent_loop = AsyncMock(return_value="agent")
        loop.sessions = MagicMock(save=lambda _session: None)
        loop.runtime_observability = None

        msg = InboundMessage(
            channel="cli",
            sender_id="user",
            chat_id="direct",
            content="ya jalankan sekarang",
            _session_key="cli:direct",
        )
        result = await process_message(loop, msg)

        exec_tool.execute.assert_awaited_once()
        assert approval_id
        assert result.content == "from-chat-ok"
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)
