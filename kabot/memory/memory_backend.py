"""Abstract base class for all memory backends."""
from __future__ import annotations

from abc import ABC, abstractmethod


class MemoryBackend(ABC):
    """Contract for swappable memory backends.

    All backends must implement these methods to be compatible
    with the AgentLoop and memory tools.
    """

    @abstractmethod
    def add_message(self, session_id: str, role: str, content: str,
                    parent_id: str | None = None,
                    tool_calls: list | None = None,
                    tool_results: list | None = None,
                    metadata: dict | None = None) -> str:
        """Add a message to memory. Returns message_id."""

    @abstractmethod
    def search_memory(self, query: str, session_id: str | None = None,
                      limit: int = 5) -> list[dict]:
        """Search memory for relevant results."""

    @abstractmethod
    def remember_fact(self, fact: str, category: str = "general",
                      session_id: str | None = None,
                      confidence: float = 1.0) -> str:
        """Store a long-term fact. Returns fact_id."""

    @abstractmethod
    def get_conversation_context(self, session_id: str,
                                  max_messages: int = 20) -> list[dict]:
        """Get recent conversation context."""

    @abstractmethod
    def create_session(self, session_id: str, channel: str, chat_id: str,
                       user_id: str | None = None) -> None:
        """Create a new conversation session."""

    @abstractmethod
    def get_stats(self) -> dict:
        """Get memory system statistics."""

    @abstractmethod
    def health_check(self) -> dict:
        """Check memory system health."""
