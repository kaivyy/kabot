"""Tests for SQLiteMemory (lightweight backend)."""

import pytest

from kabot.memory.memory_backend import MemoryBackend
from kabot.memory.sqlite_memory import SQLiteMemory


@pytest.fixture
def mem(tmp_path):
    return SQLiteMemory(workspace=tmp_path / "test_mem")


def test_sqlite_memory_is_memory_backend(mem):
    assert isinstance(mem, MemoryBackend)


def test_add_and_search_message(mem):
    mem.create_session("s1", "telegram", "chat1")
    mem.add_message("s1", "user", "I love pizza")
    results = mem.search_memory("pizza")
    assert len(results) >= 1
    assert "pizza" in results[0]["content"].lower()


def test_remember_and_retrieve_fact(mem):
    fact_id = mem.remember_fact("User prefers dark mode", category="preference")
    assert isinstance(fact_id, str)
    stats = mem.get_stats()
    assert stats["facts"] >= 1


def test_get_conversation_context(mem):
    mem.create_session("s1", "telegram", "chat1")
    mem.add_message("s1", "user", "hello")
    mem.add_message("s1", "assistant", "hi there!")
    ctx = mem.get_conversation_context("s1")
    assert len(ctx) == 2


def test_get_conversation_context_surfaces_tool_call_id_for_tool_messages(mem):
    mem.create_session("s1", "telegram", "chat1")
    mem.add_message(
        "s1",
        "assistant",
        "",
        tool_calls=[{"id": "call-1", "name": "web_fetch", "arguments": {"url": "https://example.com"}}],
    )
    mem.add_message(
        "s1",
        "tool",
        "HTTP 200",
        tool_results=[{"tool_call_id": "call-1", "name": "web_fetch", "result": "HTTP 200"}],
    )

    ctx = mem.get_conversation_context("s1")

    assert ctx[-1]["role"] == "tool"
    assert ctx[-1]["tool_call_id"] == "call-1"
    assert ctx[-1]["name"] == "web_fetch"


def test_health_check(mem):
    status = mem.health_check()
    assert status["status"] == "ok"
    assert status["backend"] == "sqlite_only"
