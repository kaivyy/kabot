# Context Build Lean Probe Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce one-shot `kabot agent -m ...` context build latency by keeping probe-mode GENERAL prompts lean for lightweight conversational turns while preserving full skill and memory context for explicit skill or recall-style requests.

**Architecture:** Add a narrow “lean probe” path inside `ContextBuilder` that skips expensive auto-skill matching and large memory-context injection when a probe GENERAL turn is clearly a lightweight chat/temporal question. Keep explicit skill-use, skill catalog, memory-recall, and substantive task turns on the full context path. Cache static runtime/workspace identity fragments so `_get_identity()` only recomputes the current timestamp.

**Tech Stack:** Python, pytest, ContextBuilder, SkillsLoader, MemoryStore, Typer CLI

---

### Task 1: Add failing tests for lean probe skill skipping

**Files:**
- Modify: `tests/agent/test_context_builder.py`
- Modify: `kabot/agent/context.py`
- Test: `tests/agent/test_context_builder.py`

**Step 1: Write the failing test**

```python
def test_context_builder_probe_mode_skips_auto_skill_match_for_light_general_turn(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    calls = {"match": 0}

    def _match(_msg: str, _profile: str):
        calls["match"] += 1
        return ["weather"]

    builder.skills.match_skills = _match  # type: ignore[assignment]

    builder.build_messages(
        history=[],
        current_message="hari apa sekarang?",
        profile="GENERAL",
        budget_hints={"probe_mode": True},
    )

    assert calls["match"] == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_context_builder.py::test_context_builder_probe_mode_skips_auto_skill_match_for_light_general_turn -q`
Expected: FAIL because probe mode still calls `match_skills()`.

**Step 3: Write minimal implementation**

Add a cheap `lean_probe` heuristic for compact GENERAL probe turns that are lightweight/non-task. When active, skip auto skill matching unless:
- `skill_names` is explicitly provided
- the message looks like a skill-use or skill-catalog request

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_context_builder.py::test_context_builder_probe_mode_skips_auto_skill_match_for_light_general_turn -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/agent/test_context_builder.py kabot/agent/context.py
git commit -m "perf: skip auto skill scan for lean probe chats"
```

### Task 2: Add failing tests for lean probe memory skipping

**Files:**
- Modify: `tests/agent/test_context_builder.py`
- Modify: `kabot/agent/context.py`
- Test: `tests/agent/test_context_builder.py`

**Step 1: Write the failing test**

```python
def test_context_builder_probe_mode_skips_memory_context_for_light_general_turn(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    builder.memory.get_memory_context = lambda: "VERY LARGE MEMORY BLOCK"  # type: ignore[assignment]

    prompt = builder.build_messages(
        history=[],
        current_message="hari apa sekarang?",
        profile="GENERAL",
        budget_hints={"probe_mode": True},
    )[0]["content"]

    assert "VERY LARGE MEMORY BLOCK" not in prompt
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_context_builder.py::test_context_builder_probe_mode_skips_memory_context_for_light_general_turn -q`
Expected: FAIL because probe mode still injects memory context.

**Step 3: Write minimal implementation**

Reuse the same `lean_probe` heuristic to skip `MemoryStore.get_memory_context()` unless the message looks like a recall/personal-memory request.

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_context_builder.py::test_context_builder_probe_mode_skips_memory_context_for_light_general_turn -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/agent/test_context_builder.py kabot/agent/context.py
git commit -m "perf: skip large memory context for lean probe chats"
```

### Task 3: Add failing tests for explicit skill and memory recall preservation

**Files:**
- Modify: `tests/agent/test_context_builder.py`
- Modify: `kabot/agent/context.py`
- Test: `tests/agent/test_context_builder.py`

**Step 1: Write the failing tests**

```python
def test_context_builder_probe_mode_still_loads_explicit_skill_context(tmp_path: Path):
    ...

def test_context_builder_probe_mode_still_includes_memory_for_recall_turn(tmp_path: Path):
    ...
```

**Step 2: Run tests to verify they fail if the heuristic is too aggressive**

Run: `pytest tests/agent/test_context_builder.py -q`
Expected: FAIL until the heuristic preserves explicit-skill and memory-recall turns.

**Step 3: Write minimal implementation**

Add cheap text checks so lean probe is disabled for:
- explicit skill-use / skill-catalog / skill creation/install turns
- recall/personal-memory questions (`ingat`, `remember`, `memory`, `preferensi`, `my name`, etc.)

**Step 4: Run tests to verify they pass**

Run: `pytest tests/agent/test_context_builder.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/agent/test_context_builder.py kabot/agent/context.py
git commit -m "test: preserve probe context for explicit skill and recall turns"
```

### Task 4: Add small runtime identity caching

**Files:**
- Modify: `tests/agent/test_context_builder.py`
- Modify: `kabot/agent/context.py`
- Test: `tests/agent/test_context_builder.py`

**Step 1: Write the failing test**

```python
def test_context_builder_compact_identity_still_includes_timezone_and_workspace(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    prompt = builder._get_identity(compact=True)
    assert "Timezone:" in prompt
    assert str(tmp_path) in prompt
```

**Step 2: Run test to verify it passes before refactor**

Run: `pytest tests/agent/test_context_builder.py::test_context_builder_compact_identity_still_includes_timezone_and_workspace -q`
Expected: PASS

**Step 3: Refactor safely**

Cache static runtime/workspace fragments in `ContextBuilder.__init__()` and keep only current time formatting dynamic in `_get_identity()`.

**Step 4: Run test to verify it still passes**

Run: `pytest tests/agent/test_context_builder.py::test_context_builder_compact_identity_still_includes_timezone_and_workspace -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/agent/test_context_builder.py kabot/agent/context.py
git commit -m "perf: cache static compact identity fields"
```

### Task 5: Verify probe behavior through CLI/runtime smoke

**Files:**
- Modify: `CHANGELOG.md`
- Test: `tests/agent/test_context_builder.py`
- Test: `tests/cli/test_agent_skill_runtime.py`

**Step 1: Run targeted tests**

Run: `pytest tests/agent/test_context_builder.py tests/cli/test_agent_skill_runtime.py -q`
Expected: PASS

**Step 2: Run broader regression**

Run: `pytest tests/agent tests/cli tests/gateway -q`
Expected: PASS

**Step 3: Run local CLI smoke**

Run:

```bash
python -m kabot.cli.commands agent -m "hari apa sekarang? jawab singkat, pakai WIB ya." --no-markdown --logs
python -m kabot.cli.commands agent -m "Please use the weather skill for this request." --no-markdown --logs
```

Expected:
- simple temporal turn no longer loads expensive skill/memory context
- explicit skill turn still loads auto-selected skill context
- `context_build_ms` improves materially for lightweight GENERAL probe turns

**Step 4: Update docs**

Add a changelog note for lean probe context optimization and preserved explicit-skill behavior.

**Step 5: Commit**

```bash
git add CHANGELOG.md tests/agent/test_context_builder.py kabot/agent/context.py
git commit -m "perf: add lean probe context path for one-shot chats"
```
