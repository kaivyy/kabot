"""Graph memory query tool."""

from __future__ import annotations

from loguru import logger

from kabot.agent.tools.base import Tool


class GraphMemoryTool(Tool):
    """Inspect entity-relation memory extracted from prior conversations."""

    name = "graph_memory"
    description = "Query relational graph memory (entities and their relations)"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["query", "summarize"],
                "description": "query: find relations for an entity, summarize: compact relation summary",
                "default": "query",
            },
            "entity": {
                "type": "string",
                "description": "Entity name to query (required for action=query)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum rows to return",
                "default": 8,
            },
        },
        "required": [],
    }

    def __init__(self, memory_manager=None):
        self.memory = memory_manager
        self._session_key = ""

    def set_context(self, session_key: str) -> None:
        self._session_key = session_key

    async def execute(self, action: str = "query", entity: str | None = None, limit: int = 8) -> str:
        if not self.memory:
            return "Graph memory unavailable: memory manager not initialized."

        lim = max(1, int(limit or 8))
        try:
            if action == "summarize":
                query = entity.strip() if isinstance(entity, str) and entity.strip() else None
                summary_fn = getattr(self.memory, "get_graph_context", None)
                if not callable(summary_fn):
                    return "Graph memory unavailable for current backend."
                summary = summary_fn(query=query, limit=lim)
                return summary or "Graph memory is currently empty."

            if not entity or not entity.strip():
                return "Error: `entity` is required for graph query."

            query_fn = getattr(self.memory, "search_graph", None)
            if not callable(query_fn):
                return "Graph memory unavailable for current backend."

            rows = query_fn(entity.strip(), limit=lim)
            if not rows:
                return f"No graph relations found for '{entity.strip()}'."

            lines = []
            for row in rows:
                src = str(row.get("src_name", "")).strip()
                rel = str(row.get("relation", "")).strip()
                dst = str(row.get("dst_name", "")).strip()
                mentions = int(row.get("mentions", 1) or 1)
                if src and rel and dst:
                    lines.append(f"- {src} {rel} {dst} (mentions={mentions})")
            if not lines:
                return f"No graph relations found for '{entity.strip()}'."
            return "\n".join(lines)
        except Exception as exc:
            logger.error(f"GraphMemoryTool error: {exc}")
            return f"Error: {exc}"

