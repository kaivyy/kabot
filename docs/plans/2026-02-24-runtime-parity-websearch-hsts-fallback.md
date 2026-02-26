# Runtime Parity: Kimi Web Search, Gateway HSTS, and Auto Fallback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add high-impact runtime parity features so Kabot is more resilient on provider auth failure, supports Kimi-backed web search, and can emit strict transport headers when deployed behind HTTPS.

**Architecture:** Extend existing config models to carry new settings, wire them through setup/runtime constructors, and implement behavior in focused runtime components (`web_search`, `webhook_server`, CLI runtime fallback resolver). Keep changes backward compatible and covered by targeted tests.

**Tech Stack:** Python 3.13, Pydantic models, aiohttp, httpx, pytest, Typer CLI setup flow.

---

### Task 1: Add Kimi provider support to `web_search` tool (config + runtime)

**Files:**
- Modify: `kabot/config/schema.py`
- Modify: `kabot/agent/tools/web_search.py`
- Modify: `kabot/agent/loop.py`
- Modify: `kabot/agent/subagent.py`
- Modify: `kabot/cli/wizard/sections/tools_gateway_skills.py`
- Modify: `kabot/cli/wizard/ui.py`
- Test: `tests/agent/tools/test_web_search.py` (new)

**Step 1: Write failing tests first (RED)**
- Add tests for:
  - Provider selection prefers configured `provider="kimi"` when Kimi key exists.
  - Auto-detection can choose Kimi when premium keys available.
  - Kimi HTTP response parsing returns text and sources.
  - Fallback behavior moves to Brave when Kimi request fails and Brave key exists.

**Step 2: Run test to confirm failure**
- Run: `pytest tests/agent/tools/test_web_search.py -q`
- Expected: failing tests because Kimi provider path does not exist yet.

**Step 3: Implement minimal code (GREEN)**
- Extend `WebSearchConfig` with `kimi_api_key` and `kimi_model`.
- Extend `WebSearchTool` to support `provider="kimi"` and `KIMI_API_KEY`/`MOONSHOT_API_KEY`.
- Add `_search_kimi()` request/parse path.
- Wire new config fields in `AgentLoop` tool registration.
- Wire subagent web search constructor to include config keys.
- Add setup prompts for Kimi key and summary label in wizard UI.

**Step 4: Run tests to confirm pass**
- Run: `pytest tests/agent/tools/test_web_search.py -q`
- Expected: all tests pass.

---

### Task 2: Add optional Gateway HSTS support (config + server header middleware)

**Files:**
- Modify: `kabot/config/schema.py`
- Modify: `kabot/gateway/webhook_server.py`
- Modify: `kabot/cli/commands.py`
- Modify: `kabot/cli/wizard/sections/tools_gateway_skills.py`
- Test: `tests/gateway/test_webhooks.py`
- Test: `tests/cli/test_setup_wizard_gateway.py`

**Step 1: Write failing tests first (RED)**
- Add tests for:
  - HSTS header is set when enabled and request is HTTPS-forwarded.
  - Header is not set when disabled.
  - Setup wizard can set HSTS enable flag and custom value.

**Step 2: Run tests to confirm failure**
- Run: `pytest tests/gateway/test_webhooks.py tests/cli/test_setup_wizard_gateway.py -q`
- Expected: failures because config and middleware are missing.

**Step 3: Implement minimal code (GREEN)**
- Add gateway HTTP security headers config model:
  - `gateway.http.security_headers.strict_transport_security` (bool)
  - `gateway.http.security_headers.strict_transport_security_value` (string)
- In `WebhookServer`, add middleware that conditionally sets `Strict-Transport-Security` for HTTPS/forwarded HTTPS requests.
- Pass config values from CLI gateway startup into `WebhookServer`.
- Add wizard prompts under gateway section to configure HSTS.

**Step 4: Run tests to confirm pass**
- Run: `pytest tests/gateway/test_webhooks.py tests/cli/test_setup_wizard_gateway.py -q`
- Expected: all pass.

---

### Task 3: Improve runtime model fallback for OpenAI auth expiry cases

**Files:**
- Modify: `kabot/cli/commands.py`
- Modify: `kabot/cli/wizard/sections/model_auth.py`
- Test: `tests/cli/test_provider_runtime_config.py`
- Test: `tests/cli/test_setup_wizard_default_model.py`

**Step 1: Write failing tests first (RED)**
- Add tests for:
  - Runtime provider creation auto-injects Groq fallback when primary is OpenAI/OpenAI-Codex and no explicit fallbacks are configured but Groq credentials exist.
  - Post-login OpenAI default chain appends Groq fallback when Groq credentials are present.

**Step 2: Run test to confirm failure**
- Run: `pytest tests/cli/test_provider_runtime_config.py tests/cli/test_setup_wizard_default_model.py -q`
- Expected: failing tests because current behavior requires explicit fallback config.

**Step 3: Implement minimal code (GREEN)**
- Add helper in CLI runtime resolver to detect provider credentials and build implicit fallback list.
- Merge implicit fallback list into runtime fallback chain only when explicit chain is empty.
- Update wizard post-login default chain to include Groq fallback if available.

**Step 4: Run tests to confirm pass**
- Run: `pytest tests/cli/test_provider_runtime_config.py tests/cli/test_setup_wizard_default_model.py -q`
- Expected: all pass.

---

### Task 4: Documentation and changelog updates

**Files:**
- Modify: `HOW-TO-USE.md`
- Modify: `CHANGELOG.md`

**Step 1: Update user documentation**
- Add:
  - How to configure Kimi as web search provider.
  - How to enable Gateway HSTS and when to use it.
  - How automatic OpenAI-to-Groq runtime fallback behaves.

**Step 2: Update changelog**
- Add `Unreleased` bullets for web search provider expansion, gateway security headers, and runtime fallback resilience.

**Step 3: Verify docs formatting**
- Run: `python -m pytest tests/cli/test_setup_wizard_default_model.py -q`
- Expected: unchanged docs should not affect tests; this acts as a quick smoke check after docs + code touches.

---

### Task 5: Final verification bundle

**Files:**
- No additional file edits.

**Step 1: Run focused verification suite**
- Run:
  - `pytest tests/agent/tools/test_web_search.py -q`
  - `pytest tests/gateway/test_webhooks.py tests/cli/test_setup_wizard_gateway.py -q`
  - `pytest tests/cli/test_provider_runtime_config.py tests/cli/test_setup_wizard_default_model.py -q`

**Step 2: Run combined command**
- Run: `pytest tests/agent/tools/test_web_search.py tests/gateway/test_webhooks.py tests/cli/test_setup_wizard_gateway.py tests/cli/test_provider_runtime_config.py tests/cli/test_setup_wizard_default_model.py -q`
- Expected: all pass.

**Step 3: Summarize**
- Report implemented behavior, updated docs/changelog entries, and verification outputs.
