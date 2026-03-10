# Chat Continuity Follow-up Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Kabot preserve recent chat intent for short follow-ups without letting stale stock/weather tool context hijack the conversation.

**Architecture:** Keep the runtime AI-driven, but harden the continuity lane around `pending_followup_intent`, generic follow-up detection, and history-based tool inheritance. Favor recent assistant/user conversational context over stale tool reuse when the current turn is low-information and context-seeking.

**Tech Stack:** Python, pytest, agent runtime follow-up helpers, CLI smoke tests.

---

### Task 1: Reproduce transcript regressions with tests

**Files:**
- Modify: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py`
- Modify: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_skill_workflows.py`

**Step 1: Write failing tests**

Add tests for:
- `lanjut rencana` should not infer `stock` from stale user history.
- `ya lanjut analisis` should continue recent assistant offer context when available.
- Generic `kenapa/maksudnya` follow-ups should force context-aware chat instead of direct tool reuse.

**Step 2: Run tests to verify they fail**

Run:
`pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_skill_workflows.py -q`

Expected: failures showing stale tool inference still wins.

### Task 2: Harden follow-up continuity logic

**Files:**
- Modify: `kabot/agent/loop_core/message_runtime.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/helpers.py`

**Step 1: Implement minimal helper logic**

Add a focused helper that recognizes generic continuation/context-seeking follow-ups such as:
- `lanjut`
- `lanjut rencana`
- `ya lanjut`
- `kenapa`
- `maksudnya gimana`

**Step 2: Wire it into runtime**

- Prevent history-based tool inheritance from claiming those turns too early.
- Force recent conversation context to stay available for the LLM on those turns.
- Preserve existing assistant-offer flow and keep AI-driven behavior.

**Step 3: Run targeted tests**

Run:
`pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_skill_workflows.py -q`

Expected: pass.

### Task 3: Verify against broader regressions and agent behavior

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Run broader verification**

Run:
`pytest tests/agent tests/cli tests/gateway -q`

**Step 2: Run lint on touched files**

Run:
`ruff check kabot/agent/loop_core/message_runtime.py kabot/agent/loop_core/message_runtime_parts/helpers.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_skill_workflows.py`

**Step 3: Smoke test actual agent**

Run CLI transcript checks for:
- Purwokerto weather -> follow-up why
- AAPL stock -> trend -> continue plan

**Step 4: Update changelog**

Add note about follow-up continuity hardening and Open-Meteo-first continuity verification.
