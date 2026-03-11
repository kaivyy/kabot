# Committed Action Continuity Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Kabot treat assistant-promised actions and user follow-up approvals as a first-class continuity path across tools and skills, so side-effecting requests stay grounded and do not drift into unrelated parsers or hallucinated completion.

**Architecture:** Extend pending follow-up intent storage to distinguish ordinary assistant offers from committed actions. Teach the message runtime to prioritize committed actions over weak parser guesses, and escalate generic side-effect/generation requests into the agent loop so the model uses tools/skills instead of shallow chat completions.

**Tech Stack:** Python, pytest, async message runtime, session metadata continuity state

---

### Task 1: Add failing tests for committed-action state

**Files:**
- Modify: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_fast_paths_and_status.py`

**Step 1: Write the failing test**

Add assertions that promise-style assistant replies store `kind="assistant_committed_action"` and persist the originating user request text for later follow-up reuse.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_fast_paths_and_status.py -q`

Expected: FAIL on `kind` and missing `request_text`.

### Task 2: Add failing tests for committed-action routing

**Files:**
- Modify: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py`

**Step 1: Write the failing test**

Add coverage for:
- `ya lakukan` against pending committed action forcing `_run_agent_loop`
- stale last tool execution not overriding committed action
- media/file generation follow-up reusing original user request text
- explicit generation/build requests escalating to agent loop up front

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py -q`

Expected: FAIL because current runtime routes these through simple chat.

### Task 3: Implement committed-action continuity state

**Files:**
- Modify: `kabot/agent/loop_core/message_runtime_parts/followup.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/helpers.py`

**Step 1: Write minimal implementation**

Extend pending intent payloads to support:
- `kind="assistant_committed_action"`
- `request_text`

Add helpers to detect side-effect/generation requests and committed-action follow-up confirmations without narrowing to one domain.

**Step 2: Run focused tests**

Run: `python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_fast_paths_and_status.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py -q`

Expected: Some failures remain in runtime integration.

### Task 4: Implement message runtime routing

**Files:**
- Modify: `kabot/agent/loop_core/message_runtime.py`

**Step 1: Write minimal implementation**

Update runtime to:
- prioritize `assistant_committed_action` before weak parser/tool heuristics
- inject committed-action grounding notes into LLM context
- force `decision.is_complex = True` for committed-action follow-ups
- route initial side-effect/generation/build requests into `_run_agent_loop`
- preserve regular `assistant_offer` behavior for option prompts/questions

**Step 2: Run focused tests**

Run: `python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_fast_paths_and_status.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py -q`

Expected: PASS

### Task 5: Verify regression surface and document change

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Run broader verification**

Run: `python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_basics.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_fast_paths_and_status.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py tests/cli/test_agent_smoke_matrix.py -q`

Expected: PASS

**Step 2: Run real-agent smoke**

Run: `python -X utf8 -m kabot.cli.agent_smoke_matrix --no-default-cases --continuity-cases --mcp-local-echo --json`

Expected: exit 0 and continuity cases still pass.
