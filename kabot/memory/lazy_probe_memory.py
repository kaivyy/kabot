"""Lazy memory backend for probe-style one-shot runs.

This backend keeps session creation and recent history lightweight via SQLite,
and only boots the configured hybrid memory stack if a semantic memory
operation is actually requested.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from kabot.memory.memory_backend import MemoryBackend
from kabot.memory.sqlite_memory import SQLiteMemory


class LazyProbeMemory(MemoryBackend):
    """Delay heavy hybrid memory initialization for one-shot probe runs."""

    def __init__(self, config: dict[str, Any], workspace: Path):
        self._config = dict(config)
        self._workspace = Path(workspace)
        self._memory_workspace = self._workspace / "memory_db"
        self._memory_config = dict(self._config.get("memory", {}))
        enable_graph = bool(self._memory_config.get("enable_graph_memory", True))
        self._sqlite = SQLiteMemory(
            workspace=self._memory_workspace,
            enable_graph_memory=enable_graph,
        )
        self._hybrid = None
        self._pending_index_rows: list[tuple[str, str, str, dict[str, Any] | None]] = []
        self.metadata = self._sqlite.metadata
        self.graph = self._sqlite.graph

    @classmethod
    def from_config(cls, config: dict[str, Any], workspace: Path) -> "LazyProbeMemory":
        return cls(config=config, workspace=workspace)

    def _ensure_hybrid(self):
        if self._hybrid is not None:
            return self._hybrid

        from kabot.memory.memory_factory import MemoryFactory

        self._hybrid = MemoryFactory.create(self._config, self._workspace, lazy_probe=False)
        self.metadata = getattr(self._hybrid, "metadata", self.metadata)
        self.graph = getattr(self._hybrid, "graph", self.graph)
        logger.info("Lazy probe memory upgraded to configured backend")
        return self._hybrid

    async def _index_with_hybrid(
        self,
        session_id: str,
        message_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        hybrid = self._ensure_hybrid()
        index_message = getattr(hybrid, "_index_message", None)
        if callable(index_message):
            await index_message(session_id, message_id, content, metadata)

    async def _flush_pending_indexes(self) -> None:
        if not self._pending_index_rows:
            return
        pending_rows = list(self._pending_index_rows)
        self._pending_index_rows.clear()
        for session_id, message_id, content, metadata in pending_rows:
            try:
                await self._index_with_hybrid(session_id, message_id, content, metadata)
            except Exception as exc:
                logger.warning(f"Lazy probe memory index backfill failed: {exc}")

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        parent_id: str | None = None,
        tool_calls: list | None = None,
        tool_results: list | None = None,
        metadata: dict | None = None,
    ) -> str:
        message_id = self._sqlite.add_message(
            session_id=session_id,
            role=role,
            content=content,
            parent_id=parent_id,
            tool_calls=tool_calls,
            tool_results=tool_results,
            metadata=metadata,
        )
        if self._hybrid is None:
            self._pending_index_rows.append((session_id, str(message_id), content, metadata))
            return str(message_id)

        try:
            await self._index_with_hybrid(session_id, str(message_id), content, metadata)
        except Exception as exc:
            logger.warning(f"Lazy probe memory live index failed: {exc}")
        return str(message_id)

    async def search_memory(
        self,
        query: str,
        session_id: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        try:
            hybrid = self._ensure_hybrid()
            await self._flush_pending_indexes()
            return await hybrid.search_memory(query=query, session_id=session_id, limit=limit)
        except Exception as exc:
            logger.warning(f"Lazy probe memory search falling back to SQLite: {exc}")
            return self._sqlite.search_memory(query=query, session_id=session_id, limit=limit)

    async def remember_fact(
        self,
        fact: str,
        category: str = "general",
        session_id: str | None = None,
        confidence: float = 1.0,
    ) -> str | bool:
        try:
            hybrid = self._ensure_hybrid()
            await self._flush_pending_indexes()
            return await hybrid.remember_fact(
                fact=fact,
                category=category,
                session_id=session_id,
                confidence=confidence,
            )
        except Exception as exc:
            logger.warning(f"Lazy probe memory remember_fact falling back to SQLite: {exc}")
            return self._sqlite.remember_fact(
                fact=fact,
                category=category,
                session_id=session_id,
                confidence=confidence,
            )

    def get_conversation_context(self, session_id: str, max_messages: int = 20) -> list[dict]:
        return self._sqlite.get_conversation_context(session_id, max_messages=max_messages)

    def create_session(self, session_id: str, channel: str, chat_id: str, user_id: str | None = None) -> None:
        self._sqlite.create_session(session_id, channel, chat_id, user_id=user_id)

    def get_stats(self) -> dict:
        if self._hybrid is not None:
            stats = dict(self._hybrid.get_stats())
        else:
            stats = dict(self._sqlite.get_stats())
        stats["lazy_probe"] = True
        stats["hybrid_loaded"] = self._hybrid is not None
        return stats

    def health_check(self) -> dict:
        if self._hybrid is not None:
            health = dict(self._hybrid.health_check())
        else:
            health = dict(self._sqlite.health_check())
        health["lazy_probe"] = True
        health["hybrid_loaded"] = self._hybrid is not None
        return health

    def search_graph(self, entity: str, limit: int = 10) -> list[dict]:
        try:
            hybrid = self._ensure_hybrid()
            return hybrid.search_graph(entity, limit=limit)
        except Exception as exc:
            logger.warning(f"Lazy probe memory graph search falling back to SQLite: {exc}")
            return self._sqlite.search_graph(entity, limit=limit)

    def get_graph_context(self, query: str | None = None, limit: int = 8) -> str:
        try:
            hybrid = self._ensure_hybrid()
            return hybrid.get_graph_context(query=query, limit=limit)
        except Exception as exc:
            logger.warning(f"Lazy probe memory graph context falling back to SQLite: {exc}")
            return self._sqlite.get_graph_context(query=query, limit=limit)

    async def warmup(self) -> None:
        """Probe-mode runs skip eager warmup by design."""
        return None
