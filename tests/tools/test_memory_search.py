"""Tests for memory search tool."""


import pytest

from kabot.agent.tools.memory_search import MemorySearchTool
from kabot.memory.vector_store import VectorStore


@pytest.fixture
def memory_store(tmp_path):
    """Create a vector store with test data."""
    store = VectorStore(path=str(tmp_path), collection_name="test_search")
    store.add(
        documents=[
            "We discussed sharks and their hunting behavior",
            "Python programming tips for beginners",
            "The weather forecast for tomorrow is sunny"
        ],
        ids=["1", "2", "3"]
    )
    return store


@pytest.mark.asyncio
async def test_memory_search_tool(memory_store):
    """Test basic memory search functionality."""
    tool = MemorySearchTool(memory_store)

    assert tool.name == "memory_search"
    assert "query" in tool.parameters["properties"]

    result = await tool.execute(query="sharks")
    assert "sharks" in result.lower() or "hunting" in result.lower()


@pytest.mark.asyncio
async def test_memory_search_no_results(tmp_path):
    """Test search with no results."""
    store = VectorStore(path=str(tmp_path), collection_name="empty_search")
    tool = MemorySearchTool(store)

    result = await tool.execute(query="nonexistent topic")
    assert "No relevant memories found" in result


@pytest.mark.asyncio
async def test_memory_search_with_k_param(memory_store):
    """Test search with custom k parameter."""
    tool = MemorySearchTool(memory_store)

    result = await tool.execute(query="programming", k=1)
    # Should return only 1 result
    assert result.count("\n\n") == 0  # No double newlines means single result
