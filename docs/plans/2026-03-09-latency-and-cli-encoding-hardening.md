# Latency And CLI Encoding Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce one-shot `first_response_ms` for lightweight temporal chats and harden CLI multilingual input handling across Windows, macOS, and Linux shells.

**Architecture:** Avoid the extra routing LLM call for obviously lightweight temporal/day-time queries by adding deterministic fast-route coverage in `IntentRouter`. Add a narrow CLI input normalization layer that preserves clean Unicode text but repairs common mojibake patterns when shells hand Python already-garbled argv text.

**Tech Stack:** Python, Typer, pytest, asyncio, subprocess smoke tests

---

### Task 1: Lock router fast-path behavior with failing tests

**Files:**
- Modify: `tests/agent/test_router.py`

**Step 1: Write the failing test**

- Add router tests asserting multilingual temporal queries (Indonesian, Chinese, Thai, Japanese) return `GENERAL` + `is_complex=False` without invoking provider classification.

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_router.py -q`

Expected: FAIL because the router still calls LLM classification for ambiguous temporal queries.

### Task 2: Lock CLI mojibake repair behavior with failing tests

**Files:**
- Modify: `tests/cli/test_console_encoding.py`
- Modify: `tests/cli/test_agent_skill_runtime.py`

**Step 1: Write the failing test**

- Add unit coverage for a CLI normalization helper that keeps clean Unicode unchanged but repairs common mojibake input such as mis-decoded Chinese/Thai/Japanese phrases.
- Add CLI invocation coverage proving normalized prompts still reach the agent/provider in repaired form.

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_console_encoding.py tests/cli/test_agent_skill_runtime.py -q`

Expected: FAIL because no repair helper exists yet.

### Task 3: Implement minimal runtime changes

**Files:**
- Modify: `kabot/agent/router.py`
- Modify: `kabot/utils/text_safety.py`
- Modify: `kabot/cli/commands_agent_command.py`

**Step 1: Write minimal implementation**

- Add a deterministic temporal-query fast path to `IntentRouter.route()`.
- Add a narrow `repair_common_mojibake_text()` helper in `kabot.utils.text_safety`.
- Normalize one-shot CLI `message` input before handing it to `AgentLoop`, without altering already-correct Unicode input.

**Step 2: Run focused tests**

Run: `pytest tests/agent/test_router.py tests/cli/test_console_encoding.py tests/cli/test_agent_skill_runtime.py -q`

Expected: PASS.

### Task 4: Verify cross-path behavior and real smoke

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Run broader verification**

Run: `pytest tests/agent tests/cli tests/gateway -q`

Expected: PASS.

**Step 2: Run real CLI smoke**

Run:
- `python -m kabot.cli.commands agent -m "hari apa sekarang? jawab singkat, pakai WIB ya." --no-markdown --logs`
- `python -m kabot.cli.commands agent -m "今天星期几？只回答一行。" --no-markdown --logs`
- `python -m kabot.cli.commands agent -m "デスクトップのbotフォルダの中、最初の5件だけ見せて。" --no-markdown --logs`

Expected:
- shorter `first_response_ms` for temporal one-shot turns,
- multilingual direct args remain readable,
- no regression in agent understanding on Windows-hosted smoke, with POSIX/macOS path semantics still covered by tests.
