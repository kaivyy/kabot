"""Memory retrieval strategy selection."""

from __future__ import annotations

from typing import Literal

MemoryRoute = Literal["episodic", "knowledge", "hybrid"]


class SmartRouter:
    """Return a stable retrieval strategy without lexical query parsing.

    Hybrid memory already combines semantic search, lexical BM25 search, and
    reranking. Letting keyword buckets suppress parts of that stack makes
    retrieval brittle and language-dependent, so the router now defaults to the
    full hybrid path for every query.
    """

    def route(self, query: str) -> MemoryRoute:
        """Return the retrieval strategy for a query."""
        return "hybrid"
