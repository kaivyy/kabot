import pytest
import asyncio
from kabot.memory.sentence_embeddings import SentenceEmbeddingProvider

@pytest.mark.asyncio
async def test_model_unload_mechanism():
    """Verify model unload mechanism works correctly.

    Note: This test verifies the unload API works, not actual OS-level memory freeing.
    PyTorch and sentence-transformers may retain memory in internal pools even after
    model deletion, which is expected Python/PyTorch behavior.
    """
    provider = SentenceEmbeddingProvider()

    # Initially no model loaded
    assert provider._model is None
    assert len(provider._cache) == 0

    # Load model by embedding
    result = await provider.embed("test query")
    assert result is not None
    assert len(result) == 384  # all-MiniLM-L6-v2 dimensions
    assert provider._model is not None
    assert len(provider._cache) == 1  # Query cached

    # Embed another query
    result2 = await provider.embed("another query")
    assert result2 is not None
    assert provider._model is not None
    assert len(provider._cache) == 2

    # Unload model
    provider.unload_model()

    # Verify model and cache are cleared
    assert provider._model is None, "Model should be None after unload"
    assert len(provider._cache) == 0, "Cache should be cleared after unload"

    # Verify model can be reloaded
    result3 = await provider.embed("third query")
    assert result3 is not None
    assert provider._model is not None
    assert len(provider._cache) == 1

    # Cleanup
    provider.unload_model()
    assert provider._model is None
