import pytest
import asyncio
import psutil
import os
import gc
from kabot.memory.sentence_embeddings import SentenceEmbeddingProvider

@pytest.mark.asyncio
async def test_no_memory_leak_after_unload():
    """RAM should be freed after unload."""
    process = psutil.Process(os.getpid())

    # Baseline
    baseline_mb = process.memory_info().rss / 1024 / 1024

    # Load model (first time)
    provider = SentenceEmbeddingProvider()
    await provider.embed("test query")
    loaded_mb = process.memory_info().rss / 1024 / 1024

    # Should increase by ~150MB+ (model loading)
    assert loaded_mb - baseline_mb > 100

    # Unload
    provider.unload_model()
    del provider

    # Force garbage collection
    for _ in range(10):
        gc.collect()
    await asyncio.sleep(2)

    unloaded_mb = process.memory_info().rss / 1024 / 1024

    # Load model again (second time)
    provider2 = SentenceEmbeddingProvider()
    await provider2.embed("test query 2")
    reloaded_mb = process.memory_info().rss / 1024 / 1024

    # Unload again
    provider2.unload_model()
    del provider2

    # Force garbage collection
    for _ in range(10):
        gc.collect()

    # Key test: If there's no leak, reloading shouldn't increase memory significantly
    # beyond the first load. Memory should be reused from the pool.
    # Allow 60MB tolerance for Python allocator overhead and variance
    assert abs(reloaded_mb - loaded_mb) < 60, \
        f"Memory leak detected! First load: {loaded_mb:.1f}MB, Reload: {reloaded_mb:.1f}MB, Diff: {reloaded_mb - loaded_mb:.1f}MB"
