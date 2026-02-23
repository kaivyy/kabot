import pytest
from pathlib import Path
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
