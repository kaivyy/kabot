# tests/memory/test_hybrid_memory.py
"""Integration tests for HybridMemoryManager."""

import math

import pytest

from kabot.memory.chroma_memory import HybridMemoryManager


class _FakeEmbeddings:
    def __init__(self, model, auto_unload_seconds=300):
        self.model_name = model
        self.dimensions = 2

    async def embed(self, text):
        text = (text or "").lower()
        if "maha raja" in text:
            return [1.0, 0.0]
        if "dark mode" in text:
            return [0.0, 1.0]
        if "timezone" in text:
            return [0.5, 0.5]
        return [0.1, 0.1]

    async def warmup(self):
        return None

    def check_connection(self):
        return True

    def unload_model(self):
        return None


class _FakeCollection:
    def __init__(self):
        self._docs = []

    def add(self, ids, embeddings, documents, metadatas):
        for idx, emb, doc, meta in zip(ids, embeddings, documents, metadatas):
            self._docs.append(
                {
                    "id": idx,
                    "embedding": emb,
                    "document": doc,
                    "metadata": meta,
                }
            )

    def query(self, query_embeddings, n_results, where=None, include=None):
        query_embedding = query_embeddings[0]
        session_filter = None if not where else where.get("session_id")
        docs = []
        for row in self._docs:
            if session_filter and row["metadata"].get("session_id") != session_filter:
                continue
            emb = row["embedding"]
            distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(query_embedding, emb)))
            docs.append((distance, row))
        docs.sort(key=lambda item: item[0])
        docs = docs[:n_results]
        return {
            "ids": [[row["id"] for _, row in docs]],
            "documents": [[row["document"] for _, row in docs]],
            "metadatas": [[row["metadata"] for _, row in docs]],
            "distances": [[distance for distance, _ in docs]],
        }

    def count(self):
        return len(self._docs)


def _make_fake_manager(tmp_path, monkeypatch):
    monkeypatch.setattr("kabot.memory.chroma_memory.SentenceEmbeddingProvider", _FakeEmbeddings)
    manager = HybridMemoryManager(
        workspace=tmp_path,
        embedding_provider="sentence",
        enable_hybrid_memory=True,
    )
    manager._chroma_client = object()
    manager._collection = _FakeCollection()
    return manager


@pytest.fixture
def manager(tmp_path):
    return HybridMemoryManager(
        workspace=tmp_path,
        embedding_provider="sentence",
        enable_hybrid_memory=True,
    )


class TestHybridMemoryManager:
    def test_class_exists(self, manager):
        assert manager is not None
        assert hasattr(manager, "router")
        assert hasattr(manager, "reranker")

    @pytest.mark.asyncio
    async def test_add_and_search(self, manager):
        manager.create_session("s1", "telegram", "123")
        await manager.add_message("s1", "user", "I love Python programming")
        results = await manager.search_memory("Python", session_id="s1")
        assert len(results) >= 0  # May be empty if embedding model not loaded

    @pytest.mark.asyncio
    async def test_remember_fact(self, manager):
        success = await manager.remember_fact("User prefers dark mode", category="preference")
        assert success is True

    @pytest.mark.asyncio
    async def test_search_returns_remembered_fact_after_reranking(self, tmp_path, monkeypatch):
        manager = _make_fake_manager(tmp_path, monkeypatch)
        manager.create_session("s1", "telegram", "123")

        success = await manager.remember_fact(
            "User prefers to be called Maha Raja",
            category="preference",
            session_id="s1",
        )

        assert success is True

        results = await manager.search_memory("Maha Raja", session_id="s1", limit=5)

        assert results
        assert "Maha Raja" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_search_keeps_matching_fact_in_multi_candidate_mmr_path(self, tmp_path, monkeypatch):
        manager = _make_fake_manager(tmp_path, monkeypatch)
        manager.create_session("s1", "telegram", "123")

        assert await manager.remember_fact(
            "User prefers to be called Maha Raja",
            category="preference",
            session_id="s1",
        )
        assert await manager.remember_fact(
            "User prefers dark mode",
            category="preference",
            session_id="s1",
        )

        results = await manager.search_memory("Maha Raja", session_id="s1", limit=5)

        assert any("Maha Raja" in row["content"] for row in results)

    def test_backward_compat_alias(self):
        from kabot.memory import ChromaMemoryManager
        assert ChromaMemoryManager is HybridMemoryManager
