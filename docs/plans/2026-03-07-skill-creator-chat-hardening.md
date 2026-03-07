# Skill Creator Chat Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make chat-driven skill creation reliably trigger the `skill-creator` workflow, stay multilingual, and enforce discovery/plan approval without becoming rigid.

**Architecture:** Add a lightweight semantic detector for skill-creation intent, use it to force-load `skill-creator` into prompt context, and attach a hidden workflow note in session/runtime so the model follows discovery -> planning -> approval -> execution. Keep the system conversational by using structural state and prompt hints instead of a brittle command parser.

**Tech Stack:** Python, pytest, Kabot agent runtime/context, skills matcher, i18n helpers.

---

### Task 1: Add failing matcher tests for multilingual skill-creation intent

**Files:**
- Modify: `tests/agent/test_skills_matching.py`

**Steps:**
1. Add failing tests for natural phrases that should map to `skill-creator`:
   - Indonesian colloquial (`buat kemampuan baru buat kabot`)
   - English (`create a capability for posting to threads`)
   - Thai / Japanese / Chinese examples
2. Run targeted pytest and confirm failures.

### Task 2: Add failing runtime tests for forced skill loading and workflow note

**Files:**
- Modify: `tests/agent/loop_core/test_message_runtime.py`

**Steps:**
1. Add failing test verifying a skill-creation request passes `skill_names=["skill-creator"]` into `build_messages`.
2. Add failing test verifying current message gets a hidden workflow note that blocks direct file creation before plan approval.
3. Add failing test verifying follow-up `ya/lanjut` with active skill-creation flow keeps the workflow note.
4. Run targeted pytest and confirm failures.

### Task 3: Implement semantic skill-creation detector and matcher hardening

**Files:**
- Modify: `kabot/agent/skills.py`

**Steps:**
1. Add a reusable helper for skill-creation intent detection.
2. Expand non-rigid multilingual patterns for capability/integration/plugin/skill creation.
3. Keep false-positive risk low by requiring creation/build intent + artifact/domain cues.
4. Run matching tests until green.

### Task 4: Implement runtime workflow guard for skill creation

**Files:**
- Modify: `kabot/agent/loop_core/message_runtime.py`

**Steps:**
1. Add session metadata for active skill-creation workflow.
2. Force-load `skill-creator` via `skill_names` when semantic detector fires.
3. Inject hidden workflow guidance into `effective_content`:
   - first turn: discovery only
   - active flow: no file writes before explicit plan approval
4. Clear workflow on explicit topic change/abort.
5. Run runtime tests until green.

### Task 5: Align skill-creator docs with actual workspace skill location

**Files:**
- Modify: `kabot/skills/skill-creator/SKILL.md`
- Modify: `kabot/skills/skill-creator/references/workflows.md`
- Modify: `docs/skill-system.md`

**Steps:**
1. Update docs to say new user-created skills belong in active workspace `skills/` directory, not builtin package dir.
2. Clarify API-skill guidance: env requirements, no hardcoded secrets, fail-fast when missing.

### Task 6: Verify multilingual behavior with focused live probes

**Files:**
- No code changes required unless probes reveal gaps.

**Steps:**
1. Run targeted pytest for touched areas.
2. Run `ruff check` on touched files.
3. Probe live agent with varied chat styles/languages.
4. If probes show residual gaps, make minimal follow-up patches and re-run tests.
