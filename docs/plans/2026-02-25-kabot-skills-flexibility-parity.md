# Kabot Skills Flexibility Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bring Kabot skill behavior to a more flexible model with layered skill sources, per-skill config entries, and wizard flow aligned with modern skill management.

**Architecture:** Add a shared skills-config normalization layer, wire it into `SkillsLoader` + setup wizard + CLI env injection, and extend tests to lock precedence and compatibility behavior. Keep backward compatibility by accepting legacy flat `skills` maps while saving/using canonical `skills.entries`.

**Tech Stack:** Python, Pydantic config model, Rich/Questionary wizard, pytest.

---

### Task 1: Add canonical skills-config normalization helpers

**Files:**
- Create: `kabot/config/skills_settings.py`
- Modify: `kabot/config/schema.py`
- Test: `tests/config/test_skills_settings.py`

**Step 1: Write the failing tests**

```python
def test_normalize_skills_settings_merges_legacy_and_entries():
    ...

def test_iter_skill_env_pairs_reads_entries_and_legacy():
    ...

def test_set_skill_entry_env_writes_into_entries():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/config/test_skills_settings.py -q`
Expected: FAIL because helper module/functions do not exist yet.

**Step 3: Write minimal implementation**

- Implement canonical helpers:
  - normalize settings to `entries`, `allow_bundled`, `load`.
  - read env bindings from both canonical and legacy forms.
  - upsert entry env in canonical `entries`.
- Relax `Config.skills` typing to accept richer structure.

**Step 4: Run test to verify it passes**

Run: `pytest tests/config/test_skills_settings.py -q`
Expected: PASS.

### Task 2: Implement layered skill source precedence in loader

**Files:**
- Modify: `kabot/agent/skills.py`
- Test: `tests/agent/test_skills_loader_precedence.py`

**Step 1: Write the failing tests**

```python
def test_skills_precedence_workspace_over_managed_over_builtin():
    ...

def test_skills_loader_supports_managed_dir_from_config():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_skills_loader_precedence.py -q`
Expected: FAIL with current workspace+builtin-only behavior.

**Step 3: Write minimal implementation**

- Extend `SkillsLoader` constructor to accept `skills_config`.
- Resolve source roots from config (`managed_dir`, `extra_dirs`) with deterministic precedence:
  - workspace > managed > bundled > extra.
- Update `load_skill()` and `list_skills()` to honor precedence.

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_skills_loader_precedence.py -q`
Expected: PASS.

### Task 3: Apply `skills.entries` semantics in eligibility and env requirements

**Files:**
- Modify: `kabot/agent/skills.py`
- Test: `tests/agent/test_skills_entries_semantics.py`

**Step 1: Write the failing tests**

```python
def test_entries_env_satisfies_required_env():
    ...

def test_disabled_entry_marks_skill_ineligible():
    ...

def test_allow_bundled_blocks_bundled_only():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_skills_entries_semantics.py -q`
Expected: FAIL with current eligibility logic.

**Step 3: Write minimal implementation**

- Consume `skills.entries.<skill_key>` in requirement checks.
- Support `api_key` convenience mapped to `primaryEnv`.
- Mark disabled and bundled-allowlist blocked skills as ineligible with status fields.

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_skills_entries_semantics.py -q`
Expected: PASS.

### Task 4: Migrate wizard + CLI env injection to canonical entries

**Files:**
- Modify: `kabot/cli/wizard/sections/tools_gateway_skills.py`
- Modify: `kabot/cli/commands.py`
- Modify: `tests/cli/test_setup_wizard_skills.py`

**Step 1: Write/adjust failing tests**

- Update/extend wizard tests to assert env values are persisted under:
  - `config.skills["entries"][skill_key]["env"][ENV_KEY]`
- Keep compatibility test for legacy read path.

**Step 2: Run tests to verify failures**

Run: `pytest tests/cli/test_setup_wizard_skills.py -q`
Expected: FAIL before migration.

**Step 3: Write minimal implementation**

- Wizard reads normalized settings and writes env into canonical entries.
- Wizard injects env from both canonical and legacy config.
- CLI startup env injection also reads both formats.

**Step 4: Run tests to verify pass**

Run: `pytest tests/cli/test_setup_wizard_skills.py -q`
Expected: PASS.

### Task 5: Wire runtime context loader with skills config and verify

**Files:**
- Modify: `kabot/agent/context.py`
- Modify: `kabot/agent/loop.py`
- Test: `tests/agent/test_context_builder.py` (new or existing extension)

**Step 1: Write failing test**

```python
def test_context_builder_passes_skills_config_to_loader():
    ...
```

**Step 2: Run test to verify fail**

Run: `pytest tests/agent/test_context_builder.py -q`
Expected: FAIL before wiring.

**Step 3: Implement minimal code**

- Accept optional `skills_config` in `ContextBuilder`.
- Pass `config.skills` from `AgentLoop` to `ContextBuilder` so runtime skills resolution uses config entries/precedence.

**Step 4: Run test to verify pass**

Run: `pytest tests/agent/test_context_builder.py -q`
Expected: PASS.

### Task 6: Update docs and changelog

**Files:**
- Modify: `HOW_TO_USE.MD`
- Modify: `CHANGELOG.md`

**Step 1: Document new behavior**

- Explain canonical skills config (`skills.entries`, `allowBundled`, `load.managedDir`, `load.extraDirs`).
- Explain source precedence and legacy compatibility notes.

**Step 2: Update changelog**

- Add `Unreleased` entries for:
  - skills-config canonicalization.
  - layered precedence and eligibility improvements.
  - wizard persistence changes.

**Step 3: Verify docs formatting**

Run: `rg -n "skills.entries|managedDir|allowBundled" HOW_TO_USE.MD CHANGELOG.md`
Expected: entries found in both docs.

### Task 7: Final verification batch

**Files:**
- Verify targeted tests only.

**Step 1: Run focused verification**

Run:
- `pytest tests/config/test_skills_settings.py -q`
- `pytest tests/agent/test_skills_loader_precedence.py -q`
- `pytest tests/agent/test_skills_entries_semantics.py -q`
- `pytest tests/cli/test_setup_wizard_skills.py -q`
- `pytest tests/agent/test_skills_requirements_os.py -q`

**Step 2: Confirm no regressions in touched modules**

Run:
- `pytest tests/agent/test_skills_matching.py -q`
- `pytest tests/agent/test_context_builder.py -q`

**Step 3: Summarize outcomes**

- List changed files.
- List behavior deltas.
- Note any non-blocking follow-up.
