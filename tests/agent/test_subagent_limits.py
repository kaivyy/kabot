"""Tests for sub-agent spawn limits."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kabot.agent.subagent import SubagentManager
from kabot.config.schema import SubagentDefaults


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.get_default_model.return_value = "test/model"
    return provider


@pytest.fixture
def mock_bus():
    bus = MagicMock()
    bus.publish_inbound = AsyncMock()
    return bus


@pytest.fixture
def manager(mock_provider, mock_bus, tmp_path):
    return SubagentManager(
        provider=mock_provider,
        workspace=tmp_path,
        bus=mock_bus,
        subagent_config=SubagentDefaults(max_children_per_agent=2),
    )


class TestSubagentLimits:
    @pytest.mark.asyncio
    async def test_rejects_when_max_children_reached(self, manager):
        """spawn() should reject if running count >= max_children_per_agent."""
        manager._running_tasks = {"a": MagicMock(), "b": MagicMock()}
        result = await manager.spawn("task3")
        assert "limit" in result.lower() or "max" in result.lower()

    @pytest.mark.asyncio
    async def test_allows_spawn_under_limit(self, manager):
        """spawn() should allow if running count < max_children_per_agent."""
        with patch.object(manager, "_run_subagent", new_callable=AsyncMock):
            result = await manager.spawn("task1")
            assert "started" in result.lower()

    def test_default_depth_is_tracked(self, manager):
        """Manager should track current_depth."""
        assert manager.current_depth == 0

    @pytest.mark.asyncio
    async def test_rejects_nested_spawn_at_max_depth(self, manager):
        """spawn() should reject when depth >= max_spawn_depth."""
        manager.current_depth = 1  # At max (default max_spawn_depth=1)
        result = await manager.spawn("nested task")
        assert "depth" in result.lower() or "nested" in result.lower()
