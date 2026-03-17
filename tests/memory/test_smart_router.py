"""Tests for SmartRouter query classification."""

import pytest

from kabot.memory.smart_router import SmartRouter


@pytest.fixture
def router():
    return SmartRouter()


class TestSmartRouter:
    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("kamu tadi bilang apa?", "hybrid"),
            ("do you remember what I said?", "hybrid"),
            ("apa itu machine learning?", "hybrid"),
            ("explain how DNS works", "hybrid"),
            ("tadi kamu jelaskan apa itu API kan?", "hybrid"),
            ("hello how are you", "hybrid"),
            ("", "hybrid"),
            ("ã‚ãªãŸã¯ä½•ã¨è¨€ã„ã¾ã—ãã‹", "hybrid"),
        ],
    )
    def test_router_defaults_to_hybrid_for_all_queries(self, router, query, expected):
        assert router.route(query) == expected
