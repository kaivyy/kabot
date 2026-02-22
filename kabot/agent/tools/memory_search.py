"""Memory search tool for semantic search over conversation history."""

from typing import Any

from kabot.agent.tools.base import Tool
from kabot.memory.vector_store import VectorStore


class MemorySearchTool(Tool):
    """Tool for searching memory semantically."""

    def __init__(self, store: Any):
        """
        Initialize memory search tool.

        Args:
            store: Vector store instance or callable that returns it
        """
        self._store_provider = store

    @property
    def store(self) -> VectorStore:
        if callable(self._store_provider):
            return self._store_provider()
        return self._store_provider

    @property
    def name(self) -> str:
        return "memory_search"

    @property
    def description(self) -> str:
        return """Search memory for relevant past conversations and facts.

Use this when you need to recall:
- Previous discussions about a topic
- Facts or information mentioned earlier
- Context from past conversations

Example: memory_search(query="what did we discuss about sharks?")"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to find relevant memories"
                },
                "k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 3)"
                }
            },
            "required": ["query"]
        }

    async def execute(self, query: str, k: int = 3, **kwargs: Any) -> str:
        """
        Execute semantic search over memory.

        Args:
            query: Search query
            k: Number of results to return

        Returns:
            Formatted search results
        """
        results = self.store.search(query, k=k)

        if not results:
            return "No relevant memories found."

        output = []
        for i, r in enumerate(results, 1):
            output.append(f"{i}. {r.content}")

        return "\n\n".join(output)
