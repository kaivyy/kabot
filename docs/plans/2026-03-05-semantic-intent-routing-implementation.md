# Semantic Intent Routing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move Kabot routing from lexicon-first toward semantic-first (with deterministic fallback), while preserving existing tools/skills/channel behavior.

**Architecture:** Add a semantic intent router stage in runtime, keep current deterministic scorer as fallback/tie-breaker, and harden skills preflight + web-search/fetch orchestration under existing loop/runtime structure.

**Tech Stack:** Python 3.11, pytest, ruff, Kabot runtime (`message_runtime`, `tool_enforcement`, `cron_fallback_nlp`), i18n catalog.

---

## Phase 1: Semantic Router Foundation

### Task 1.1: Add semantic intent router module

**Files:**
- Create: `kabot/agent/language/semantic_intent.py`
- Test: `tests/agent/language/test_semantic_intent.py`

**Steps:**
1. Define `IntentCandidate`, `SemanticRoutingResult`, and confidence bands.
2. Implement scorer API:
   - `score_intents(text, history, locale, available_tools)`.
3. Add slot extraction hooks for weather/location, market entities, URL/topic.
4. Write tests for multilingual natural prompts + ambiguity cases.

### Task 1.2: Wire semantic stage into required-tool decision

**Files:**
- Modify: `kabot/agent/loop_core/tool_enforcement.py`
- Modify: `kabot/agent/cron_fallback_nlp.py`
- Test: `tests/agent/test_tool_enforcement.py`
- Test: `tests/agent/test_cron_fallback_nlp.py`

**Steps:**
1. Add semantic-first path in required tool resolution facade.
2. Keep deterministic scorer as fallback.
3. Add ambiguity branch: one short clarification message.
4. Add tests for:
   - news prompts not routed to stock,
   - natural weather prompts routed correctly,
   - low-confidence prompts not force-routed.

---

## Phase 2: Web Search/Fetch Intent Orchestration

### Task 2.1: Normalize live-news decision path

**Files:**
- Modify: `kabot/agent/loop_core/message_runtime.py`
- Modify: `kabot/agent/loop_core/execution_runtime.py`
- Test: `tests/agent/loop_core/test_message_runtime.py`
- Test: `tests/agent/loop_core/test_execution_runtime.py`

**Steps:**
1. Route live/recent/news intent to `web_search` when available.
2. Add optional fetch-enrichment helper for top links using `web_fetch`.
3. Preserve queued/thinking/tool/done status sequence.
4. Add regression tests for:
   - `web_search` missing-key fallback guidance,
   - URL-direct requests using `web_fetch`.

### Task 2.2: Keep failure path deterministic and localized

**Files:**
- Modify: `kabot/i18n/catalog.py`
- Test: `tests/tools/test_web_fetch_i18n.py`
- Test: `tests/agent/tools/test_web_search.py`

**Steps:**
1. Add/verify i18n keys for web search unavailability and setup guidance.
2. Ensure no raw hardcoded English fallback leaks in user-facing errors.
3. Validate cross-locale responses for `en`, `id`, `ms` minimum.

---

## Phase 3: Skills Preflight Hardening (API/Binary Skills)

### Task 3.1: Introduce generic preflight gate

**Files:**
- Modify: `kabot/agent/loop.py`
- Modify: `kabot/agent/tools/message.py` (if needed for skill execution metadata)
- Modify: `kabot/agent/tools/knowledge.py` (if preflight helpers shared there)
- Test: `tests/agent/test_skills_loader_precedence.py`
- Test: `tests/agent/test_skills_matching.py`
- Test: `tests/cli/test_skills_commands.py`

**Steps:**
1. Add preflight contract:
   - required env vars,
   - binary existence,
   - timeout defaults.
2. Fail-fast with actionable localized setup message.
3. Keep successful path unchanged.
4. Add tests using representative API skills (Nano Banana/TTS style requirements).

### Task 3.2: Error normalization for skill runtime failures

**Files:**
- Modify: `kabot/agent/loop_core/execution_runtime.py`
- Modify: `kabot/i18n/catalog.py`
- Test: `tests/tools/test_tool_i18n_errors.py`

**Steps:**
1. Normalize provider/network/timeout exceptions.
2. Return concise localized user message with next action.
3. Keep internal diagnostics in logs only.

---

## Phase 4: Channel Responsiveness Guard

### Task 4.1: Verify phase parity and typing keepalive not regressed

**Files:**
- Modify (only if needed): `kabot/channels/telegram.py`, `kabot/channels/discord.py`, `kabot/channels/slack.py`
- Test: `tests/channels/test_telegram_typing_status.py`
- Test: `tests/channels/test_discord_typing_status.py`
- Test: `tests/channels/test_status_updates_cross_channel.py`

**Steps:**
1. Ensure semantic routing path still emits same status lifecycle.
2. Ensure no duplicate or stuck status bubble.
3. Ensure keepalive cadence remains consistent.

---

## Phase 5: Observability + Safety Rollout

### Task 5.1: Add shadow-mode and telemetry comparison

**Files:**
- Modify: `kabot/agent/loop_core/message_runtime.py`
- Modify: `kabot/agent/loop_core/execution_runtime.py`
- Test: `tests/agent/loop_core/test_message_runtime.py`

**Steps:**
1. Add shadow logs comparing semantic and deterministic decision.
2. Add feature flag to enable semantic-first per tool class.
3. Keep rollback switch for rapid disable.

### Task 5.2: Documentation and operator guidance

**Files:**
- Modify: `README.md`
- Modify: `HOW_TO_USE.MD`
- Modify: `CHANGELOG.md`
- Add: `docs/logs/2026-03-05-semantic-intent-routing-verification.md`

**Steps:**
1. Document semantic routing behavior and fallback model.
2. Document web_search/web_fetch behavior when key is missing.
3. Document skill preflight expectations.

---

## Verification Checklist (Execution Gate)

Run in this order and capture output in verification log:

1. `ruff check kabot tests`
2. `pytest -q tests/agent/tests_placeholder  # replace with concrete targeted suites`
3. `pytest -q tests/agent tests/channels tests/tools tests/gateway`

Minimum required targeted suites:
- `tests/agent/test_cron_fallback_nlp.py`
- `tests/agent/test_tool_enforcement.py`
- `tests/agent/loop_core/test_message_runtime.py`
- `tests/agent/loop_core/test_execution_runtime.py`
- `tests/channels/test_status_updates_cross_channel.py`
- `tests/tools/test_web_fetch_i18n.py`
- `tests/agent/tools/test_web_search.py`

---

## Commit Strategy

1. `feat(routing): add semantic intent scoring stage and fallback integration`
2. `feat(runtime): add web_search/web_fetch semantic orchestration with fallback guidance`
3. `feat(skills): add generic preflight gate for API/binary requirements`
4. `test(regression): add multilingual intent and channel lifecycle coverage`
5. `docs: add semantic routing design/plan and verification log`

---

## Done Criteria

1. Natural multilingual prompts route to correct tool without rigid formatting.
2. `web_search`/`web_fetch` behavior is deterministic and understandable when keys are missing.
3. API-based skills fail-fast with actionable setup message.
4. No regressions in channel typing/status lifecycle.
5. `ruff` + selected `pytest` suites pass and are logged.
