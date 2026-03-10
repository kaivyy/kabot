# OpenClaw -> Kabot 2026.3.8 Parity Design

This document details the architectural approach for bringing Kabot to full parity with the most impactful features from the OpenClaw 2026.3.7 and 2026.3.8 changelog.

## Goal
Implement Military-Grade Chat Continuity, Automatic Config Backups, and TUI/Model Enhancements in Kabot.

## Phase 1: Military-Grade Chat Continuity & Failover Queue

### Problem
When Kabot restarts or experiences a network drop, pending messages can be lost, and provider timeouts (e.g., 402 Payment Required vs. transient network errors) are grouped too aggressively, leading to false rate-limit lockouts. In OpenClaw, this is handled via `node.pending.enqueue` and explicit transient tracking.

### Architecture Updates
- **Dormant Session Queue:** Implement a lightweight in-memory (or SQLite backed) queue for `pending_work`. If a request is running and the connection drops, the queue holds the work until the session resumes.
- **Failover Classification:** Modify the LiteLLM/API exception handlers in `kabot.providers.litellm_provider` to explicitly separate HTTP 429/402 (billing/hard rate limit) from HTTP 499 (Client Closed/Timeout). 
- **Data Flow:** Inbound Message -> Enqueue -> Process -> If Fail (Transient) -> Keep in Queue -> Re-attempt on wakeup.

## Phase 2: Configuration Backup & Safety System

### Problem
Users risk losing their configured environments (`.env`, `providers.json`, local DB state) during destructive updates or OS-level faults. OpenClaw introduced `openclaw backup create --only-config` and fails closed on invalid configs.

### Architecture Updates
- **CLI Commands:** Add `kabot backup create [--only-config]` and `kabot backup verify` to the main CLI.
- **Backup Mechanism:** Use Python's `zipfile` or `shutil.make_archive` to atomically snapshot the `~/.kabot` or local config directory. Ensure sensitive data (like `.env`) is included but appropriately warned in the UI.
- **Fail-Closed Config:** Update `kabot.core.config.load()` to throw a hard fatal error (and exit with a clear message) if the JSON/YAML configuration is malformed, rather than falling back to empty/default permissive states.

## Phase 3: TUI Intelligence & Advanced Model Integration

### Problem
The interactive CLI (TUI) currently requires manual setup for workspace-bound agents. Additionally, new model standards (GPT-5.4 1M context, Grok preference, Brave LLM-Context) are supported in OpenClaw but absent or manual in Kabot.

### Architecture Updates
- **Workspace Auto-Detection:** When `kabot agent` is run, check `os.getcwd()` for a local `.kabot_workspace` or similar marker. If found, automatically bind the session to that agent ID instead of defaulting to `main`.
- **Model Registry Updates:**
  - Update `openai/gpt-5.4` fallback tokens (to 128k output / 1M input).
  - Inject the Brave Search LLM-context mode into the `web_search` tool parameters if the Brave provider is selected.
  - Fix any parallel tool-call crashes by standardizing the `tool_choice` payload specifically for providers like `MiniMax` or `xAI`.

## Phase 4: Plugin/Hooks Architecture (2026.3.7 Features)

### Problem
OpenClaw 2026.3.7 added huge integration upgrades: a ContextEngine plugin slot (allowing drop-in replacement of context management), persistent channel bindings for ACP topics (so Slack/Telegram threads survive restarts), and advanced Markdown parsing guardrails. Kabot needs these to extend easily.

### Architecture Updates
- **Pluggable Context Engine:** Introduce an interface `ContextEngine` in Kabot that plugins can subclass. Wrap the existing token compaction inside `LegacyContextEngine`. This hooks into the session `assemble` and `compact` lifecycles.
- **Persistent Channel Bindings:** Instead of relying strictly on runtime thread IDs, save active bot-bound threads into `channels.sqlite` or `~/.kabot/bindings.json` so that they can be resumed natively by ACP agents even if Kabot restarts.
- **Fail-safe Markdown Render:** Add crash guards (`try/except`) around Control UI/Webchat markdown parsing so malformed LLM outputs don't crash the frontend.

## Verification & Testing
1. **Phase 1:** Simulate a network drop mid-request using a mock LiteLLM server. Ensure the message remains in the queue and resumes.
2. **Phase 2:** Corrupt `provider.json` and verify Kabot crashes cleanly rather than starting an open gateway.
3. **Phase 3:** Launch `kabot agent` inside a configured folder and verify the session ID infers the local agent context.
4. **Phase 4:** Restart Kabot mid-thread on a Telegram binding and ensure the bot still responds to the topic natively.

---
*Created during the Brainstorming phase via user request "semuanya" against the 2026.3.8 OpenClaw Changelog.*
