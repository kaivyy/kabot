# Dashboard Full Sweep Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bring Kabot's dashboard much closer to OpenClaw-style monitoring and operator parity by enriching dashboard data, adding richer panels, and wiring cron/skills actions from the UI.

**Architecture:** Keep the dashboard HTMX-driven and lightweight. Expand the gateway status payload in `kabot/cli/commands.py` using existing runtime services (`CostTracker`, `CronService`, `SkillsLoader`, `SubagentRegistry`) plus local git metadata, then render that richer payload in `kabot/gateway/handlers/dashboard.py`. Add targeted dashboard POST handlers for cron and skills actions so panels are interactive without introducing a second control architecture.

**Tech Stack:** Python, aiohttp, HTMX, pytest, existing Kabot config/cron/skills registries

---

### Task 1: Enrich Dashboard Cost And Monitoring Data

**Files:**
- Modify: `kabot/core/cost_tracker.py`
- Modify: `kabot/cli/commands.py`
- Test: `tests/cli/test_gateway_dashboard_helpers.py`

**Step 1: Write failing tests**

Add tests that expect:
- `CostTracker.get_summary()` to expose daily history and per-model usage/cost breakdown.
- `_gateway_status_provider()` payload to include `costs`, `token_usage`, `model_usage`, and `cost_history`.

**Step 2: Run tests to verify they fail**

Run: `pytest tests/cli/test_gateway_dashboard_helpers.py -q`

**Step 3: Write minimal implementation**

Implement:
- richer aggregation in `CostTracker`
- status payload wiring in `_gateway_status_provider()`

**Step 4: Run tests to verify they pass**

Run: `pytest tests/cli/test_gateway_dashboard_helpers.py -q`

### Task 2: Add Cron, Skills, Subagent, And Git Dashboard Data

**Files:**
- Modify: `kabot/cli/commands.py`
- Modify: `kabot/gateway/webhook_server.py`
- Test: `tests/cli/test_gateway_dashboard_helpers.py`
- Test: `tests/gateway/test_webhooks.py`

**Step 1: Write failing tests**

Add tests that expect:
- status payload to include `cron_jobs_list`, `skills`, `subagent_activity`, and `git_log`
- dashboard routes to support panel actions for cron and skills

**Step 2: Run tests to verify they fail**

Run: `pytest tests/cli/test_gateway_dashboard_helpers.py tests/gateway/test_webhooks.py -q`

**Step 3: Write minimal implementation**

Implement helper collection for:
- cron list + run history preview
- skill status using `SkillsLoader.list_skills(filter_unavailable=False)`
- subagent runs from `SubagentRegistry`
- recent commits via local `git log`
- POST routes for dashboard cron and skills actions

**Step 4: Run tests to verify they pass**

Run: `pytest tests/cli/test_gateway_dashboard_helpers.py tests/gateway/test_webhooks.py -q`

### Task 3: Add Dashboard Control Actions For Cron And Skills

**Files:**
- Modify: `kabot/cli/commands.py`
- Modify: `kabot/gateway/handlers/control.py`
- Modify: `kabot/gateway/handlers/dashboard.py`
- Test: `tests/cli/test_gateway_dashboard_helpers.py`

**Step 1: Write failing tests**

Add tests for:
- `cron.enable`, `cron.disable`, `cron.run`, `cron.delete`
- `skills.enable`, `skills.disable`, `skills.set_api_key`

**Step 2: Run tests to verify they fail**

Run: `pytest tests/cli/test_gateway_dashboard_helpers.py -q`

**Step 3: Write minimal implementation**

Extend `_gateway_dashboard_control_action()` to:
- mutate cron jobs through `CronService`
- update skill config via `set_skill_entry_enabled()` and `set_skill_entry_env()`
- persist config changes with `save_config_fn`

**Step 4: Run tests to verify they pass**

Run: `pytest tests/cli/test_gateway_dashboard_helpers.py -q`

### Task 4: Upgrade Dashboard Panels And Rendering

**Files:**
- Modify: `kabot/gateway/handlers/dashboard.py`
- Modify: `kabot/gateway/templates/sections/overview.html`
- Modify: `kabot/gateway/templates/sections/engine.html`
- Modify: `kabot/gateway/templates/sections/settings.html`
- Test: `tests/gateway/test_webhooks.py`

**Step 1: Write failing tests**

Add tests that expect rendered dashboard fragments to show:
- cost/model breakdown
- daily usage chart data
- cron detail rows with actions
- skill state rows with actions
- subagent activity panel
- git log panel

**Step 2: Run tests to verify they fail**

Run: `pytest tests/gateway/test_webhooks.py -q`

**Step 3: Write minimal implementation**

Render:
- richer cost cards and chart blocks
- actionable cron and skills rows
- new subagent and git panels
- stronger alerts based on cost, cron failures, and subagent failures

**Step 4: Run tests to verify they pass**

Run: `pytest tests/gateway/test_webhooks.py -q`

### Task 5: Final Verification

**Files:**
- Verify only

**Step 1: Run targeted verification**

Run: `pytest tests/cli/test_gateway_dashboard_helpers.py tests/gateway/test_webhooks.py tests/gateway/test_cron_api.py -q`

**Step 2: Run a requirements check**

Verify the final payload and UI cover:
- richer monitoring data
- richer alerts
- cron detail + actions
- skills detail + actions
- subagent activity
- git log

**Step 3: Summarize remaining intentional gaps**

Document anything still not implemented, especially if it would require networked installs or a bigger API surface than the current dashboard architecture supports.
