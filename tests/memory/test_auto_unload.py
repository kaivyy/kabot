import pytest
import asyncio
from kabot.memory.sentence_embeddings import SentenceEmbeddingProvider

@pytest.mark.asyncio
async def test_model_auto_unloads_after_timeout():
    """Model should unload after idle timeout."""
    provider = SentenceEmbeddingProvider(
        model="all-MiniLM-L6-v2",
        auto_unload_seconds=2
    )

    # Trigger model load
    result = await provider.embed("test query")
    assert result is not None
    assert provider._model is not None

    # Wait for auto-unload
    await asyncio.sleep(3)
    assert provider._model is None

@pytest.mark.asyncio
async def test_timer_resets_on_new_request():
    """Timer should reset when new request comes in."""
    provider = SentenceEmbeddingProvider(auto_unload_seconds=3)

    await provider.embed("query 1")
    await asyncio.sleep(1.5)
    await provider.embed("query 2")  # Reset timer
    await asyncio.sleep(2)

    # Model should still be loaded (only 2s since last request)
    assert provider._model is not None

@pytest.mark.asyncio
async def test_manual_unload():
    """Manual unload should work immediately."""
    provider = SentenceEmbeddingProvider()
    await provider.embed("test")
    assert provider._model is not None

    provider.unload_model()
    assert provider._model is None

@pytest.mark.asyncio
async def test_auto_unload_disabled_when_timeout_zero():
    """Auto-unload should be disabled when timeout is 0."""
    provider = SentenceEmbeddingProvider(auto_unload_seconds=0)
    await provider.embed("test")
    assert provider._model is not None

    await asyncio.sleep(2)
    assert provider._model is not None  # Still loaded

@pytest.mark.asyncio
async def test_model_reloads_after_unload():
    """Model should reload after unload."""
    provider = SentenceEmbeddingProvider(auto_unload_seconds=0)
    result1 = await provider.embed("test query 1")

    provider.unload_model()
    assert provider._model is None

    result2 = await provider.embed("test query 2")
    assert result2 is not None
    assert provider._model is not None
