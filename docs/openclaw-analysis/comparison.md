# OpenClaw vs. Kabot: Architectural Comparison

This document highlights the key architectural and feature differences between the analyzed OpenClaw codebase (`src/`) and the current state of Kabot.

## 1. Core Architecture

| Feature | OpenClaw | Kabot | Gap / Action Item |
| :--- | :--- | :--- | :--- |
| **System Model** | **Distributed**: Agents, CLI, and Gateway are distinct, loosely coupled components communicating via JSON-RPC. | **Monolithic**: CLI-first Python application. Components (Cron, Gateway) are tightly integrated modules. | **Low**: Monolith is fine for now. Consider decoupling if scaling to multiple machines. |
| **Orchestration** | **Event-Driven**: `dispatch-from-config.ts` acts as a central orchestrator, routing messages based on complex rules (triggers, DMs). | **Poller/Webhook**: Relies on direct polling or basic webhook endpoints. | **Medium**: Need a central `Dispatcher` service to unify logic for "Who handles this message?". |
| **Input Layer** | **Input Adaptors**: dedicated "Monitors" (e.g., `monitorWebInbox`) that normalize raw events into a standard `MsgContext`. | **Direct Integration**: Handlers likely parse raw payloads directly. | **High**: Adopt "Input Adaptor" pattern to strictly separate channel protocol details from agent logic. |

## 2. Agent Runtime ("The Brain")

| Feature | OpenClaw | Kabot | Gap / Action Item |
| :--- | :--- | :--- | :--- |
| **Context Mgmt** | **Auto-Compaction**: Automatically summarizes/truncates history when near token limits (`active-context.ts`). | **Basic**: Appends messages. Manual pruning or FIFO. | **High**: Implement `ContextGuard` and `Compactor` to prevent crashes on long conversations. |
| **Directives** | **Inline**: Parses commands like `/think`, `/verbose` on one line. Dynamic behavior per-message. | **Static**: Config-driven. | **High**: Implement `DirectiveParser` to allow power-user control over agent behavior in real-time. |
| **Resilience** | **Auth Rotation**: Automatically tries next API key on 429/401 errors. | **Single Key**: Fails if key is invalid/rate-limited. | **Medium**: Implement `AuthManager.rotate_key()` for production reliability. |
| **Fallback** | **Model Cascading**: Falls back to cheaper/dumber models if the primary fails. | **Fixed**: Uses configured model. | **Low**: Nice to have for cost/reliability. |

## 3. System Internals

| Feature | OpenClaw | Kabot | Gap / Action Item |
| :--- | :--- | :--- | :--- |
| **Heartbeat** | **Injective**: Injects cron results and long-running command outputs into the agent's stream (`EXEC_EVENT_PROMPT`). | **Trigger-based**: Cron triggers a standard task. | **Medium**: Adopt "Event Injection" to allow the agent to *react* to background tasks naturally. |
| **Health** | **Doctor**: `openclaw doctor` checks dependencies, config health, and runs migrations. | **Basic**: `kabot check` (planned). | **High**: Implement `DoctorService` to reduce support burden. |
| **Updates** | **Self-Update**: CLI wrapper manages git pull + rebuild. | **Manual**: User runs `git pull`. | **Medium**: Implement `UpdateService` for smoother upgrades. |
| **Plugins** | **Hooks System**: `src/plugins` allows interception of every lifecycle event. | **None**: Planned Phase 6. | **High**: Essential for community extensions. |

## 4. Subagents

| Feature | OpenClaw | Kabot | Gap / Action Item |
| :--- | :--- | :--- | :--- |
| **Isolation** | **Process/Sandboxed**: Can run in Docker/Firecracker. | **Thread/Process**: `SubagentManager` uses local processes. | **Medium**: Add Docker sandbox support for safety. |
| **Persistence** | **Disk-Backed**: Subagent runs are saved to JSON, resuming after restart. | **In-Memory**: Lost on restart? | **High**: Ensure subagent state is persisted to disk (`subagents.json`). |

## Summary of Recommendations

1.  **Immediate (Phase 8)**: Implement **Directives** (CommandRouter) and **Doctor/Status** services.
2.  **Short Term**: Refactor Input Layer to use **Input Adaptors** (`MsgContext` normalization).
3.  **Short Term**: Implement **Auto-Compaction** for context management.
4.  **Medium Term**: Build the **Plugin System** (hooks) to allow extensibility without core changes.
