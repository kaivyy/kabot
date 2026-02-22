"""Test plugin system integration into agent loop."""

from unittest.mock import MagicMock

import pytest

from kabot.agent.loop import AgentLoop
from kabot.bus.queue import MessageBus


@pytest.fixture
def test_workspace(tmp_path):
    """Provide a temporary workspace."""
    workspace = tmp_path / "test_workspace"
    workspace.mkdir(exist_ok=True)
    yield workspace
    # Cleanup
    import shutil
    if workspace.exists():
        try:
            shutil.rmtree(workspace)
        except PermissionError:
            pass  # Ignore cleanup errors on Windows


@pytest.mark.asyncio
async def test_plugin_system_initialized(test_workspace):
    """Test that plugin system is initialized in agent loop."""
    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="gpt-4")

    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=test_workspace,
        enable_hybrid_memory=False
    )

    # Verify plugin registry exists
    assert hasattr(agent, 'plugin_registry')
    assert agent.plugin_registry is not None

    # Verify plugins can be listed
    plugins = agent.plugin_registry.list_all()
    assert isinstance(plugins, list)


@pytest.mark.asyncio
async def test_vector_store_lazy_initialization(test_workspace):
    """Test that vector store is lazily initialized."""
    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="gpt-4")

    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=test_workspace,
        enable_hybrid_memory=False
    )

    # Access vector_store property triggers lazy initialization
    store = agent.vector_store

    # Verify it has search method (either real or dummy)
    assert hasattr(store, 'search')


@pytest.mark.asyncio
async def test_memory_search_tool_registered(test_workspace):
    """Test that memory search tool is registered."""
    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="gpt-4")

    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=test_workspace,
        enable_hybrid_memory=False
    )

    # Verify memory_search tool is registered
    tool = agent.tools.get("memory_search")
    assert tool is not None
    assert tool.name == "memory_search"

