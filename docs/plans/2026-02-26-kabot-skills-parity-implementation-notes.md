# Kabot Skills Parity (Implementation Notes)

Date: 2026-02-26
Scope: Wizard + Runtime, cross-platform strict

## What Was Implemented

1. Canonical skills config model (with legacy compatibility):
- `skills.entries.<skill_key>.enabled|env|apiKey|config`
- `skills.allowBundled`
- `skills.load.managedDir|extraDirs`
- `skills.install.mode|nodeManager|preferBrew`

2. Runtime skills parity:
- Installer metadata normalized to list form (`metadata.kabot.install`) with legacy `{ "cmd": ... }` compatibility.
- Installer specs filtered by OS and ranked by install preference.
- Skill status payload standardized for wizard/runtime use (`eligible`, `missing`, `install`, `primaryEnv`, `skill_key`, etc.).
- Source precedence finalized:
  - `extraDirs` -> bundled -> managed -> `~/.agents/skills` -> `<workspace>/.agents/skills` -> `<workspace>/skills`.

3. Wizard skills parity (hybrid UI + manual install):
- Added `kabot/cli/wizard/skills_prompts.py` for richer checkbox prompt in skills flow only.
- Skills dependency flow switched to manual plan mode:
  - no automatic dependency command execution,
  - node manager prompt appears only when selected skills include node installer metadata,
  - install plan printed per skill with doctor/docs hints.
- Env configuration now stays skill-scoped and dedupes same env key across selected skills.

4. Config migration + safety:
- Skills legacy config is auto-normalized at load.
- Migrated config is persisted atomically with timestamped backup.
- Constant-style keys (e.g. `OPENAI_API_KEY`) are preserved during key conversion.

## Validation Summary

- Focused parity tests passed:
  - `tests/config/test_skills_settings.py`
  - `tests/config/test_loader_meta_migration.py`
  - `tests/agent/test_skills_loader_precedence.py`
  - `tests/agent/test_skills_entries_semantics.py`
  - `tests/cli/test_setup_wizard_skills.py`
- Regression set passed:
  - `tests/agent/test_skills_requirements_os.py`
  - `tests/agent/test_context_builder.py`
  - `tests/cli/test_skill_env_injection.py`
  - `tests/cli/test_wizard_modules.py`
  - `tests/cli/test_setup_wizard_ui_style.py`
  - `tests/cli/test_setup_wizard_tools_menu.py`

## Interactive Verification Notes

- Real command smoke run through `kabot config` path was executed in piped/non-TTY mode.
- Prior crash at `ClackUI.clack_select` (`NoConsoleScreenBufferError`) was fixed with non-TTY fallback behavior.
- Wizard skills/menu regression coverage remains green after fix:
  - `tests/cli/test_setup_wizard_skills.py`
  - `tests/cli/test_setup_wizard_ui_style.py`
  - `tests/cli/test_wizard_modules.py`
  - `tests/cli/test_skill_env_injection.py`
