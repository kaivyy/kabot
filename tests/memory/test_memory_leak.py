import asyncio

import psutil
import pytest

from kabot.memory.sentence_embeddings import SentenceEmbeddingProvider


@pytest.mark.asyncio
async def test_no_memory_leak_after_unload():
    """Verify subprocess is properly terminated and memory is freed.

    With subprocess architecture, the model runs in a separate process.
    When unloaded, the subprocess is killed and OS reclaims ALL its memory.
    This test verifies the subprocess lifecycle, not main process memory.
    """
    # Load model (starts subprocess)
    provider = SentenceEmbeddingProvider(auto_unload_seconds=0)
    await provider.embed("test query")

    # Verify subprocess is running
    assert provider._is_subprocess_alive(), "Subprocess should be alive after embed"
    subprocess_pid = provider._process.pid

    # Verify subprocess exists in OS
    try:
        subprocess_process = psutil.Process(subprocess_pid)
        subprocess_mb = subprocess_process.memory_info().rss / 1024 / 1024
        assert subprocess_mb > 100, f"Subprocess should use >100MB for model, got {subprocess_mb:.1f}MB"
    except psutil.NoSuchProcess:
        pytest.fail("Subprocess should exist in OS")

    # Unload (kills subprocess)
    provider.unload_model()
    await asyncio.sleep(1)  # Give OS time to clean up

    # Verify subprocess is terminated
    assert not provider._is_subprocess_alive(), "Subprocess should be terminated after unload"

    # Verify subprocess no longer exists in OS (memory freed)
    try:
        psutil.Process(subprocess_pid)
        pytest.fail("Subprocess should not exist in OS after unload")
    except psutil.NoSuchProcess:
        # Expected - subprocess was killed and OS reclaimed memory
        pass
