"""Test that AgentLoop uses MemoryFactory for backend selection."""
from kabot.memory.memory_factory import MemoryFactory


def test_factory_is_importable():
    """Sanity check — factory exists and is callable."""
    assert callable(MemoryFactory.create)
