"""SQLite-only memory backend — lightweight, no external deps."""
from __future__ import annotations

import uuid
from pathlib import Path

from loguru import logger

from kabot.memory.memory_backend import MemoryBackend
from kabot.memory.sqlite_store import SQLiteMetadataStore


class SQLiteMemory(MemoryBackend):
    """Lightweight memory using only SQLite. No ChromaDB, no embeddings.

    Best for: Termux, Raspberry Pi, low-resource environments.
    Search uses SQL LIKE (keyword match), not semantic similarity.
    """

    def __init__(self, workspace: Path, enable_graph_memory: bool = True):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.metadata = SQLiteMetadataStore(self.workspace / "metadata.db")
        self.graph = None
        if enable_graph_memory:
            try:
                from kabot.memory.graph_memory import GraphMemory
                self.graph = GraphMemory(self.workspace / "graph_memory.db", enabled=True)
            except Exception as e:
                logger.warning(f"SQLiteMemory graph init failed: {e}")
                self.graph = None
        logger.info("SQLiteMemory initialized (lightweight mode, no embeddings)")

    def add_message(self, session_id, role, content, parent_id=None,
                    tool_calls=None, tool_results=None, metadata=None):
        msg_id = str(uuid.uuid4())
        self.metadata.add_message(
            msg_id, session_id, role, content,
            parent_id=parent_id,
            tool_calls=tool_calls,
            tool_results=tool_results,
            metadata=metadata,
        )
        if self.graph:
            self.graph.ingest_text(session_id=session_id, role=role, content=content)
        return msg_id

    def search_memory(self, query, session_id=None, limit=5):
        """Keyword-based search using SQL LIKE."""
        try:
            with self.metadata._get_connection() as conn:
                if session_id:
                    rows = conn.execute(
                        "SELECT message_id, content, role, created_at FROM messages "
                        "WHERE session_id = ? AND content LIKE ? "
                        "ORDER BY created_at DESC LIMIT ?",
                        (session_id, f"%{query}%", limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT message_id, content, role, created_at FROM messages "
                        "WHERE content LIKE ? "
                        "ORDER BY created_at DESC LIMIT ?",
                        (f"%{query}%", limit),
                    ).fetchall()
            return [
                {"id": r[0], "content": r[1], "role": r[2],
                 "created_at": r[3], "score": 1.0}
                for r in rows
            ]
        except Exception as e:
            logger.error(f"SQLiteMemory search error: {e}")
            return []

    def remember_fact(self, fact, category="general", session_id=None,
                      confidence=1.0):
        fact_id = str(uuid.uuid4())
        self.metadata.add_fact(fact_id, category, category, fact,
                               session_id=session_id, confidence=confidence)
        if self.graph:
            self.graph.ingest_text(
                session_id=session_id or "global",
                role="fact",
                content=fact,
                category=category,
            )
        return fact_id

    def get_conversation_context(self, session_id, max_messages=20):
        return self.metadata.get_message_chain(session_id, limit=max_messages)

    def create_session(self, session_id, channel, chat_id, user_id=None):
        self.metadata.create_session(session_id, channel, chat_id, user_id=user_id)

    def get_stats(self):
        base = self.metadata.get_stats()
        base["backend"] = "sqlite_only"
        if self.graph:
            base["graph"] = self.graph.get_stats()
        return base

    def health_check(self):
        try:
            self.metadata.get_stats()
            payload = {"status": "ok", "backend": "sqlite_only"}
            if self.graph:
                payload["graph_memory"] = self.graph.health_check()
            return payload
        except Exception as e:
            return {"status": "error", "backend": "sqlite_only", "error": str(e)}

    def search_graph(self, entity: str, limit: int = 10) -> list[dict]:
        if not self.graph:
            return []
        return self.graph.query_related(entity, limit=limit)

    def get_graph_context(self, query: str | None = None, limit: int = 8) -> str:
        if not self.graph:
            return ""
        return self.graph.summarize(query=query, limit=limit)
