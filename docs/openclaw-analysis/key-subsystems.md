# OpenClaw Key Subsystems

This document details the critical subsystems that power OpenClaw.

## 1. The Agent Runtime (`src/agents/pi-embedded-runner`)

The runtime is responsible for the "Think-Act" loop. It is designed to be resilient and self-correcting.

### Core Features:
- **Context Window Guard:** Automatically checks if the conversation history exceeds the model's context window. If it does, it triggers auto-compaction.
- **Auto-Compaction:** Summarizes older messages in the session history to free up tokens without losing context. Implemented in `compact.ts`.
- **Auth Profile Rotation:** If an API key fails (e.g., rate limit), it automatically tries the next available key/profile. Implemented in `model-auth.ts`.
- **Model Fallback:** If the primary model fails repeatedly, it switches to a configured fallback model.

## 2. The Gateway (`src/gateway`)

The Gateway is the central nervous system. It decouples the CLI and other interfaces from the agent logic.

### Architecture:
- **JSON-RPC:** All communication happens via a structured JSON-RPC protocol.
- **Scopes & Auth:** Each connection has associated scopes (`operator.read`, `operator.write`). `authorizeGatewayMethod` enforces these permissions strictly.
- **Method Dispatch:** Requests are routed to handlers in `server-methods/`. This allows for easy extensibility.

## 3. Subagent Management (`src/agents/subagent-registry.ts`)

OpenClaw treats subagents as first-class citizens.

### Workflow:
1.  **Spawn:** Parent agent calls `sessions.spawn`.
2.  **Register:** Subagent run is registered in `subagentRuns` map and persisted to disk.
3.  **Execute:** Subagent runs (potentially in a separate process or thread).
4.  **Wait:** Parent agent calls `agent.wait` (via Gateway) to pause and wait for the child.
5.  **Announce:** Upon completion, the subagent "announces" its result back to the parent via the Gateway.

## 4. Tooling System (`src/agents/openclaw-tools.ts`)

Tools are the primary way agents interact with the world.

### Design:
- **Unified Factory:** `createOpenClawTools` creates all tools at once, ensuring consistent configuration.
- **Policy Enforcement:** Tools are filtered based on permission policies (Global, Agent-specific, User-specific).
- **Sandboxing:** Subagents can run in sandboxed environments (Docker/Firecracker) with restricted tool access.

## 5. Directives System (`src/auto-reply/reply/get-reply-directives.ts`)

OpenClaw controls agent behavior via "Inline Directives" in messages.
-   **Parsing**: Parses commands like `/think`, `/verbose`, `/elevated` from the message body.
-   **State**: Modifies the `SessionEntry` state (e.g., enabling verbose mode for a session).
-   **Triggers**: Determines if the message should trigger a reply (e.g., mentions in groups vs. every message in DMs).

## 6. Heartbeat & Cron (`src/infra/heartbeat-runner.ts`)

The system maintains a heartbeat to keep agents alive and perform scheduled tasks.
-   **Smart Scheduling**: Respects `activeHours` to avoid running when not needed.
-   **Event Injection**: Injects "System Events" (like cron job results or long-running command completions) into the agent's context via `EXEC_EVENT_PROMPT`.
-   **Health Checks**: Can be configured to ping external services to report status.
