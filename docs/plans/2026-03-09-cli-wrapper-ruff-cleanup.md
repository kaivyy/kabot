# CLI Wrapper Ruff Cleanup Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce repo-wide Ruff backlog safely by cleaning the extracted CLI wrapper modules without changing command behavior or breaking compatibility exports.

**Architecture:** Tackle the mechanically fixable CLI wrapper files as an isolated batch. Use existing CLI export/runtime tests as safety rails, apply Ruff fixes only to selected modules, then verify with targeted and full test suites before recounting repo-wide Ruff findings.

**Tech Stack:** Python, Ruff, pytest, Typer CLI modules.

---

### Task 1: Lock safety rails for CLI wrappers

**Files:**
- Verify: `tests/cli/test_commands_module_exports.py`
- Verify: `tests/cli/test_agent_runtime_config.py`
- Verify: `tests/cli/test_doctor_commands.py`

**Step 1: Inspect existing test coverage for CLI wrapper exports and runtime behavior**

Run: `pytest tests/cli/test_commands_module_exports.py tests/cli/test_agent_runtime_config.py tests/cli/test_doctor_commands.py -q`
Expected: PASS

**Step 2: Add tests only if a missing compatibility surface is discovered during cleanup**

No code change unless the cleanup reveals an unguarded export.

### Task 2: Clean extracted CLI wrapper modules

**Files:**
- Modify: `kabot/cli/commands.py`
- Modify: `kabot/cli/commands_setup.py`
- Modify: `kabot/cli/commands_provider_runtime.py`
- Modify: `kabot/cli/commands_models_auth.py`
- Modify: `kabot/cli/commands_gateway.py`
- Modify: `kabot/cli/commands_approvals.py`
- Modify: `kabot/cli/commands_agent_command.py`

**Step 1: Inspect Ruff findings for selected files**

Run: `ruff check kabot/cli/commands.py kabot/cli/commands_setup.py kabot/cli/commands_provider_runtime.py kabot/cli/commands_models_auth.py kabot/cli/commands_gateway.py kabot/cli/commands_approvals.py kabot/cli/commands_agent_command.py --statistics`
Expected: only mechanical categories (`F401`, `I001`, `E402`, whitespace, limited `F811`)

**Step 2: Apply minimal mechanical cleanup**

Run: `ruff check <selected files> --fix`
Expected: import sorting/unused import cleanup only

**Step 3: Manually restore any intentional facade/re-export import if Ruff removes it**

Verification target: existing CLI tests stay green.

### Task 3: Verify behavior and recount backlog

**Files:**
- Modify: `CHANGELOG.md` only if this batch materially changes backlog numbers

**Step 1: Run targeted CLI verification**

Run: `pytest tests/cli/test_commands_module_exports.py tests/cli/test_agent_runtime_config.py tests/cli/test_doctor_commands.py tests/cli/test_agent_smoke_matrix.py -q`
Expected: PASS

**Step 2: Run full suite**

Run: `pytest tests/agent tests/cli tests/gateway -q`
Expected: PASS

**Step 3: Recount repo-wide Ruff backlog**

Run: `ruff check . --statistics`
Expected: lower total than before this batch
