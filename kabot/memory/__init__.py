# kabot/memory/__init__.py
"""Memory system for Kabot — Hybrid Architecture (ChromaDB + BM25 + SmartRouter + Reranker)."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .chroma_memory import ChromaMemoryManager, HybridMemoryManager
    from .episodic_extractor import EpisodicExtractor, ExtractedFact
    from .memory_pruner import MemoryPruner
    from .ollama_embeddings import OllamaEmbeddingProvider
    from .reranker import Reranker
    from .sentence_embeddings import SentenceEmbeddingProvider
    from .smart_router import SmartRouter
    from .sqlite_store import SQLiteMetadataStore

_MODULE_LOCKS = {
    "HybridMemoryManager": ".chroma_memory",
    "ChromaMemoryManager": ".chroma_memory",
    "SmartRouter": ".smart_router",
    "Reranker": ".reranker",
    "EpisodicExtractor": ".episodic_extractor",
    "ExtractedFact": ".episodic_extractor",
    "MemoryPruner": ".memory_pruner",
    "SentenceEmbeddingProvider": ".sentence_embeddings",
    "OllamaEmbeddingProvider": ".ollama_embeddings",
    "SQLiteMetadataStore": ".sqlite_store",
}

__all__ = list(_MODULE_LOCKS.keys())


def __getattr__(name: str):
    if name in _MODULE_LOCKS:
        import importlib
        module_path = _MODULE_LOCKS[name]
        module = importlib.import_module(module_path, __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__} has no attribute {name}")


def __dir__():
    return __all__
