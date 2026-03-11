# Large Runtime File Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor Kabot's 1000+ line runtime source files into smaller grouped modules and slimmer orchestrators without changing user-visible logic, routing decisions, continuity behavior, or verification guarantees.

**Architecture:** Preserve behavior by extracting existing logic into compatibility modules instead of redesigning flows. Keep import surfaces stable where practical, move helper clusters into new files under existing `*_parts` packages, and reduce the orchestrator files by delegating grouped subflows to small functions with explicit inputs and outputs.

**Tech Stack:** Python, asyncio, pytest, Kabot loop runtime, deterministic tool fallbacks, message/session metadata

---

## Scope And Safety Rules

- Focus on production source files first:
  - `kabot/agent/loop_core/execution_runtime_parts/helpers.py`
  - `kabot/agent/loop_core/message_runtime_parts/helpers.py`
  - `kabot/agent/loop_core/execution_runtime.py`
  - `kabot/agent/loop_core/message_runtime.py`
  - `kabot/agent/loop_core/tool_enforcement.py`
- Do not intentionally change routing priority, continuity sources, memory behavior, artifact verification, or delivery verification.
- Prefer extraction and re-export over semantic rewrites.
- Use existing test suites as characterization coverage.

### Task 1: Split `execution_runtime_parts/helpers.py` Into Grouped Modules

**Files:**
- Create: `kabot/agent/loop_core/execution_runtime_parts/artifacts.py`
- Create: `kabot/agent/loop_core/execution_runtime_parts/intent.py`
- Create: `kabot/agent/loop_core/execution_runtime_parts/observability.py`
- Create: `kabot/agent/loop_core/execution_runtime_parts/persistence.py`
- Modify: `kabot/agent/loop_core/execution_runtime_parts/helpers.py`
- Test: `tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py`
- Test: `tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_direct_paths_and_research.py`

**Step 1: Write the failing tests**

Add/confirm regression coverage that still imports and exercises helper behavior through the current runtime entrypoints:
- artifact path extraction from structured tool results
- live research gating vs personal HR/memory turns
- completion evidence updates
- pending interrupt note creation and draining

**Step 2: Run tests to verify the characterization baseline**

Run: `python -m pytest tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_direct_paths_and_research.py -q`

Expected: PASS before refactor, establishing the baseline.

**Step 3: Write minimal extraction**

- Move artifact-path and completion-evidence helpers to `artifacts.py`
- Move live-research, confirmation, query-resolution, and tool-intent helpers to `intent.py`
- Move runtime event and quota/performance config helpers to `observability.py`
- Move memory-write scheduling and pending-interrupt queue helpers to `persistence.py`
- Keep `helpers.py` as a compact compatibility facade that re-exports the moved functions

**Step 4: Run focused tests to verify they still pass**

Run: `python -m pytest tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_direct_paths_and_research.py -q`

Expected: PASS

### Task 2: Split `message_runtime_parts/helpers.py` Into Grouped Modules

**Files:**
- Create: `kabot/agent/loop_core/message_runtime_parts/context_notes.py`
- Create: `kabot/agent/loop_core/message_runtime_parts/locale_and_memory.py`
- Create: `kabot/agent/loop_core/message_runtime_parts/observability.py`
- Create: `kabot/agent/loop_core/message_runtime_parts/query_shapes.py`
- Create: `kabot/agent/loop_core/message_runtime_parts/reference_resolution.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/helpers.py`
- Test: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_basics.py`
- Test: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py`
- Test: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_memory_durability.py`

**Step 1: Write the failing tests**

Add/confirm regression coverage for:
- answer-reference follow-up resolution
- memory recall and memory-fact injection
- filesystem/weather/context follow-up detection
- runtime observability events and locale resolution

**Step 2: Run tests to verify the characterization baseline**

Run: `python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_basics.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_memory_durability.py -q`

Expected: PASS before refactor, establishing the baseline.

**Step 3: Write minimal extraction**

- Move runtime event emission to `observability.py`
- Move locale/memory helpers to `locale_and_memory.py`
- Move contextual-note builders to `context_notes.py`
- Move follow-up and query-shape detectors to `query_shapes.py`
- Move assistant-answer/option reference resolvers to `reference_resolution.py`
- Keep `helpers.py` as a compact compatibility facade that re-exports the moved functions

**Step 4: Run focused tests to verify they still pass**

Run: `python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_basics.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_memory_durability.py -q`

Expected: PASS

### Task 3: Slim `execution_runtime.py` By Extracting Orchestration Subflows

**Files:**
- Create: `kabot/agent/loop_core/execution_runtime_parts/direct_flow.py`
- Create: `kabot/agent/loop_core/execution_runtime_parts/progress.py`
- Create: `kabot/agent/loop_core/execution_runtime_parts/tool_processing.py`
- Modify: `kabot/agent/loop_core/execution_runtime.py`
- Test: `tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py`
- Test: `tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_direct_paths_and_research.py`
- Test: `tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_tool_calls_and_skill_phases.py`

**Step 1: Write the failing tests**

Add/confirm regression coverage for:
- direct deterministic tool execution
- delivery verification recovery
- interrupt acknowledgments during long-running work
- tool call processing and idempotency preservation

**Step 2: Run tests to verify the characterization baseline**

Run: `python -m pytest tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_direct_paths_and_research.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_tool_calls_and_skill_phases.py -q`

Expected: PASS before refactor, establishing the baseline.

**Step 3: Write minimal extraction**

- Move status/draft/reasoning publishing helpers to `progress.py`
- Move direct `find/create/generate -> send` flow helpers to `direct_flow.py`
- Move tool-call loop support helpers to `tool_processing.py`
- Reduce `execution_runtime.py` to the public orchestration entrypoints plus slim local glue

**Step 4: Run focused tests to verify they still pass**

Run: `python -m pytest tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_direct_paths_and_research.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_tool_calls_and_skill_phases.py -q`

Expected: PASS

### Task 4: Slim `message_runtime.py` By Extracting Message-Building Subflows

**Files:**
- Create: `kabot/agent/loop_core/message_runtime_parts/continuity_flow.py`
- Create: `kabot/agent/loop_core/message_runtime_parts/context_assembly.py`
- Create: `kabot/agent/loop_core/message_runtime_parts/status_flow.py`
- Modify: `kabot/agent/loop_core/message_runtime.py`
- Test: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_basics.py`
- Test: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py`
- Test: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py`
- Test: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_memory_durability.py`

**Step 1: Write the failing tests**

Add/confirm regression coverage for:
- continuity-source prioritization
- committed action/coding follow-up continuation
- layered context-source metadata
- fast replies vs context-rich replies

**Step 2: Run tests to verify the characterization baseline**

Run: `python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_basics.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_memory_durability.py -q`

Expected: PASS before refactor, establishing the baseline.

**Step 3: Write minimal extraction**

- Move continuity-resolution chunks to `continuity_flow.py`
- Move context-note assembly and metadata packaging to `context_assembly.py`
- Move status/keepalive helpers to `status_flow.py`
- Reduce `message_runtime.py` to public entrypoints, early guards, and top-level orchestration

**Step 4: Run focused tests to verify they still pass**

Run: `python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_basics.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_memory_durability.py -q`

Expected: PASS

### Task 5: Split `tool_enforcement.py` Into Grouped Routing Modules

**Files:**
- Create: `kabot/agent/loop_core/tool_enforcement_parts/action_requests.py`
- Create: `kabot/agent/loop_core/tool_enforcement_parts/filesystem_paths.py`
- Create: `kabot/agent/loop_core/tool_enforcement_parts/history_routing.py`
- Create: `kabot/agent/loop_core/tool_enforcement_parts/required_tool_fallback.py`
- Create: `kabot/agent/loop_core/tool_enforcement_parts/__init__.py`
- Modify: `kabot/agent/loop_core/tool_enforcement.py`
- Test: `tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py`

**Step 1: Write the failing tests**

Add/confirm regression coverage for:
- action-tool inference for file/image/media requests
- relative path extraction and special directory handling
- history-based required tool inference
- deterministic fallback execution formatting

**Step 2: Run tests to verify the characterization baseline**

Run: `python -m pytest tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py -q`

Expected: PASS before refactor, establishing the baseline.

**Step 3: Write minimal extraction**

- Move path extraction and normalization helpers to `filesystem_paths.py`
- Move action/media request detection to `action_requests.py`
- Move history/tool selection logic to `history_routing.py`
- Move deterministic fallback execution helpers to `required_tool_fallback.py`
- Keep `tool_enforcement.py` as the thin public compatibility layer

**Step 4: Run focused tests to verify they still pass**

Run: `python -m pytest tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py -q`

Expected: PASS

### Task 6: Verify Broadly And Update Changelog

**Files:**
- Modify: `CHANGELOG.md`
- Test: `tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py`
- Test: `tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_direct_paths_and_research.py`
- Test: `tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_tool_calls_and_skill_phases.py`
- Test: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_basics.py`
- Test: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py`
- Test: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py`
- Test: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_memory_durability.py`
- Test: `tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py`
- Test: `tests/cli/test_agent_smoke_matrix.py`

**Step 1: Run the broad verification suite**

Run: `python -m pytest tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_direct_paths_and_research.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_tool_calls_and_skill_phases.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_basics.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_followup_reuse.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_memory_durability.py tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py tests/cli/test_agent_smoke_matrix.py -q`

Expected: PASS

**Step 2: Update the changelog**

Document that the runtime source was structurally split into grouped modules, with no intended behavior change, to improve maintainability while preserving continuity, tool selection, and evidence-based completion.

**Step 3: Optional real-agent smoke**

Run: `python -X utf8 -m kabot.cli.agent_smoke_matrix --no-default-cases --continuity-cases --memory-cases --delivery-cases --mcp-local-echo --json`

Expected: exit `0`
