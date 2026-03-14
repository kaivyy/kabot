# reference platform-Style AI-Driven CLI Parity Roadmap

## Goal
Make `python -m kabot.cli.commands agent -m "..."` feel closer to reference platform:
- follow-up continuity survives across separate one-shot invocations,
- answers stay human and AI-shaped instead of sounding like raw parser output,
- skills remain the preferred execution lane when available,
- and tool evidence stays honest when a real action is required.

## What We Fixed In This Batch
- One-shot CLI default sessions are now workspace-scoped instead of per-command ephemeral.
- Cross-process filesystem continuity now survives:
  - `buka folder desktop`
  - `buka folder bot`
  - `kirim file tes.md ke sini`
  - `buka folder pi-mono`
- Direct filesystem errors now get humanized by the model instead of always surfacing as raw tool strings.

## Remaining Gaps

### 1. AI-Driven One-Shot Follow-Ups
- Keep short follow-ups like `kenapa gabisa kirim` grounded in the previous action result even when run as separate CLI invocations.
- Prefer conversational explanation over asking for the same path again if the folder context is already known.

### 2. Skill-First External Capability Use
- When a matching external skill exists, surface that skill lane before parser/tool fallback.
- Continue reducing domain-specific parser dependence in favor of skill summaries + explicit skill execution notes.

### 3. Browser/Web Behavior Closer To reference platform
- If live web info is needed and `web_search` is unavailable or unsuitable, prefer an AI-guided `browser` / `web_fetch` lane instead of brittle parser escalation.
- Keep the distinction honest:
  - `web_search` for search results,
  - `web_fetch` for known pages,
  - `browser` for interactive/JS-heavy/live pages.

### 4. Humanized Operational Replies
- Expand AI-mediated wording for:
  - send failures,
  - ambiguous path resolution,
  - missing credentials/dependencies,
  - skill setup blockers.
- Keep raw listings/tool evidence for successful operational actions.

### 5. Replay + Regression Coverage
- Add more transcript packs around:
  - `kenapa gabisa kirim`
  - `cek status server`
  - `skill setup then continue`
  - `browser vs web_search fallback`
- Keep validating both:
  - same-session `process_direct(...)`,
  - cross-instance one-shot CLI replay.

## Success Criteria
- One-shot CLI follow-ups behave like a continuous chat unless the user clearly starts a new topic.
- File delivery/path workflows stop drifting into stale temp paths.
- External skills are used naturally before legacy parser-heavy routes.
- Operational errors read like an assistant, not a parser dump.
- Real actions still require real filesystem/tool evidence before Kabot claims success.
