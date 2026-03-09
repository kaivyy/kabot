# Simple Response Text-Only First Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce `first_response_ms` for simple no-tool chats by starting the first LLM attempt without tool definitions.

**Architecture:** Keep complex/tool-bearing agent flows unchanged and only narrow the optimization to `run_simple_response()`. Extend the existing LLM fallback helper with an optional `include_tools_initial` flag so simple responses can start text-only while preserving the same fallback and observability path.

**Tech Stack:** Python, pytest, asyncio, provider chat fallback helpers

---

### Task 1: Lock the expected simple-response contract

**Files:**
- Modify: `tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py`

**Step 1: Write the failing test**

- Update the simple-response fallback assertion so `run_simple_response()` must call `_call_llm_with_fallback(..., include_tools_initial=False)`.

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py -q`

Expected: FAIL because `run_simple_response()` does not yet pass `include_tools_initial=False`.

### Task 2: Lock the provider-call behavior

**Files:**
- Modify: `tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py`

**Step 1: Write the failing test**

- Add a focused test for `call_llm_with_fallback()` that verifies the first provider call omits `tools` when `include_tools_initial=False`.

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py -q`

Expected: FAIL because the first provider call still includes tools.

### Task 3: Implement the minimal runtime change

**Files:**
- Modify: `kabot/agent/loop_core/execution_runtime_parts/llm.py`
- Modify: `kabot/agent/loop_parts/delegates.py`

**Step 1: Write minimal implementation**

- Add `include_tools_initial: bool = True` to `call_llm_with_fallback()`.
- Thread the same optional flag through `AgentLoop._call_llm_with_fallback(...)`.
- Change `run_simple_response()` to pass `include_tools_initial=False`.
- Keep existing complex/agent-loop callers on the default path.

**Step 2: Run focused tests**

Run: `pytest tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py -q`

Expected: PASS.

### Task 4: Verify full safety and real latency

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Run broader verification**

Run: `pytest tests/agent tests/cli tests/gateway -q`

Expected: PASS.

**Step 2: Run real CLI smoke**

Run: `python -m kabot.cli.commands agent -m "hari apa sekarang? jawab singkat, pakai WIB ya." --no-markdown --logs`

Expected: Correct short answer with lower `first_response_ms` than before and no tool-routing regressions.
