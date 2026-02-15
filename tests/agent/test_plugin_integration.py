"""Test plugin system integration into agent loop."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from kabot.agent.loop import AgentLoop
from kabot.bus.queue import MessageBus


@pytest.mark.asyncio
async def test_plugin_system_initialized():
    """Test that plugin system is initialized in agent loop."""
    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="gpt-4")

    workspace = Path("./test_workspace")
    workspace.mkdir(exist_ok=True)

    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
        enable_hybrid_memory=False
    )

    # Verify plugin registry exists
    assert hasattr(agent, 'plugin_registry')
    assert agent.plugin_registry is not None

    # Verify plugins can be listed
    plugins = agent.plugin_registry.list_all()
    assert isinstance(plugins, list)

    # Cleanup
    import shutil
    if workspace.exists():
        shutil.rmtree(workspace)


@pytest.mark.asyncio
async def test_vector_store_lazy_initialization():
    """Test that vector store is lazily initialized."""
    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="gpt-4")

    workspace = Path("./test_workspace")
    workspace.mkdir(exist_ok=True)

    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
        enable_hybrid_memory=False
    )

    # Verify vector store is not initialized yet
    assert agent._vector_store is None

    # Access vector_store property triggers lazy initialization
    store = agent.vector_store
    assert store is not None

    # Verify it has search method (either real or dummy)
    assert hasattr(store, 'search')

    # Cleanup
    import shutil
    if workspace.exists():
        shutil.rmtree(workspace)


@pytest.mark.asyncio
async def test_memory_search_tool_registered():
    """Test that memory search tool is registered."""
    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="gpt-4")

    workspace = Path("./test_workspace")
    workspace.mkdir(exist_ok=True)

    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
        enable_hybrid_memory=False
    )

    # Verify memory_search tool is registered
    tool = agent.tools.get("memory_search")
    assert tool is not None
    assert tool.name == "memory_search"

    # Cleanup
    import shutil
    if workspace.exists():
        shutil.rmtree(workspace)
