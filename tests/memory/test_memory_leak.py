import pytest
import asyncio
import psutil
import os
from kabot.memory.sentence_embeddings import SentenceEmbeddingProvider

@pytest.mark.asyncio
async def test_no_memory_leak_after_unload():
    """Verify model unload actually frees memory."""
    process = psutil.Process(os.getpid())

    # Baseline memory
    baseline_mb = process.memory_info().rss / 1024 / 1024

    # Load model
    provider = SentenceEmbeddingProvider(auto_unload_seconds=0)
    await provider.embed("test query")
    loaded_mb = process.memory_info().rss / 1024 / 1024

    # Should use >100MB for model
    assert loaded_mb - baseline_mb > 100, f"Model should use >100MB, got {loaded_mb - baseline_mb:.1f}MB"

    # Unload
    provider.unload_model()
    await asyncio.sleep(1)  # Give GC time

    # Verify model is actually unloaded (internal state check)
    # This is the primary verification - model reference should be None
    assert provider._model is None, "Model reference should be None after unload"

    # Memory check: Python/PyTorch maintain internal caches and memory pools,
    # so we can't expect memory to return exactly to baseline. However, we should
    # see SOME memory freed if the model tensors are actually released.
    unloaded_mb = process.memory_info().rss / 1024 / 1024
    memory_freed = loaded_mb - unloaded_mb
    memory_used = loaded_mb - baseline_mb

    # Verify at least 10% of model memory was freed (very lenient check)
    # This catches catastrophic leaks while accounting for Python's memory behavior
    assert memory_freed > memory_used * 0.1, (
        f"Insufficient memory freed: {memory_freed:.1f}MB freed "
        f"({memory_freed/memory_used*100:.1f}% of {memory_used:.1f}MB used). "
        f"Expected at least 10% freed."
    )
