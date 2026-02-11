"""Ollama embedding provider for local embeddings."""

import httpx
import hashlib
from typing import Any

from loguru import logger


class OllamaEmbeddingProvider:
    """
    Local embedding provider using Ollama.

    Supports models like:
    - nomic-embed-text (recommended, 768 dimensions)
    - mxbai-embed-large
    - all-minilm
    """

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "nomic-embed-text"):
        self.base_url = base_url
        self.model = model
        self._cache = {}  # Simple LRU cache
        self._cache_size = 1000

    async def embed(self, text: str) -> list[float] | None:
        """
        Generate embedding for text using Ollama.

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

            url = f"{self.base_url}/api/embeddings"
            payload = {
                "model": self.model,
                "prompt": text
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=30.0)

                if response.status_code != 200:
                    logger.error(f"Ollama embedding failed: {response.status_code}")
                    return None

                data = response.json()
                embedding = data.get("embedding")

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
        # Process sequentially to avoid overwhelming Ollama
        results = []
        for text in texts:
            embedding = await self.embed(text)
            results.append(embedding)
        return results

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions for current model."""
        dimensions_map = {
            "nomic-embed-text": 768,
            "mxbai-embed-large": 1024,
            "all-minilm": 384,
        }
        return dimensions_map.get(self.model, 768)

    def check_connection(self) -> bool:
        """Check if Ollama is running."""
        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False
