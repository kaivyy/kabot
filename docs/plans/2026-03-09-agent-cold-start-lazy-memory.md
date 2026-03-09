# Agent Cold Start Lazy Memory Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce real `kabot agent -m "..."` cold-start time by avoiding eager hybrid memory initialization during probe-style one-shot runs while preserving session history and memory tool behavior.

**Architecture:** Introduce a lightweight lazy memory backend wrapper that serves session creation and conversation history immediately via SQLite, then upgrades to the configured hybrid backend only when semantic memory operations are actually needed. Wire `AgentLoop` to construct this wrapper in probe-friendly paths without changing the rest of the loop, tool registration, or session flow logic.

**Tech Stack:** Python, pytest, Typer CLI, AgentLoop runtime, SQLite memory backend, hybrid Chroma/sentence-transformers memory backend

---

### Task 1: Add failing tests for lazy memory factory behavior

**Files:**
- Create: `tests/memory/test_memory_factory_lazy.py`
- Modify: `kabot/memory/memory_factory.py`
- Test: `tests/memory/test_memory_factory_lazy.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from kabot.memory.memory_factory import MemoryFactory


def test_memory_factory_returns_lazy_backend_for_probe_mode(monkeypatch, tmp_path: Path):
    calls: list[str] = []

    class _FakeHybrid:
        def __init__(self, *args, **kwargs):
            calls.append("hybrid")

    monkeypatch.setattr(
        "kabot.memory.memory_factory.HybridMemoryManager",
        _FakeHybrid,
        raising=False,
    )

    backend = MemoryFactory.create(
        {
            "memory": {"backend": "hybrid"},
            "runtime": {"performance": {"lazy_probe_memory": True}},
        },
        tmp_path,
        lazy_probe=True,
    )

    assert backend.__class__.__name__ == "LazyProbeMemory"
    assert calls == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/memory/test_memory_factory_lazy.py::test_memory_factory_returns_lazy_backend_for_probe_mode -q`
Expected: FAIL because `MemoryFactory.create()` does not accept `lazy_probe` and no lazy backend exists yet.

**Step 3: Write minimal implementation**

Create a new lazy wrapper backend and extend `MemoryFactory.create()` to optionally return it when:
- configured backend is `hybrid`
- probe/lazy flag is enabled
- lightweight history must remain available

**Step 4: Run test to verify it passes**

Run: `pytest tests/memory/test_memory_factory_lazy.py::test_memory_factory_returns_lazy_backend_for_probe_mode -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/memory/test_memory_factory_lazy.py kabot/memory/memory_factory.py kabot/memory/lazy_probe_memory.py
git commit -m "refactor: add lazy probe memory backend"
```

### Task 2: Add failing tests for lightweight history preservation

**Files:**
- Modify: `tests/memory/test_memory_factory_lazy.py`
- Modify: `kabot/memory/lazy_probe_memory.py`
- Test: `tests/memory/test_memory_factory_lazy.py`

**Step 1: Write the failing test**

```python
def test_lazy_probe_memory_uses_sqlite_history_without_booting_hybrid(monkeypatch, tmp_path: Path):
    calls: list[str] = []

    class _FakeHybrid:
        def __init__(self, *args, **kwargs):
            calls.append("hybrid")

    monkeypatch.setattr(
        "kabot.memory.lazy_probe_memory.HybridMemoryManager",
        _FakeHybrid,
    )

    backend = LazyProbeMemory.from_config({"memory": {"backend": "hybrid"}}, tmp_path)
    backend.create_session("cli:direct", "cli", "direct")
    backend.add_message("cli:direct", "user", "halo")

    history = backend.get_conversation_context("cli:direct")

    assert len(history) == 1
    assert history[0]["content"] == "halo"
    assert calls == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/memory/test_memory_factory_lazy.py::test_lazy_probe_memory_uses_sqlite_history_without_booting_hybrid -q`
Expected: FAIL because the lazy backend does not exist or still boots the heavy backend too early.

**Step 3: Write minimal implementation**

Implement `LazyProbeMemory` so these methods stay lightweight and do not trigger hybrid boot:
- `create_session`
- `add_message`
- `get_conversation_context`
- `get_stats`
- `health_check`

Use `SQLiteMemory` internally for this path.

**Step 4: Run test to verify it passes**

Run: `pytest tests/memory/test_memory_factory_lazy.py::test_lazy_probe_memory_uses_sqlite_history_without_booting_hybrid -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/memory/test_memory_factory_lazy.py kabot/memory/lazy_probe_memory.py
git commit -m "test: preserve probe history without eager hybrid boot"
```

### Task 3: Add failing tests for on-demand hybrid upgrade

**Files:**
- Modify: `tests/memory/test_memory_factory_lazy.py`
- Modify: `kabot/memory/lazy_probe_memory.py`
- Test: `tests/memory/test_memory_factory_lazy.py`

**Step 1: Write the failing test**

```python
def test_lazy_probe_memory_upgrades_only_on_semantic_operations(monkeypatch, tmp_path: Path):
    calls: list[str] = []

    class _FakeHybrid:
        def __init__(self, *args, **kwargs):
            calls.append("hybrid")

        async def search_memory(self, query, session_id=None, limit=5):
            return [{"content": query}]

    monkeypatch.setattr(
        "kabot.memory.lazy_probe_memory.HybridMemoryManager",
        _FakeHybrid,
    )

    backend = LazyProbeMemory.from_config({"memory": {"backend": "hybrid"}}, tmp_path)
    backend.get_conversation_context("cli:direct")
    assert calls == []

    import asyncio
    results = asyncio.run(backend.search_memory("timezone"))

    assert calls == ["hybrid"]
    assert results == [{"content": "timezone"}]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/memory/test_memory_factory_lazy.py::test_lazy_probe_memory_upgrades_only_on_semantic_operations -q`
Expected: FAIL because semantic operations are not lazily delegated yet.

**Step 3: Write minimal implementation**

Trigger hybrid initialization only for:
- `search_memory`
- `remember_fact`
- `search_graph`
- `get_graph_context`

Keep upgrade cached so heavy backend boots once.

**Step 4: Run test to verify it passes**

Run: `pytest tests/memory/test_memory_factory_lazy.py::test_lazy_probe_memory_upgrades_only_on_semantic_operations -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/memory/test_memory_factory_lazy.py kabot/memory/lazy_probe_memory.py
git commit -m "feat: upgrade probe memory lazily on semantic access"
```

### Task 4: Add failing AgentLoop wiring tests

**Files:**
- Modify: `tests/cli/test_agent_runtime_config.py`
- Modify: `kabot/agent/loop.py`
- Modify: `kabot/cli/commands_agent_command.py`
- Test: `tests/cli/test_agent_runtime_config.py`

**Step 1: Write the failing test**

```python
def test_agent_loop_enables_lazy_probe_memory_flag_for_probe_friendly_runs(monkeypatch, tmp_path):
    captured = {}

    def _fake_create(config_dict, workspace, lazy_probe=False):
        captured["lazy_probe"] = lazy_probe
        return DummyMemory()

    monkeypatch.setattr("kabot.memory.memory_factory.MemoryFactory.create", _fake_create)

    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        config=cfg,
        model="openai-codex/gpt-5.3-codex",
        cron_service=CronService(tmp_path / "cron.json"),
    )

    assert captured["lazy_probe"] is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_agent_runtime_config.py::test_agent_loop_enables_lazy_probe_memory_flag_for_probe_friendly_runs -q`
Expected: FAIL because `AgentLoop` still calls `MemoryFactory.create()` without a lazy flag.

**Step 3: Write minimal implementation**

Pass a narrow lazy-probe flag from `AgentLoop` into the memory factory using existing config/runtime conditions that already identify probe-friendly direct CLI runs.

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_agent_runtime_config.py::test_agent_loop_enables_lazy_probe_memory_flag_for_probe_friendly_runs -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/cli/test_agent_runtime_config.py kabot/agent/loop.py kabot/cli/commands_agent_command.py
git commit -m "refactor: wire lazy probe memory into agent loop"
```

### Task 5: Add CLI smoke guard for one-shot path

**Files:**
- Modify: `tests/cli/test_agent_runtime_config.py`
- Test: `tests/cli/test_agent_runtime_config.py`

**Step 1: Write the failing test**

```python
def test_agent_cli_one_shot_keeps_persist_history_with_lazy_probe_memory(monkeypatch, tmp_path):
    captured = {}

    class _DummyAgentLoop:
        async def process_direct(self, message, session_key, suppress_post_response_warmup=False, probe_mode=False, persist_history=False):
            captured["probe_mode"] = probe_mode
            captured["persist_history"] = persist_history
            return "ok"

    ...
    assert captured == {"probe_mode": True, "persist_history": True}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_agent_runtime_config.py::test_agent_cli_one_shot_keeps_persist_history_with_lazy_probe_memory -q`
Expected: FAIL only if wiring changed behavior unexpectedly.

**Step 3: Write minimal implementation**

Keep the existing direct CLI behavior unchanged:
- `probe_mode=True`
- `persist_history=True`

Lazy memory optimization must be internal only.

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_agent_runtime_config.py::test_agent_cli_one_shot_keeps_persist_history_with_lazy_probe_memory -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/cli/test_agent_runtime_config.py
git commit -m "test: preserve one-shot probe history behavior"
```

### Task 6: Verify targeted and full behavior

**Files:**
- Modify: `CHANGELOG.md`
- Test: `tests/memory/test_memory_factory_lazy.py`
- Test: `tests/cli/test_agent_runtime_config.py`

**Step 1: Run targeted tests**

Run: `pytest tests/memory/test_memory_factory_lazy.py tests/cli/test_agent_runtime_config.py -q`
Expected: PASS

**Step 2: Run broader regression tests**

Run: `pytest tests/agent tests/cli tests/gateway -q`
Expected: PASS

**Step 3: Run real CLI smoke**

Run:

```bash
kabot agent -m "hari apa sekarang" --no-markdown
kabot agent -m "cek file/folder di desktop isinya apa aja, 5 item pertama aja" --no-markdown
```

Expected:
- agent responds correctly
- one-shot path still preserves history behavior
- startup feels faster and logs no eager hybrid memory boot before first response

**Step 4: Update docs**

Add concise changelog entry describing lazy probe memory startup optimization.

**Step 5: Commit**

```bash
git add CHANGELOG.md tests/memory/test_memory_factory_lazy.py tests/cli/test_agent_runtime_config.py kabot/memory/memory_factory.py kabot/memory/lazy_probe_memory.py kabot/agent/loop.py
git commit -m "perf: lazy-load hybrid memory for one-shot agent runs"
```
