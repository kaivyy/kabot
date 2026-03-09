# kabot/memory/__init__.py
"""Memory system for Kabot — Hybrid Architecture (ChromaDB + BM25 + SmartRouter + Reranker)."""

_MODULE_LOCKS = {
    "HybridMemoryManager": ".chroma_memory",
    "ChromaMemoryManager": ".chroma_memory",
    "MemoryBackend": ".memory_backend",
    "MemoryFactory": ".memory_factory",
    "LazyProbeMemory": ".lazy_probe_memory",
    "NullMemory": ".null_memory",
    "SQLiteMemory": ".sqlite_memory",
    "SmartRouter": ".smart_router",
    "Reranker": ".reranker",
    "EpisodicExtractor": ".episodic_extractor",
    "ExtractedFact": ".episodic_extractor",
    "MemoryPruner": ".memory_pruner",
    "GraphMemory": ".graph_memory",
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
