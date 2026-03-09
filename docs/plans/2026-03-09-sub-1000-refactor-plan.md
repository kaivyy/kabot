# Sub-1000 Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce every repo-owned source and test file above 1000 lines to under 1000 lines without changing behavior.

**Architecture:** Convert oversized files into thin facades plus focused helper modules. Preserve public imports, Typer command registration, monkeypatch targets, and existing tests by re-exporting extracted functions from their original modules.

**Tech Stack:** Python, Typer, pytest, Rich

---

### Task 1: Finish modularizing `kabot/cli/commands.py`

**Files:**
- Modify: `kabot/cli/commands.py`
- Create: `kabot/cli/commands_setup.py`
- Create: `kabot/cli/commands_provider_runtime.py`
- Create: `kabot/cli/commands_gateway.py`
- Create: `kabot/cli/commands_agent_command.py`
- Create: `kabot/cli/commands_operations.py`
- Test: `tests/cli/test_commands_module_exports.py`

**Steps:**
1. Add a failing structural regression test asserting `kabot.cli.commands` re-exports selected functions from the new modules.
2. Extract command groups plus their private helpers into the new modules.
3. Keep `kabot/cli/commands.py` as a thin facade that imports and registers command functions with `app.command(...)`.
4. Preserve monkeypatch compatibility by dynamically resolving overrides via `kabot.cli.commands` for any helper currently patched in tests.
5. Run focused CLI and gateway tests after each extraction slice.

### Task 2: Split oversized agent runtime files

**Files:**
- Modify: `kabot/agent/loop_core/message_runtime.py`
- Modify: `kabot/agent/loop_core/execution_runtime.py`
- Modify: `kabot/agent/cron_fallback_nlp.py`
- Modify: `kabot/agent/skills.py`
- Modify: `kabot/agent/tools/stock.py`
- Create focused helper modules alongside each file
- Test: existing runtime and tool test modules, plus structural export tests if needed

**Steps:**
1. Add failing structural tests for extracted helpers where public imports or monkeypatch points matter.
2. Move follow-up state, classifier, tool-guard, and extractor helpers into new sibling modules.
3. Keep original files as orchestrators/re-export facades until line counts fall under 1000.
4. Run focused runtime, agent, and tool suites after each file family.

### Task 3: Split oversized wizard modules

**Files:**
- Modify: `kabot/cli/wizard/sections/channels.py`
- Modify: `kabot/cli/wizard/sections/model_auth.py`
- Modify: `kabot/cli/wizard/sections/tools_gateway_skills.py`
- Create focused helper modules beside each file
- Test: related wizard/CLI tests

**Steps:**
1. Move rendering, prompt helpers, and writeback helpers into sibling modules.
2. Preserve the section entrypoints and imports.
3. Run wizard or CLI integration tests that cover setup flows.

### Task 4: Split oversized tests

**Files:**
- Modify: `tests/agent/loop_core/test_message_runtime.py`
- Modify: `tests/agent/loop_core/test_execution_runtime.py`
- Modify: `tests/agent/test_tool_enforcement.py`
- Modify: `tests/agent/tools/test_stock.py`
- Modify: `tests/gateway/test_webhooks.py`
- Create new focused test modules per concern

**Steps:**
1. Group tests by feature area and move them without changing assertions.
2. Keep imports and fixtures stable.
3. Run each split suite to confirm collection and behavior stay unchanged.

### Task 5: Final verification and line-count audit

**Files:**
- Modify: `CHANGELOG.md`

**Steps:**
1. Run repo line-count audit excluding `.venv`, `.worktrees`, and generated directories.
2. Run broad verification suites for CLI, gateway, agent loop, wizard, and tools.
3. Update changelog with the modularization work and final count summary.
