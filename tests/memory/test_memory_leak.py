import pytest
import asyncio
import psutil
import os
from kabot.memory.sentence_embeddings import SentenceEmbeddingProvider

@pytest.mark.asyncio
async def test_no_memory_leak_after_unload():
    """RAM should be freed after unload."""
    process = psutil.Process(os.getpid())

    # Baseline
    baseline_mb = process.memory_info().rss / 1024 / 1024

    # Load model
    provider = SentenceEmbeddingProvider()
    await provider.embed("test query")
    loaded_mb = process.memory_info().rss / 1024 / 1024

    # Should increase by ~150MB+ (model loading)
    assert loaded_mb - baseline_mb > 100

    # Unload
    provider.unload_model()
    await asyncio.sleep(1)  # Give GC time
    unloaded_mb = process.memory_info().rss / 1024 / 1024

    # Should drop back near baseline (within 100MB tolerance)
    # Tolerance is higher because Python doesn't always release to OS immediately
    assert abs(unloaded_mb - baseline_mb) < 100
