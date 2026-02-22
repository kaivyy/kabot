# tests/agent/test_loop_collaborative.py
from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
async def test_agent_loop_multi_mode(tmp_path):
    from kabot.agent.loop import AgentLoop
    from kabot.agent.mode_manager import ModeManager
    from kabot.bus.queue import MessageBus

    bus = MessageBus()
    provider = MagicMock()
    mode_manager = ModeManager(tmp_path / "mode_config.json")
    mode_manager.set_mode("user:telegram:123", "multi")

    loop = AgentLoop(bus, provider, tmp_path, mode_manager=mode_manager)

    # Should use collaborative mode
    assert loop.mode_manager.get_mode("user:telegram:123") == "multi"
