# Kabot -> reference platform Parity Roadmap (Focused on Reliability)

## Goal
Make Kabot feel as dependable as reference platform for natural chat commands, filesystem actions, skill-first execution, and channel behavior.

## Current Baseline (2026-03-13)
- Focused filesystem/action regression cluster: **262 passed**
- Workspace/bootstrap/template verification: **35 passed**
- Recently verified behavior:
  - `kirim file tes.md -> ya pakai path desktop bot -> buka folder bot -> kirim file tes.md ke sini` now succeeds in a single session
  - repo root no longer grows duplicate `AGENTS.md` / `SOUL.md` / `IDENTITY.md` / `TOOLS.md` / `USER.md` / `BOOTSTRAP.md` when a real `workspace/` already exists
  - external skills can be installed from `path`, `git`, `url`, and catalog sources
  - skill-first finance routing is active, with legacy finance tools pushed down to fallback lanes

## Progress Summary
- Phase 1 - Intent/Routing Hardening: **mostly complete**
- Phase 2 - Filesystem Conversation Reliability: **mostly complete**
- Phase 3 - Skill-First Execution: **in progress**
- Phase 4 - reference platform-Style Safety + UX Consistency: **partially complete**

## Phase 1 - Intent/Routing Hardening
**Target:** stop wrong-tool activations in short follow-ups.

### Completed
- Explicit action intent now beats stale weak parser guesses in key file-delivery turns.
- Help/how-to style demotion exists in multiple routing seams, reducing accidental direct tool execution.
- Indonesian-heavy transcript regressions were added for:
  - `kirim file X`
  - `ya pakai path desktop bot`
  - `buka folder bot`
  - `kirim file tes.md ke sini`
- Follow-up continuity now better preserves committed actions instead of collapsing back to parser lanes.

### Remaining
- Add a single route-debug metadata snapshot for every required-tool decision, not just partial observability across runtime logs.
- Expand transcript pack coverage beyond file workflows into update/status/system-monitoring chat transcripts.

**Success metric:** 0 false stock/file routes on curated transcript pack.

## Phase 2 - Filesystem Conversation Reliability
**Target:** folder navigation and file delivery behave like a human expects.

### Completed
- Dedicated continuity state is now in real use:
  - `last_navigated_path`
  - `last_delivery_path`
  - `last_tool_context`
- Bare filename delivery prefers the active navigated folder.
- Internal temp folders are deprioritized for user-facing delivery.
- Failed `list_dir` / `message` executions no longer poison path state as aggressively.
- Direct delivery verification now reuses valid navigated folder context when stale paths drift.
- Root bootstrap duplication is now blocked when a nested `workspace/` is the real home for persona files.

### Remaining
- Add `last_found_file_candidates` as a dedicated first-class state key rather than relying mostly on path/context fallbacks.
- Add one more fallback search pass in the active navigated folder before returning not-found in all delivery-related seams.
- Add CLI multi-process replay coverage, not only single-session `AgentLoop.process_direct(...)` coverage.

**Success metric:** scripted E2E chat scenarios pass 100% for folder -> send workflow.

## Phase 3 - Skill-First Execution
**Target:** reduce brittle parser dependence and move complex tasks to skill lanes.

### Completed
- External skills can be installed from:
  - local path
  - git repo
  - URL
  - JSON catalog
- Skills now have lifecycle helpers:
  - install
  - list
  - update
  - pack
  - publish
  - sync
- Built-in finance lanes are demoted toward legacy fallback behavior.
- External finance skills can outrank legacy `stock` / `crypto` lanes when eligible.
- Skill-creator flow now better supports:
  - `SKILL.md`
  - `references/`
  - `scripts/`
  - `assets/`

### Remaining
- Continue reducing parser dominance outside finance, especially for ambiguous general/action turns.
- Add broader compatibility shims for public reference-style skills that expect specific capability contracts or external CLI tools.
- Improve direct skill execution so more public skills run end-to-end without environment-specific manual adaptation.
- Make command transparency more explicit in debug output for every skill-vs-parser conflict.

**Success metric:** finance/social/automation intents pick intended skill lane on benchmark prompts.

## Phase 4 - reference platform-Style Safety + UX Consistency
**Target:** predictable behavior across channels.

### Completed
- Telegram command surface is no longer limited to 3 static commands.
- Command surfaces are now shared across:
  - Telegram
  - `/help`
  - dashboard payloads/UI
- Telegram preview behavior is closer to reference platform:
  - preview updates can be materialized
  - stale preview cleanup exists
- Workspace bootstrap/persona files now have stronger influence on context than before.

### Remaining
- Add richer channel-specific confirmation contracts for destructive actions.
- Normalize error wording further across channels:
  - not-found
  - ambiguous path
  - missing credentials
  - skill dependency missing
- Expand deterministic follow-up memory coverage for short turns in more real-world transcripts.
- Expand integration tests across Telegram + CLI agent mode with persistent multi-turn replay, not only unit/integration slices.

**Success metric:** no dead-end loops in chat-based operational flows.

## Always-On Track
- Convert each production bug transcript into regression coverage first.
- Keep changelog entries strict by:
  - symptom
  - root cause
  - fix behavior
- Prefer skill-first or AI-grounded continuity over new parser growth.
- Keep workspace persona/bootstrap files authoritative when a real workspace exists.

## Immediate Next 5 Tasks
1. Add route-decision snapshot metadata for every required-tool decision and expose it in replay/debug paths.
2. Add CLI multi-process transcript replay coverage for the exact `tes.md` flow, not only same-process session replay.
3. Promote `last_found_file_candidates` to dedicated session state and use it in delivery fallback.
4. Expand transcript regression pack to update/status/server-monitoring flows that still feel less natural than reference platform.
5. Continue shrinking parser-heavy fallback seams in non-finance domains without removing safe deterministic evidence checks.
