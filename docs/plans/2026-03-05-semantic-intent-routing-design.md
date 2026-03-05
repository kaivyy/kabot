# Semantic Intent Routing Design (Kabot)

## Context

Kabot already has strong deterministic routing and multilingual fallback logic, but practical chat logs show remaining rigidity on natural prompts (for example, geopolitical/news queries misrouting into finance, and natural weather phrasing requiring strict formatting). The main issue is ordering: keyword/lexicon routing still dominates in some paths before semantic context resolution.

This design keeps the existing Kabot architecture and tool surface intact. We do not remove current tools, skills, or channel lifecycle behavior. Instead, we shift decision priority to semantic intent + conversational context first, then use existing lexicon/deterministic routing as confidence fallback.

## Goals

1. Make tool selection more human-like for natural multilingual prompts.
2. Preserve deterministic safety for high-risk actions and ambiguous intent.
3. Keep all existing tools and skills backward-compatible.
4. Keep channel responsiveness (queued/thinking/tool/done/error + typing keepalive) unchanged or better.
5. Avoid hallucinated tool execution when capability/config is missing.

## Non-Goals

1. Replacing all current routing with a fully black-box LLM router.
2. Breaking existing deterministic command paths.
3. Introducing tool behavior changes that require user-side migration.

## Proposed Routing Order

1. Explicit command/directive and hard safety/abort checks.
2. Semantic intent scorer (context-aware, multilingual, slot-aware).
3. Existing deterministic scorer (`required_tool_for_query`) as fallback/tie-breaker.
4. Clarification prompt only when confidence gap is below threshold.

## Core Design

### A. Semantic Intent Layer

Add a dedicated semantic router module that outputs:
- top intent candidates,
- confidence,
- extracted slots (location, symbols, entities, time window),
- ambiguity reason.

Decision rule:
- confidence high: route directly.
- confidence medium + deterministic agreement: route.
- confidence medium + disagreement: ask one short clarification.
- confidence low: continue as chat/no forced tool.

### B. Slot Extraction Before Tool Call

For candidate tools, run lightweight slot extraction:
- `weather`: robust location extraction from natural sentence patterns.
- `stock/crypto`: entity and symbol extraction with novice alias support.
- `web_search`: normalize topic query from context.
- `web_fetch`: trigger only when URL exists.

If required slot is missing, return a concise localized follow-up question (not generic failure).

### C. Web Search + Fetch Orchestration

For live-news queries:
1. Route to `web_search` to discover sources.
2. Optionally call `web_fetch` on top N links (default 1-3) for summary grounding.
3. If `web_search` unavailable, return explicit setup guidance + fallback behavior:
   - use `web_fetch` when URL is supplied,
   - or state non-live mode clearly.

### D. Skills Runtime Contract (API-based Skills)

Keep current skills behavior, add mandatory preflight stage:
- skill enabled check,
- required env key check,
- required binaries/dependencies check,
- timeout/network guard.

On preflight failure: fail-fast localized setup message.  
On runtime failure: normalized localized error + retry policy + optional fallback skill.

### E. Channel Responsiveness Parity

Preserve existing lifecycle semantics:
- status phases: `queued -> thinking -> tool -> done|error`,
- typing keepalive for capable channels,
- mutable status lane where supported.

Semantic routing must not bypass status emission.

## Data/Config Additions

1. `intent_router` config block:
- thresholds (`high`, `medium`, `ambiguity_delta`),
- semantic on/off kill-switch,
- per-tool weights.

2. `skill_preflight` config block:
- strict mode toggle,
- timeout defaults,
- localized error policy.

3. Optional alias extension files remain external-config first (not hardcoded growth in code).

## Migration & Rollout

### Phase 0 (Safe Intro)
- Add semantic router in shadow mode (log-only decisions, no behavior change).
- Compare semantic vs deterministic route in observability logs.

### Phase 1 (Controlled Activation)
- Enable semantic-first for low-risk tool classes (`weather`, `web_search`, `web_fetch`).
- Keep deterministic fallback active.

### Phase 2 (Broader Coverage)
- Extend to `stock/crypto` with ambiguity clarification guard.
- Keep strict no-hallucination and explicit slot requirements.

### Phase 3 (Skills Preflight Hardening)
- Enforce preflight for API-based skills globally.

### Phase 4 (Tuning)
- Use real chat regressions to tune thresholds and slot extraction.

## Testing Strategy

1. Unit tests:
- semantic intent scoring,
- ambiguity branch behavior,
- slot extraction outputs.

2. Integration tests:
- message runtime routing decisions across multilingual samples,
- tool enforcement interplay,
- status lifecycle unaffected.

3. Regression tests:
- known failures from production logs (news->stock, natural weather phrasing, short follow-up continuity).

## Success Criteria

1. Significant reduction in misrouted natural prompts.
2. No regression in deterministic safety and stop/abort behavior.
3. Skills with missing API keys fail-fast with actionable localized message.
4. Channel interactivity remains consistent across supported channels.
