# OpenClaw-Style Bootstrap Onboarding Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Kabot feel closer to OpenClaw during first-run and skill-creation conversations by improving bootstrap tone, persisting onboarding answers into workspace identity files, and softening rigid skill-creator behavior.

**Architecture:** Keep Kabot's runtime architecture intact, but add a dedicated bootstrap onboarding persistence helper invoked from message-response tail. Update workspace templates and prompt text to be more OpenClaw-like, while keeping evidence-based tool execution untouched.

**Tech Stack:** Python, pytest, markdown workspace templates, Kabot message runtime.

---

### Task 1: Refresh bootstrap templates

**Files:**
- Modify: `kabot/utils/workspace_templates.py`
- Test: `tests/utils/test_workspace_templates.py`

**Steps:**
1. Write/adjust tests to assert bootstrap templates include OpenClaw-style guidance and completion semantics.
2. Update `SOUL.md`, `IDENTITY.md`, `USER.md`, and `BOOTSTRAP.md` template text to be more natural and persona-driven.
3. Run targeted template tests.

### Task 2: Add onboarding persistence helper

**Files:**
- Create: `kabot/agent/loop_core/message_runtime_parts/bootstrap_onboarding.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/response_runtime.py`
- Test: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_bootstrap_onboarding.py`

**Steps:**
1. Write failing tests for multi-turn onboarding persistence into `IDENTITY.md` and `USER.md` plus `BOOTSTRAP.md` removal.
2. Implement permissive parsing for numbered/labeled/free-text onboarding answers.
3. Persist partial onboarding state in session metadata.
4. Write identity/user files when data appears and delete `BOOTSTRAP.md` once minimum fields are complete.
5. Run targeted onboarding tests.

### Task 3: Soften prompt and skill-creator tone

**Files:**
- Modify: `kabot/agent/context.py`
- Modify: `kabot/skills/skill-creator/SKILL.md`
- Test: `tests/agent/test_context_builder.py`

**Steps:**
1. Add failing assertions for more OpenClaw-like bootstrap/persona prompt presence where appropriate.
2. Adjust general/chat identity guidance to be less stiff and less template-heavy.
3. Rewrite `skill-creator` instructions to favor natural discovery/planning language without exposing rigid phase labels to users.
4. Run targeted prompt tests.

### Task 4: Verify and document

**Files:**
- Modify: `CHANGELOG.md`

**Steps:**
1. Run focused pytest suite for templates, onboarding, context builder, and relevant runtime cases.
2. Update changelog with bootstrap onboarding persistence and tone changes.
3. Report what changed, what was verified, and any parity gaps still remaining.
