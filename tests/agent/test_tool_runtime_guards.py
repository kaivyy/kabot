from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.loop import AgentLoop
from kabot.bus.events import InboundMessage
from kabot.bus.queue import MessageBus
from kabot.cron.service import CronService
from kabot.providers.base import LLMResponse, ToolCallRequest


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
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="openai-codex/gpt-5.3-codex",
        cron_service=CronService(tmp_path / "cron_jobs.json"),
    )
    loop.max_iterations = 2
    return loop


@pytest.mark.asyncio
async def test_required_tool_query_falls_back_when_model_keeps_calling_wrong_tool(agent_loop):
    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="cek suhu Cilacap sekarang",
        timestamp=datetime.now(),
    )
    messages = [{"role": "user", "content": msg.content}]
    session = MagicMock()
    session.metadata = {}

    agent_loop._plan_task = AsyncMock(return_value=None)
    agent_loop._apply_think_mode = MagicMock(side_effect=lambda m, s: m)
    agent_loop._self_evaluate = MagicMock(return_value=(True, None))
    agent_loop._critic_evaluate = AsyncMock(return_value=(8, "ok"))
    agent_loop._log_lesson = AsyncMock(return_value=None)
    agent_loop._process_tool_calls = AsyncMock(side_effect=lambda _msg, msgs, _res, _session: msgs)

    wrong_tool_response = LLMResponse(
        content="",
        tool_calls=[ToolCallRequest(id="call_1", name="memory_search", arguments={"query": "cilacap"})],
    )
    agent_loop._call_llm_with_fallback = AsyncMock(
        side_effect=[(wrong_tool_response, None), (wrong_tool_response, None)]
    )

    fallback_execute = AsyncMock(return_value="Cilacap: [Clear] +29C")
    agent_loop._execute_required_tool_fallback = fallback_execute

    result = await agent_loop._run_agent_loop(msg, messages, session)
    assert str(result) in {"Cilacap: [Clear] +29C", "ok"}
    fallback_execute.assert_awaited_once_with("weather", msg)


@pytest.mark.asyncio
async def test_system_messages_skip_required_tool_enforcement(agent_loop):
    msg = InboundMessage(
        channel="system",
        chat_id="telegram:8086618307",
        sender_id="system",
        content="[System] Cron job 'Reminder Salat Subuh' completed.",
        timestamp=datetime.now(),
    )
    messages = [{"role": "user", "content": msg.content}]
    session = MagicMock()
    session.metadata = {}

    agent_loop._plan_task = AsyncMock(return_value=None)
    agent_loop._apply_think_mode = MagicMock(side_effect=lambda m, s: m)
    agent_loop._self_evaluate = MagicMock(return_value=(True, None))
    agent_loop._critic_evaluate = AsyncMock(return_value=(8, "ok"))
    agent_loop._log_lesson = AsyncMock(return_value=None)

    text_only = LLMResponse(content="Reminder delivered.", tool_calls=[])
    agent_loop._call_llm_with_fallback = AsyncMock(return_value=(text_only, None))
    fallback_execute = AsyncMock(return_value="should-not-run")
    agent_loop._execute_required_tool_fallback = fallback_execute

    result = await agent_loop._run_agent_loop(msg, messages, session)

    assert "Reminder delivered" in str(result)
    fallback_execute.assert_not_awaited()
