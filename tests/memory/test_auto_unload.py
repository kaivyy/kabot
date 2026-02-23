import pytest
import time
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
    time.sleep(3)
    assert provider._model is None
