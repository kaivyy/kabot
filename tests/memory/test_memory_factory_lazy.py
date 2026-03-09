from __future__ import annotations

from pathlib import Path

import pytest

from kabot.memory.memory_factory import MemoryFactory


def test_factory_can_create_lazy_probe_memory_for_hybrid_backend(tmp_path: Path):
    from kabot.memory.lazy_probe_memory import LazyProbeMemory

    backend = MemoryFactory.create(
        {"memory": {"backend": "hybrid"}},
        tmp_path,
        lazy_probe=True,
    )

    assert isinstance(backend, LazyProbeMemory)
    assert backend._hybrid is None


@pytest.mark.asyncio
async def test_lazy_probe_memory_preserves_history_without_hybrid_boot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    from kabot.memory.lazy_probe_memory import LazyProbeMemory

    calls: list[str] = []

    class _FakeHybrid:
        def __init__(self, *args, **kwargs):
            calls.append("hybrid")

    monkeypatch.setattr("kabot.memory.chroma_memory.HybridMemoryManager", _FakeHybrid)

    backend = LazyProbeMemory.from_config({"memory": {"backend": "hybrid"}}, tmp_path)
    backend.create_session("cli:direct", "cli", "direct")
    await backend.add_message("cli:direct", "user", "halo")

    history = backend.get_conversation_context("cli:direct")

    assert [item["content"] for item in history] == ["halo"]
    assert calls == []


@pytest.mark.asyncio
async def test_lazy_probe_memory_upgrades_only_on_semantic_search(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    from kabot.memory.lazy_probe_memory import LazyProbeMemory

    calls: list[str] = []

    class _FakeHybrid:
        def __init__(self, *args, **kwargs):
            calls.append("hybrid")
            self.metadata = object()

        async def search_memory(self, query, session_id=None, limit=5):
            return [{"content": query, "session_id": session_id, "limit": limit}]

        async def remember_fact(self, fact, category="general", session_id=None, confidence=1.0):
            return True

        def search_graph(self, entity: str, limit: int = 10):
            return [{"src_name": entity, "relation": "knows", "dst_name": "bot"}]

        def get_graph_context(self, query: str | None = None, limit: int = 8):
            return f"graph:{query}:{limit}"

        def get_stats(self):
            return {"backend": "hybrid"}

        def health_check(self):
            return {"status": "ok", "backend": "hybrid"}

    monkeypatch.setattr("kabot.memory.chroma_memory.HybridMemoryManager", _FakeHybrid)

    backend = LazyProbeMemory.from_config({"memory": {"backend": "hybrid"}}, tmp_path)
    backend.create_session("cli:direct", "cli", "direct")
    await backend.add_message("cli:direct", "user", "halo")

    assert calls == []

    results = await backend.search_memory("timezone", session_id="cli:direct", limit=3)

    assert calls == ["hybrid"]
    assert results == [{"content": "timezone", "session_id": "cli:direct", "limit": 3}]
