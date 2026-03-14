# reference platform File Continuity

This note explains, as precisely as possible from source inspection, how reference platform keeps file and delivery context coherent across chat turns, and how that differs from Kabot today.

## Short Answer

reference platform does **not** appear to rely on a single hardcoded parser file or on Kabot-style breadcrumb fields such as `last_navigated_path` and `last_delivery_path`.

Instead, its file continuity comes from a pipeline:

1. reply orchestration,
2. history assembly,
3. persisted session route state,
4. ACP runtime state such as `cwd`,
5. delivery-context normalization,
6. safe path and file tooling,
7. tool-policy checks before execution.

Kabot historically leaned more on explicit filesystem breadcrumbs. The current parity work is moving Kabot toward a more reference-like shape by making `working_directory` the canonical continuity anchor and leaving the older breadcrumb fields as fallbacks.

## The Earlier Explanation: What Was Right and What Was Not

An earlier summary described reference platform like this:

- detect intent from chat,
- remember `last_navigated_path`,
- remember `last_delivery_path`,
- combine short file names with the last folder,
- validate against the real filesystem,
- execute the delivery tool.

That description is **directionally right** about the overall behavior, but it is **not literally accurate** for reference platform.

### What is directionally correct

- reference platform absolutely uses prior chat state.
- It persists delivery/session information across turns.
- It validates and normalizes file operations through safe tooling and policy layers.
- The logic is spread across multiple files, not one giant parser file.

### What is not literally correct

- A repo search over `reference-repo/src` did **not** find `last_navigated_path`.
- A repo search over `reference-repo/src` did **not** find `last_delivery_path`.
- reference platform does **not** appear to use those exact Kabot-style breadcrumb fields.

## reference platform: The Real Pipeline

### 1. Reply Entry and Orchestration

Primary entrypoint:

- `src/auto-reply/reply/get-reply.ts`

This layer prepares the reply run, wires history, session state, runtime config, and tools together, and starts the turn. It is the orchestration shell around the actual agent run.

Why it matters:

- continuity starts here because every turn is attached to an existing session,
- route and runtime state are pulled in before the model decides what to do next.

### 2. History Context

Primary file:

- `src/auto-reply/reply/history.ts`

This file builds the history context that the agent sees for the turn.

Why it matters:

- reference platform does not need a language-specific â€œfile location parserâ€ if the model can see the relevant prior messages,
- follow-up turns such as â€œsend itâ€, â€œopen that folderâ€, or â€œuse the same placeâ€ become possible because the agent has structured history to reason over.

### 3. Session State and Delivery Route Persistence

Primary files:

- `src/auto-reply/reply/session.ts`
- `src/config/sessions/store.ts`
- `src/config/sessions/metadata.ts`
- `src/config/sessions/delivery-info.ts`

This is where reference platform carries forward route and delivery-related session fields.

From source inspection, the fields that matter are closer to:

- `lastChannel`
- `lastTo`
- `lastAccountId`
- `lastThreadId`
- `deliveryContext`

Why it matters:

- when the user says â€œsend hereâ€ or â€œsend it againâ€, reference platform can reconstruct the correct delivery route,
- this is route continuity, not just text matching.

### 4. Delivery Context Normalization

Primary file:

- `src/utils/delivery-context.ts`

This layer normalizes and merges delivery information across sessions and channels.

Why it matters:

- a reply tool does not need to guess destination metadata from raw chat text every time,
- the system keeps a stable notion of where â€œhereâ€ means for the current session.

### 5. ACP Runtime State and `cwd`

Primary files:

- `src/config/sessions/types.ts`
- `src/acp/session.ts`
- `src/acp/control-plane/runtime-options.ts`

This is the most important correction to the earlier explanation.

reference platform does appear to keep a real working-directory style runtime state through ACP session/runtime options, including `cwd`.

Why it matters:

- when a coding or file-oriented turn happens, the model is not reasoning only from breadcrumb memory,
- it can operate with an explicit session-scoped working directory,
- this feels much closer to â€œI know where we areâ€ than â€œI parsed a folder name from Indonesian textâ€.

## 6. Safe File and Path Tooling

Primary files:

- `src/agents/pi-tools.read.ts`
- `src/infra/fs-safe.ts`
- `src/agents/path-policy.ts`

These files are where reference platform constrains and resolves file operations.

What they do conceptually:

- read/list/edit operations go through safe file helpers,
- paths are normalized and checked,
- path-policy layers restrict unsafe or surprising access patterns.

Why it matters:

- continuity is grounded on real filesystem evidence,
- the agent can say â€œnot foundâ€ honestly because the tool layer has real path checks,
- this is a big reason reference platform feels trustworthy instead of hallucinated.

### 7. Tool Policy Pipeline

Primary files:

- `src/agents/tool-policy.ts`
- `src/agents/tool-policy-pipeline.ts`

This is the policy layer that decides whether a tool call should be allowed, adjusted, or blocked.

Why it matters:

- the model can be flexible in language understanding,
- policy and execution still stay safe and structured,
- this is a key part of why reference platform can feel AI-driven without becoming reckless.

## What reference platform Does Not Seem to Do

Based on current source inspection, reference platform does **not** seem to depend on:

- a dedicated Indonesian parser for file navigation,
- a single â€œfile continuity parserâ€ that hardcodes follow-up rules,
- Kabot-style explicit breadcrumb fields named `last_navigated_path` and `last_delivery_path`.

That does **not** mean it has no state.

It means the state shape is closer to:

- conversation history,
- persisted delivery routing,
- session metadata,
- ACP runtime state like `cwd`,
- safe tool/path layers.

## Kabot: Current Shape

Kabot today still has a more explicit breadcrumb model, although recent parity work has moved it closer to reference platform.

### Existing continuity fields

Kabot currently persists:

- `working_directory`
- `last_navigated_path`
- `last_delivery_path`

Relevant areas:

- `kabot/agent/loop_core/message_runtime_parts/turn_metadata.py`
- `kabot/agent/loop_core/session_flow.py`
- `kabot/agent/loop_core/execution_runtime_parts/artifacts.py`
- `kabot/agent/loop_core/execution_runtime_parts/agent_loop.py`
- `kabot/agent/loop_core/execution_runtime_parts/intent.py`
- `kabot/agent/loop_core/tool_enforcement_parts/core.py`

### Why `working_directory` matters

Recent parity work makes `working_directory` the closest Kabot equivalent to the reference platform's `cwd`-style runtime state.

That means:

- screenshot/artifact outputs now seed a reusable working directory,
- bare send-file requests can reuse session `working_directory`,
- session init/finalize now hydrate and persist `working_directory`,
- find-files root selection can prefer `working_directory` before older breadcrumbs.

This is an important design shift:

- older Kabot behavior depended more heavily on explicit breadcrumbs,
- newer behavior treats `working_directory` as the canonical current place,
- breadcrumb fields remain mainly as compatibility and fallback state.

## Practical Comparison

### reference platform

Think of the continuity model as:

- `history + persisted delivery route + ACP cwd + safe tools + tool policy`

### Kabot

Think of the continuity model as:

- `history + working_directory + explicit breadcrumbs + artifact verification`

### Direction of parity

To become more reference-like, Kabot should:

- prefer `working_directory` over breadcrumb-specific path memory,
- let history and tool state carry more of the continuity burden,
- keep explicit breadcrumbs only as fallback evidence,
- avoid language-specific routing rules for file continuity whenever possible.

## Why This Matters for Coding Chats

The user's real goal here is not just â€œsend a file correctlyâ€.

It is:

- easier coding sessions,
- less brittle follow-up behavior,
- less parser-heavy routing,
- more natural continuity like reference platform.

That is exactly why `working_directory` is a better anchor than a pile of narrow parser rules:

- it helps `open folder -> inspect file -> edit file -> send file` flows stay coherent,
- it reduces the need to rediscover path context every turn,
- it keeps the system grounded on real filesystem state.

## Final Takeaway

If we phrase it accurately:

- **reference platform** understands file location from chat through a combination of history, persisted delivery/session state, ACP `cwd`, safe path tooling, and tool policy.
- **Kabot** has historically used explicit filesystem breadcrumbs more directly, but it is now being moved toward a more reference-like model by centering continuity on `working_directory` and using breadcrumb fields as fallback state.
