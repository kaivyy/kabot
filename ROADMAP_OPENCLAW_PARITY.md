# Kabot → OpenClaw Parity Roadmap (Focused on Reliability)

## Goal
Make Kabot feel as dependable as OpenClaw for natural chat commands, filesystem actions, and tool routing.

## Current Baseline (today)
- Core regression bundle: **189 passed**
- Recent fixes landed:
  - stale stock-routing continuity guard
  - `kirim file ...` bare filename delivery routing
  - directory context fallback for `read_file`
  - stale helper prompt/path filtering
  - navigated-folder priority over stale temp paths (`.basetemp`)

## Phase 1 — Intent/Routing Hardening (Week 1)
**Target:** stop wrong-tool activations in short follow-ups.

1. Add precedence ladder for action intents:
   - explicit action (kirim/buka/baca) > stale context > parser hint
2. Add explicit "help/how-to" demotion:
   - "cara ...", "how to ..." should not trigger direct execution tools.
3. Add transcript-based regression cases (Indonesian-heavy):
   - `kirim file X`
   - `ya pakai path desktop bot`
   - `buka folder bot`
   - `kirim file tes.md ke sini`
4. Add route-debug metadata snapshot for every required-tool decision.

**Success metric:** 0 false stock/file routes on curated transcript pack.

## Phase 2 — Filesystem Conversation Reliability (Week 2)
**Target:** folder navigation and file delivery behave like a human expects.

1. Keep dedicated state keys:
   - `last_navigated_path`
   - `last_found_file_candidates`
   - `last_delivered_path`
2. Prefer navigated folder for bare filename delivery.
3. Add fallback search in active navigated dir before returning not-found.
4. Add guard: internal temp folders (`.basetemp`, `.tmp-*`) are low-priority for user file delivery unless explicitly asked.

**Success metric:** scripted E2E chat scenarios pass 100% for folder→send workflow.

## Phase 3 — Skill-First Execution (Week 3)
**Target:** reduce brittle parser dependence and move complex tasks to skill lanes.

1. Promote skill dispatch before legacy parser lanes for supported domains.
2. Keep built-in tools as fallback only.
3. Add command transparency mode:
   - show selected lane + why in debug logs.
4. Add conflict resolver when parser and skill disagree.

**Success metric:** finance/social/automation intents pick intended skill lane on benchmark prompts.

## Phase 4 — OpenClaw-Style Safety + UX Consistency (Week 4)
**Target:** predictable behavior across channels.

1. Add channel-specific confirmation contracts for destructive actions.
2. Normalize response templates for errors:
   - not-found, ambiguous path, missing credentials.
3. Add deterministic follow-up memory for short turns (`ya`, `lanjut`, `yang tadi`).
4. Expand integration tests across Telegram + CLI agent mode (`python -m agent ...`).

**Success metric:** no dead-end loops in chat-based operational flows.

## Always-On Track (continuous)
- Weekly bug triage from real chat transcripts.
- Convert every production bug into regression tests first.
- Keep changelog strict by symptom + root cause + fix note.

## Immediate next 5 tasks (starting now)
1. Build transcript replay test for your exact `tes.md` flow in agent CLI mode.
2. Add low-priority ranking for internal temp directories in message delivery resolution.
3. Add route-decision trace logging (single-line JSON) for failed delivery cases.
4. Add assertion that `required_tool=message` for `kirim file <filename>` (without explicit path).
5. Add CI job that runs transcript regression pack on every PR.
