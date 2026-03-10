"""Dormant session queue helpers for resumable pending work."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


class DormantQueue:
    """Store pending work grouped by session key."""

    def __init__(self, initial: dict[str, list[Any]] | None = None):
        self._store: dict[str, deque[Any]] = defaultdict(deque)
        if initial:
            for session_id, items in initial.items():
                if items:
                    self._store[session_id].extend(items)

    def enqueue(self, session_id: str, payload: Any) -> None:
        self._store[session_id].append(payload)

    def has_pending(self, session_id: str) -> bool:
        return bool(self._store.get(session_id))

    def drain(self, session_id: str) -> list[Any]:
        if not self.has_pending(session_id):
            return []
        items = list(self._store[session_id])
        self._store.pop(session_id, None)
        return items

    def snapshot(self) -> dict[str, list[Any]]:
        return {
            session_id: list(items)
            for session_id, items in self._store.items()
            if items
        }
