# OpenClaw Implementation Patterns

This document describes the key implementation patterns used in the OpenClaw codebase.

## Error Handling

OpenClaw uses a sophisticated error handling system, centered around `FailoverError`.

### Key Components:
- **`FailoverError`**: A custom error class that wraps underlying errors (e.g., API failures) and includes metadata like `provider`, `model`, and `reason`.
- **Classification**: Errors are classified into categories like `rate_limit`, `billing`, `context_overflow`, etc., using regex matching (`classifyFailoverReason` in `pi-embedded-helpers.ts`).
- **Recovery**: The `runEmbeddedPiAgent` loop catches these errors and decides whether to retry (e.g., rate limit), failover (e.g., auth failure), or abort.

## State Management

OpenClaw uses a file-based state management system for simplicity and portability.

### Session Stores:
- **Structure**: Each session is a JSON file in the `.openclaw/sessions` directory.
- **Content**: Stores conversation history, tool results, and metadata.
- **Locking**: Uses file locking (`session-write-lock.ts`) to prevent concurrent write issues.
- **Updates**: State updates are atomic where possible, ensuring data integrity.

## Configuration Persistence

Configuration is hierarchical and layered.

### Layers (Highest Priority First):
1.  **Session Overrides**: Arguments passed to the CLI command (e.g., `--model`, `--provider`).
2.  **Agent Config**: `config.json` specific to an agent workspace.
3.  **Global Config**: `~/.openclaw/config.json`.
4.  **Defaults**: Hardcoded defaults in `src/config/defaults.ts`.

### Schema & Validation:
- **Zod Schemas**: The entire configuration surface is defined in `src/config/schema.ts` using Zod. This acts as the single source of truth.
- **UI Hints**: The schema includes `ConfigUiHint` metadata (labels, grouping, ordering) that drives the frontend settings UI.
- **Hot Reloading**: The Gateway supports hot-reloading keys and settings without restarting.

## Auto-Reply & Dispatch

The `src/auto-reply` module governs how the bot responds to messages.

### Flow:
1.  **Dispatch**: `dispatchInboundMessage` attempts to process a message.
2.  **Decision**: `getReplyFromConfig` determines *if* and *how* to reply based on triggers (mentions, DMs, keywords).
3.  **Execution**: The agent loop is invoked if a reply is needed.
4.  **Routing**: `routeReply` handles cross-provider responses (e.g., replying to a Telegram message via a Slack-connected agent).

## Infra & System Events

OpenClaw has a robust infrastructure layer.

### Heartbeats:
- **Smart Scheduling**: Checks `activeHours` and `queueSize` before running.
- **Event Injection**: Cron jobs and long-running execution results are injected into the heartbeat loop (`EXEC_EVENT_PROMPT`) to prompt the agent to report them.
- **Cost Saving**: Skips heartbeats if `HEARTBEAT.md` is empty/default.

### Execution Sandbox (`src/infra/exec-approvals.ts`):
- **Modes**: `deny`, `allowlist`, `full`.
- **Parsing**: Uses a custom shell tokenizer to validate commands against the allowlist.


## Tool Execution

Tools are executed in a standardized way.

### Flow:
1.  **Selection**: The LLM suggests a tool call.
2.  **Validation**: The runtime validates the tool name and arguments against the schema.
3.  **Policy Check**: The runtime checks if the tool is allowed for the current user/context (`pi-tools.policy.ts`).
4.  **Execution**: The tool's `execute` function is called.
5.  **Result Handling**: The result is captured, potentially truncated if too large (`tool-result-truncation.ts`), and fed back to the model.
