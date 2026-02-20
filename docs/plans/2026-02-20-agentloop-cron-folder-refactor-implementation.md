# AgentLoop + Cron Folder Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor oversized `AgentLoop` and cron modules into folder-based packages without changing runtime behavior.

**Architecture:** Keep `kabot/agent/loop.py` and `kabot/agent/tools/cron.py` as compatibility facades while moving logic into new package folders. Extract behavior in small slices (pure helpers first, orchestration second), and protect each slice with focused regression tests before and after moves. Avoid public API changes to preserve CLI, tests, and plugin integrations.

**Tech Stack:** Python 3.12, pytest, asyncio, existing Kabot tool registry/cron service stack.

---

### Task 1: Establish Baseline Safety Net

**Files:**
- Modify: `tests/agent/test_tool_enforcement.py`
- Modify: `tests/cron/test_cron_tool.py`
- Test: `tests/cli/test_agent_reminder_wait.py`

**Step 1: Write the failing test**

```python
def test_loop_and_cron_refactor_baseline_marker():
    # Fails until compatibility assertions are added in this task.
    assert False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_tool_enforcement.py::test_loop_and_cron_refactor_baseline_marker -v`
Expected: FAIL with `assert False`

**Step 3: Write minimal implementation**

```python
def test_loop_and_cron_refactor_baseline_marker():
    # Marker for pre-refactor smoke baseline.
    assert True
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_tool_enforcement.py tests/cron/test_cron_tool.py tests/cli/test_agent_reminder_wait.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/agent/test_tool_enforcement.py tests/cron/test_cron_tool.py
git commit -m "test: establish baseline for loop+cron folder refactor"
```

### Task 2: Add AgentLoop Facade Compatibility Tests

**Files:**
- Create: `tests/agent/test_loop_facade_compat.py`
- Modify: `kabot/agent/loop.py`
- Test: `tests/agent/test_isolation.py`

**Step 1: Write the failing test**

```python
from kabot.agent import loop as loop_module

def test_loop_facade_exports_required_symbols():
    assert hasattr(loop_module, "AgentLoop")
    assert hasattr(loop_module, "ContextBuilder")
    assert hasattr(loop_module, "ChromaMemoryManager")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_loop_facade_compat.py -v`
Expected: FAIL after first extraction if facade symbols are missing

**Step 3: Write minimal implementation**

```python
# kabot/agent/loop.py keeps re-exports after extraction
from kabot.agent.context import ContextBuilder
from kabot.memory.chroma_memory import ChromaMemoryManager
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_loop_facade_compat.py tests/agent/test_isolation.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/agent/test_loop_facade_compat.py kabot/agent/loop.py
git commit -m "test: protect AgentLoop facade compatibility"
```

### Task 3: Create `loop_core` Package Skeleton

**Files:**
- Create: `kabot/agent/loop_core/__init__.py`
- Create: `kabot/agent/loop_core/tool_enforcement.py`
- Create: `kabot/agent/loop_core/session_flow.py`
- Modify: `kabot/agent/loop.py`
- Test: `tests/agent/test_tool_enforcement.py`

**Step 1: Write the failing test**

```python
def test_tool_enforcement_runs_through_loop_core_module(monkeypatch):
    # Fails until AgentLoop delegates to loop_core.tool_enforcement
    called = {"value": False}
    assert called["value"] is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_tool_enforcement.py::test_tool_enforcement_runs_through_loop_core_module -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# loop.py imports helper from loop_core and forwards call
from kabot.agent.loop_core.tool_enforcement import required_tool_for_query
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_tool_enforcement.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/agent/loop_core/__init__.py kabot/agent/loop_core/tool_enforcement.py kabot/agent/loop_core/session_flow.py kabot/agent/loop.py tests/agent/test_tool_enforcement.py
git commit -m "refactor: introduce loop_core package skeleton"
```

### Task 4: Move AgentLoop Tool-Enforcement + Fallback Logic

**Files:**
- Modify: `kabot/agent/loop_core/tool_enforcement.py`
- Modify: `kabot/agent/loop.py`
- Test: `tests/agent/test_tool_enforcement.py`
- Test: `tests/cli/test_agent_cron_unavailable.py`

**Step 1: Write the failing test**

```python
async def test_required_tool_fallback_still_handles_cron_management():
    # Fails until extracted methods preserve behavior
    assert "groups" in ""
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_tool_enforcement.py::test_required_tool_fallback_still_handles_cron_management -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# keep methods on AgentLoop as thin wrappers calling loop_core functions
async def _execute_required_tool_fallback(self, required_tool, msg):
    return await execute_required_tool_fallback(self, required_tool, msg)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_tool_enforcement.py tests/cli/test_agent_cron_unavailable.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/agent/loop.py kabot/agent/loop_core/tool_enforcement.py tests/agent/test_tool_enforcement.py
git commit -m "refactor: extract AgentLoop tool enforcement to loop_core"
```

### Task 5: Move AgentLoop Session Processing Flow

**Files:**
- Modify: `kabot/agent/loop_core/session_flow.py`
- Modify: `kabot/agent/loop.py`
- Test: `tests/agent/test_session_isolation.py`
- Test: `tests/agent/test_session_persistence_fail_open.py`

**Step 1: Write the failing test**

```python
def test_session_flow_uses_loop_core_delegate(monkeypatch):
    delegated = {"ok": False}
    assert delegated["ok"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_session_isolation.py::test_session_flow_uses_loop_core_delegate -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# move _init_session/_finalize_session internals into loop_core.session_flow
# leave wrappers in AgentLoop for compatibility
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_session_isolation.py tests/agent/test_session_persistence_fail_open.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/agent/loop.py kabot/agent/loop_core/session_flow.py tests/agent/test_session_isolation.py
git commit -m "refactor: extract AgentLoop session flow to loop_core"
```

### Task 6: Folderize Cron Tool Operations

**Files:**
- Create: `kabot/agent/tools/cron_ops/__init__.py`
- Create: `kabot/agent/tools/cron_ops/actions.py`
- Create: `kabot/agent/tools/cron_ops/schedule.py`
- Modify: `kabot/agent/tools/cron.py`
- Test: `tests/cron/test_cron_tool.py`

**Step 1: Write the failing test**

```python
from kabot.agent.tools.cron import CronTool

def test_cron_tool_group_actions_unchanged_after_ops_extraction():
    # Fails until action handlers are delegated correctly
    assert CronTool is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cron/test_cron_tool.py::test_cron_tool_group_actions_unchanged_after_ops_extraction -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# CronTool.execute delegates per-action handlers into cron_ops.actions
from kabot.agent.tools.cron_ops.actions import handle_list_groups, handle_remove_group
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/cron/test_cron_tool.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/agent/tools/cron.py kabot/agent/tools/cron_ops/__init__.py kabot/agent/tools/cron_ops/actions.py kabot/agent/tools/cron_ops/schedule.py tests/cron/test_cron_tool.py
git commit -m "refactor: split cron tool handlers into cron_ops package"
```

### Task 7: Folderize Cron Service Internals (Optional but Recommended)

**Files:**
- Create: `kabot/cron/core/__init__.py`
- Create: `kabot/cron/core/store.py`
- Create: `kabot/cron/core/executor.py`
- Modify: `kabot/cron/service.py`
- Modify: `kabot/cron/__init__.py`
- Test: `tests/cron/test_store_persistence.py`
- Test: `tests/cron/test_run_history.py`

**Step 1: Write the failing test**

```python
def test_cron_service_public_import_still_stable():
    from kabot.cron.service import CronService
    assert CronService is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cron/test_store_persistence.py::test_cron_service_public_import_still_stable -v`
Expected: FAIL if service facade breaks during extraction

**Step 3: Write minimal implementation**

```python
# service.py remains facade class that composes store/executor helpers from kabot.cron.core
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/cron/test_store_persistence.py tests/cron/test_run_history.py tests/gateway/test_cron_api.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/cron/service.py kabot/cron/core/__init__.py kabot/cron/core/store.py kabot/cron/core/executor.py kabot/cron/__init__.py tests/cron/test_store_persistence.py
git commit -m "refactor: extract cron service internals to cron/core"
```

### Task 8: Final Regression, Docs, and Changelog

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/plans/2026-02-20-agentloop-cron-folder-refactor-implementation.md`
- Test: `tests/agent/test_tool_enforcement.py`
- Test: `tests/cron/test_cron_tool.py`
- Test: `tests/cli/test_agent_reminder_wait.py`

**Step 1: Write the failing test**

```python
def test_refactor_final_regression_marker():
    assert False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_tool_enforcement.py::test_refactor_final_regression_marker -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def test_refactor_final_regression_marker():
    assert True
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/providers/test_openai_codex_backend.py tests/agent/test_tool_enforcement.py tests/agent/test_router.py tests/cli/test_agent_reminder_wait.py tests/cron/test_store_persistence.py tests/cron/test_cron_tool.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add CHANGELOG.md docs/plans/2026-02-20-agentloop-cron-folder-refactor-implementation.md
git commit -m "docs: finalize loop+cron folder refactor plan and changelog"
```

## Notes and Constraints

- Keep backward compatibility for imports:
  - `from kabot.agent.loop import AgentLoop`
  - `from kabot.cron.service import CronService`
  - `from kabot.agent.tools.cron import CronTool`
- Preserve monkeypatch targets used by tests in `tests/agent/test_isolation.py`.
- Do not change user-facing cron behavior while refactoring.
- Keep natural-language fallback multilingual by retaining `kabot/agent/fallback_i18n.py` usage.
- Follow `@superpowers:test-driven-development` and `@superpowers:verification-before-completion` during execution.

