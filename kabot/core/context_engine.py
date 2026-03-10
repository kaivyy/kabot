"""Pluggable context engine primitives."""

from __future__ import annotations

from typing import Any


class ContextEngine:
    """Interface for compiling model-ready context from session state."""

    def compile(self, session: Any) -> list[dict[str, Any]]:
        raise NotImplementedError


class LegacyContextEngine(ContextEngine):
    """Wrapper around Kabot's legacy session-history behavior."""

    def __init__(self, *, max_messages: int = 50):
        self.max_messages = max(1, int(max_messages))

    def compile(self, session: Any) -> list[dict[str, Any]]:
        if isinstance(session, dict):
            raw_messages = session.get("history") or session.get("messages") or []
        else:
            raw_messages = getattr(session, "messages", [])

        messages = raw_messages[-self.max_messages:] if len(raw_messages) > self.max_messages else raw_messages
        compiled: list[dict[str, Any]] = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            compiled.append(
                {
                    "role": message.get("role", ""),
                    "content": message.get("content", ""),
                }
            )
        return compiled
