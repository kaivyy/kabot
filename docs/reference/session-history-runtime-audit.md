# reference platform vs Kabot Session, History, and Runtime Architecture

This audit compares how reference platform and Kabot handle:

- session identity,
- conversation history,
- delivery routing,
- runtime working-directory state,
- transcript persistence,
- tool/runtime carry-over,
- and follow-up continuity.

It is based on direct inspection of:

- `reference-repo/src/auto-reply/reply/*`
- `reference-repo/src/acp/*`
- `reference-repo/src/config/sessions/*`
- `STRUKTOR OPEN.txt`
- Kabot files under `kabot/session/`, `kabot/agent/loop_core/`, and related tool-enforcement helpers

This is not a claim that both systems already behave the same way.

The goal is to pin down:

1. what reference platform actually does,
2. which parts Kabot should imitate more closely,
3. and which Kabot-specific strengths should stay.

## Short Verdict

reference platform has the cleaner session/runtime architecture.

Kabot has the more direct and memory-native chat state integration.

reference platform is stronger at:

- session-key normalization,
- delivery-route persistence,
- transcript orchestration,
- ACP runtime state,
- working-directory semantics,
- and keeping orchestration, session persistence, and runtime execution separated.

Kabot is stronger at:

- making session state immediately usable inside live assistant turns,
- wiring chat history directly into memory backends,
- and exposing continuity/debug metadata at runtime.

The right parity target is:

- make Kabot's session/history/runtime architecture more reference-like,
- without giving up Kabot's stronger memory integration and route observability.

## reference platform: The Real Shape

## 1. `get-reply.ts` Is the Entry Shell, Not the Whole Brain

Primary file:

- `reference-repo/src/auto-reply/reply/get-reply.ts`

This file does not try to "understand everything" itself.

It orchestrates:

- config loading,
- workspace/bootstrap readiness,
- inbound/media normalization,
- session initialization,
- command/directive handling,
- typing/update emissions,
- then hands the prepared turn into the agent runtime.

This matters because reference platform feels coherent due to layers, not because one giant parser guesses everything from chat text.

## 2. `history.ts` Is a Real History Layer

Primary file:

- `reference-repo/src/auto-reply/reply/history.ts`

reference platform keeps a bounded history map keyed by conversation identity and formats explicit context blocks such as:

- prior messages,
- current message markers,
- bounded accumulation,
- and history formatting separate from transport.

That means continuity is a real subsystem, not an accidental side-effect of transcript files.

## 3. `session.ts` Turns an Inbound Message into a Stable Runtime Identity

Primary file:

- `reference-repo/src/auto-reply/reply/session.ts`

This is one of the most important files in the whole stack.

It handles:

- explicit and implicit session-key resolution,
- group/direct/thread scope,
- daily/thread reset policy,
- session-store loading,
- parent-session forking,
- delivery-route carry-over,
- session transcript file selection,
- and ACP-aware reset/session interactions.

This is the point where reference platform converts an incoming turn into a durable session identity with proper routing state.

## 4. `session-delivery.ts` Keeps Route Logic Out of the Main Session Blob

Primary file:

- `reference-repo/src/auto-reply/reply/session-delivery.ts`

This layer:

- resolves channel hints from session keys,
- distinguishes internal vs external routing surfaces,
- preserves real delivery destinations when a turn originates from internal/web surfaces,
- and retires legacy main-session delivery routes when a direct-session route has taken over.

This is a good example of the reference platform's style: route continuity is its own subsystem, not just a side effect of message history.

## 5. `session-updates.ts` Persists More than Raw Transcript State

Primary file:

- `reference-repo/src/auto-reply/reply/session-updates.ts`

This layer persists:

- `skillsSnapshot`,
- system-event drains,
- compaction counters,
- maintenance notes,
- and first-turn session envelope updates.

So an reference platform session is not just "conversation text on disk". It becomes a small durable runtime envelope.

## 6. `session-usage.ts` and `agent-runner-memory.ts` Tie Prompt/Compaction Accounting Back into the Session

Relevant files:

- `reference-repo/src/auto-reply/reply/session-usage.ts`
- `reference-repo/src/auto-reply/reply/agent-runner-memory.ts`

These layers keep:

- response usage,
- prompt/system-prompt accounting,
- transcript token estimates,
- compaction thresholds,
- and memory flush decisions

attached to the same session lifecycle.

This is part of why reference platform sessions feel like runtime objects, not merely chat transcripts.

## 7. Session Schema Is Structured, Not Ad-Hoc

Primary file:

- `reference-repo/src/config/sessions/types.ts`

Important fields include:

- `deliveryContext`
- `lastChannel`
- `lastTo`
- `lastAccountId`
- `lastThreadId`
- `origin`
- `skillsSnapshot`
- `systemPromptReport`
- `sessionKey`
- `acp`
- `acp.runtimeOptions`
- `acp.cwd`

This is much more structured than "stash some metadata in a dict and hope follow-ups work".

## 8. `store.ts` Treats Session Persistence Like Infrastructure

Primary file:

- `reference-repo/src/config/sessions/store.ts`

Important behavior:

- normalized session keys,
- delivery-field normalization,
- TTL-backed caching,
- object-cache invalidation,
- migration handling,
- file-stat-aware reads,
- multi-process-safe writes,
- maintenance hooks,
- and disk-budget enforcement.

This is one of the reference platform's biggest structural advantages over Kabot today.

## 9. `metadata.ts`, `delivery-info.ts`, and `explicit-session-key-normalization.ts` Split Session Concerns Cleanly

Relevant files:

- `reference-repo/src/config/sessions/metadata.ts`
- `reference-repo/src/config/sessions/delivery-info.ts`
- `reference-repo/src/config/sessions/explicit-session-key-normalization.ts`

These layers split the work cleanly:

- `metadata.ts` derives origin/group/session patches,
- `delivery-info.ts` extracts route context and thread info from persisted entries and session keys,
- `explicit-session-key-normalization.ts` normalizes provider/surface-specific explicit keys before they pollute the store.

This separation helps reference platform keep channel quirks from leaking all over the main runtime.

## 10. `transcript.ts` Manages Transcript Lifecycle as a Distinct Policy Layer

Primary file:

- `reference-repo/src/config/sessions/transcript.ts`

This layer:

- resolves real transcript files,
- ensures the transcript header exists,
- mirrors assistant delivery messages into session files,
- and emits transcript update events.

Transcript policy is therefore not buried in the reply loop. It is its own lifecycle layer.

## 11. ACP Adds a Second, Explicit Runtime Session Layer

Relevant files:

- `reference-repo/src/acp/session.ts`
- `reference-repo/src/acp/control-plane/runtime-options.ts`
- `reference-repo/src/acp/translator.ts`
- `reference-repo/src/acp/session-mapper.ts`

ACP is not just a tool runner.

It adds:

- its own session store,
- stable `sessionId`,
- bound `sessionKey`,
- validated absolute `cwd`,
- active run tracking,
- abort control,
- runtime-option normalization,
- gateway transcript replay,
- and session mapping between ACP presentation and gateway session identity.

This is why reference platform coding/file turns feel less like "parser guessed a folder" and more like "the runtime knows where it is".

## 12. What reference platform Does Not Seem to Use

From direct repo search, reference platform does **not** appear to use Kabot-style literal breadcrumb fields such as:

- `last_navigated_path`
- `last_delivery_path`

Its continuity is much closer to:

- history,
- normalized session identity,
- persisted delivery route,
- ACP `cwd`,
- transcript/session store,
- and tool/runtime policy.

## Kabot: The Current Shape

## 1. `session_flow.py` Is the Main Session Orchestrator

Primary file:

- `kabot/agent/loop_core/session_flow.py`

Kabot's session lifecycle is much more directly attached to turn processing.

It:

- resolves the session key,
- loads or creates the session object,
- hydrates inbound metadata from prior session metadata,
- writes user/assistant turns into memory,
- updates `working_directory`, `last_navigated_path`, and `last_delivery_path`,
- refreshes durable snapshots,
- then saves the session.

This is practical and effective, but less modular than reference platform.

## 2. `session/manager.py` Is Simpler and Easier to Read

Primary file:

- `kabot/session/manager.py`

Kabot's session store is JSONL-based and straightforward:

- messages,
- metadata,
- created/updated timestamps,
- durable history snapshot,
- pending work queue,
- atomic save with a PID lock,
- and now a dedicated transcript mirror sidecar under `~/.kabot/sessions/transcripts/`.

This is easier to reason about than the reference platform's larger session-store machinery, but it also means Kabot still has fewer built-in layers for route normalization, migration, transcript policy, and session-key cleanup.

## 3. Kabot Now Has a More Structured Runtime Anchor, but Breadcrumb Fallbacks Still Exist

Relevant files:

- `kabot/agent/loop_core/tool_enforcement_parts/core.py`
- `kabot/agent/loop_core/message_runtime_parts/turn_metadata.py`
- `kabot/agent/loop_core/execution_runtime_parts/artifacts.py`

Kabot now persists and reuses:

- `delivery_route`
- `working_directory`
- `last_navigated_path`
- `last_delivery_path`

The architecture is improving because:

- `working_directory` is now the canonical filesystem anchor,
- `delivery_route` is now stored as a structured session object,
- and `last_navigated_path` / `last_delivery_path` are increasingly fallback-style continuity hints.

Compared to reference platform, this is still more explicit and more runtime-breadcrumb-oriented.

## 4. Kabot Has Better Inline Runtime Observability

Relevant files:

- `kabot/agent/loop_core/message_runtime_parts/turn_metadata.py`
- `kabot/cli/commands_agent_command.py`
- `kabot/cli/dashboard_payloads.py`

Kabot already exposes:

- `route_decision_snapshot`
- turn category
- continuity source
- required tool
- required tool query
- forced skills

This makes continuity and routing failures easier to replay than in many assistants.

reference platform is architecturally cleaner, but Kabot is currently more explicit in replay/debug surfaces.

## 5. Kabot Ties Sessions Directly into Memory Backends

Relevant files:

- `kabot/agent/loop_core/session_flow.py`
- `kabot/agent/loop_core/message_runtime_parts/process_flow.py`
- `kabot/memory/*`

Kabot sessions feed:

- SQLite message persistence,
- profile memory,
- facts and lessons,
- hybrid retrieval,
- and subprocess-backed embedding flows.

That directness is one of Kabot's strongest advantages and should not be weakened just for structural parity.

## 6. Kabot Has Fewer Dedicated Layers Between History, Session State, and Runtime

Relevant files:

- `kabot/session/manager.py`
- `kabot/agent/context.py`
- `kabot/agent/loop_core/message_runtime_parts/context_notes.py`
- `kabot/agent/loop_core/tool_enforcement_parts/action_requests.py`

History, runtime hints, and follow-up continuity are effective in Kabot, but they are more interleaved than in reference platform.

That makes Kabot fast to evolve, but it also makes parity harder because concerns are less isolated.

## Direct Comparison

## Session Identity

reference platform:

- richer and more normalized,
- route and thread context are first-class,
- ACP can bind a runtime session independently of raw chat text.

Kabot:

- simpler,
- usually `channel:chat_id` style,
- with routing and continuity layered on top through metadata and runtime helpers.

Verdict:

- reference platform is stronger here.

## History Assembly

reference platform:

- dedicated history layer,
- bounded history maps,
- explicit context assembly markers,
- cleaner separation from runtime.

Kabot:

- history is spread across session objects, memory backends, and context-note inference,
- durable snapshots help,
- but the architecture is more mixed.

Verdict:

- reference platform is cleaner,
- Kabot is more tightly fused with memory behavior.

## Delivery Continuity

reference platform:

- delivery route is part of session schema,
- persisted through `deliveryContext`, `lastChannel`, `lastTo`, and `lastThreadId`,
- normalized through dedicated helpers.

Kabot:

- delivery continuity is effective,
- now has a structured `delivery_route` in session metadata,
- but still depends more on explicit remembered file/folder state than reference platform,
- with route context still less deeply integrated than the reference platform's delivery/session layers.

Verdict:

- reference platform is architecturally stronger.

## Working Directory / File Runtime

reference platform:

- ACP has a validated `cwd`,
- runtime options normalize and protect it,
- ACP translator and session mapping keep that runtime state aligned with gateway sessions.

Kabot:

- `working_directory` now exists and is improving,
- it now behaves more like the canonical cwd-style anchor during tool follow-up reuse,
- relative artifact/path reuse now prefers `working_directory` before `last_delivery_path` and `last_navigated_path`,
- but it still coexists with breadcrumb-style follow-up fields for compatibility.

Verdict:

- reference platform remains the better reference.

## Transcript Lifecycle

reference platform:

- transcript files, headers, mirrored assistant delivery messages, and update events are handled by dedicated files.

Kabot:

- transcript-like continuity is still mostly carried by session JSONL, memory writes, and runtime metadata,
- but there is now a separate transcript mirror sidecar that records session messages with a header containing `cwd` and `delivery_route`.

Verdict:

- reference platform is cleaner here.

## Memory Integration

reference platform:

- cleaner separation between session/runtime and memory-search systems.

Kabot:

- stronger direct assistant-memory integration,
- session turns feed live memory backends more immediately.

Verdict:

- Kabot is stronger here.

## Best Parity Direction

Kabot should become more reference-like in:

- session schema structure,
- delivery-route normalization,
- transcript lifecycle,
- runtime `cwd` semantics,
- and separation between history assembly and turn execution.

Kabot should stay stronger in:

- session-to-memory integration,
- durable fact/profile recall,
- hybrid memory over live assistant conversations,
- subprocess/lazy memory lifecycle,
- and inline route/debug observability.

## Practical Recommendation

The best next-step architecture for Kabot is:

1. make `working_directory` the true session runtime anchor,
2. push `last_navigated_path` and `last_delivery_path` toward compatibility fallbacks only,
3. normalize delivery-route state more centrally,
4. keep route/debug snapshots,
5. keep moving artifact/file reuse toward `working_directory` first,
6. keep direct memory integration with SQLite + hybrid recall + subprocess embeddings,
7. avoid replacing Kabot's stronger memory core just to imitate the reference platform's file layout.

Recent parity progress on that path:

- `last_delivery_path` is still persisted in session state, but it is no longer rehydrated into inbound metadata by default during `_init_session(...)`,
- `turn_metadata` also stopped exporting `last_delivery_path` into active message metadata,
- so active turns lean a little less on explicit file breadcrumbs and a little more on durable session/runtime state,
- legacy sessions that only persisted `last_navigated_path` are now promoted into active `working_directory` state on init instead of being re-exposed as a live breadcrumb,
- `turn_metadata` now also stops re-exporting `last_navigated_path` into active message metadata, so the live turn has to work from `working_directory`, `delivery_route`, and real tool/runtime context first,
- while compatibility follow-ups can still fall back to the persisted session value when the user really means "send it again",
- bare send-message continuity now also treats structured `delivery_route` as sufficient route state even when no file breadcrumb is active,
- active bare-send guard checks now trust live `working_directory` / `delivery_route` first and only consult persisted session breadcrumbs as fallback, instead of treating an active-turn `last_delivery_path` or `last_navigated_path` as sufficient on their own,
- `_get_last_navigated_path(...)` now also prefers the persisted session breadcrumb over any active-turn `last_navigated_path`, so navigation fallback matches the same session-first rule as delivery fallback,
- `_get_last_delivery_path(...)` also now prefers the persisted session breadcrumb over any active-turn `last_delivery_path`, which keeps that field aligned with "compatibility fallback" rather than "live turn state",
- `_get_working_directory(...)` now also prefers the persisted session `working_directory` over a stale active-turn cwd hint, so the canonical filesystem anchor follows the session runtime state first instead of whichever copy happened to be attached to the inbound turn,
- the direct delivery-candidate resolver in `agent_loop` now likewise prefers the persisted session `last_navigated_path` over an active-turn breadcrumb when no `working_directory` is available, so delivery verification follows the session runtime anchor instead of stale live metadata,
- and that same direct delivery-candidate resolver now goes through the canonical `working_directory` / navigation helpers instead of manually re-reading raw metadata keys, which keeps send-file verification aligned with the same session-first cwd semantics as the rest of tool enforcement,
- relative artifact follow-up resolution in `artifacts.py` now also prefers `working_directory`, then the previous live `last_tool_context.path`, before falling back to stale delivery/navigation breadcrumbs, which makes follow-up file paths behave more like runtime state and less like breadcrumb carry-over,
- `find_files` root resolution in `action_requests.py` now follows the same direction by preferring `working_directory`, then a live `last_tool_context.path`, before stale `last_navigated_path` state, so filesystem action roots rely more on current runtime context than breadcrumb drift,
- `finalize_session(...)` now also drops a redundant persisted `last_navigated_path` when it is identical to the canonical `working_directory`, so the session keeps one cwd-style filesystem anchor instead of storing the same location twice under two keys,
- live `list_dir` navigation now follows that same cleanup rule: when tool execution establishes a directory as `working_directory`, Kabot no longer also persists the same directory again under `last_navigated_path`, so new sessions stay more cwd-centric even during direct tool execution,
- the artifact/follow-up updater in `artifacts.py` now follows the same rule too, so directory-shaped tool results update `working_directory` without reintroducing a duplicate `last_navigated_path` behind the scenes,
- `_set_last_delivery_path(...)` now follows the same session-first pattern for files: it updates `working_directory` in the live turn, but keeps `last_delivery_path` itself session-local as a compatibility fallback instead of copying that file path back into active turn metadata,
- and the active runtime now keeps leaning toward `working_directory + delivery_route + transcript/session state` first, with breadcrumb fields becoming compatibility-only hints.

## Bottom Line

reference platform is the stronger reference for:

- session identity
- route persistence
- history assembly
- transcript/runtime layering
- ACP working-directory semantics

Kabot is the stronger base for:

- assistant-native memory
- direct session-to-memory persistence
- runtime observability
- hybrid recall tied to live sessions
- and practical continuity over real chat workflows

So parity should mean:

- **reference-like session/runtime architecture**
- **Kabot-strong memory integration**

## Related Internal Audits

- `docs/reference/reference-file-continuity.md`
- `docs/reference/reference-repo-reference.md`
- `docs/reference/reference-vs-kabot-memory.md`
