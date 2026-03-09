# Explicit Skill Fast Path Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce cold `match_skills()` cost for explicit skill-use prompts without changing behavior for general skill matching.

**Architecture:** Add a narrow fast path in `SkillsLoader.match_skills()` for prompts that explicitly mention a concrete skill name. Build a lightweight name lookup from skill roots and frontmatter metadata, and only fall back to the full keyword/body index when the prompt is not an explicit skill-reference turn.

**Tech Stack:** Python, pytest, SkillsLoader, ContextBuilder, CLI one-shot agent runtime

---

### Task 1: Lock explicit-skill fast path behavior with failing tests

**Files:**
- Modify: `tests/agent/test_skills_matching.py`
- Modify: `kabot/agent/skills.py`

**Step 1: Write failing tests**
- Add a test proving `match_skills()` can resolve an explicit prompt like `Please use the weather skill for this request.` without calling `_build_skill_index()`.
- Add a second test proving non-explicit prompts still call `_build_skill_index()` so broad behavior is preserved.

**Step 2: Run tests to verify RED**
Run: `pytest tests/agent/test_skills_matching.py::test_match_skills_explicit_skill_turn_skips_full_index tests/agent/test_skills_matching.py::test_match_skills_non_explicit_turn_still_uses_full_index -q`
Expected: first test fails because `_build_skill_index()` is still used for explicit-skill turns.

### Task 2: Implement minimal explicit-skill resolver

**Files:**
- Modify: `kabot/agent/skills.py`

**Step 1: Add a small skill-name lookup helper**
- Reuse skill-root precedence.
- Match normalized explicit skill names from directory names.
- Preserve workflow expansion and requirement validation.

**Step 2: Use it only for explicit skill-reference turns**
- Keep general prompts on the existing keyword/body index path.
- Avoid broad parser rules; only activate when the prompt clearly asks to use a named skill.

**Step 3: Run targeted tests**
Run: `pytest tests/agent/test_skills_matching.py::test_match_skills_explicit_skill_turn_skips_full_index tests/agent/test_skills_matching.py::test_match_skills_non_explicit_turn_still_uses_full_index -q`
Expected: PASS

### Task 3: Verify context/runtime impact

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Run targeted regression**
Run: `pytest tests/agent/test_context_builder.py tests/agent/test_skills_matching.py tests/agent/test_skills_entries_semantics.py tests/cli/test_agent_skill_runtime.py -q`
Expected: PASS

**Step 2: Run full regression**
Run: `pytest tests/agent tests/cli tests/gateway -q`
Expected: PASS

**Step 3: Run local CLI smoke**
Run:
- `python -m kabot.cli.commands agent -m "Please use the weather skill for this request." --no-markdown --logs`
- `python -m kabot.cli.commands agent -m "hari apa sekarang? jawab singkat, pakai WIB ya." --no-markdown --logs`

Expected:
- explicit-skill `context_build_ms` drops materially from the current ~`1148ms` path,
- temporal lean probe remains fast,
- prompt behavior stays natural and AI-driven.
