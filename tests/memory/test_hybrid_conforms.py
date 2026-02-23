"""Test that HybridMemoryManager conforms to MemoryBackend ABC."""
from kabot.memory.memory_backend import MemoryBackend


def test_hybrid_is_subclass_of_memory_backend():
    from kabot.memory.chroma_memory import HybridMemoryManager
    assert issubclass(HybridMemoryManager, MemoryBackend)
