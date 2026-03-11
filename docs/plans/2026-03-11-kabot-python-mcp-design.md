# Kabot Full-Python MCP Design

Date: 2026-03-11
Status: Draft design plan
Scope: Runtime architecture plan for adding MCP to Kabot without requiring npm on the Kabot side

## Goal

Add first-class MCP support to Kabot using Python-native runtime components so that:

- Kabot stays AI-driven, not rule-bot driven
- Kabot does not hallucinate MCP behavior or spawn tools blindly
- Kabot keeps understanding user intent and session context
- Kabot can use MCP servers through a stable, session-scoped runtime layer
- Kabot itself does not require npm or Node.js to implement MCP support

Important caveat:

- Kabot can be full Python as the MCP client/runtime.
- Some external MCP servers may still require Node.js if those servers are published as npm-only programs.
- In that case, Kabot remains Python-native, but the external server process may still be Node-based.

## What Was Studied

This plan is based on reading the OpenClaw and mcporter MCP paths closely, especially the files that shape:

- MCP configuration and runtime wiring
- Session bootstrap behavior
- Transcript hygiene and repair
- Tool loop prevention
- System prompt ownership
- Agent loop lifecycle and persistence

### OpenClaw MCP path reviewed

- `openclaw/extensions/acpx/src/config.ts`
- `openclaw/extensions/acpx/src/runtime.ts`
- `openclaw/extensions/acpx/src/runtime-internals/mcp-agent-command.ts`
- `openclaw/extensions/acpx/src/runtime-internals/mcp-proxy.mjs`
- `openclaw/extensions/acpx/src/service.ts`
- related ACPX tests

### OpenClaw grounding and anti-hallucination path reviewed

- `openclaw/src/agents/system-prompt.ts`
- `openclaw/src/agents/context.ts`
- `openclaw/src/agents/transcript-policy.ts`
- `openclaw/src/agents/session-transcript-repair.ts`
- `openclaw/src/agents/session-file-repair.ts`
- `openclaw/src/agents/tool-policy.ts`
- `openclaw/src/agents/tool-loop-detection.ts`
- `openclaw/src/agents/session-transcript-repair.ts`
- `openclaw/docs/concepts/agent-loop.md`
- `openclaw/docs/concepts/system-prompt.md`
- `openclaw/docs/reference/transcript-hygiene.md`
- `openclaw/docs/reference/session-management-compaction.md`

### mcporter path reviewed

- `mcporter/src/config*.ts`
- `mcporter/src/runtime*.ts`
- `mcporter/src/server-proxy.ts`
- `mcporter/src/oauth.ts`
- `mcporter/src/daemon/*`
- `mcporter/src/cli/call-command.ts`
- `mcporter/src/cli/list-command.ts`
- `mcporter/docs/*` around MCP/config/daemon/import/tool-calling

## Key Findings From OpenClaw

OpenClaw stays AI-driven not because it removes model freedom, but because it puts stronger runtime structure around the model.

### 1. The system prompt is runtime-owned

OpenClaw assembles its own compact system prompt and does not rely on the default prompt of the underlying agent runtime.

That prompt explicitly controls:

- available tools
- when to use memory
- when to load skills
- workspace context
- time handling
- messaging behavior
- sandbox behavior

Implication for Kabot:

- MCP should not be introduced only as a skill or as a loose instruction block.
- MCP availability must become part of Kabot's runtime-owned context model.

### 2. Transcript hygiene is a first-class reliability layer

Before model context is rebuilt, OpenClaw repairs or sanitizes transcript structure:

- malformed tool calls are dropped
- invalid tool names and empty tool inputs are removed
- orphaned tool results are repaired
- synthetic tool results can be inserted when needed
- provider-specific transcript constraints are enforced
- broken session files are repaired before load

Implication for Kabot:

- MCP support must ship with transcript repair logic, not only transport code.
- Otherwise MCP tool traffic will create more confusion, not less.

### 3. Tool-loop detection is explicit

OpenClaw includes loop detection and circuit-breaker style logic so the model cannot stay stuck in repetitive tool calls indefinitely.

Kabot already has a simpler loop detector, but it is narrower and not yet MCP-aware.

Implication for Kabot:

- MCP tools must be integrated with loop detection from day one.

### 4. MCP in OpenClaw is session-scoped

OpenClaw ACPX does not ask the model to invent MCP execution at prompt time.
Instead, it injects `mcpServers` into session bootstrap (`session/new`, `session/load`, `session/fork`).

Implication for Kabot:

- MCP attachment should happen at session/runtime level, not as an ad-hoc prompt trick.

### 5. mcporter is a bridge, not the agent runtime itself

mcporter is a general MCP client/runtime bridge:

- config loading
- config import
- transport handling
- OAuth
- daemon keep-alive
- tool/resource listing
- tool calling

Implication for Kabot:

- Kabot does not need to copy mcporter literally.
- Kabot should copy the architecture idea: MCP is a runtime capability, not a model improvisation.

## Current Kabot Gap

Kabot currently has:

- strong internal tool orchestration
- context builder and memory systems
- session management
- skill loading and matching
- some loop detection

Kabot currently does not have:

- native `mcpServers` config model
- MCP client runtime
- session-scoped MCP attachment
- MCP transport manager
- MCP transcript repair rules
- MCP-aware loop detection
- dashboard/config surface for MCP

At the moment, MCP in Kabot is effectively skill-level guidance only:

- `kabot/skills/mcporter/SKILL.md`

That is not enough for grounded behavior.

## Design Principles For Kabot MCP

1. Python-native runtime
- Use the official Python MCP SDK as the primary implementation base.
- Avoid npm as a Kabot dependency.

2. Session-scoped capability attachment
- MCP servers are attached to a session, not improvised per prompt.

3. Runtime-owned truth
- The runtime tells the model which MCP capabilities are available.
- The model never invents MCP tools from memory.

4. Intent first, tool second
- Current user intent must beat stale tool context.
- MCP availability should not override conversation continuity.

5. Honest failure
- If an MCP server is unavailable, Kabot says so plainly.
- It must not pretend it called a server or fabricate results.

6. Transcript hygiene by default
- MCP tool traffic must be normalized and repaired before rebuild.

7. Namespaced, explainable tool surface
- MCP-exposed tools should be clear and stable.

## Recommended Architecture

### Proposed package layout

```text
kabot/mcp/
  __init__.py
  config.py
  models.py
  registry.py
  runtime.py
  session_state.py
  policy.py
  transcript.py
  loop_guard.py
  tool_bridge.py
  prompt_bridge.py
  resource_bridge.py
  auth.py
  daemon.py
  transports/
    __init__.py
    stdio.py
    streamable_http.py
```

### Component responsibilities

#### `config.py`

- Parse and validate `mcp.servers`
- Support Python-native config structure
- Keep server definitions explicit and deterministic

Example target config shape:

```json
{
  "mcp": {
    "enabled": true,
    "servers": {
      "weather": {
        "transport": "streamable_http",
        "url": "https://example.com/mcp"
      },
      "local_tools": {
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "my_mcp_server"]
      }
    }
  }
}
```

#### `runtime.py`

- Own MCP runtime lifecycle for a session
- Open, cache, reuse, and close client connections
- Resolve which servers are active for a given session/run

#### `registry.py`

- Build a namespaced capability registry from connected servers
- Track:
  - tools
  - resources
  - prompts
  - server metadata

#### `tool_bridge.py`

- Present MCP tools into Kabot as first-class runtime tools
- Convert MCP tool schemas into Kabot-callable tools
- Preserve deterministic names

Recommended tool naming:

- `mcp.<server>.<tool>`

Example:

- `mcp.linear.list_issues`
- `mcp.github.create_issue`

This avoids ambiguity and makes loop detection simpler.

#### `transcript.py`

- Normalize MCP tool calls and results before context rebuild
- Repair orphaned result events
- Mark synthetic error results when needed
- Tag provenance for inter-session or synthetic events

#### `loop_guard.py`

- Extend Kabot's loop detector with MCP-aware signatures:
  - repeated same MCP tool + same args
  - repeated server failure with no progress
  - ping-pong across MCP tools

#### `prompt_bridge.py`

- Inject compact MCP availability into system/runtime prompt
- Keep prompt small
- Avoid dumping entire schemas into the main prompt

Recommended behavior:

- expose tool names and short descriptions
- load detail only on demand

#### `resource_bridge.py`

- Optional v2 or gated v1.5 component
- Provide MCP resources and prompts through explicit runtime calls
- Avoid bloating first release

#### `auth.py`

- Manage auth material needed by HTTP-based MCP servers
- Keep secrets in Kabot config or environment
- Never push auth management into the model layer

#### `daemon.py`

- Optional v2+
- Keep stateful MCP connections warm
- Useful for servers with expensive startup or OAuth handshakes

## Recommended Rollout

### Phase 0: Design and schema

Deliverables:

- config schema
- runtime boundaries
- tool naming rules
- transcript repair rules
- tests for config validation

### Phase 1: MCP runtime core

Scope:

- `stdio`
- `streamable_http`
- session-scoped runtime
- tool listing
- tool invocation

Out of scope in phase 1:

- prompt resources
- dashboard UI
- daemon keep-alive
- server importers

Success criteria:

- Kabot can attach one or more MCP servers to a session
- Kabot can list and call MCP tools without hallucinating availability

### Phase 2: Grounding and reliability

Scope:

- transcript hygiene
- orphan repair
- synthetic error results
- MCP-aware loop detection
- honest failure messaging

Success criteria:

- broken MCP tool history does not poison later turns
- repeated bad MCP calls do not loop indefinitely

### Phase 3: Resources and prompts

Scope:

- MCP resources
- MCP prompts
- prompt-resource fetch policy

Success criteria:

- Kabot can use MCP beyond tools without blowing up prompt size

### Phase 4: UX and operator surface

Scope:

- dashboard config panel
- session/server diagnostics
- enable/disable server controls
- latency and error stats

### Phase 5: Optional daemon and importers

Scope:

- keep-alive for expensive servers
- import config from other tools when useful

This is optional. It should not block phase 1.

## How Kabot Stays AI-Driven

The target behavior is not:

- hardcoded if/else bot
- skill-only MCP wrapper
- automatic tool execution on keyword match

The target behavior is:

1. The model sees a grounded, session-specific MCP capability surface.
2. The runtime decides what is truly available.
3. The model chooses when to use those tools.
4. The runtime prevents invalid transcript shapes, stale tool confusion, and infinite loops.
5. If the model is unsure, it can ask, but it cannot fabricate tool execution.

This is close to the OpenClaw pattern:

- keep AI freedom at decision time
- keep runtime strict at state, transport, and persistence time

## Anti-Hallucination Requirements

These should be explicit engineering requirements, not nice-to-have ideas.

1. Never expose a tool the session cannot actually call
2. Never pretend a tool ran if transport failed
3. Never let stale MCP context override a newer clear user request
4. Always tag MCP tool results with enough metadata for repair and follow-up reuse
5. Insert synthetic error tool results when pairing would otherwise break context
6. Treat repeated no-progress MCP calls as loop-risk
7. Keep prompt summaries small and deterministic

## Proposed Session Model

Each Kabot session should have MCP state like:

```json
{
  "mcp": {
    "enabled": true,
    "attachedServers": ["github", "linear"],
    "tools": [
      "mcp.github.create_issue",
      "mcp.github.list_prs",
      "mcp.linear.list_issues"
    ],
    "lastRefreshAt": "...",
    "serverHealth": {
      "github": "ok",
      "linear": "ok"
    }
  }
}
```

This allows:

- context rebuild from session truth
- dashboard diagnostics
- graceful degradation

## Prompt Strategy Recommendation

Do not dump full MCP server specs into the system prompt.

Instead:

- add a compact runtime section:
  - active MCP servers
  - available MCP tool names
  - short one-line descriptions
- fetch richer schema only when needed

This mirrors the best part of OpenClaw's prompt philosophy:

- compact base prompt
- controlled context expansion

## Comparison Table

| Area | OpenClaw | Kabot today | Kabot target |
|---|---|---|---|
| MCP config | Yes via ACPX/mcporter path | No native config | Yes, native Python config |
| Session-scoped MCP | Yes in ACPX | No | Yes |
| MCP transport runtime | Yes through bridge/runtime | No | Yes, Python-native |
| Transcript repair | Strong | Partial, not MCP-specific | Strong and MCP-aware |
| Tool-loop protection | Stronger and explicit | Present but simpler | Stronger and MCP-aware |
| Prompt ownership | Strong | Strong | Strong |
| npm required in core | No | No | No |
| Can use npm-only external servers | Through external tooling | No runtime layer yet | Yes, if external server has Node; Kabot still stays Python |

## Recommended First Implementation Scope

For Kabot v1 MCP, the best scope is:

- tools only
- `stdio` + `streamable_http`
- session-scoped runtime
- transcript hygiene
- MCP-aware loop detection

Do not put these in v1:

- full prompt/resource support
- daemon keep-alive
- dashboard editor
- importer ecosystem

Those are valuable, but they should come after the core is trustworthy.

## Acceptance Criteria

1. Kabot can attach MCP servers from config without npm in Kabot itself
2. Kabot can list and call MCP tools through a Python-native runtime
3. MCP tool names shown to the model are always real and callable
4. Broken or partial MCP transcript entries do not derail later turns
5. Repeated no-progress MCP tool loops are stopped or downgraded
6. User follow-up continuity remains stronger than stale MCP/tool context
7. Kabot remains multilingual and AI-driven across normal chat and MCP-enabled turns

## Risks

### Risk: prompt bloat

Mitigation:

- compact tool summaries
- schema on demand

### Risk: external server instability

Mitigation:

- session health tracking
- honest failure replies
- synthetic error results for transcript integrity

### Risk: over-hardening turns Kabot into a rigid rules bot

Mitigation:

- keep decision-making with the model
- keep transport, transcript, and loop safety in runtime

### Risk: npm-free goal misunderstood

Mitigation:

- document clearly:
  - Kabot core stays Python
  - external Node-based MCP servers may still need Node

## Next Steps

1. Add MCP config schema to Kabot
2. Create Python-native runtime package skeleton under `kabot/mcp/`
3. Implement phase-1 transports
4. Build tool registry bridge
5. Add transcript hygiene rules for MCP tool traffic
6. Extend loop detection for MCP signatures
7. Add operator diagnostics after runtime core is stable

## Recommendation

Proceed with a Python-native MCP runtime in Kabot that copies OpenClaw's strongest architectural ideas:

- session-scoped attachment
- runtime-owned prompt truth
- transcript hygiene
- tool-loop protection

But do not copy OpenClaw's stack literally.

Kabot should stay Python-first and use MCP as a grounded runtime capability, not as a skill prompt or a shell trick.
