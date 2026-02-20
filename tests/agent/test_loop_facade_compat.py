from unittest.mock import AsyncMock, MagicMock

import pytest

import kabot.agent.loop as loop_module
from kabot.agent.loop import AgentLoop
from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.bus.queue import MessageBus
from kabot.cron.service import CronService


def test_loop_facade_exports_legacy_symbols():
    assert hasattr(loop_module, "AgentLoop")
    assert hasattr(loop_module, "ContextBuilder")
    assert hasattr(loop_module, "ChromaMemoryManager")
    assert hasattr(loop_module, "IntentRouter")
    assert hasattr(loop_module, "SubagentManager")


@pytest.fixture
def agent_loop(tmp_path):
    provider = MagicMock()
    provider.get_default_model.return_value = "openai-codex/gpt-5.3-codex"
    provider.chat = AsyncMock(
        return_value=MagicMock(
            content="ok",
            has_tool_calls=False,
            tool_calls=[],
            reasoning_content=None,
        )
    )
    return AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="openai-codex/gpt-5.3-codex",
        cron_service=CronService(tmp_path / "cron_jobs.json"),
    )


def test_required_tool_wrapper_delegates_to_loop_core(monkeypatch, agent_loop):
    from kabot.agent.loop_core import tool_enforcement

    called = {"question": None}

    def _fake_required(loop, question):
        called["question"] = question
        return "cron"

    monkeypatch.setattr(tool_enforcement, "required_tool_for_query_for_loop", _fake_required)
    result = agent_loop._required_tool_for_query("ingatkan 10 menit lagi")
    assert result == "cron"
    assert called["question"] == "ingatkan 10 menit lagi"


@pytest.mark.asyncio
async def test_fallback_wrapper_delegates_to_loop_core(monkeypatch, agent_loop):
    from kabot.agent.loop_core import tool_enforcement

    async def _fake_execute(loop, required_tool, msg):
        return f"delegated:{required_tool}:{msg.content}"

    monkeypatch.setattr(tool_enforcement, "execute_required_tool_fallback", _fake_execute)
    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="ingatkan 2 menit lagi makan",
    )

    result = await agent_loop._execute_required_tool_fallback("cron", msg)
    assert result == "delegated:cron:ingatkan 2 menit lagi makan"


def test_session_key_wrapper_delegates_to_session_flow(monkeypatch, agent_loop):
    from kabot.agent.loop_core import session_flow

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="hello",
    )

    called = {"value": False}

    def _fake_get_session_key(loop, inbound):
        called["value"] = True
        assert loop is agent_loop
        assert inbound is msg
        return "cli:from-session-flow"

    monkeypatch.setattr(session_flow, "get_session_key", _fake_get_session_key)
    assert agent_loop._get_session_key(msg) == "cli:from-session-flow"
    assert called["value"] is True


@pytest.mark.asyncio
async def test_finalize_session_wrapper_delegates_to_session_flow(monkeypatch, agent_loop):
    from kabot.agent.loop_core import session_flow

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="hello",
        _session_key="cli:direct",
    )
    session = MagicMock()
    expected = OutboundMessage(channel="cli", chat_id="direct", content="ok")

    async def _fake_finalize(loop, inbound, current_session, final_content):
        assert loop is agent_loop
        assert inbound is msg
        assert current_session is session
        assert final_content == "ok"
        return expected

    monkeypatch.setattr(session_flow, "finalize_session", _fake_finalize)
    result = await agent_loop._finalize_session(msg, session, "ok")
    assert result is expected


@pytest.mark.asyncio
async def test_plan_task_wrapper_delegates_to_quality_runtime(monkeypatch, agent_loop):
    from kabot.agent.loop_core import quality_runtime

    async def _fake_plan(loop, question):
        assert loop is agent_loop
        assert question == "buatkan rencana migrasi"
        return "plan-ok"

    monkeypatch.setattr(quality_runtime, "plan_task", _fake_plan)
    result = await agent_loop._plan_task("buatkan rencana migrasi")
    assert result == "plan-ok"


def test_apply_think_mode_wrapper_delegates_to_directives_runtime(monkeypatch, agent_loop):
    from kabot.agent.loop_core import directives_runtime

    called = {"value": False}

    def _fake_apply(loop, messages, session):
        called["value"] = True
        assert loop is agent_loop
        return [{"role": "system", "content": "delegated"}]

    monkeypatch.setattr(directives_runtime, "apply_think_mode", _fake_apply)
    result = agent_loop._apply_think_mode([], MagicMock(metadata={}))
    assert called["value"] is True
    assert result == [{"role": "system", "content": "delegated"}]


@pytest.mark.asyncio
async def test_process_message_wrapper_delegates_to_message_runtime(monkeypatch, agent_loop):
    from kabot.agent.loop_core import message_runtime

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="hello",
    )
    expected = OutboundMessage(channel="cli", chat_id="direct", content="delegated")

    async def _fake_process(loop, inbound):
        assert loop is agent_loop
        assert inbound is msg
        return expected

    monkeypatch.setattr(message_runtime, "process_message", _fake_process)
    result = await agent_loop._process_message(msg)
    assert result is expected


@pytest.mark.asyncio
async def test_process_system_message_wrapper_delegates_to_message_runtime(monkeypatch, agent_loop):
    from kabot.agent.loop_core import message_runtime

    msg = InboundMessage(
        channel="system",
        chat_id="cli:direct",
        sender_id="cron",
        content="reminder ping",
    )
    expected = OutboundMessage(channel="cli", chat_id="direct", content="done")

    async def _fake_process_system(loop, inbound):
        assert loop is agent_loop
        assert inbound is msg
        return expected

    monkeypatch.setattr(message_runtime, "process_system_message", _fake_process_system)
    result = await agent_loop._process_system_message(msg)
    assert result is expected


@pytest.mark.asyncio
async def test_process_isolated_wrapper_delegates_to_message_runtime(monkeypatch, agent_loop):
    from kabot.agent.loop_core import message_runtime

    async def _fake_process_isolated(loop, content, channel, chat_id, job_id):
        assert loop is agent_loop
        assert content == "ping"
        assert channel == "cli"
        assert chat_id == "direct"
        assert job_id == "job-1"
        return "isolated-ok"

    monkeypatch.setattr(message_runtime, "process_isolated", _fake_process_isolated)
    result = await agent_loop.process_isolated("ping", job_id="job-1")
    assert result == "isolated-ok"


@pytest.mark.asyncio
async def test_process_pending_exec_approval_wrapper_delegates_to_message_runtime(monkeypatch, agent_loop):
    from kabot.agent.loop_core import message_runtime

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="/approve cmd-123",
    )
    expected = OutboundMessage(channel="cli", chat_id="direct", content="approved")

    async def _fake_process_approval(loop, inbound, action, approval_id):
        assert loop is agent_loop
        assert inbound is msg
        assert action == "approve"
        assert approval_id == "cmd-123"
        return expected

    monkeypatch.setattr(message_runtime, "process_pending_exec_approval", _fake_process_approval)
    result = await agent_loop._process_pending_exec_approval(msg, action="approve", approval_id="cmd-123")
    assert result is expected


def test_resolve_models_for_message_wrapper_delegates_to_routing_runtime(monkeypatch, agent_loop):
    from kabot.agent.loop_core import routing_runtime

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="hello",
    )

    def _fake_resolve(loop, inbound):
        assert loop is agent_loop
        assert inbound is msg
        return ["openai-codex/gpt-5.3-codex", "openai/gpt-4o-mini"]

    monkeypatch.setattr(routing_runtime, "resolve_models_for_message", _fake_resolve)
    result = agent_loop._resolve_models_for_message(msg)
    assert result == ["openai-codex/gpt-5.3-codex", "openai/gpt-4o-mini"]
