# Skyclaw Continuity Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bring Kabot closer to Skyclaw/OpenClaw-style continuity by making history persistence, short follow-up grounding, tool-vs-chat routing, long-running task interruption, and verified delivery behave as one coherent runtime instead of several loosely-coupled heuristics.

**Architecture:** Use Skyclaw's strongest patterns as reference: history-first turn handling, early `chat` vs `order` bifurcation, layered context assembly, pending-message awareness during long tasks, and evidence-based completion. Keep Kabot's existing multilingual heuristics, direct-tool fast paths, and continuity metadata, but move more decisions to a runtime contract that is explicit, durable, and testable.

**Tech Stack:** Python, pytest, async message runtime, session metadata, memory backends, tool enforcement, execution runtime, smoke CLI

---

## Skyclaw Findings To Mirror

- Skyclaw appends the user message to history before classification, so even fast chat turns are durable in context and persistence.
  - Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-agent/src/runtime.rs`
- Skyclaw performs an early LLM `chat` vs `order` split, which reduces accidental tool routing for ordinary conversational turns.
  - Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-agent/src/llm_classifier.rs`
- Skyclaw restores persisted conversation snapshots on worker start and re-saves the snapshot after each turn.
  - Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/src/main.rs`
- Skyclaw's context builder reserves budget for recent messages, memory search, persistent knowledge, learnings, and older history in a fixed priority order.
  - Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-agent/src/context.rs`
- Skyclaw injects pending user messages into tool results during long-running work and also exposes them through a `check_messages` tool.
  - Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-agent/src/runtime.rs`
  - Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-tools/src/check_messages.rs`
- Skyclaw treats `send_message` and `send_file` as first-class tools and does not rely on plain-text claims for delivery.
  - Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-tools/src/send_message.rs`
  - Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-tools/src/send_file.rs`
- Skyclaw appends verification guidance after tool execution and stores cross-task learnings for future prompts.
  - Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-agent/src/runtime.rs`
  - Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-agent/src/learning.rs`

## Current Kabot Gaps

- Kabot persists messages early, but several fast or isolated paths still build from partial or fresh history instead of a single durable turn contract.
  - Reference: `kabot/agent/loop_core/session_flow.py`
  - Reference: `kabot/agent/loop_core/message_runtime_parts/tail.py`
- Kabot continuity is strong for many short follow-ups, but it still depends on layered heuristics (`answer_reference`, `tool_execution`, `user_intent`) rather than an explicit early turn category.
  - Reference: `kabot/agent/loop_core/message_runtime.py`
  - Reference: `kabot/agent/loop_core/message_runtime_parts/followup.py`
- Kabot direct-tool fallbacks are powerful, but that means some turns still decide too early from parser/tool hints before building the best grounded context.
  - Reference: `kabot/agent/loop_core/execution_runtime.py`
  - Reference: `kabot/agent/loop_core/tool_enforcement.py`
- Kabot now supports delivery verification, but it still lacks a general pending-message interruption lane comparable to Skyclaw's in-task awareness.
  - Reference: `kabot/agent/loop_core/execution_runtime.py`
- Kabot memory is durable enough for many cases, but it does not yet have a single prompt-layer contract for recent history, persistent facts, task learnings, and replayable session snapshots.

### Task 1: Add Skyclaw-style Turn Categorization Contract

**Files:**
- Modify: `kabot/agent/loop_core/message_runtime.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/helpers.py`
- Modify: `kabot/agent/router.py`
- Test: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_basics.py`
- Test: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py`
- Test: `tests/agent/test_router.py`
- Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-agent/src/llm_classifier.rs`
- Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-agent/src/runtime.rs`

**Step 1: Write the failing tests**

Add coverage for a `turn_category`-style contract that distinguishes:
- conversational chat that should answer directly without tool forcing
- actionable orders that must stay in tool/skill-capable mode
- contextual follow-ups that are chat-like in wording but action-like in commitment

Add regression cases for:
- `jam berapa`
- `iq manusia rata rata berapa`
- `oke lanjut bikin file`
- `ya lanjut kirim ke chat ini`

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_basics.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py tests/agent/test_router.py -q`

Expected: FAIL because Kabot does not yet expose a single explicit turn category that consistently wins over weak parser guesses.

**Step 3: Write minimal implementation**

Introduce a turn-level classification payload in message metadata, for example:
- `chat`
- `action`
- `contextual_action`
- `command`

Use it to gate:
- direct fast replies
- required-tool inference
- skill-creation/coding escalation
- continuity reuse from recent answer and last tool execution

**Step 4: Run focused tests to verify they pass**

Run: `python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_basics.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py tests/agent/test_router.py -q`

Expected: PASS

### Task 2: Unify History Hydration And Durable Session Snapshots

**Files:**
- Modify: `kabot/agent/loop_core/session_flow.py`
- Modify: `kabot/agent/loop_core/message_runtime.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/tail.py`
- Modify: `kabot/memory/*` as needed for snapshot helpers
- Test: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_memory_durability.py`
- Test: `tests/agent/test_session_persistence_fail_open.py`
- Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/src/main.rs`
- Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-gateway/src/session.rs`

**Step 1: Write the failing tests**

Add coverage proving that:
- chat turns and slash/system turns share one durable session contract
- history is restorable after process-level restart or new loop instance
- isolated/system flows do not silently lose immediately-relevant context unless explicitly intended

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_memory_durability.py tests/agent/test_session_persistence_fail_open.py -q`

Expected: FAIL on missing snapshot hydration or inconsistent history reuse across special paths.

**Step 3: Write minimal implementation**

Add a lightweight persisted session snapshot layer so Kabot can:
- read the latest durable conversation slice when initializing a session
- write back a bounded snapshot after each completed turn
- make isolated/system paths opt into explicit fresh-context behavior instead of implicit history bypass

**Step 4: Run focused tests to verify they pass**

Run: `python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_memory_durability.py tests/agent/test_session_persistence_fail_open.py -q`

Expected: PASS

### Task 3: Build A Layered Context Resolver For Recent History, Memory, And Learnings

**Files:**
- Modify: `kabot/agent/loop_core/message_runtime.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/helpers.py`
- Modify: `kabot/agent/loop_core/quality_runtime.py`
- Modify: `kabot/agent/tools/memory.py`
- Test: `tests/agent/test_direct_runtime_hints.py`
- Test: `tests/agent/test_semantic_intent.py`
- Test: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py`
- Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-agent/src/context.rs`
- Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-agent/src/learning.rs`
- Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-agent/src/prompt_patches.rs`

**Step 1: Write the failing tests**

Add coverage showing that:
- memory recall questions prefer saved facts over stale parser/tool state
- short contextual follow-ups prefer recent answer references before older tool context
- previously learned tool-success hints can bias future execution safely without hardcoding a domain parser

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/agent/test_direct_runtime_hints.py tests/agent/test_semantic_intent.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py -q`

Expected: FAIL because Kabot does not yet have one explicit layered context contract for recent history, memory facts, and learned execution hints.

**Step 3: Write minimal implementation**

Create a context resolver that assembles, in order:
1. recent turn history
2. recent assistant answer reference
3. last verified tool execution
4. pending committed action
5. saved memory facts relevant to the new query
6. lightweight learned hints from successful or failed prior tasks

Keep the learned layer bounded and evidence-based so it never overrides explicit user intent.

**Step 4: Run focused tests to verify they pass**

Run: `python -m pytest tests/agent/test_direct_runtime_hints.py tests/agent/test_semantic_intent.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py -q`

Expected: PASS

### Task 4: Add Pending-Message Awareness During Long-Running Tool Work

**Files:**
- Modify: `kabot/agent/loop_core/execution_runtime.py`
- Modify: `kabot/agent/loop_core/execution_runtime_parts/helpers.py`
- Modify: `kabot/agent/tools/message.py`
- Modify: `kabot/agent/tools/spawn.py` or equivalent long-task helpers if needed
- Test: `tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_tool_calls_and_skill_phases.py`
- Test: `tests/cli/test_agent_smoke_matrix.py`
- Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-agent/src/runtime.rs`
- Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-tools/src/check_messages.rs`
- Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-tools/src/send_message.rs`

**Step 1: Write the failing tests**

Add coverage for:
- a long-running action receiving a new user message mid-flight
- the runtime surfacing that new message to the model/tool loop
- the assistant sending an intermediate acknowledgment instead of ignoring the interruption

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_tool_calls_and_skill_phases.py tests/cli/test_agent_smoke_matrix.py -q`

Expected: FAIL because Kabot currently lacks a generic pending-message injection lane during long-running work.

**Step 3: Write minimal implementation**

Add a per-chat pending-message queue and teach the execution loop to:
- inspect it between long-running tool/skill phases
- inject a compact notice into the active reasoning/tool context
- optionally send a progress/acknowledgment message through the real message tool

**Step 4: Run focused tests to verify they pass**

Run: `python -m pytest tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_tool_calls_and_skill_phases.py tests/cli/test_agent_smoke_matrix.py -q`

Expected: PASS

### Task 5: Promote Verified Completion And Delivery To A Runtime Rule

**Files:**
- Modify: `kabot/agent/loop_core/execution_runtime.py`
- Modify: `kabot/agent/loop_core/execution_runtime_parts/helpers.py`
- Modify: `kabot/agent/loop_core/tool_enforcement.py`
- Test: `tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py`
- Test: `tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_direct_paths_and_research.py`
- Test: `tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py`
- Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-agent/src/runtime.rs`
- Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-agent/src/done_criteria.rs`
- Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-tools/src/send_file.rs`

**Step 1: Write the failing tests**

Add coverage proving that Kabot cannot declare success for:
- generated files not actually written
- screenshots not actually created
- `kirim ke chat ini` flows that never reached `message(files=...)`
- multi-step goals whose verification evidence is missing

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_direct_paths_and_research.py tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py -q`

Expected: FAIL because verification is still distributed across several guards instead of one durable completion rule.

**Step 3: Write minimal implementation**

Unify completion checks so that:
- artifact creation requires file/path evidence
- file delivery requires verified `message` execution with attachment input
- multi-step action completion records a small evidence summary in metadata for follow-up reuse

**Step 4: Run focused tests to verify they pass**

Run: `python -m pytest tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_direct_paths_and_research.py tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py -q`

Expected: PASS

### Task 6: Expand Multilingual Smoke Coverage And Runtime Observability

**Files:**
- Modify: `kabot/cli/agent_smoke_matrix.py`
- Modify: `kabot/cli/dashboard_payloads.py`
- Modify: `CHANGELOG.md`
- Test: `tests/cli/test_agent_smoke_matrix.py`
- Test: `tests/cli/test_gateway_dashboard_helpers.py`
- Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-agent/src/model_router.rs`
- Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-memory/src/search.rs`
- Reference: `C:/Users/Arvy Kairi/Desktop/bot/skyclaw/crates/skyclaw-mcp/src/bridge.rs`

**Step 1: Write the failing tests**

Add smoke cases for:
- multilingual memory recall
- contextual follow-up after tool output
- `find -> send`, `create -> send`, `generate -> send`
- MCP/custom tool follow-up continuity
- long-running task interruption

Add dashboard assertions for:
- `continuity_source`
- `turn_category`
- `completion_evidence`
- `pending_interrupt_count`

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/cli/test_agent_smoke_matrix.py tests/cli/test_gateway_dashboard_helpers.py -q`

Expected: FAIL because the new observability fields and smoke scenarios do not exist yet.

**Step 3: Write minimal implementation**

Expose the new runtime metadata through the smoke runner and dashboard payloads, then document the change in the changelog.

**Step 4: Run broader verification**

Run: `python -m pytest tests/agent/test_router.py tests/agent/test_direct_runtime_hints.py tests/agent/test_semantic_intent.py tests/agent/test_session_persistence_fail_open.py tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_basics.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_memory_durability.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_direct_paths_and_research.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_tool_calls_and_skill_phases.py tests/cli/test_agent_smoke_matrix.py tests/cli/test_gateway_dashboard_helpers.py -q`

Expected: PASS

**Step 5: Run real-agent smoke**

Run: `python -X utf8 -m kabot.cli.agent_smoke_matrix --no-default-cases --continuity-cases --memory-cases --delivery-cases --mcp-local-echo --json`

Expected: exit 0, with multilingual continuity cases, memory follow-ups, and delivery flows passing without hallucinated completion claims.
