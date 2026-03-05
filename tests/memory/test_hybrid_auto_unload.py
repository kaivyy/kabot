import asyncio

import pytest

from kabot.memory.chroma_memory import HybridMemoryManager


@pytest.mark.asyncio
async def test_manual_unload_api(tmp_path):
    """Manual unload API should work."""
    memory = HybridMemoryManager(
        workspace=tmp_path,
        auto_unload_seconds=300
    )

    # Trigger search (loads model)
    await memory.add_message("test", "user", "test message")
    await memory.search_memory("test", session_id="test")

    # Unload resources
    memory.unload_resources()

    # Check stats
    stats = memory.get_memory_stats()
    assert stats["embedding"]["model_loaded"] is False

@pytest.mark.asyncio
async def test_hybrid_memory_auto_unload_integration(tmp_path):
    """Full hybrid backend should auto-unload model."""
    memory = HybridMemoryManager(
        workspace=tmp_path,
        auto_unload_seconds=2
    )

    # Trigger search (loads model)
    await memory.add_message("test", "user", "test message")
    await memory.search_memory("test query", session_id="test")

    stats = memory.get_memory_stats()
    assert stats["embedding"]["model_loaded"] is True

    # Wait for auto-unload
    await asyncio.sleep(3)

    stats = memory.get_memory_stats()
    assert stats["embedding"]["model_loaded"] is False
