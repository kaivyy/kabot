# OpenClaw Bootstrap Reply Parity Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bring Kabot closer to OpenClaw for first-run onboarding, reply-aware Telegram delivery, and capability handoff when a requested integration is not fully available.

**Architecture:** Use workspace bootstrap files as the source of truth for onboarding, keep Telegram reply semantics in the channel transport instead of prompt magic, and route missing-breadth capability requests toward skill creation/handoff without pretending the built-in capability is already complete.

**Tech Stack:** Python, pytest, python-telegram-bot, existing Kabot session/context runtime.

---

### Task 1: Bootstrap workspace parity

**Files:**
- Modify: `kabot/utils/workspace_templates.py`
- Modify: `kabot/agent/context.py`
- Modify: `kabot/utils/bootstrap_parity.py`
- Modify: `kabot/config/schema.py`
- Test: `tests/utils/test_workspace_templates.py`
- Test: `tests/agent/test_context_builder.py`

**Step 1: Write the failing tests**
- Extend workspace template tests to expect `IDENTITY.md` and `BOOTSTRAP.md` creation for new workspaces.
- Add a context-builder test proving `BOOTSTRAP.md` content is injected when present.

**Step 2: Run tests to verify they fail**
Run: `python -m pytest tests/utils/test_workspace_templates.py tests/agent/test_context_builder.py -q`
Expected: FAIL because new bootstrap files are not yet created or loaded.

**Step 3: Write minimal implementation**
- Add default templates for `IDENTITY.md` and `BOOTSTRAP.md`.
- Include `BOOTSTRAP.md` in the context bootstrap file list.
- Update bootstrap parity defaults/schema so doctor/setup does not treat the new files as out-of-band.

**Step 4: Run tests to verify they pass**
Run: `python -m pytest tests/utils/test_workspace_templates.py tests/agent/test_context_builder.py -q`
Expected: PASS.

### Task 2: Telegram /start grounded onboarding

**Files:**
- Modify: `kabot/channels/telegram.py`
- Test: `tests/channels/test_telegram_channel.py` (create if missing)

**Step 1: Write the failing tests**
- Add a test showing `/start` on a workspace with `BOOTSTRAP.md` replies with onboarding-style guidance, not the generic “Hi, I'm kabot” text.
- Add a test showing `/start` on a workspace without `BOOTSTRAP.md` falls back to the normal welcome.

**Step 2: Run tests to verify they fail**
Run: `python -m pytest tests/channels/test_telegram_channel.py -q`
Expected: FAIL because current `/start` is static.

**Step 3: Write minimal implementation**
- Teach Telegram `/start` to inspect the configured workspace.
- If `BOOTSTRAP.md` exists, reply with a concise onboarding prompt derived from bootstrap state.
- Otherwise keep the current generic welcome.

**Step 4: Run tests to verify they pass**
Run: `python -m pytest tests/channels/test_telegram_channel.py -q`
Expected: PASS.

### Task 3: Reply-aware Telegram delivery

**Files:**
- Modify: `kabot/channels/telegram.py`
- Test: `tests/channels/test_telegram_channel.py`

**Step 1: Write the failing tests**
- Add a test proving a normal outbound message with `reply_to` uses Telegram `reply_to_message_id`.
- Add a test proving outbound document sends preserve the same reply target.

**Step 2: Run tests to verify they fail**
Run: `python -m pytest tests/channels/test_telegram_channel.py -q`
Expected: FAIL because current send path ignores `msg.reply_to`.

**Step 3: Write minimal implementation**
- Thread `msg.reply_to` through `send_message` and `send_document` calls in the Telegram channel.
- Keep progress/status messages unchanged unless explicitly needed.

**Step 4: Run tests to verify they pass**
Run: `python -m pytest tests/channels/test_telegram_channel.py -q`
Expected: PASS.

### Task 4: Capability handoff for Meta Threads style requests

**Files:**
- Modify: `kabot/agent/loop_core/message_runtime_parts/process_flow.py`
- Modify: `kabot/agent/loop_core/message_runtime_parts/context_notes.py`
- Test: `tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_skill_workflows.py`
- Test: `tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py`

**Step 1: Write the failing tests**
- Add a regression showing a request like `bisakah bikin skills untuk koneksi ke meta threads` enters skill-creation/handoff instead of sounding like the built-in Meta Graph tool already solves everything.
- Add a regression showing narrower requests that the built-in tool can satisfy still route normally.

**Step 2: Run tests to verify they fail**
Run: `python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_skill_workflows.py tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py -q`
Expected: FAIL because current routing does not distinguish breadth of capability strongly enough.

**Step 3: Write minimal implementation**
- Add a small heuristic that treats “bikin skill / full connector / official API / mentions + scheduler + insights” as a skill-creation request.
- Keep the existing built-in Meta Graph lane for direct publishing actions.

**Step 4: Run tests to verify they pass**
Run: `python -m pytest tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_skill_workflows.py tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py -q`
Expected: PASS.

### Task 5: Focused verification and docs note

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Run focused verification**
Run:
`python -m pytest tests/utils/test_workspace_templates.py tests/agent/test_context_builder.py tests/channels/test_telegram_channel.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_skill_workflows.py tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py -q`
Expected: PASS.

**Step 2: Update changelog**
- Add a short note covering bootstrap onboarding parity, Telegram reply-aware sends, and Meta Threads capability handoff.

**Step 3: Commit**
```bash
git add kabot/utils/workspace_templates.py kabot/agent/context.py kabot/utils/bootstrap_parity.py kabot/config/schema.py kabot/channels/telegram.py kabot/agent/loop_core/message_runtime_parts/process_flow.py kabot/agent/loop_core/message_runtime_parts/context_notes.py tests/utils/test_workspace_templates.py tests/agent/test_context_builder.py tests/channels/test_telegram_channel.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_skill_workflows.py tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py CHANGELOG.md docs/plans/2026-03-12-openclaw-bootstrap-reply-parity-implementation.md
git commit -m "feat: add bootstrap and reply parity improvements"
```
