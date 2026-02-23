"""Tests for MemoryFactory — config-driven backend creation."""
import pytest
from pathlib import Path
from kabot.memory.memory_factory import MemoryFactory
from kabot.memory.memory_backend import MemoryBackend
from kabot.memory.null_memory import NullMemory


@pytest.fixture
def workspace(tmp_path):
    return tmp_path / "test_workspace"


def test_factory_creates_disabled_backend(workspace):
    config = {"memory": {"backend": "disabled"}}
    mem = MemoryFactory.create(config, workspace)
    assert isinstance(mem, NullMemory)


def test_factory_creates_sqlite_backend(workspace):
    from kabot.memory.sqlite_memory import SQLiteMemory
    config = {"memory": {"backend": "sqlite_only"}}
    mem = MemoryFactory.create(config, workspace)
    assert isinstance(mem, SQLiteMemory)


def test_factory_creates_hybrid_backend_by_default(workspace):
    from kabot.memory.chroma_memory import HybridMemoryManager
    config = {}  # no memory key = default hybrid
    mem = MemoryFactory.create(config, workspace)
    assert isinstance(mem, HybridMemoryManager)


def test_factory_passes_embedding_config(workspace):
    config = {
        "memory": {
            "backend": "hybrid",
            "embedding_provider": "sentence",
            "embedding_model": "all-MiniLM-L6-v2",
        }
    }
    mem = MemoryFactory.create(config, workspace)
    assert isinstance(mem, MemoryBackend)


def test_factory_unknown_backend_raises(workspace):
    config = {"memory": {"backend": "redis"}}
    with pytest.raises(ValueError, match="Unknown memory backend"):
        MemoryFactory.create(config, workspace)


def test_factory_all_backends_are_memory_backend(workspace):
    for backend_name in ["hybrid", "sqlite_only", "disabled"]:
        config = {"memory": {"backend": backend_name}}
        mem = MemoryFactory.create(config, workspace / backend_name)
        assert isinstance(mem, MemoryBackend), f"{backend_name} not a MemoryBackend"
