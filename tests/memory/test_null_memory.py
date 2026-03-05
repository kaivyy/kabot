"""Tests for NullMemory (disabled backend)."""
from kabot.memory.memory_backend import MemoryBackend
from kabot.memory.null_memory import NullMemory


def test_null_memory_is_memory_backend():
    mem = NullMemory()
    assert isinstance(mem, MemoryBackend)


def test_null_memory_search_returns_empty():
    mem = NullMemory()
    assert mem.search_memory("anything") == []


def test_null_memory_add_message_returns_id():
    mem = NullMemory()
    msg_id = mem.add_message("sess1", "user", "hello")
    assert isinstance(msg_id, str)
    assert len(msg_id) > 0


def test_null_memory_remember_fact_returns_id():
    mem = NullMemory()
    fact_id = mem.remember_fact("user likes coffee")
    assert isinstance(fact_id, str)


def test_null_memory_get_context_returns_empty():
    mem = NullMemory()
    assert mem.get_conversation_context("sess1") == []


def test_null_memory_create_session_does_not_raise():
    mem = NullMemory()
    mem.create_session("s1", "telegram", "chat1")  # no exception


def test_null_memory_health_check():
    mem = NullMemory()
    status = mem.health_check()
    assert status["status"] == "ok"
    assert status["backend"] == "disabled"


def test_null_memory_get_stats():
    mem = NullMemory()
    stats = mem.get_stats()
    assert stats["backend"] == "disabled"
    assert stats["messages"] == 0
