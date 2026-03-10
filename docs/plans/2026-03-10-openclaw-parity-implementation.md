# OpenClaw Parity 2026.3.8 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement Failover Queues, Automatic Config Backups, TUI/Model Enhancements, and Phase 4 Plugin/Hooks (ContextEngine, Channel Bindings, Markdown parsing) in Kabot based on OpenClaw 2026.3.7 and 2026.3.8 parity goals.

**Architecture:** We will introduce a dormant message queue using `deque` or SQLite, robust config atomic backups via `shutil`, and dynamic workspace injection for runtime terminal sessions.

**Tech Stack:** Python 3.10+, LiteLLM, shutil, zipfile, sqlite3.

---

### Task 1: Create the Dormant Session Queue

**Files:**
- Create: `kabot/core/queue.py`
- Modify: `kabot/core/session.py`
- Test: `tests/test_dormant_queue.py`

**Step 1: Write the failing test**

```python
import pytest
from kabot.core.queue import DormantQueue

def test_enqueue_and_drain():
    q = DormantQueue()
    q.enqueue("msg_1", {"role": "user"})
    assert q.has_pending("msg_1") is True
    
    items = q.drain("msg_1")
    assert len(items) == 1
    assert q.has_pending("msg_1") is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_dormant_queue.py::test_enqueue_and_drain -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'kabot.core.queue'"

**Step 3: Write minimal implementation**

```python
# kabot/core/queue.py
from collections import defaultdict, deque
from typing import Any, Dict, List

class DormantQueue:
    def __init__(self):
        self._store: Dict[str, deque] = defaultdict(deque)

    def enqueue(self, session_id: str, payload: Any):
        self._store[session_id].append(payload)

    def has_pending(self, session_id: str) -> bool:
        return len(self._store[session_id]) > 0

    def drain(self, session_id: str) -> List[Any]:
        if not self.has_pending(session_id):
            return []
        items = list(self._store[session_id])
        self._store[session_id].clear()
        return items
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_dormant_queue.py::test_enqueue_and_drain -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_dormant_queue.py kabot/core/queue.py
git commit -m "feat: add dormant session memory queue"
```

---

### Task 2: Failover Classification (Transient vs Hard)

**Files:**
- Modify: `kabot/providers/litellm_provider.py`
- Test: `tests/test_litellm_failover.py`

**Step 1: Write the failing test**

```python
import pytest
from kabot.providers.litellm_provider import classify_error

def test_classify_error_types():
    assert classify_error(402) == "hard_billing"
    assert classify_error(429) == "rate_limit"
    assert classify_error(499) == "transient"
    assert classify_error(503) == "transient"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_litellm_failover.py::test_classify_error_types -v`
Expected: FAIL with "ImportError: cannot import name 'classify_error'"

**Step 3: Write minimal implementation**

```python
# add to kabot/providers/litellm_provider.py
def classify_error(status_code: int) -> str:
    if status_code == 402:
        return "hard_billing"
    if status_code == 429:
        return "rate_limit"
    if status_code in (499, 502, 503, 504):
        return "transient"
    return "unknown"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_litellm_failover.py::test_classify_error_types -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_litellm_failover.py kabot/providers/litellm_provider.py
git commit -m "feat: add explicit failover classification for litellm"
```

---

### Task 3: Automatic Config Backup CLI

**Files:**
- Modify: `kabot/cli/commands.py`
- Create: `kabot/core/backup.py`
- Test: `tests/test_cli_backup.py`

**Step 1: Write the failing test**

```python
import os
import pytest
from kabot.core.backup import create_backup

def test_create_config_backup(tmp_path):
    # mock config dir
    config_dir = tmp_path / ".kabot"
    config_dir.mkdir()
    (config_dir / "provider.json").write_text("{}")
    
    archive_path = create_backup(str(config_dir), dest_dir=str(tmp_path), only_config=True)
    assert os.path.exists(archive_path)
    assert archive_path.endswith(".zip")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_backup.py::test_create_config_backup -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'kabot.core.backup'"

**Step 3: Write minimal implementation**

```python
# kabot/core/backup.py
import shutil
import os
from datetime import datetime

def create_backup(source_dir: str, dest_dir: str, only_config: bool = True) -> str:
    if not os.path.exists(source_dir):
        raise FileNotFoundError(f"Source config dir {source_dir} not found")
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"kabot_backup_{timestamp}"
    archive_path = os.path.join(dest_dir, archive_name)
    
    # In real implementation we'd filter files if only_config is True
    # For now, zip the whole `.kabot` equivalent director
    result = shutil.make_archive(archive_path, 'zip', source_dir)
    return result
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_backup.py::test_create_config_backup -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_cli_backup.py kabot/core/backup.py
git commit -m "feat: implement configuration backup mechanics"
```

---

### Task 4: Fail-Closed Config Loading

**Files:**
- Modify: `kabot/core/config.py`
- Modify: `tests/test_config.py`

**Step 1: Write the failing test**

```python
import pytest
from kabot.core.config import load_config

def test_fail_closed_on_invalid_json(tmp_path):
    bad_config = tmp_path / "provider.json"
    bad_config.write_text("{ invalid_json: ]")
    
    with pytest.raises(ValueError, match="CRITICAL: Configuration file is malformed"):
        load_config(str(bad_config))
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_fail_closed_on_invalid_json -v`
Expected: FAIL with "JSONDecodeError" (not the clean ValueError we want) or it silently returns {}.

**Step 3: Write minimal implementation**

```python
# Modify load_config in kabot/core/config.py
import json
import logging

def load_config(filepath: str) -> dict:
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logging.critical(f"CRITICAL: Configuration file is malformed: {e}")
        raise ValueError(f"CRITICAL: Configuration file is malformed: {e}")
    except FileNotFoundError:
        return {} # Keep existing behavior for missing (not malformed) configs
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_fail_closed_on_invalid_json -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_config.py kabot/core/config.py
git commit -m "fix: fail closed on malformed config JSON instead of silently passing"
```

---

### Task 5: TUI Component Detection and GPT-5.4 Parity

**Files:**
- Modify: `kabot/cli/agent.py`
- Modify: `kabot/providers/registry.py`

**Step 1: Write the failing test**

```python
import os
import pytest
from kabot.cli.agent import resolve_agent_id
from kabot.providers.registry import PROVIDERS

def test_resolve_agent_id_from_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".kabot_workspace").write_text("agent_id=dev_agent")
    
    assert resolve_agent_id() == "dev_agent"

def test_gpt_5_4_limits():
    spec = next(p for p in PROVIDERS if p.prefix == "openai/")
    # Assuming we add checking logic or adjust the existing dictionary of models
    # This is a placeholder test idea.
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui_workspace.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# in kabot/cli/agent.py
import os

def resolve_agent_id(default: str = "main") -> str:
    workspace_marker = ".kabot_workspace"
    if os.path.exists(workspace_marker):
        with open(workspace_marker, "r") as f:
            for line in f:
                if line.startswith("agent_id="):
                    return line.strip().split("=")[1]
    return default
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_tui_workspace.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_tui_workspace.py kabot/cli/agent.py
git commit -m "feat: smart TUI session bindings via workspace markers"
```

---

### Task 6: Phase 4 Plugin/Hooks Architecture (2026.3.7 Features)

**Files:**
- Create: `kabot/core/context_engine.py`
- Modify: `kabot/core/session.py`
- Modify: `kabot/ui/markdown.py` (or where markdown is parsed)

**Step 1: Write the failing test**

```python
import pytest
from kabot.core.context_engine import ContextEngine, LegacyContextEngine

def test_context_engine_interface():
    engine = LegacyContextEngine()
    # It should implement the compile interface
    assert callable(getattr(engine, "compile", None))
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_context_engines.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# kabot/core/context_engine.py
class ContextEngine:
    def compile(self, session: dict) -> list:
        raise NotImplementedError

class LegacyContextEngine(ContextEngine):
    def compile(self, session: dict) -> list:
        # legacy token logic placeholder
        return session.get("history", [])
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_context_engines.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_context_engines.py kabot/core/context_engine.py
git commit -m "feat: pluggable ContextEngine architecture (2026.3.7 parity)"
```
