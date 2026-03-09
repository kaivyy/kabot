# Commands Dashboard Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split the dashboard payload/helper block out of `kabot/cli/commands.py` into a dedicated module without changing behavior.

**Architecture:** Keep `commands.py` as the CLI entrypoint and command registry, but move dashboard/runtime helper functions into a focused module that `commands.py` re-exports. Preserve existing tests and call sites so this is a safe refactor-first step.

**Tech Stack:** Python, Typer, pytest

---

### Task 1: Lock the new module boundary with a regression test

**Files:**
- Create: `tests/cli/test_dashboard_payloads_module.py`

**Step 1: Write the failing test**

Add a test that imports `kabot.cli.dashboard_payloads` and asserts:
- the module exists
- `kabot.cli.commands` re-exports `_build_dashboard_config_summary`
- `kabot.cli.commands` re-exports `_build_dashboard_status_payload`

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_dashboard_payloads_module.py -q`
Expected: FAIL because the module does not exist yet.

### Task 2: Extract dashboard/runtime helpers into a dedicated CLI module

**Files:**
- Create: `kabot/cli/dashboard_payloads.py`
- Modify: `kabot/cli/commands.py`

**Step 1: Move cohesive helpers**

Extract these helpers into `kabot/cli/dashboard_payloads.py`:
- `_build_dashboard_config_summary`
- `_list_provider_models_for_dashboard`
- `_compose_model_override`
- `_parse_model_fallbacks`
- `_build_dashboard_nodes`
- `_build_dashboard_cost_payload`
- `_format_dashboard_timestamp_ms`
- `_describe_dashboard_schedule`
- `_build_dashboard_channel_rows`
- `_build_dashboard_cron_snapshot`
- `_build_dashboard_skills_snapshot`
- `_build_dashboard_subagent_activity`
- `_build_dashboard_git_log`
- `_build_dashboard_status_payload`

**Step 2: Keep `commands.py` behavior stable**

Import those helpers back into `commands.py` so existing tests and external imports still work.

### Task 3: Verify focused and broader regressions

**Files:**
- Test: `tests/cli/test_dashboard_payloads_module.py`
- Test: `tests/cli/test_gateway_dashboard_helpers.py`
- Test: `tests/gateway/test_webhooks.py`

**Step 1: Focused verification**

Run: `pytest tests/cli/test_dashboard_payloads_module.py tests/cli/test_gateway_dashboard_helpers.py -q`

**Step 2: Broader gateway verification**

Run: `pytest tests/gateway/test_webhooks.py -q`

**Step 3: Combined verification**

Run: `pytest tests/cli/test_dashboard_payloads_module.py tests/cli/test_gateway_dashboard_helpers.py tests/gateway/test_webhooks.py -q`
