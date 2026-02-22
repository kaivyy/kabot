# kabot/memory/reranker.py
"""Reranker: score filtering + token guard for memory injection."""

from __future__ import annotations

from loguru import logger


class Reranker:
    """Score, filter, and cap memory results before LLM injection.

    Three-stage pipeline:
    1. Threshold filter: discard results below minimum relevance
    2. Top-K selection: keep only the best K results
    3. Token guard: enforce hard token budget on total injected text
    """

    def __init__(
        self,
        threshold: float = 0.6,
        top_k: int = 3,
        max_tokens: int = 500,
    ):
        self.threshold = threshold
        self.top_k = top_k
        self.max_tokens = max_tokens

    def rank(self, query: str, results: list[dict]) -> list[dict]:
        """Filter and rank results through the three-stage pipeline.

        Args:
            query: Original query (for logging).
            results: List of dicts with at least 'content' and 'score' keys.

        Returns:
            Filtered, sorted, token-guarded list of results.
        """
        if not results:
            return []

        # Stage 1: threshold filter
        above = [r for r in results if float(r.get("score", 0)) >= self.threshold]

        # Stage 2: sort + top-k
        above.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
        top = above[: self.top_k]

        # Stage 3: token guard
        guarded = self._token_guard(top)

        if len(guarded) < len(results):
            logger.debug(
                f"Reranker: {len(results)} → {len(guarded)} results "
                f"(threshold={self.threshold}, top_k={self.top_k}, max_tok={self.max_tokens})"
            )

        return guarded

    def _token_guard(self, results: list[dict]) -> list[dict]:
        """Enforce hard token budget on cumulative content."""
        total = 0.0
        kept: list[dict] = []
        for r in results:
            content = r.get("content", "")
            tokens = self.count_tokens(content)
            if total + tokens <= self.max_tokens:
                kept.append(r)
                total += tokens
            else:
                break  # budget exhausted
        return kept

    @staticmethod
    def count_tokens(text: str) -> float:
        """Estimate token count using word-count × 1.3 heuristic."""
        return len(text.split()) * 1.3
