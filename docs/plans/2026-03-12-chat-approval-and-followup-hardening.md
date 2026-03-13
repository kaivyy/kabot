# Chat Approval And Follow-up Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace chat-level legacy slash execution approval with natural-language approval turns, while hardening weather and Meta Threads follow-up routing from `BUG.MD`.

**Architecture:** Keep the existing firewall and pending exec queue, but change the conversational contract from slash commands to session-aware natural-language approval/denial resolution. Reuse the same follow-up continuity layer to resolve weather forecasts and suppress finance routing when the user is clearly talking about Meta Threads/API integration rather than the stock ticker.

**Tech Stack:** Python, pytest, Kabot agent loop runtime, shell exec tool, continuity/follow-up helpers.

---

### Task 1: Lock The Broken Transcript With Tests

**Files:**
- Modify: `tests/agent/test_exec_approval_flow.py`
- Modify: `tests/agent/tools/test_shell_firewall_ask_mode.py`
- Modify: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py`
- Modify: `tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py`

**Step 1: Write the failing tests**

- Add a test showing a pending exec approval can be accepted by a normal chat turn such as `ya jalankan sekarang`, without any slash approval command.
- Add a test showing a pending exec approval can be denied by a normal chat turn such as `jangan jadi jalankan`.
- Add a test showing the shell approval prompt no longer instructs the user to reply with a slash approval command.
- Add a weather follow-up regression for:
  - current weather already fetched for Cilacap
  - user says `prediksi 3-6 jam ke depan`
  - runtime keeps `weather` and reuses `Cilacap`
- Add a routing regression showing `saya mau koneksi api meta threads` does **not** route to stock.

**Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/agent/test_exec_approval_flow.py tests/agent/tools/test_shell_firewall_ask_mode.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py -q
```

Expected:
- New approval-via-chat tests fail because only the legacy slash approval and denial commands are supported.
- New shell prompt assertion fails because the tool still instructs the legacy slash approval command.
- New weather forecast follow-up test fails if query/context degrades to location-less or wrong follow-up handling.
- New Meta Threads test fails if routing still chooses `stock`.

### Task 2: Replace Slash Approval With Natural-Language Approval Resolution

**Files:**
- Modify: `kabot/agent/tools/shell.py`
- Modify: `kabot/agent/loop_parts/delegates.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/tail.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/process_flow.py`

**Step 1: Implement approval intent parsing for pending exec state**

- Add a natural-language resolver that classifies a short turn against a pending exec approval as:
  - `approve`
  - `deny`
  - `none`
- Keep this resolver scoped to sessions with a pending exec approval entry so normal `ya` turns elsewhere are untouched.

**Step 2: Update the shell approval prompt**

- Change pending approval copy from slash-command instructions to a conversational instruction such as:
  - approve: `ya, jalankan`
  - deny: `jangan jalankan`
- Keep approval id internal for storage/audit, but stop exposing the legacy slash approval command.

**Step 3: Wire runtime interception**

- Remove chat reliance on the legacy slash-approval parser for exec approvals.
- Before normal routing, if a session has a pending approval and the new turn resolves to approval or denial, process it immediately.

**Step 4: Run focused tests**

Run:
```bash
python -m pytest tests/agent/test_exec_approval_flow.py tests/agent/tools/test_shell_firewall_ask_mode.py -q
```

Expected: PASS

### Task 3: Harden Weather Forecast Follow-ups

**Files:**
- Modify: `kabot/agent/loop_core/message_runtime_parts/reference_resolution.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/followup.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/process_flow.py`
- Modify: `kabot/agent/cron_fallback_nlp.py`

**Step 1: Tighten forecast-style follow-up detection**

- Extend short weather follow-up markers to include `prediksi`, `forecast`, `prakiraan`, `3-6 jam`, `per jam`, and similar compact forecast phrasing.

**Step 2: Preserve last clean location**

- When weather follow-up text has no fresh location, preserve the previous clean `location` from `last_tool_context`/`last_tool_execution`.
- Prevent raw forecast nouns like `Prediksi` from being reinterpreted as a new location.

**Step 3: Run focused tests**

Run:
```bash
python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py tests/agent/test_cron_fallback_nlp.py -q
```

Expected: PASS

### Task 4: Suppress Stock Routing For Meta Threads/API Intents

**Files:**
- Modify: `kabot/agent/tools/stock_matching.py`
- Modify: `kabot/agent/loop_core/execution_runtime_parts/intent.py`
- Modify: `kabot/agent/cron_fallback_parts/intent_scoring.py`

**Step 1: Add conflict guards**

- If the query contains strong integration/API/platform markers like `api`, `threads`, `meta threads`, `graph api`, `connect`, `koneksi`, `integration`, suppress stock routing even if `META` is present.

**Step 2: Keep real stock queries intact**

- Ensure `META berapa`, `harga META`, or explicit stock markers still resolve to `stock`.

**Step 3: Run focused tests**

Run:
```bash
python -m pytest tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py tests/agent/tools/test_stock_extractors.py -q
```

Expected: PASS

### Task 5: Verify Broader Runtime Regression Safety

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Run broader regression suite**

Run:
```bash
python -m pytest tests/agent/test_exec_approval_flow.py tests/agent/tools/test_shell_firewall_ask_mode.py tests/agent/test_cron_fallback_nlp.py tests/agent/tools/test_stock_extractors.py tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_basics.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_fast_paths_and_status.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_direct_paths_and_research.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_tool_calls_and_skill_phases.py -q
```

Expected: PASS

**Step 2: Update changelog**

- Add one release note entry describing:
  - approval via normal chat instead of the legacy slash approval command
  - weather forecast follow-up continuity hardening
  - Meta Threads/API routing no longer collides with stock ticker routing
