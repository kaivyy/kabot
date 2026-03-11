# Filesystem Search And Delivery AI-Driven Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Kabot handle requests like "periksa file di server/PC/Mac lalu kirim file X ke chat ini" with grounded, AI-driven tool execution that can search, verify, and deliver real local files without hallucinating completion.

**Architecture:** Add a generic filesystem search primitive (`find_files`) alongside existing filesystem tools, teach the runtime to infer search-vs-delivery intent without hardcoding per domain, and add execution-time delivery evidence guards so multi-step flows such as `find -> verify -> message(files=...)` must actually happen before Kabot can claim success.

**Tech Stack:** Python, pytest, async tool runtime, session/message metadata, filesystem tools, message delivery tool

---

### Task 1: Add failing tool tests for filesystem search and same-channel delivery

**Files:**
- Modify: `tests/agent/tools/test_filesystem.py`
- Modify: `tests/tools/test_tool_i18n_errors.py`

**Step 1: Write the failing tests**

Add coverage for:
- `FindFilesTool` returning matching files and folders under an allowed root
- `FindFilesTool` respecting path restriction and result limit
- `MessageTool` clearly supporting current-channel file attachments when context is already set

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/agent/tools/test_filesystem.py tests/tools/test_tool_i18n_errors.py -q`

Expected: FAIL because `find_files` does not exist yet and message-tool expectations are not updated.

### Task 2: Add failing routing tests for search-file and send-file requests

**Files:**
- Modify: `tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py`
- Modify: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py`

**Step 1: Write the failing tests**

Add coverage for:
- `cari file report.pdf` inferring `find_files`
- `kirim file C:\\...\\report.pdf ke chat ini` inferring `message`
- combined requests like `cari file report.pdf lalu kirim ke chat ini` staying in AI-driven action mode instead of direct single-tool fallback
- committed-action follow-ups around file delivery reusing the original delivery request

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py -q`

Expected: FAIL because the runtime cannot yet search files or explicitly enforce delivery evidence.

### Task 3: Add failing execution tests for delivery evidence guards

**Files:**
- Modify: `tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py`
- Modify: `tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_direct_paths_and_research.py`

**Step 1: Write the failing tests**

Add coverage for:
- direct fallback `find_files`
- direct fallback `message` when the request contains an explicit file path and current chat context
- action requests that mention sending/uploading files retrying or failing if no `message` tool execution happened
- action requests that use `message(files=...)` succeeding once delivery evidence exists

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_direct_paths_and_research.py -q`

Expected: FAIL because current execution guards only verify tool usage/artifact existence, not attachment delivery.

### Task 4: Implement the generic search and delivery primitives

**Files:**
- Modify: `kabot/agent/tools/filesystem.py`
- Modify: `kabot/agent/tools/message.py`
- Modify: `kabot/agent/tools/tool_policy.py`
- Modify: `kabot/agent/loop.py`

**Step 1: Write minimal implementation**

Add:
- `FindFilesTool`
- registration in the default tool registry
- policy-group inclusion under `@fs`
- clearer `message` tool description for same-channel file delivery

Keep search generic enough for workspace, server, PC, or Mac roots, while still honoring `allowed_dir` restrictions when enabled.

**Step 2: Run focused tests**

Run: `python -m pytest tests/agent/tools/test_filesystem.py tests/tools/test_tool_i18n_errors.py -q`

Expected: PASS

### Task 5: Implement routing and deterministic fallback

**Files:**
- Modify: `kabot/agent/loop_core/tool_enforcement.py`
- Modify: `kabot/agent/loop_core/message_runtime.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/helpers.py`
- Modify: `kabot/agent/loop_core/execution_runtime_parts/helpers.py`

**Step 1: Write minimal implementation**

Teach the runtime to:
- infer `find_files` for direct filesystem-search asks
- infer `message` for explicit send-file requests with a concrete path
- keep compound `find + send` requests AI-driven in the agent loop
- store delivery-related continuity notes and last execution context without parser lock-in

**Step 2: Run focused tests**

Run: `python -m pytest tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py -q`

Expected: PASS

### Task 6: Implement delivery evidence enforcement and verify regressions

**Files:**
- Modify: `kabot/agent/loop_core/execution_runtime.py`
- Modify: `CHANGELOG.md`

**Step 1: Write minimal implementation**

Add execution-time guards so requests that explicitly require delivery/attachment/file sending must either:
- execute `message` with real files, or
- fail honestly with a concrete blocker.

Do not allow plain-text "terkirim/sudah dikirim" claims without delivery evidence.

**Step 2: Run broader verification**

Run: `python -m pytest tests/agent/tools/test_filesystem.py tests/tools/test_tool_i18n_errors.py tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_budget_hints.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_simple_and_guards.py tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_direct_paths_and_research.py -q`

Expected: PASS

**Step 3: Run real-agent smoke**

Run: `python -X utf8 -m kabot.cli.commands agent -m "cari file CHANGELOG.md di workspace lalu kirim ke chat ini" --session cli:smoke-send-file-v1 --no-markdown --logs`

Expected: the agent either finds and sends the file through `message(files=...)`, or fails honestly with a specific blocker instead of hallucinating delivery.
