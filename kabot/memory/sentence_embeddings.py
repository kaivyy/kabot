"""Sentence-Transformers embedding provider for local embeddings."""

import hashlib
from typing import Any

from loguru import logger


class SentenceEmbeddingProvider:
    """
    Local embedding provider using Sentence-Transformers.

    Supports models like:
    - all-MiniLM-L6-v2 (recommended, 384 dimensions, fast)
    - all-mpnet-base-v2 (768 dimensions, more accurate)
    - paraphrase-multilingual-MiniLM-L12-v2 (multilingual support)
    """

    def __init__(self, model: str = "all-MiniLM-L6-v2"):
        self.model_name = model
        self._model = None
        self._cache = {}  # Simple LRU cache
        self._cache_size = 1000

    def _load_model(self):
        """Lazy load the sentence-transformers model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading sentence-transformers model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                logger.info(f"Model loaded successfully. Dimensions: {self.dimensions}")

            except ImportError:
                logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
                raise
            except Exception as e:
                logger.error(f"Error loading model: {e}")
                raise

    async def embed(self, text: str) -> list[float] | None:
        """
        Generate embedding for text using Sentence-Transformers.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if failed
        """
        try:
            # Check cache
            cache_key = hashlib.md5(text.encode()).hexdigest()
            if cache_key in self._cache:
                return self._cache[cache_key]

            # Load model if needed
            self._load_model()

            # Generate embedding
            embedding = self._model.encode(text)
            if hasattr(embedding, 'tolist'):
                embedding = embedding.tolist()

            if embedding:
                # Cache result
                if len(self._cache) >= self._cache_size:
                    # Remove oldest entry (simple FIFO)
                    self._cache.pop(next(iter(self._cache)))
                self._cache[cache_key] = embedding

            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings
        """
        try:
            # Load model if needed
            self._load_model()

            # Generate embeddings in batch (more efficient)
            embeddings = self._model.encode(texts)
            if hasattr(embeddings, 'tolist'):
                embeddings = embeddings.tolist()

            # Cache results
            results = []
            for text, embedding in zip(texts, embeddings):
                cache_key = hashlib.md5(text.encode()).hexdigest()
                if len(self._cache) >= self._cache_size:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[cache_key] = embedding
                results.append(embedding)

            return results

        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            return [None] * len(texts)

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions for current model."""
        dimensions_map = {
            "all-MiniLM-L6-v2": 384,
            "all-mpnet-base-v2": 768,
            "paraphrase-multilingual-MiniLM-L12-v2": 384,
            "all-distilroberta-v1": 768,
            "all-MiniLM-L12-v2": 384,
        }
        return dimensions_map.get(self.model_name, 384)

    def check_connection(self) -> bool:
        """Check if model can be loaded."""
        try:
            self._load_model()
            return self._model is not None
        except Exception:
            return False

    def get_model_info(self) -> dict:
        """Get information about the loaded model."""
        return {
            "model_name": self.model_name,
            "dimensions": self.dimensions,
            "cached_items": len(self._cache),
            "loaded": self._model is not None
        }
