"""Tests for context window guard."""

import pytest
from kabot.agent.context_guard import ContextGuard


def test_context_guard_detects_overflow():
    """Test that guard detects when context exceeds limit."""
    guard = ContextGuard(max_tokens=1000, buffer_tokens=100)

    # Simulate messages that exceed limit (use varied content for realistic token count)
    messages = [
        {"role": "user", "content": " ".join([f"word{i}" for i in range(200)])},
        {"role": "assistant", "content": " ".join([f"response{i}" for i in range(200)])},
        {"role": "user", "content": " ".join([f"question{i}" for i in range(100)])},
    ]

    needs_compaction = guard.check_overflow(messages, model="gpt-4")
    assert needs_compaction is True


def test_context_guard_allows_within_limit():
    """Test that guard allows messages within limit."""
    guard = ContextGuard(max_tokens=10000, buffer_tokens=1000)

    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]

    needs_compaction = guard.check_overflow(messages, model="gpt-4")
    assert needs_compaction is False
