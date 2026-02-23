# Memory Slot Architecture — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow users to swap Kabot's memory backend (Hybrid/SQLite-only/Redis/Mem0/Disabled) via `config.json` and the interactive Setup Wizard — without touching Python code.

**Architecture:** Introduce an abstract `MemoryBackend` protocol (Python ABC) that defines the contract for `add_message`, `search_memory`, `remember_fact`, etc. The existing `HybridMemoryManager` becomes the default implementation. A `MemoryFactory` reads `config.json["memory"]["backend"]` and returns the correct concrete instance. The Setup Wizard gets a new "Memory" menu section to configure this visually.

**Tech Stack:** Python 3.11+, pytest, `abc.ABC`, `questionary` (setup wizard), `chromadb`, `sqlite3`

---

## Current State (Audit Summary)

| File | Role | Key Finding |
|------|------|-------------|
| [chroma_memory.py](file:///C:/Users/Arvy%20Kairi/Desktop/bot/kabot/kabot/memory/chroma_memory.py) | `HybridMemoryManager` class (843 lines) | Tightly coupled: ChromaDB + SQLite + BM25 + SmartRouter + Reranker. `__init__` takes `embedding_provider` ("sentence"/"ollama") and `embedding_model` |
| [loop.py](file:///C:/Users/Arvy%20Kairi/Desktop/bot/kabot/kabot/agent/loop.py#L147-L151) | Agent loop instantiation | Hardcoded: `HybridMemoryManager(workspace / "memory_db", enable_hybrid_memory=...)` |
| [tools/memory.py](file:///C:/Users/Arvy%20Kairi/Desktop/bot/kabot/kabot/agent/tools/memory.py) | Memory search tool | Imports `ChromaMemoryManager` alias |
| [tools/knowledge.py](file:///C:/Users/Arvy%20Kairi/Desktop/bot/kabot/kabot/agent/tools/knowledge.py#L69) | Knowledge tool | Creates its own `HybridMemoryManager` instance |
| [setup_wizard.py](file:///C:/Users/Arvy%20Kairi/Desktop/bot/kabot/kabot/cli/setup_wizard.py#L493-L517) | Wizard menu | No "Memory" option exists. Current menu: workspace, model, tools, gateway, skills, google, channels, autostart, logging, doctor |
| [__init__.py](file:///C:/Users/Arvy%20Kairi/Desktop/bot/kabot/kabot/memory/__init__.py) | Lazy loader | Exports all classes via `__getattr__`, no factory pattern |

---

## Proposed Changes

### Component 1: Abstract Memory Backend Protocol

#### [NEW] [memory_backend.py](file:///C:/Users/Arvy%20Kairi/Desktop/bot/kabot/kabot/memory/memory_backend.py)

Defines the `MemoryBackend` ABC that all backends must implement. This is the **contract** ensuring swappability.

---

### Component 2: Memory Factory

#### [NEW] [memory_factory.py](file:///C:/Users/Arvy%20Kairi/Desktop/bot/kabot/kabot/memory/memory_factory.py)

Reads `config.json["memory"]` and instantiates the correct backend. Supports: `hybrid` (default), `sqlite_only`, `disabled`. Extensible for `redis`/`mem0` later.

---

### Component 3: SQLite-Only Backend

#### [NEW] [sqlite_memory.py](file:///C:/Users/Arvy%20Kairi/Desktop/bot/kabot/kabot/memory/sqlite_memory.py)

Lightweight backend using only SQLite (no ChromaDB, no embeddings). Good for low-resource environments (Termux, Raspberry Pi).

---

### Component 4: Disabled Backend (NullMemory)

#### [NEW] [null_memory.py](file:///C:/Users/Arvy%20Kairi/Desktop/bot/kabot/kabot/memory/null_memory.py)

No-op implementation. Returns empty results for all queries. For users who don't want memory.

---

### Component 5: Agent Loop Integration

#### [MODIFY] [loop.py](file:///C:/Users/Arvy%20Kairi/Desktop/bot/kabot/kabot/agent/loop.py#L147-L151)

Replace hardcoded `HybridMemoryManager(...)` with `MemoryFactory.create(config, workspace)`.

---

### Component 6: Setup Wizard Memory Menu

#### [MODIFY] [setup_wizard.py](file:///C:/Users/Arvy%20Kairi/Desktop/bot/kabot/kabot/cli/setup_wizard.py#L493-L533)

Add a "Memory" option to the main menu with sub-selections for backend, embedding provider, and embedding model.

---

### Component 7: Config Schema

#### [MODIFY] Config loading

Add `memory` section to `config.json`:
```json
{
  "memory": {
    "backend": "hybrid",
    "embedding_provider": "sentence",
    "embedding_model": "all-MiniLM-L6-v2",
    "enable_hybrid_search": true
  }
}
```

---

## Tasks

### Task 1: Abstract MemoryBackend Protocol

**Files:**
- Create: `kabot/memory/memory_backend.py`
- Test: `tests/memory/test_memory_backend.py`

**Step 1: Write the failing test**

```python
# tests/memory/test_memory_backend.py
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/memory/test_memory_backend.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# kabot/memory/memory_backend.py
"""Abstract base class for all memory backends."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class MemoryBackend(ABC):
    """Contract for swappable memory backends.

    All backends must implement these methods to be compatible
    with the AgentLoop and memory tools.
    """

    @abstractmethod
    def add_message(self, session_id: str, role: str, content: str,
                    parent_id: str | None = None,
                    tool_calls: list | None = None,
                    tool_results: list | None = None,
                    metadata: dict | None = None) -> str:
        """Add a message to memory. Returns message_id."""

    @abstractmethod
    def search_memory(self, query: str, session_id: str | None = None,
                      limit: int = 5) -> list[dict]:
        """Search memory for relevant results."""

    @abstractmethod
    def remember_fact(self, fact: str, category: str = "general",
                      session_id: str | None = None,
                      confidence: float = 1.0) -> str:
        """Store a long-term fact. Returns fact_id."""

    @abstractmethod
    def get_conversation_context(self, session_id: str,
                                  max_messages: int = 20) -> list[dict]:
        """Get recent conversation context."""

    @abstractmethod
    def create_session(self, session_id: str, channel: str, chat_id: str,
                       user_id: str | None = None) -> None:
        """Create a new conversation session."""

    @abstractmethod
    def get_stats(self) -> dict:
        """Get memory system statistics."""

    @abstractmethod
    def health_check(self) -> dict:
        """Check memory system health."""
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/memory/test_memory_backend.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/memory/memory_backend.py tests/memory/test_memory_backend.py
git commit -m "feat(memory): add abstract MemoryBackend protocol"
```

---

### Task 2: NullMemory (Disabled Backend)

**Files:**
- Create: `kabot/memory/null_memory.py`
- Test: `tests/memory/test_null_memory.py`

**Step 1: Write the failing test**

```python
# tests/memory/test_null_memory.py
"""Tests for NullMemory (disabled backend)."""
import pytest
from kabot.memory.null_memory import NullMemory
from kabot.memory.memory_backend import MemoryBackend


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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/memory/test_null_memory.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# kabot/memory/null_memory.py
"""Null memory backend — no-op implementation for disabled memory."""
from __future__ import annotations

import uuid

from kabot.memory.memory_backend import MemoryBackend


class NullMemory(MemoryBackend):
    """No-op memory backend. All reads return empty, all writes are discarded."""

    def add_message(self, session_id, role, content, parent_id=None,
                    tool_calls=None, tool_results=None, metadata=None):
        return str(uuid.uuid4())

    def search_memory(self, query, session_id=None, limit=5):
        return []

    def remember_fact(self, fact, category="general", session_id=None,
                      confidence=1.0):
        return str(uuid.uuid4())

    def get_conversation_context(self, session_id, max_messages=20):
        return []

    def create_session(self, session_id, channel, chat_id, user_id=None):
        pass

    def get_stats(self):
        return {"backend": "disabled", "messages": 0, "facts": 0, "sessions": 0}

    def health_check(self):
        return {"status": "ok", "backend": "disabled", "message": "Memory disabled"}
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/memory/test_null_memory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/memory/null_memory.py tests/memory/test_null_memory.py
git commit -m "feat(memory): add NullMemory (disabled backend)"
```

---

### Task 3: SQLite-Only Backend

**Files:**
- Create: `kabot/memory/sqlite_memory.py`
- Test: `tests/memory/test_sqlite_memory.py`

**Step 1: Write the failing test**

```python
# tests/memory/test_sqlite_memory.py
"""Tests for SQLiteMemory (lightweight backend)."""
import pytest
from pathlib import Path
from kabot.memory.sqlite_memory import SQLiteMemory
from kabot.memory.memory_backend import MemoryBackend


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


def test_health_check(mem):
    status = mem.health_check()
    assert status["status"] == "ok"
    assert status["backend"] == "sqlite_only"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/memory/test_sqlite_memory.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# kabot/memory/sqlite_memory.py
"""SQLite-only memory backend — lightweight, no external deps."""
from __future__ import annotations

import uuid
from pathlib import Path

from loguru import logger

from kabot.memory.memory_backend import MemoryBackend
from kabot.memory.sqlite_store import SQLiteMetadataStore


class SQLiteMemory(MemoryBackend):
    """Lightweight memory using only SQLite. No ChromaDB, no embeddings.

    Best for: Termux, Raspberry Pi, low-resource environments.
    Search uses SQL LIKE (keyword match), not semantic similarity.
    """

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.metadata = SQLiteMetadataStore(self.workspace / "metadata.db")
        logger.info("SQLiteMemory initialized (lightweight mode, no embeddings)")

    def add_message(self, session_id, role, content, parent_id=None,
                    tool_calls=None, tool_results=None, metadata=None):
        msg_id = str(uuid.uuid4())
        self.metadata.add_message(
            msg_id, session_id, role, content,
            parent_id=parent_id,
            tool_calls=tool_calls,
            tool_results=tool_results,
            metadata=metadata,
        )
        return msg_id

    def search_memory(self, query, session_id=None, limit=5):
        """Keyword-based search using SQL LIKE."""
        try:
            with self.metadata._get_connection() as conn:
                if session_id:
                    rows = conn.execute(
                        "SELECT id, content, role, created_at FROM messages "
                        "WHERE session_id = ? AND content LIKE ? "
                        "ORDER BY created_at DESC LIMIT ?",
                        (session_id, f"%{query}%", limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT id, content, role, created_at FROM messages "
                        "WHERE content LIKE ? "
                        "ORDER BY created_at DESC LIMIT ?",
                        (f"%{query}%", limit),
                    ).fetchall()
            return [
                {"id": r[0], "content": r[1], "role": r[2],
                 "created_at": r[3], "score": 1.0}
                for r in rows
            ]
        except Exception as e:
            logger.error(f"SQLiteMemory search error: {e}")
            return []

    def remember_fact(self, fact, category="general", session_id=None,
                      confidence=1.0):
        fact_id = str(uuid.uuid4())
        self.metadata.add_fact(fact_id, category, category, fact,
                               session_id=session_id, confidence=confidence)
        return fact_id

    def get_conversation_context(self, session_id, max_messages=20):
        return self.metadata.get_message_chain(session_id, limit=max_messages)

    def create_session(self, session_id, channel, chat_id, user_id=None):
        self.metadata.create_session(session_id, channel, chat_id, user_id=user_id)

    def get_stats(self):
        base = self.metadata.get_stats()
        base["backend"] = "sqlite_only"
        return base

    def health_check(self):
        try:
            self.metadata.get_stats()
            return {"status": "ok", "backend": "sqlite_only"}
        except Exception as e:
            return {"status": "error", "backend": "sqlite_only", "error": str(e)}
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/memory/test_sqlite_memory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/memory/sqlite_memory.py tests/memory/test_sqlite_memory.py
git commit -m "feat(memory): add SQLiteMemory (lightweight backend)"
```

---

### Task 4: Make HybridMemoryManager Conform to MemoryBackend

**Files:**
- Modify: `kabot/memory/chroma_memory.py:21`
- Test: `tests/memory/test_hybrid_conforms.py`

**Step 1: Write the failing test**

```python
# tests/memory/test_hybrid_conforms.py
"""Test that HybridMemoryManager conforms to MemoryBackend ABC."""
from kabot.memory.memory_backend import MemoryBackend


def test_hybrid_is_subclass_of_memory_backend():
    from kabot.memory.chroma_memory import HybridMemoryManager
    assert issubclass(HybridMemoryManager, MemoryBackend)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/memory/test_hybrid_conforms.py -v`
Expected: FAIL with "AssertionError"

**Step 3: Modify HybridMemoryManager to inherit from MemoryBackend**

In `kabot/memory/chroma_memory.py`, change line 21:
```diff
-class HybridMemoryManager:
+from kabot.memory.memory_backend import MemoryBackend
+
+class HybridMemoryManager(MemoryBackend):
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/memory/test_hybrid_conforms.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/memory/chroma_memory.py tests/memory/test_hybrid_conforms.py
git commit -m "refactor(memory): HybridMemoryManager now inherits MemoryBackend"
```

---

### Task 5: Memory Factory

**Files:**
- Create: `kabot/memory/memory_factory.py`
- Test: `tests/memory/test_memory_factory.py`

**Step 1: Write the failing test**

```python
# tests/memory/test_memory_factory.py
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/memory/test_memory_factory.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# kabot/memory/memory_factory.py
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
        logger.info(
            f"Memory backend: hybrid "
            f"(embeddings={embedding_provider}, model={embedding_model})"
        )
        return HybridMemoryManager(
            workspace=workspace / "memory_db",
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            enable_hybrid_memory=enable_hybrid,
        )
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/memory/test_memory_factory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/memory/memory_factory.py tests/memory/test_memory_factory.py
git commit -m "feat(memory): add MemoryFactory for config-driven backend creation"
```

---

### Task 6: Wire Factory into AgentLoop

**Files:**
- Modify: `kabot/agent/loop.py:147-151`
- Test: `tests/memory/test_loop_memory_integration.py`

**Step 1: Write the failing test**

```python
# tests/memory/test_loop_memory_integration.py
"""Test that AgentLoop uses MemoryFactory for backend selection."""
from kabot.memory.memory_factory import MemoryFactory


def test_factory_is_importable():
    """Sanity check — factory exists and is callable."""
    assert callable(MemoryFactory.create)
```

**Step 2: Modify loop.py**

Replace lines 147-151 in `kabot/agent/loop.py`:
```diff
-        from kabot.memory import HybridMemoryManager
-        self.memory = HybridMemoryManager(
-            workspace / "memory_db",
-            enable_hybrid_memory=enable_hybrid_memory
-        )
+        from kabot.memory.memory_factory import MemoryFactory
+        from kabot.core.config_manager import load_config
+        _cfg = load_config()
+        # Allow constructor param to override config
+        if not enable_hybrid_memory:
+            _cfg.setdefault("memory", {})["enable_hybrid_search"] = False
+        self.memory = MemoryFactory.create(_cfg, workspace)
```

**Step 3: Run existing tests**

Run: `python -m pytest tests/ -v -k "not live" --timeout=30`
Expected: All existing tests PASS (backward compatible)

**Step 4: Commit**

```bash
git add kabot/agent/loop.py tests/memory/test_loop_memory_integration.py
git commit -m "refactor(loop): use MemoryFactory instead of hardcoded HybridMemoryManager"
```

---

### Task 7: Setup Wizard Memory Menu

**Files:**
- Modify: `kabot/cli/setup_wizard.py`
- Test: `tests/cli/test_setup_wizard_memory.py`

**Step 1: Write the failing test**

```python
# tests/cli/test_setup_wizard_memory.py
"""Test that setup wizard includes a Memory configuration option."""


def test_memory_in_advanced_menu_options():
    """Memory should appear in the advanced menu options list."""
    from kabot.cli.setup_wizard import SetupWizard
    wizard = SetupWizard()
    wizard.setup_mode = "advanced"
    options = wizard._main_menu_option_values()
    assert "memory" in options


def test_memory_in_simple_menu_options():
    """Memory should appear in the simple menu options list."""
    from kabot.cli.setup_wizard import SetupWizard
    wizard = SetupWizard()
    wizard.setup_mode = "simple"
    options = wizard._main_menu_option_values()
    assert "memory" in options
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/cli/test_setup_wizard_memory.py -v`
Expected: FAIL with "AssertionError" (memory not in list)

**Step 3: Add memory to menu and implement _configure_memory**

In `setup_wizard.py`, add `"memory"` to both `_main_menu_option_values` lists (advanced at line ~500, simple at line ~510), add the label in `_main_menu_choices`, add the `elif choice == "memory"` handler in the `run` loop, and implement `_configure_memory`:

```python
def _configure_memory(self) -> None:
    """Configure memory backend settings."""
    from kabot.memory.memory_factory import SUPPORTED_BACKENDS

    ClackUI.section_start("Memory Configuration")

    current = self.config.get("memory", {}).get("backend", "hybrid")
    console.print(f"│  [dim]Current backend: {current}[/dim]")

    backend = ClackUI.clack_select(
        "Memory backend",
        choices=[
            questionary.Choice("Hybrid (ChromaDB + SQLite + BM25) — Full power", value="hybrid"),
            questionary.Choice("SQLite Only — Lightweight, no embeddings", value="sqlite_only"),
            questionary.Choice("Disabled — No memory at all", value="disabled"),
        ],
        default=current,
    )
    if backend is None:
        ClackUI.section_end()
        return

    if "memory" not in self.config:
        self.config["memory"] = {}
    self.config["memory"]["backend"] = backend

    if backend == "hybrid":
        current_emb = self.config.get("memory", {}).get("embedding_provider", "sentence")
        emb_provider = ClackUI.clack_select(
            "Embedding provider",
            choices=[
                questionary.Choice("Sentence-Transformers (Local, recommended)", value="sentence"),
                questionary.Choice("Ollama (Requires running Ollama server)", value="ollama"),
            ],
            default=current_emb,
        )
        if emb_provider:
            self.config["memory"]["embedding_provider"] = emb_provider

    save_config(self.config)
    self._save_setup_state("memory", completed=True, backend=backend)
    console.print(f"│  [green]✓ Memory backend set to: {backend}[/green]")
    ClackUI.section_end()
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/cli/test_setup_wizard_memory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/cli/setup_wizard.py tests/cli/test_setup_wizard_memory.py
git commit -m "feat(wizard): add Memory configuration to setup wizard"
```

---

### Task 8: Update __init__.py and Exports

**Files:**
- Modify: `kabot/memory/__init__.py`

**Step 1: Add new exports**

```diff
 _MODULE_LOCKS = {
     "HybridMemoryManager": ".chroma_memory",
     "ChromaMemoryManager": ".chroma_memory",
+    "MemoryBackend": ".memory_backend",
+    "MemoryFactory": ".memory_factory",
+    "NullMemory": ".null_memory",
+    "SQLiteMemory": ".sqlite_memory",
     "SmartRouter": ".smart_router",
     ...
 }
```

**Step 2: Run all tests**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All PASS

**Step 3: Commit**

```bash
git add kabot/memory/__init__.py
git commit -m "refactor(memory): export new backends from __init__.py"
```

---

### Task 9: Update CHANGELOG.md

**Files:**
- Modify: `CHANGELOG.md`

Add under `### Added`:
```markdown
- **Memory Slot Architecture**: Users can now switch memory backends (`hybrid`, `sqlite_only`, `disabled`) via `config.json` or the interactive Setup Wizard. No code changes required.
- **MemoryBackend ABC**: Abstract base class defining the contract for all memory backends, enabling future extensibility (Redis, Mem0, etc.).
- **SQLiteMemory**: Lightweight memory backend using only SQLite (no ChromaDB or embeddings). Ideal for Termux or Raspberry Pi.
- **NullMemory**: No-op memory backend for users who want to disable memory entirely.
- **MemoryFactory**: Config-driven factory that reads `config.json["memory"]["backend"]` and instantiates the correct backend.
- **Setup Wizard → Memory**: New "Memory" menu option in the setup wizard for selecting backend and embedding provider.
```

**Step 1: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: document Memory Slot Architecture in CHANGELOG"
```

---

## Verification Plan

### Automated Tests

Run the full test suite:
```bash
python -m pytest tests/memory/ -v --timeout=30
python -m pytest tests/cli/test_setup_wizard_memory.py -v
python -m pytest tests/ -v --timeout=60 -k "not live"
```

Expected: **All green.** The 6 new test files should each pass independently. No existing tests should break because `MemoryFactory` defaults to `hybrid` when no config is present (backward compatible).

### Manual Verification

1. **Default behavior unchanged**: Start Kabot without any `config.json` memory section → should use HybridMemoryManager as before.
2. **SQLite-only mode**: Set `"memory": {"backend": "sqlite_only"}` in config.json → bot should work with keyword search instead of semantic search.
3. **Disabled mode**: Set `"memory": {"backend": "disabled"}` → bot should reply normally but not remember anything.
4. **Setup Wizard**: Run `python -m kabot setup` → "Memory" option should appear in menu.
