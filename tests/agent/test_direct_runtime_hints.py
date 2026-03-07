from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.loop import AgentLoop
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
    )

    assert result == "ok"
    assert captured["metadata"]["suppress_post_response_warmup"] is True
    assert captured["metadata"]["probe_mode"] is True
