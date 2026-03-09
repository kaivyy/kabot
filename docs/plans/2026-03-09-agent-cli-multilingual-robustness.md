# Agent CLI Multilingual Robustness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Validate the real `kabot agent` CLI against multilingual, noisy, and odd conversational prompts, then fix only the verified routing/context bugs without making the assistant rigid.

**Architecture:** Use the real `kabot` CLI entrypoint with persisted one-shot sessions to simulate natural follow-up turns. Classify failures by runtime layer first, then add targeted regression tests before changing implementation.

**Tech Stack:** Typer CLI, AgentLoop runtime, pytest, PowerShell/Python subprocess smoke harness

---

### Task 1: Audit the real CLI entrypoint

**Files:**
- Inspect: `pyproject.toml`
- Inspect: `kabot/cli/commands.py`
- Inspect: `kabot/cli/commands_agent_command.py`
- Inspect: `kabot/config/loader.py`

**Step 1: Verify the supported entrypoint**

Run: `kabot --help`
Expected: help text renders and includes the `agent` command

**Step 2: Verify runtime environment**

Run: `kabot auth status`
Expected: at least one usable provider shows as configured

**Step 3: Record any entrypoint mismatch**

Run: `python -m kabot.cli.commands --help`
Expected: if it fails, record it as a separate CLI-facade issue and continue testing through `kabot`

---

### Task 2: Run multilingual real-agent smoke tests

**Files:**
- Create: temporary inline harness only
- Inspect: `kabot/agent/loop_core/message_runtime.py`
- Inspect: `kabot/agent/loop_core/execution_runtime.py`

**Step 1: Build a prompt matrix**

Cover:
- Indonesian casual/slang
- English direct
- Chinese
- Japanese
- Thai
- mixed code-switching
- odd punctuation / abbreviations / sarcasm

**Step 2: Run one-shot prompts through the real CLI**

Run pattern:
`kabot agent -m "<prompt>" --session "<session>" --no-markdown`

Expected: agent responds naturally in the same language, does not crash, and does not route unrelated meta/correction turns to the web.

**Step 3: Run follow-up session probes**

Use repeated `--session` values for:
- temporal correction
- memory commit follow-up
- filesystem continuation

Expected: follow-up answers reflect prior turns within the same session.

---

### Task 3: Classify failures before fixing

**Files:**
- Inspect: `kabot/agent/context.py`
- Inspect: `kabot/agent/semantic_intent.py`
- Inspect: `kabot/agent/loop_core/message_runtime_parts/helpers.py`
- Inspect: `kabot/agent/loop_core/tool_enforcement.py`

**Step 1: Group each failure**

Buckets:
- time/date context
- follow-up memory continuity
- wrong deterministic tool routing
- live-search latch leakage
- multilingual naturalness only

**Step 2: Keep only reproducible failures**

Expected: each fix candidate has a concrete prompt transcript that reproduces it at least once.

---

### Task 4: Fix only verified bugs with TDD

**Files:**
- Modify only the exact runtime/helper files implicated by the reproduction
- Test: `tests/agent/...`
- Test: `tests/cli/...` if CLI-specific

**Step 1: Write failing regression tests**

Expected: new tests fail on the verified bug path

**Step 2: Implement minimal fix**

Expected: behavior changes only for the reproduced failure class

**Step 3: Re-run targeted tests**

Run: `pytest <targeted test paths> -q`
Expected: green

---

### Task 5: Re-run real-agent smoke tests and full verification

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Re-run the failing real-agent prompts**

Expected: the same prompts now behave correctly

**Step 2: Run broad verification**

Run: `pytest tests/agent tests/cli tests/gateway -q`
Expected: all pass

**Step 3: Document findings**

Update changelog with:
- what failed in real-agent CLI
- what was fixed
- what remains intentionally AI-driven
