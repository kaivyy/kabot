"""Tests for MemoryBackend abstract protocol."""
import pytest

from kabot.memory.memory_backend import MemoryBackend


def test_memory_backend_cannot_be_instantiated():
    """ABC should not be directly instantiatable."""
    with pytest.raises(TypeError):
        MemoryBackend()


def test_memory_backend_has_required_methods():
    """ABC must define the contract methods."""
    required = {"add_message", "search_memory", "remember_fact",
                "get_conversation_context", "create_session",
                "get_stats", "health_check"}
    abstract_methods = set(MemoryBackend.__abstractmethods__)
    assert required.issubset(abstract_methods)
