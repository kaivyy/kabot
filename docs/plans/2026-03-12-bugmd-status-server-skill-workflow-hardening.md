# BUG.MD Status Server And Skill Workflow Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the remaining `BUG.MD` regressions where short follow-ups break `status server` continuity and skill-creation workflows reset after the user answers discovery questions.

**Architecture:** Keep the existing continuity/runtime design, but tighten two seams: committed assistant actions should reuse the promised task text to infer the correct tool, and active skill workflows should recognize substantive discovery answers instead of only `yes/approve`-style turns. The fix stays behavior-focused and test-first.

**Tech Stack:** Python, pytest, Kabot message runtime.

---

### Task 1: Reproduce the `status server -> ya` continuation bug

**Files:**
- Modify: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py`

**Steps:**
1. Add a failing test where `pending_followup_intent.kind == assistant_committed_action` and the committed request text is a server-status request.
2. Assert that a short follow-up like `ya` reuses that committed request and infers `required_tool=server_monitor`.
3. Run only that test to confirm it fails for the current root cause.

### Task 2: Reproduce the skill-creator discovery reset bug

**Files:**
- Modify: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_skill_workflows.py`

**Steps:**
1. Add a failing test with an active `skill_creation_flow` in `discovery`.
2. Use a substantive structured answer like `1. a,b,c,d ...` instead of a short approval.
3. Assert the runtime keeps `skill-creator` forced, preserves follow-up context, and does not fall back to a plain chat turn.

### Task 3: Implement the minimal runtime fix

**Files:**
- Modify: `kabot/agent/loop_core/message_runtime_parts/continuity_runtime.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/context_notes.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/process_flow.py`

**Steps:**
1. Infer a deterministic tool from committed action request text when the pending follow-up is `assistant_committed_action`.
2. Add a small helper for substantive skill-workflow follow-up answers.
3. Extend skill workflow continuation logic to keep discovery/planning active on those answers without broad topic hijacking.

### Task 4: Verify and document

**Files:**
- Modify: `CHANGELOG.md`

**Steps:**
1. Run targeted pytest for the affected runtime modules.
2. Run a slightly broader regression slice covering continuity + skill workflows.
3. Update changelog with the new hardening notes.
