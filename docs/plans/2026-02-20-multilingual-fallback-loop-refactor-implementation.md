# Multilingual Fallback + AgentLoop Runtime Split Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove Indonesian hardcoding from deterministic fallback responses and continue splitting `AgentLoop` internals so `loop.py` becomes a thinner facade without behavior regressions.

**Architecture:** Keep `kabot/agent/loop.py` as the stable public entrypoint. Move message/routing runtime bodies into `kabot/agent/loop_core/` modules and leave wrapper methods in `AgentLoop`. Expand fallback language detection/messages into a compact i18n table with script/keyword heuristics for English, Indonesian, Malay, Thai, and Chinese.

**Tech Stack:** Python 3.12, pytest, asyncio, existing Kabot loop/tool registry.

---

### Task 1: Add Failing Tests for Multilingual Fallback

**Files:**
- Create: `tests/agent/test_fallback_i18n.py`
- Modify: `tests/agent/test_tool_enforcement.py`

**Step 1: Write failing tests**
- Assert `detect_language()` recognizes `en`, `id`, `ms`, `th`, `zh`.
- Assert fallback text for `cron_time_unclear` is localized per input language.
- Assert `_required_tool_for_query()` detects reminder/weather intents for Malay/Thai/Chinese prompts.

**Step 2: Run tests to verify failure**
- Run: `pytest tests/agent/test_fallback_i18n.py tests/agent/test_tool_enforcement.py -q`
- Expected: FAIL due unsupported languages/keywords.

### Task 2: Implement Multilingual Fallback + Keyword Coverage

**Files:**
- Modify: `kabot/agent/fallback_i18n.py`
- Modify: `kabot/agent/cron_fallback_nlp.py`

**Step 1: Implement minimal behavior**
- Add language hint markers and script checks (Thai/CJK).
- Add message tables for `ms`, `th`, `zh` with English fallback.
- Extend reminder/weather/management keywords for `ms/th/zh` so deterministic tool enforcement triggers.

**Step 2: Verify tests pass**
- Run: `pytest tests/agent/test_fallback_i18n.py tests/agent/test_tool_enforcement.py -q`
- Expected: PASS.

### Task 3: Add Failing Tests for Further `loop.py` Delegation

**Files:**
- Modify: `tests/agent/test_loop_facade_compat.py`

**Step 1: Write failing tests**
- Add monkeypatch-based checks that:
  - `_process_message` delegates to `loop_core.message_runtime`.
  - `_process_pending_exec_approval` delegates to `loop_core.message_runtime`.
  - `_process_system_message` delegates to `loop_core.message_runtime`.
  - `process_isolated` delegates to `loop_core.message_runtime`.
  - `_resolve_models_for_message` delegates to `loop_core.routing_runtime`.

**Step 2: Run tests to verify failure**
- Run: `pytest tests/agent/test_loop_facade_compat.py -q`
- Expected: FAIL until new modules/wrappers exist.

### Task 4: Extract Runtime Modules and Keep Facade Behavior

**Files:**
- Create: `kabot/agent/loop_core/message_runtime.py`
- Create: `kabot/agent/loop_core/routing_runtime.py`
- Modify: `kabot/agent/loop_core/__init__.py`
- Modify: `kabot/agent/loop.py`

**Step 1: Move method bodies**
- Move routing/model-chain internals into `routing_runtime.py`.
- Move message processing/approval/system/isolated internals into `message_runtime.py`.
- Keep `AgentLoop` methods as thin wrappers for compatibility.

**Step 2: Verify behavior via tests**
- Run: `pytest tests/agent/test_loop_facade_compat.py tests/agent/test_tool_enforcement.py tests/cli/test_agent_reminder_wait.py -q`
- Expected: PASS.

### Task 5: Full Regression + Changelog

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Run focused regression**
- Run: `pytest tests/agent/test_fallback_i18n.py tests/agent/test_tool_enforcement.py tests/agent/test_loop_facade_compat.py tests/cron/test_service_facade.py tests/providers/test_openai_codex_backend.py tests/cli/test_agent_reminder_wait.py -q`

**Step 2: Update docs**
- Record multilingual i18n coverage and loop split details in `CHANGELOG.md`.

**Constraints**
- Do not change public class/function import paths.
- Keep cron and reminder behavior stable.
- Keep edits localized to loop-core/i18n/keyword surface and tests.
