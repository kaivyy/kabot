# Weather Skill-First Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make weather and forecast turns route through a skill-first continuity lane so follow-ups stay grounded to the last real location/context instead of drifting into generic tool or parser guesses.

**Architecture:** Keep Kabot's existing weather tool as the execution primitive, but add a higher-level runtime lane that explicitly injects the `weather` skill and suppresses conflicting direct-tool heuristics when the turn is clearly weather-oriented or a weather follow-up. Reuse existing pending follow-up state and last tool context so the new behavior stays compatible with current continuity and observability metadata.

**Tech Stack:** Python, pytest, existing Kabot message runtime, context builder, skills loader, weather tool.

---

### Task 1: Lock the desired behavior with failing tests

**Files:**
- Modify: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_fast_paths_and_status.py`
- Modify: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py`

**Step 1: Write failing tests**

Add tests that assert:
- a weather prompt automatically injects the `weather` skill into context
- weather follow-up prompts like forecast continuation preserve `forced_skill_names=["weather"]`
- conflicting direct-tool inference is suppressed when the turn is already committed to the weather skill lane

**Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_fast_paths_and_status.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py -q
```

Expected: FAIL on the new skill-first weather assertions.

### Task 2: Implement the minimal runtime lane

**Files:**
- Modify: `kabot/agent/loop_core/message_runtime_parts/process_flow.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/helpers.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/turn_metadata.py`

**Step 1: Add a small helper**

Create a helper that decides whether a turn belongs to the weather skill lane by using:
- explicit weather intent from current text
- existing weather follow-up state
- recent last-tool/pending-follow-up context

**Step 2: Wire the lane into process_flow**

When the helper says the turn is weather-skill-first:
- set `forced_skill_names=["weather"]`
- suppress conflicting required-tool inference metadata
- preserve continuity source grounded in weather context

**Step 3: Keep the fix minimal**

Do not replace the weather tool. The skill lane only steers prompt/context and follow-up discipline; tool execution remains the same.

### Task 3: Verify regressions and document the change

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Run focused tests**

```powershell
python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_fast_paths_and_status.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py tests/agent/test_cron_fallback_nlp.py tests/tools/test_weather_tool.py -q
```

**Step 2: Run a broader regression slice**

```powershell
python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_basics.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_memory_durability.py tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py tests/agent/test_cron_fallback_nlp.py tests/tools/test_weather_tool.py -q
```

**Step 3: Update changelog**

Add a concise entry describing the new weather skill-first continuity lane and why it reduces hallucinated location/tool fallbacks.
