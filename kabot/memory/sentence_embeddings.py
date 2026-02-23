"""Sentence-Transformers embedding provider for local embeddings."""

import hashlib
import time
import gc
import threading

from loguru import logger


class SentenceEmbeddingProvider:
    """
    Local embedding provider using Sentence-Transformers.

    Supports models like:
    - all-MiniLM-L6-v2 (recommended, 384 dimensions, fast)
    - all-mpnet-base-v2 (768 dimensions, more accurate)
    - paraphrase-multilingual-MiniLM-L12-v2 (multilingual support)
    """

    def __init__(self, model: str = "all-MiniLM-L6-v2", auto_unload_seconds: int = 300):
        if auto_unload_seconds < 0:
            raise ValueError("auto_unload_seconds must be >= 0")
        self.model_name = model
        self._model = None
        self._cache = {}  # Simple LRU cache
        self._cache_size = 1000
        self._auto_unload_seconds = auto_unload_seconds
        self._last_used = None
        self._unload_timer = None
        self._auto_unload_enabled = auto_unload_seconds > 0
        self._lock = threading.RLock()  # Change Lock to RLock

    def _load_model(self):
        """Lazy load the sentence-transformers model."""
        if self._model is not None:
            return

        with self._lock:
            # Double-check inside lock
            if self._model is not None:
                return

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

    async def warmup(self):
        """Pre-load the embedding model in a background thread (non-blocking)."""
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_model)

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

            with self._lock:
                self._load_model()
                self._last_used = time.time()

                embedding = self._model.encode(text)
                if hasattr(embedding, 'tolist'):
                    embedding = embedding.tolist()

                if embedding:
                    if len(self._cache) >= self._cache_size:
                        self._cache.pop(next(iter(self._cache)))
                    self._cache[cache_key] = embedding

                if self._auto_unload_enabled:
                    self._reset_unload_timer()

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
            with self._lock:
                # Load model if needed
                self._load_model()
                self._last_used = time.time()

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

                if self._auto_unload_enabled:
                    self._reset_unload_timer()

                return results

        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            return [None] * len(texts)

    def _reset_unload_timer(self):
        """Reset the auto-unload timer."""
        with self._lock:
            if self._unload_timer:
                self._unload_timer.cancel()

            self._unload_timer = threading.Timer(
                self._auto_unload_seconds,
                self._auto_unload_callback
            )
            self._unload_timer.daemon = True
            self._unload_timer.start()

    def _auto_unload_callback(self):
        """Timer callback to unload model after idle timeout."""
        with self._lock:
            if self._model is not None:
                idle_time = time.time() - self._last_used
                if idle_time >= self._auto_unload_seconds:
                    self._unload_model_internal()

    def _unload_model_internal(self):
        """Internal unload without lock acquisition."""
        if self._model is not None:
            logger.info("Unloading sentence-transformers model from RAM")

            # Clear embedding cache first
            self._cache.clear()

            # Move model to CPU to release GPU memory
            try:
                self._model.to('cpu')
            except Exception:
                pass

            # Clear tokenizer to avoid StopIteration errors
            try:
                if hasattr(self._model, 'tokenizer'):
                    self._model.tokenizer = None
            except Exception:
                pass

            # Recursively clear all PyTorch modules to break reference cycles
            def clear_module_recursive(module):
                """Recursively clear a PyTorch module and its children."""
                if module is None:
                    return

                # Clear child modules first (depth-first)
                if hasattr(module, '_modules') and module._modules:
                    for child in list(module._modules.values()):
                        clear_module_recursive(child)
                    module._modules.clear()

                # Clear parameters and buffers
                if hasattr(module, '_parameters') and module._parameters:
                    module._parameters.clear()
                if hasattr(module, '_buffers') and module._buffers:
                    module._buffers.clear()

            # Clear the model recursively
            clear_module_recursive(self._model)

            # Delete model reference
            del self._model
            self._model = None
            self._auto_unload_enabled = False

            # Force garbage collection (multiple passes for cyclic references)
            import gc
            for _ in range(3):
                gc.collect()

            # Clear PyTorch cache
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                torch.cuda.empty_cache() if hasattr(torch.cuda, 'empty_cache') else None
            except Exception:
                pass

            # Platform-specific memory trimming
            try:
                import sys
                if sys.platform == 'win32':
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    process = kernel32.GetCurrentProcess()
                    kernel32.SetProcessWorkingSetSize(process, -1, -1)
                    kernel32.EmptyWorkingSet(process)
                elif sys.platform in ('linux', 'linux2'):
                    import ctypes
                    libc = ctypes.CDLL('libc.so.6')
                    libc.malloc_trim(0)
            except Exception:
                pass

    def unload_model(self):
        """Manually unload the model to free RAM."""
        with self._lock:
            if self._unload_timer:
                self._unload_timer.cancel()
                self._unload_timer = None
            self._unload_model_internal()

    def get_memory_stats(self) -> dict:
        """Get memory statistics."""
        return {
            "model_loaded": self._model is not None,
            "last_used": self._last_used,
            "auto_unload_seconds": self._auto_unload_seconds,
            "auto_unload_enabled": self._auto_unload_enabled
        }

    def __del__(self):
        """Cleanup on destruction."""
        if self._unload_timer:
            self._unload_timer.cancel()
        if self._model is not None:
            self._unload_model_internal()

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
