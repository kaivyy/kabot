# OpenClaw-Style Skill-First Prompting Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce Kabot's parser dependence by shifting skill usage toward OpenClaw-style summary-first prompting while preserving forced-skill/runtime continuity.

**Architecture:** Keep deterministic runtime latches for truly forced flows like weather/skill-creator, but stop auto-injecting full matched skill bodies for ordinary requests. Instead, expose English `available_skills` guidance and let the model read one `SKILL.md` when it clearly applies.

**Tech Stack:** Python, pytest, ContextBuilder, SkillsLoader, prompt assembly, message runtime.

---

### Task 1: Lock the desired prompt contract with tests

**Files:**
- Modify: `tests/agent/test_context_builder.py`
- Modify: `tests/cli/test_agent_skill_runtime.py`

**Steps:**
1. Add a failing test proving auto-matched skills no longer inject full skill bodies into the prompt for ordinary requests.
2. Add a failing test proving the prompt includes an English OpenClaw-style skills instruction block and an `available_skills` summary.
3. Add a failing test proving forced skill names still load full skill content.
4. Run focused pytest commands and verify the new tests fail for the expected reason.

### Task 2: Implement summary-first skill prompting

**Files:**
- Modify: `kabot/agent/context.py`
- Modify: `kabot/agent/skills.py`

**Steps:**
1. Add a helper that formats an OpenClaw-style English skills guidance block around the skills summary.
2. Change ordinary auto-matched skill handling so it only records selected skill candidates, not full skill bodies.
3. Keep full skill body loading for explicitly forced/requested skills.
4. Keep catalog/help requests using the skills summary block.

### Task 3: Verify multilingual behavior does not regress

**Files:**
- Modify: `tests/agent/test_context_builder.py`
- Modify: `CHANGELOG.md`

**Steps:**
1. Add/adjust tests covering Indonesian prompts that should still trigger the English skill guidance block.
2. Run focused regression suites for context builder and skill runtime.
3. Document the change and note that this is a parser-reduction tranche, not full parser removal.
