from pathlib import Path

from kabot.memory.graph_memory import GraphMemory
from kabot.memory.sqlite_memory import SQLiteMemory


def test_graph_memory_extracts_and_queries_relations(tmp_path: Path):
    graph = GraphMemory(tmp_path / "graph.db")
    out = graph.ingest_text(
        session_id="s1",
        role="user",
        content="kabot uses chromadb for memory retrieval",
    )
    assert out["relations"] >= 1

    rows = graph.query_related("kabot", limit=5)
    assert rows
    assert any(
        row.get("relation") == "uses" and "chromadb" in str(row.get("dst_name", "")).lower()
        for row in rows
    )


def test_graph_memory_summary_contains_relation(tmp_path: Path):
    graph = GraphMemory(tmp_path / "graph.db")
    graph.ingest_text(
        session_id="s1",
        role="assistant",
        content="api-gateway depends on redis cache",
    )
    summary = graph.summarize(limit=5)
    assert "depends_on" in summary
    assert "redis" in summary.lower()


def test_sqlite_memory_exposes_graph_context(tmp_path: Path):
    memory = SQLiteMemory(tmp_path / "mem", enable_graph_memory=True)
    memory.add_message("session-1", "user", "aku suka python")
    summary = memory.get_graph_context(limit=5)
    assert "user prefers python" in summary.lower()

