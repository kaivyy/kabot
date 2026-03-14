# reference platform vs Kabot Directives and Tool-Loop Architecture

This audit compares how reference platform and Kabot handle:

- inline directives,
- runtime overrides,
- ACP or tool-loop orchestration,
- streamed tool/result projection,
- and loop-safety behavior.

It is based on direct inspection of:

- `reference-repo/src/auto-reply/reply/directive-handling.*`
- `reference-repo/src/auto-reply/reply/dispatch-acp*.ts`
- `reference-repo/src/auto-reply/reply/acp-projector.ts`
- `reference-repo/src/auto-reply/reply/agent-runner-execution.ts`
- Kabot files under `kabot/core/directives.py`, `kabot/agent/loop_core/`, and `kabot/agent/loop_core/tool_loop_detection.py`

## Short Verdict

reference platform has the cleaner directives/runtime-control pipeline.

Kabot currently has the simpler directives surface and the more explicit local debugability.

reference platform is stronger at:

- separating parse, fast-lane handling, and persistence of directives,
- treating ACP dispatch as a distinct runtime path instead of just another tool call,
- projecting streamed tool/runtime events into delivery surfaces,
- and coupling loop recovery to transcript/session infrastructure.

Kabot is stronger at:

- keeping local runtime behavior easier to trace,
- exposing explicit per-turn route snapshots,
- and keeping deterministic fallback behavior easier to reason about when tools are skipped.

## reference platform: The Real Shape

## 1. Directive Parsing Is Its Own Layer

Primary file:

- `reference-repo/src/auto-reply/reply/directive-handling.parse.ts`

reference platform parses directives into a structured object with fields for:

- thinking,
- verbose mode,
- reasoning mode,
- elevated runtime,
- exec host/security/ask defaults,
- model directives,
- queue directives,
- and a cleaned body.

That parsing layer also decides whether a message is directive-only, instead of forcing later runtime code to rediscover that fact.

## 2. Directive Fast-Lane Is Separate from Persistence

Primary file:

- `reference-repo/src/auto-reply/reply/directive-handling.fast-lane.ts`

This file:

- resolves current directive levels,
- decides whether a directive-only ack should be returned,
- and updates active provider/model state after any session-backed overrides.

That means reference platform can answer `/think off`, `/model ...`, or `/elevated ask` without dragging the full agent run through unnecessary work.

## 3. Directive Persistence Is Session-Aware

Primary file:

- `reference-repo/src/auto-reply/reply/directive-handling.persist.ts`

This layer persists directive effects into session state:

- thinking level,
- verbose override,
- reasoning level,
- elevated level,
- exec defaults,
- model override and profile override,
- queue reset or queue mode.

It also emits system events when important runtime mode switches occur.

So reference platform directives are not just prompt decorations. They are part of durable session/runtime state.

## 4. Directive Acks and Validation Are Split from Persistence

Primary files:

- `reference-repo/src/auto-reply/reply/directive-handling.impl.ts`
- `reference-repo/src/auto-reply/reply/directive-handling.shared.ts`
- `reference-repo/src/auto-reply/reply/directive-handling.model.ts`
- `reference-repo/src/auto-reply/reply/directive-handling.queue-validation.ts`

This split matters.

reference platform does not dump parsing, validation, ack copy, and persistence into one function.
Instead it separates:

- what a directive means,
- whether it is valid,
- what acknowledgement to show,
- and what should be persisted.

That keeps the runtime control plane cleaner.

## 5. ACP Dispatch Is a Real Alternate Runtime Path

Primary file:

- `reference-repo/src/auto-reply/reply/dispatch-acp.ts`

reference platform does not treat ACP like a trivial tool call.

This layer:

- resolves ACP session identity,
- normalizes attachments,
- checks ACP policy,
- resolves bound conversations,
- coordinates delivery,
- and decides whether the turn should go through ACP at all.

That is a major reason why reference platform coding/file turns feel like a runtime session rather than a prompt hack.

## 6. ACP Delivery and Projection Are Separate Subsystems

Primary files:

- `reference-repo/src/auto-reply/reply/dispatch-acp-delivery.ts`
- `reference-repo/src/auto-reply/reply/acp-projector.ts`

These files handle:

- block replies,
- final replies,
- routed counts,
- editable tool messages,
- tool-call lifecycle summaries,
- live buffering and chunking,
- and projection of ACP runtime events into user-visible delivery payloads.

This is a deeper architecture than "tool ran, now stringify the result".

## 7. Agent Runner Execution Owns Recovery and Fallback Logic

Primary file:

- `reference-repo/src/auto-reply/reply/agent-runner-execution.ts`

This file combines:

- model fallback,
- CLI vs embedded runtime branching,
- streaming output handling,
- compaction recovery,
- transcript/session corruption reset behavior,
- and event emission.

The important point is that reference platform ties tool-loop/runtime recovery into the same session/transcript machinery described in the other audit notes.

## Kabot: The Current Shape

## 1. Directives Are Simpler and More Local

Primary files:

- `kabot/core/directives.py`
- `kabot/agent/loop_core/message_runtime_parts/process_flow.py`
- `kabot/agent/loop_core/directives_runtime.py`

Kabot supports a simpler directive set:

- `/think`
- `/verbose`
- `/elevated`
- `/model`
- `/json`
- `/notools`

Parsing is straightforward and easy to read, but it is much less layered than reference platform.

## 2. Directive Persistence Is Session-Local but Narrower

In Kabot, directives are stored in session metadata and then consumed by runtime helpers like:

- `apply_think_mode`
- verbose formatting
- tool permission checks

This works, but Kabot does not yet separate:

- parse,
- ack,
- validation,
- persistence,
- and runtime mode-switch events

as cleanly as reference platform does.

## 3. Kabot Tool Looping Is Easier to Inspect but Less Runtime-Rich

Primary files:

- `kabot/agent/loop_core/execution_runtime_parts/agent_loop.py`
- `kabot/agent/loop_core/execution_runtime_parts/tool_processing.py`
- `kabot/agent/loop_core/tool_loop_detection.py`

Kabot uses:

- deterministic required-tool enforcement,
- explicit tool execution fallbacks,
- and a local `LoopDetector` for repeated or ping-pong tool patterns.

This is honest and pragmatic, but it is not yet as deeply integrated with transcript/session/runtime layers as the reference platform's ACP path.

## 4. Progress and Reasoning Projection Are Simpler

Primary file:

- `kabot/agent/loop_core/execution_runtime_parts/progress.py`

Kabot has:

- status updates,
- draft updates,
- reasoning updates,
- and channel-specific mutable status handling.

That gives good UX, but it is still a thinner layer than the reference platform's ACP projector, which reasons about streamed runtime events, tool message edits, and block delivery orchestration as separate concerns.

## Direct Comparison

## Directive Parsing and Validation

reference platform:

- more structured,
- more layered,
- richer directive surface.

Kabot:

- simpler,
- easier to inspect,
- narrower feature surface.

Verdict:

- reference platform is architecturally stronger.

## Directive Persistence

reference platform:

- persists directive effects cleanly into session/runtime state,
- emits supporting system events.

Kabot:

- persists directives in session metadata,
- now has a dedicated `directive_pipeline` helper that separates parse/format/persist/override steps,
- but still has a smaller runtime-control surface than the reference platform's directive-handling layers.

Verdict:

- reference platform is the better reference.

## Tool/Runtime Loop Orchestration

reference platform:

- ACP dispatch is a full runtime path,
- with dedicated delivery and projection layers.

Kabot:

- tool loop is explicit and grounded,
- but still more monolithic around `agent_loop.py` and `tool_processing.py`.

Verdict:

- reference platform is stronger here.

## Loop Safety

reference platform:

- ties runtime recovery into session/transcript machinery.

Kabot:

- has very readable local loop detection,
- and deterministic fallback behavior that is easier to debug.

Verdict:

- reference platform is deeper,
- Kabot is more explicit.

## Best Parity Direction

Kabot should become more reference-like in:

- separating directive parse/ack/persist/runtime concerns,
- centralizing runtime-control state,
- projecting tool/runtime events through a more structured delivery layer,
- and treating coding/file execution like a runtime session instead of only a tool loop.

Recent parity progress:

- directive parsing/formatting/persistence/runtime override responsibilities are no longer all embedded directly inside `process_flow.py`,
- richer directive state now survives in session metadata,
- runtime helpers normalize that state before applying think/verbose/elevated behavior,
- active LLM provider calls now honor directive `temperature`, `max_tokens`, and `no_tools` overrides instead of storing them without runtime effect,
- `/json` now affects the real outbound response path by coercing plain-text assistant answers into structured JSON when the model did not already produce valid JSON,
- and `/raw` now propagates as outbound render metadata so CLI delivery can suppress markdown rendering instead of only persisting the flag in session state.

Kabot should keep its current strengths in:

- deterministic required-tool honesty,
- route snapshots and replay/debug observability,
- and memory-native session continuity.

## Related Internal Audits

- `docs/reference/reference-file-continuity.md`
- `docs/reference/reference-repo-reference.md`
- `docs/reference/reference-vs-kabot-memory.md`
- `docs/reference/reference-vs-kabot-session-history-runtime.md`
