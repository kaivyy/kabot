# kabot/memory/__init__.py
"""Memory system for Kabot — Hybrid Architecture (ChromaDB + BM25 + SmartRouter + Reranker)."""

from .chroma_memory import HybridMemoryManager, ChromaMemoryManager
from .episodic_extractor import EpisodicExtractor, ExtractedFact
from .memory_pruner import MemoryPruner
from .ollama_embeddings import OllamaEmbeddingProvider
from .reranker import Reranker
from .sentence_embeddings import SentenceEmbeddingProvider
from .smart_router import SmartRouter
from .sqlite_store import SQLiteMetadataStore

__all__ = [
    "HybridMemoryManager",
    "ChromaMemoryManager",  # backward compat alias
    "SmartRouter",
    "Reranker",
    "EpisodicExtractor",
    "ExtractedFact",
    "MemoryPruner",
    "SentenceEmbeddingProvider",
    "OllamaEmbeddingProvider",
    "SQLiteMetadataStore",
]
