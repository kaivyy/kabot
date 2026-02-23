"""Null memory backend — no-op implementation for disabled memory."""
from __future__ import annotations

import uuid

from kabot.memory.memory_backend import MemoryBackend


class NullMemory(MemoryBackend):
    """No-op memory backend. All reads return empty, all writes are discarded."""

    def add_message(self, session_id, role, content, parent_id=None,
                    tool_calls=None, tool_results=None, metadata=None):
        return str(uuid.uuid4())

    def search_memory(self, query, session_id=None, limit=5):
        return []

    def remember_fact(self, fact, category="general", session_id=None,
                      confidence=1.0):
        return str(uuid.uuid4())

    def get_conversation_context(self, session_id, max_messages=20):
        return []

    def create_session(self, session_id, channel, chat_id, user_id=None):
        pass

    def get_stats(self):
        return {"backend": "disabled", "messages": 0, "facts": 0, "sessions": 0}

    def health_check(self):
        return {"status": "ok", "backend": "disabled", "message": "Memory disabled"}
