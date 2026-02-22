# tests/memory/test_smart_router.py
"""Tests for SmartRouter query classification."""
import pytest

from kabot.memory.smart_router import SmartRouter


@pytest.fixture
def router():
    return SmartRouter()


class TestSmartRouter:
    def test_episodic_query_id(self, router):
        assert router.route("kamu tadi bilang apa?") == "episodic"

    def test_episodic_query_en(self, router):
        assert router.route("do you remember what I said?") == "episodic"

    def test_knowledge_query_id(self, router):
        assert router.route("apa itu machine learning?") == "knowledge"

    def test_knowledge_query_en(self, router):
        assert router.route("explain how DNS works") == "knowledge"

    def test_hybrid_query(self, router):
        assert router.route("tadi kamu jelaskan apa itu API kan?") == "hybrid"

    def test_ambiguous_defaults_hybrid(self, router):
        assert router.route("hello how are you") == "hybrid"

    def test_empty_defaults_hybrid(self, router):
        assert router.route("") == "hybrid"

    def test_multilingual_ja(self, router):
        assert router.route("あなたは何と言いましたか") == "episodic"
