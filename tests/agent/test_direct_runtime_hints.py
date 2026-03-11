import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.loop_parts.delegates import AgentLoopDelegatesMixin
from kabot.agent.loop import AgentLoop
from kabot.agent.loop_core.quality_runtime import get_learned_execution_hints
from kabot.bus.queue import MessageBus
from kabot.cron.service import CronService


@pytest.mark.asyncio
async def test_process_direct_can_suppress_post_response_warmup(tmp_path):
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

    captured: dict[str, object] = {}

    async def _fake_process_message(msg):
        captured["metadata"] = dict(msg.metadata or {})
        return SimpleNamespace(content="ok")

    loop._process_message = _fake_process_message  # type: ignore[method-assign]

    result = await loop.process_direct(
        "halo",
        suppress_post_response_warmup=True,
        probe_mode=True,
        persist_history=True,
    )

    assert result == "ok"
    assert captured["metadata"]["suppress_post_response_warmup"] is True
    assert captured["metadata"]["probe_mode"] is True
    assert captured["metadata"]["persist_history"] is True


@pytest.mark.asyncio
async def test_close_runtime_resources_drains_pending_memory_tasks():
    completed: list[str] = []

    class _FakeLoop(AgentLoopDelegatesMixin):
        pass

    loop = _FakeLoop()
    loop._pending_memory_tasks = set()
    loop._mcp_session_runtimes = {}

    async def _pending_write() -> None:
        await asyncio.sleep(0.01)
        completed.append("done")

    loop._pending_memory_tasks.add(asyncio.create_task(_pending_write()))

    await loop.close_runtime_resources()

    assert completed == ["done"]
    assert not loop._pending_memory_tasks


@pytest.mark.asyncio
async def test_process_direct_persist_history_flushes_delayed_memory_writes_on_close(tmp_path):
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
        lazy_probe_memory=True,
    )
    loop.router = SimpleNamespace(
        route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
    )
    loop._required_tool_for_query = lambda _text: None
    loop._run_simple_response = AsyncMock(return_value="ok")

    original_add_message = loop.memory.add_message

    async def _delayed_add_message(*args, **kwargs):
        await asyncio.sleep(0.02)
        return await original_add_message(*args, **kwargs)

    loop.memory.add_message = _delayed_add_message

    session_key = "cli:oneshot:memory-durability"
    result = await loop.process_direct(
        "halo kabot",
        session_key=session_key,
    )

    assert result == "ok"

    await loop.close_runtime_resources()

    history = loop.memory.get_conversation_context(session_key, max_messages=10)
    contents = [str(item.get("content") or "") for item in history]
    assert any("halo kabot" in content for content in contents)
    assert any(content == "ok" for content in contents)


def test_get_learned_execution_hints_prefers_matching_recent_lessons():
    loop = SimpleNamespace(
        memory=SimpleNamespace(
            get_recent_lessons=lambda limit=8, task_type="complex": [
                {
                    "trigger": "send screenshot file to chat",
                    "guardrail": "Only claim screenshot delivery after message(files=...) succeeds.",
                },
                {
                    "trigger": "stock price lookup",
                    "guardrail": "Verify the symbol before quoting a price.",
                },
            ]
        )
    )

    hints = get_learned_execution_hints(
        loop,
        "bikin landing page lalu screenshot dan kirim ke chat ini",
        required_tool="message",
        limit=2,
    )

    assert hints == ["Only claim screenshot delivery after message(files=...) succeeds."]
