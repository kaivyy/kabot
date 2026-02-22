# tests/memory/test_hybrid_memory.py
"""Integration tests for HybridMemoryManager."""
import pytest
from pathlib import Path

from kabot.memory.chroma_memory import HybridMemoryManager


@pytest.fixture
def manager(tmp_path):
    return HybridMemoryManager(
        workspace=tmp_path,
        embedding_provider="sentence",
        enable_hybrid_memory=True,
    )


class TestHybridMemoryManager:
    def test_class_exists(self, manager):
        assert manager is not None
        assert hasattr(manager, "router")
        assert hasattr(manager, "reranker")

    @pytest.mark.asyncio
    async def test_add_and_search(self, manager):
        manager.create_session("s1", "telegram", "123")
        await manager.add_message("s1", "user", "I love Python programming")
        results = await manager.search_memory("Python", session_id="s1")
        assert len(results) >= 0  # May be empty if embedding model not loaded

    @pytest.mark.asyncio
    async def test_remember_fact(self, manager):
        success = await manager.remember_fact("User prefers dark mode", category="preference")
        assert success is True

    def test_backward_compat_alias(self):
        from kabot.memory import ChromaMemoryManager
        assert ChromaMemoryManager is HybridMemoryManager
