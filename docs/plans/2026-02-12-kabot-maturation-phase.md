# Kabot Maturation Phase Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform Kabot into an enterprise-grade AI Gateway with Webhook support, Isolated Cron sessions, Browser automation, and Security auditing.

**Architecture:** 
1. **Webhooks**: Add an `aiohttp` server layer to the existing Gateway to accept POST requests.
2. **Isolation**: Use a prefix-based session key (e.g., `background:<id>`) to run tasks without polluting the main user transcript.
3. **Browser**: Integrate `playwright` as a new tool in `kabot/agent/tools/`.
4. **Security**: Implement a static analysis command in `kabot/cli/commands.py`.

**Tech Stack:** Python 3.11+, aiohttp, Playwright, pytest.

---

## Task 1: Webhook Ingress Infrastructure

**Files:**
- Create: `kabot/gateway/webhook_server.py`
- Modify: `kabot/cli/commands.py` (gateway command)
- Test: `tests/gateway/test_webhooks.py`

**Step 1: Write failing test for webhook endpoint**
```python
import pytest
import aiohttp

@pytest.mark.asyncio
async def test_webhook_trigger_success():
    # Mocking gateway to accept webhooks
    url = "http://localhost:18790/webhooks/trigger"
    payload = {"event": "test", "message": "hello"}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            assert resp.status == 202
```

**Step 2: Implement aiohttp Webhook Server**
Build a basic server that can be run alongside the existing gateway.

**Step 3: Integrate into `kabot gateway`**
Modify the `gateway` command to start the HTTP server.

---

## Task 2: Background Task Isolation

**Files:**
- Modify: `kabot/agent/loop.py`
- Modify: `kabot/cron/service.py`

**Step 1: Create isolated session logic**
Implement logic to skip `SessionManager.save_transcript()` if the session ID starts with `background:`.

**Step 2: Update Cron to use isolated IDs**
Update `CronService` to generate `background:cron:<id>` session keys.

**Step 3: Verify with tests**
Ensure cron tasks don't appear in `~/.kabot/workspace/memory/conversations/`.

---

## Task 3: Browser Automation (Playwright)

**Files:**
- Create: `kabot/agent/tools/browser.py`
- Modify: `kabot/agent/loop.py` (register tool)

**Step 1: Install Playwright dependency**
Add `playwright` to `pyproject.toml` or installation steps.

**Step 2: Implement BrowserTool**
Methods: `launch`, `goto`, `screenshot`, `get_content`.

**Step 3: Create tests for BrowserTool**
Test fetching a simple page and taking a screenshot.

---

## Task 4: Security Audit Tool

**Files:**
- Create: `kabot/utils/security_audit.py`
- Modify: `kabot/cli/commands.py` (add `security audit` command)

**Step 1: Implement Secret Scanner**
Regex-based scanner for `sk-`, `AIza`, etc., in the workspace.

**Step 2: Implement Permission Checker**
Check for overly permissive file modes (e.g., 777) in `.kabot` directory.

**Step 3: Add CLI Command**
`kabot security audit` outputting a Rich Table of findings.

---

## Task 5: Final Integration

**Step 1: Run Full Suite**
Execute all tests (60+ expected).

**Step 2: Manual Verification**
- Trigger a webhook via `curl`.
- Check if cron runs quietly.
- Run `kabot security audit`.
