"""Factory for creating memory backends from config."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from kabot.memory.memory_backend import MemoryBackend


# Supported backends — add new entries here to register new engines.
SUPPORTED_BACKENDS = {"hybrid", "sqlite_only", "disabled"}


class MemoryFactory:
    """Create memory backend instances from config.json settings.

    Config format (in config.json):
    {
      "memory": {
        "backend": "hybrid",           // "hybrid" | "sqlite_only" | "disabled"
        "embedding_provider": "sentence", // "sentence" | "ollama"
        "embedding_model": "all-MiniLM-L6-v2",
        "enable_hybrid_search": true
      }
    }
    """

    @staticmethod
    def create(config: dict[str, Any], workspace: Path) -> MemoryBackend:
        """Create the appropriate memory backend from configuration.

        Args:
            config: Full config dict (reads config["memory"] section).
            workspace: Workspace directory for storage.

        Returns:
            Configured MemoryBackend instance.
        """
        memory_config = config.get("memory", {})
        backend = memory_config.get("backend", "hybrid")

        if backend not in SUPPORTED_BACKENDS:
            raise ValueError(
                f"Unknown memory backend: '{backend}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_BACKENDS))}"
            )

        if backend == "disabled":
            from kabot.memory.null_memory import NullMemory
            logger.info("Memory backend: disabled (NullMemory)")
            return NullMemory()

        if backend == "sqlite_only":
            from kabot.memory.sqlite_memory import SQLiteMemory
            logger.info("Memory backend: sqlite_only")
            return SQLiteMemory(workspace=workspace / "memory_db")

        # Default: hybrid
        from kabot.memory.chroma_memory import HybridMemoryManager
        embedding_provider = memory_config.get("embedding_provider", "sentence")
        embedding_model = memory_config.get("embedding_model", None)
        enable_hybrid = memory_config.get("enable_hybrid_search", True)

        # Get auto-unload timeout with validation
        auto_unload_seconds = memory_config.get("auto_unload_timeout", 300)
        if auto_unload_seconds < 0:
            logger.warning(
                f"Invalid auto_unload_timeout={auto_unload_seconds}, using default 300s"
            )
            auto_unload_seconds = 300

        logger.info(
            f"Memory backend: hybrid "
            f"(embeddings={embedding_provider}, model={embedding_model})"
        )
        return HybridMemoryManager(
            workspace=workspace / "memory_db",
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            enable_hybrid_memory=enable_hybrid,
            auto_unload_seconds=auto_unload_seconds,
        )
