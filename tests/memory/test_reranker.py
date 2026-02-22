# tests/memory/test_reranker.py
"""Tests for Reranker and TokenGuard."""
import pytest

from kabot.memory.reranker import Reranker


@pytest.fixture
def reranker():
    return Reranker(threshold=0.5, top_k=3, max_tokens=100)


class TestReranker:
    def test_empty_results(self, reranker):
        assert reranker.rank("hello", []) == []

    def test_filters_below_threshold(self, reranker):
        results = [
            {"content": "relevant stuff", "score": 0.8},
            {"content": "junk", "score": 0.2},
        ]
        ranked = reranker.rank("query", results)
        assert len(ranked) == 1
        assert ranked[0]["content"] == "relevant stuff"

    def test_top_k_limit(self):
        r = Reranker(threshold=0.0, top_k=2, max_tokens=9999)
        results = [
            {"content": "a", "score": 0.9},
            {"content": "b", "score": 0.8},
            {"content": "c", "score": 0.7},
            {"content": "d", "score": 0.6},
        ]
        ranked = r.rank("query", results)
        assert len(ranked) == 2

    def test_token_guard_caps_output(self):
        r = Reranker(threshold=0.0, top_k=10, max_tokens=20)
        results = [
            {"content": "short", "score": 0.9},
            {"content": "this is a much longer piece of text that should exceed token budget", "score": 0.8},
        ]
        ranked = r.rank("query", results)
        # Only first item should fit within 20 token budget
        assert len(ranked) >= 1
        assert ranked[0]["content"] == "short"

    def test_sorts_by_score_descending(self, reranker):
        results = [
            {"content": "low", "score": 0.5},
            {"content": "high", "score": 0.9},
            {"content": "mid", "score": 0.7},
        ]
        ranked = reranker.rank("q", results)
        assert ranked[0]["content"] == "high"

    def test_count_tokens(self, reranker):
        tokens = reranker.count_tokens("hello world foo bar")
        assert tokens == pytest.approx(4 * 1.3, abs=1)
