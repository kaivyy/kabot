# OpenFang vs Kabot Gap Matrix Implementation Plan

> For Claude: REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

Goal: Close the highest-impact product and architecture gaps between Kabot and OpenFang while preserving Kabot's current user workflows.

Architecture: Use a layered parity strategy. First stabilize canonical config contracts and runtime model-routing correctness. Then harden skills/runtime execution contracts. Finally improve wizard UX and multi-bot automation surfaces with strict regression gates.

Tech Stack: Python 3.11+, Pydantic v2, Typer, Questionary/Rich, Litellm, pytest.

---

## Scope and Method

1. Scope compared
- Runtime architecture, fallback model behavior, channel routing, skills system, config shape, memory, and security boundaries.

2. Evidence baseline
- OpenFang source: `crates/openfang-types`, `openfang-runtime`, `openfang-skills`, `openfang-channels`, `openfang-memory`.
- Kabot source: `kabot/config`, `kabot/agent`, `kabot/cli/wizard`, `kabot/routing`, `kabot/security`, `kabot/memory`.
- OpenClaw used as compatibility reference for wizard and skills contract behavior.

3. Priority model
- P0: Causes wrong behavior, outages, duplicated actions, or broken trust.
- P1: Strong UX/product friction and maintainability risk.
- P2: Quality/performance parity improvements.

4. Effort model
- S: 0.5-1 day
- M: 2-4 days
- L: 1-2 weeks

---

## Executive Summary

1. Kabot is strong on practical multi-provider support and configurable routing, but has critical runtime correctness risks in tool-call/fallback loops and configuration contract drift in `skills`.
2. OpenFang is stronger in typed contracts and runtime determinism for provider/fallback architecture.
3. OpenClaw is stronger in wizard consistency and end-to-end onboarding polish.
4. Fastest path for Kabot is:
- P0: fallback/runtime correctness + idempotent cron/tool execution
- P1: canonical typed `skills` contract in schema + wizard/runtime contract unification
- P1: channel instance workflow hardening (edit/delete/switch without re-entering secrets)

---

## Detailed Gap Matrix (Root-Cause Level)

| ID | Domain | Current Kabot | Target (OpenFang/OpenClaw parity) | Root Cause | Impact | Priority | Effort | Risk | Action | Acceptance Criteria | File Focus |
|---|---|---|---|---|---|---|---|---|---|---|---|
| G01 | Runtime fallback correctness | Model fallback exists but can still loop or duplicate tool outcomes when tool call context desync occurs | Deterministic fallback chain with tool-call state integrity | Tool result attachment and retry path still allow repeated tool output attempts across failures | Duplicate user messages, repeated cron scheduling | P0 | M | High | Add strict idempotency key per tool-call execution + retry guard | Same request never emits duplicate `cron.add`; no repeated "Scheduling task" bursts in logs | `kabot/agent/loop_core/execution_runtime.py`, `kabot/agent/loop.py`, cron execution modules |
| G02 | Auth + fallback semantics | Auth rotation and model fallback logic mixed in one path | Explicit two-stage semantics: rotate auth first, then model fallback | Error taxonomy and state transitions are partially implicit | Unexpected provider behavior under 401/429 storms | P0 | M | High | Split fallback pipeline into explicit finite-state decision function | Unit tests for 401, 429, timeout, tool-400, and exhausted chain all deterministic | `kabot/agent/loop_core/execution_runtime.py`, tests in `tests/core` |
| G03 | Tool-call protocol robustness | Codex tool-call can fail with "No tool call found ..." in bad sequences | Always maintain coherent assistant->tool->assistant chain | Message context mutation during retries can invalidate tool-call linkage | Hard failures, long latency, user confusion | P0 | M | High | Normalize tool-call envelope storage and enforce append-once semantics | Failing reproduction no longer triggers 400 tool-call mismatch | `kabot/agent/context.py`, `kabot/agent/loop_core/execution_runtime.py` |
| G04 | Skills config contract | Root schema uses `skills: dict[str, Any]`; normalization happens in helper | First-class typed schema contract for canonical skills keys | Schema and runtime/wizard contract are not aligned at type layer | Migration drift, silent config ambiguity | P1 | M | Medium | Introduce `SkillsConfig` Pydantic model and preserve legacy migration adapter | Config load/save roundtrip stable for legacy + canonical forms | `kabot/config/schema.py`, `kabot/config/skills_settings.py`, `kabot/config/loader.py` |
| G05 | Skills precedence predictability | Effective precedence differs by implementation style (first-seen strategy by scanning order) | Explicit, documented, test-locked precedence contract | Precedence logic implicit in scan order and de-dup behavior | Surprise overrides when skill names collide | P1 | S | Medium | Make precedence resolver explicit and unit-tested by source layer | Collision tests pass for all layers with deterministic winner | `kabot/agent/skills.py`, `tests/agent/test_skills_loader_precedence.py` |
| G06 | Skills install flow | Manual plan mode is good, but actionable command context can still be incomplete per OS | Complete install plan matrix per skill and platform | Installer metadata normalization does not always produce complete user-ready steps | Setup friction and support load | P1 | S | Low | Expand normalized installer hints and render per-OS command blocks | Each selected skill outputs at least one executable install command or explicit docs fallback | `kabot/agent/skills.py`, `kabot/cli/wizard/sections/tools_gateway_skills.py` |
| G07 | External skill onboarding | Git install exists (clone/discover/validate/copy) but no full "one-step configure+env+persona" flow | OpenClaw-like turnkey onboarding for third-party skill repos | Installer currently stops at copy+validate | More manual steps than expected for non-technical users | P1 | M | Medium | Add post-install assistant flow: suggest env keys, optional SOUL injection template, enable flag | Installing a repo skill can finish in one wizard flow without manual file edits | `kabot/cli/skill_repo_installer.py`, wizard skills section, docs |
| G08 | Channel instance lifecycle | Multi-instance exists but edit/delete/return flows are still inconsistent in UX | Stable CRUD lifecycle with clear back behavior and no secret re-entry burden | Menu flow coupling and repeated prompts | User fatigue, setup errors | P1 | M | Medium | Separate create/edit/delete handlers, prefill on edit, masked secret persistence | Edit keeps token unless changed; delete reflects immediately; no loop prompts | `kabot/cli/wizard/channel_menu.py`, `kabot/cli/wizard/setup_sections.py` |
| G09 | Channel -> Agent binding UX | Binding exists but discoverability and default-model safety not strict enough | Only credential-ready models selectable for default routes | Model list not always filtered by usable credentials | Misconfigured bot routes to unavailable provider | P1 | S | Medium | Filter selectable models by resolved credential status, include warnings | Default model picker only shows credential-ready options unless explicit override | `kabot/cli/wizard/sections/model_auth.py`, provider helpers |
| G10 | Provider/profile source of truth | Provider profiles + active profile exist but some flows still mix legacy key paths | Unified profile resolution for all providers | Partial dual-path legacy handling | Intermittent mismatch in selected credentials | P1 | M | Medium | Consolidate provider credential accessor APIs and deprecate legacy write paths | All wizard login methods update one canonical profile path | `kabot/config/schema.py`, provider auth handlers, wizard model_auth |
| G11 | OpenRouter model handling | Manual model parsing can reject valid IDs with suffixes/variants | Accept provider-valid IDs and scope checks accurately | Overly strict parser assumptions | Blocks real model usage | P0 | S | High | Relax parser to allow valid model tokens while preserving provider guardrails | Known valid OpenRouter model IDs are accepted and saved | model parser/validator in wizard model selection path |
| G12 | WhatsApp bridge lifecycle | EADDRINUSE and blocking foreground behavior can trap setup flow | Managed process lifecycle with port conflict handling and return-to-menu | Bridge process orchestration and status detection not robust | Setup stalls, no QR, no background continuity | P0 | M | High | Add bridge supervisor: preflight port check, reuse running instance, non-blocking attach mode | Wizard can start/attach/stop bridge reliably and return to menu every time | bridge launcher code, channel wizard handlers |
| G13 | Config migration transparency | Migration exists, but user-facing traceability can be improved | Explicit migration summary and backup path reporting | Migration events not always surfaced in UX | Hard to trust changes for advanced users | P2 | S | Low | Print concise migration report when canonicalization occurs | User sees what changed and where backup stored | `kabot/config/loader.py`, wizard startup logs |
| G14 | Memory startup latency | Embedding subprocess startup can feel slow under cold start | Clear warm/cold memory path and lazy strategy communication | Runtime warmup and user feedback are disconnected | Perceived slowness and confusion | P2 | S | Low | Add startup status hints and optional deferred memory warmup mode | Startup UX reports memory readiness clearly; no confusion over first-query delay | `kabot/memory/*`, startup logs |
| G15 | Security policy parity | Command firewall is strong, but wizard policy control is still advanced-user heavy | Guided policy presets with safe defaults | Policy power exposed without guided presets | Misconfiguration risk | P2 | M | Low | Add wizard presets (strict/ask/dev) mapped to firewall config | Users can apply safe policy in 1 step | `kabot/security/command_firewall.py`, wizard tools/sandbox section |
| G16 | Test surface for wizard regressions | Many wizard issues regress (back/menu/color/input loops) | Snapshot-like behavioral tests for wizard critical paths | UI state machine complexity + low scenario coverage | Recurring UX regressions | P0 | M | Medium | Add golden-flow tests for setup mode, channels, model auth, skills menu | Reproduced regressions become fixed tests | `tests/cli/*setup_wizard*`, wizard modules |
| G17 | Docs operational clarity | How-to exists but advanced flows are spread across docs/threads | Single operator handbook per capability | Docs grew feature-first, not operation-first | Users miss correct flow and file locations | P1 | S | Low | Add operator playbooks: model fallback, multi-bot routing, external skills install | New users can complete major flows without chat assistance | `HOW_TO_USE.MD`, `README.md` |
| G18 | Versioned rollout discipline | Large feature merges happened with mixed stabilization | Stage-gated release checklist per version | Feature velocity ahead of release gates | Higher chance of late regressions | P1 | S | Medium | Add release gate checklist into changelog/release process | 0.5.x releases include explicit pass/fail criteria | `CHANGELOG.md`, release docs |

---

## Prioritized Execution Waves

### Wave 1 (P0 Stabilization, 4-6 days)
1. Fix fallback idempotency and tool-call chain integrity (G01, G03).
2. Split auth-rotation vs model-fallback decision pipeline (G02).
3. Fix OpenRouter model parser acceptance for real IDs (G11).
4. Harden WhatsApp bridge lifecycle and non-blocking wizard return flow (G12).
5. Add regression tests for all above (G16 partial).

Deliverable: No duplicate cron scheduling, stable fallback behavior, valid OpenRouter IDs accepted, WhatsApp wizard no longer blocks.

### Wave 2 (P1 Contract and UX Hardening, 1-2 weeks)
1. Introduce typed `SkillsConfig` in schema and keep migration adapter (G04).
2. Lock explicit skills precedence with tests (G05).
3. Improve install-plan output completeness and skill repo post-install assistant flow (G06, G07).
4. Refactor channel instance CRUD and model credential filtering (G08, G09, G10).
5. Expand wizard regression coverage (G16 full).

Deliverable: Stable typed contracts, predictable skills behavior, simpler channel/model setup.

### Wave 3 (P2 Quality and Operations, 3-5 days)
1. Memory startup UX and deferred warmup option (G14).
2. Security policy presets in wizard (G15).
3. Consolidated operator docs and release-gate checklist (G17, G18).

Deliverable: Better operator experience and safer release cadence.

---

## Task-Level Plan (Bite-Sized, Execution-Ready)

### Task 1: Stabilize fallback and tool-call chain (G01-G03)

Files:
- Modify: `kabot/agent/loop_core/execution_runtime.py`
- Modify: `kabot/agent/context.py`
- Test: `tests/core/test_failover_error.py`
- Create: `tests/core/test_tool_call_chain_integrity.py`

Steps:
1. Add failing tests for duplicate tool execution and tool-call mismatch flow.
2. Run targeted tests and confirm failures.
3. Implement idempotency key and append-once tool-call guard.
4. Re-run tests until passing.
5. Commit.

### Task 2: OpenRouter parser and model selection safety (G09, G11)

Files:
- Modify: `kabot/cli/wizard/sections/model_auth.py`
- Modify: model-id validator used by wizard
- Test: `tests/cli/test_setup_wizard_model_auth.py`

Steps:
1. Add failing tests for valid OpenRouter IDs containing provider-style suffixes.
2. Add failing tests that non-credential providers are blocked in default picker.
3. Implement parser relaxation + credential-ready filtering.
4. Re-run tests.
5. Commit.

### Task 3: WhatsApp bridge lifecycle resilience (G12)

Files:
- Modify: WhatsApp bridge launcher/orchestrator in wizard/channel runtime
- Test: `tests/channels/test_whatsapp_bridge_lifecycle.py`

Steps:
1. Add failing tests for EADDRINUSE reuse flow and non-blocking return-to-menu.
2. Implement preflight port probe and attach-to-running behavior.
3. Ensure start action can run detached with status polling.
4. Re-run tests.
5. Commit.

### Task 4: Typed skills config contract in schema (G04-G05)

Files:
- Modify: `kabot/config/schema.py`
- Modify: `kabot/config/skills_settings.py`
- Modify: `kabot/config/loader.py`
- Test: `tests/config/test_skills_settings.py`
- Test: `tests/config/test_loader_meta_migration.py`

Steps:
1. Add failing tests for typed schema roundtrip and legacy migration compatibility.
2. Implement `SkillsConfig` typed model with canonical keys.
3. Keep legacy key ingestion and backup migration path intact.
4. Re-run tests.
5. Commit.

### Task 5: Skills install/repo UX parity improvements (G06-G07)

Files:
- Modify: `kabot/agent/skills.py`
- Modify: `kabot/cli/skill_repo_installer.py`
- Modify: `kabot/cli/wizard/sections/tools_gateway_skills.py`
- Test: `tests/cli/test_setup_wizard_skills.py`

Steps:
1. Add failing tests for per-OS install-plan completeness.
2. Add failing tests for post-install env suggestion flow.
3. Implement command-plan enrichment and guided post-install setup.
4. Re-run tests.
5. Commit.

### Task 6: Channel instance CRUD and wizard flow hardening (G08)

Files:
- Modify: `kabot/cli/wizard/channel_menu.py`
- Modify: `kabot/cli/wizard/setup_sections.py`
- Test: `tests/cli/test_setup_wizard_channels.py`

Steps:
1. Add failing tests for edit/delete and back navigation persistence.
2. Refactor menu handlers into explicit create/edit/delete actions.
3. Preserve existing secret values unless changed.
4. Re-run tests.
5. Commit.

### Task 7: Documentation and release gates (G17-G18)

Files:
- Modify: `HOW_TO_USE.MD`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

Steps:
1. Document operator playbooks for model failover, multi-bot routing, and external skill install.
2. Add release gate checklist section in changelog template.
3. Validate links and command examples.
4. Commit.

---

## Verification Matrix

1. Unit and integration tests
- `pytest tests/core/test_failover_error.py -v`
- `pytest tests/core/test_tool_call_chain_integrity.py -v`
- `pytest tests/cli/test_setup_wizard_model_auth.py -v`
- `pytest tests/cli/test_setup_wizard_channels.py -v`
- `pytest tests/cli/test_setup_wizard_skills.py -v`
- `pytest tests/config/test_skills_settings.py -v`
- `pytest tests/config/test_loader_meta_migration.py -v`

2. End-to-end smoke
- `kabot config` (Model/Auth, Channels, Skills, Back flows)
- `kabot gateway` with two providers configured and fallback chain set
- Chat scenario: force primary auth failure then verify fallback response once (no duplicates)
- WhatsApp bridge scenario: running instance + re-open config flow returns to menu

3. Log assertions
- No repeated `Cron: added job` for one natural-language reminder intent.
- No repeated "tool enforcement fallback executed" loops for same iteration.
- No `No tool call found for function call output` after fix scenarios.

---

## Release Readiness Gate for 0.5.7+

1. Mandatory P0 pass
- G01, G02, G03, G11, G12, G16 (related tests) must pass.

2. Recommended P1 pass before minor release
- G04, G05, G08, G09, G10.

3. Deferred but tracked
- G14, G15, G17, G18 can ship in patch or next minor if risk accepted.

---

## Notes on Strategic Positioning

1. If Kabot wants "operator-first" positioning, prioritize deterministic runtime behavior over adding new providers/channels.
2. If Kabot wants "setup-wizard-first" positioning, prioritize channel CRUD and model credential-safe selection to reduce support load.
3. If Kabot wants "skills ecosystem" positioning, prioritize post-install automation flow and typed skills contracts for plugin reliability.
