# reference platform File Continuity Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Kabot file/navigation continuity lean more on session working-directory state and tool evidence, closer to the reference platform's history + cwd + tool-state model.

**Architecture:** Keep existing `last_navigated_path` and `last_delivery_path` as compatibility fallbacks, but introduce a canonical `working_directory` session/message state derived from successful tool paths. Use that state in delivery and follow-up path resolution before falling back to older breadcrumb fields. Add a source-accurate reference platform reference note so future parity work stays grounded.

**Tech Stack:** Python, pytest, Markdown docs, GitHub Actions

---

### Task 1: Document the reference platform logic accurately

**Files:**
- Create: `site_docs/reference/reference-file-continuity.md`
- Modify: `mkdocs.yml`

**Step 1: Write the reference note**
- Explain which parts of the earlier explanation are correct for reference platform.
- Correct the inaccurate parts:
  - no `last_navigated_path`
  - no `last_delivery_path`
  - route continuity is `deliveryContext` / `lastChannel` / `lastTo`
  - coding/file continuity also depends on ACP `cwd`

### Task 2: Add red tests for working-directory state

**Files:**
- Modify: `tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py`
- Modify: `tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_direct_paths_and_research.py`

**Step 1: Browser result updates working directory**
- Expect a screenshot tool result path to set `working_directory` to the parent folder.

**Step 2: Bare send-file can reuse session working directory**
- Expect `kirim file tes.md` to succeed when only `session.metadata["working_directory"]` is present.

### Task 3: Implement working-directory propagation

**Files:**
- Modify: `kabot/agent/loop_core/execution_runtime_parts/artifacts.py`
- Modify: `kabot/agent/loop_core/execution_runtime_parts/agent_loop.py`
- Modify: `kabot/agent/loop_core/execution_runtime_parts/intent.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/turn_metadata.py`
- Modify: `kabot/agent/loop_core/session_flow.py`
- Modify: `kabot/agent/loop_core/tool_enforcement_parts/core.py`

**Step 1: Introduce canonical working-directory helpers/state**
- Store a verified directory path in session/message metadata as `working_directory`.
- When a verified file path is seen, set `working_directory` to its parent.
- When a verified directory path is seen, set `working_directory` to that directory.

**Step 2: Prefer working directory in follow-up resolution**
- Delivery candidate resolution should consult `working_directory` before legacy breadcrumb fields.
- Message fallback should resolve bare filenames from `working_directory`.
- Intent gating should treat `working_directory` as valid file-context continuity.

### Task 4: Verify and record

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Run targeted regression commands**
- Browser/unit and runtime file-delivery slice

**Step 2: Update changelog**
- Note that Kabot now carries a session working directory derived from tool state for file/chat continuity.
