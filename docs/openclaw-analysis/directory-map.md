# OpenClaw Directory Map

This document provides a detailed breakdown of the `src/` directory structure in the OpenClaw codebase.

## Root Directories

### `src/agents`
**Core Logic:** Contains the primary agent runtime logic and tool implementations.
- `agent.ts`: Main agent lifecycle management.
- `pi-embedded-runner/`: Contains the `runEmbeddedPiAgent` loop (`run.ts`) and helper logic (`compact.ts`, `runs.ts`).
- `pi-tools.ts`: Tool registration and policy enforcement.
- `subagent-registry.ts`: Subagent lifecycle management.
- `openclaw-tools.ts`: Factory for creating all default tools.

### `src/gateway`
**Server & Networking:** Handles the JSON-RPC API and WebSocket connections.
- `server.ts`: Initial server setup.
- `server-methods.ts`: Maps RPC methods to handlers.
- `server-methods/`: Implementations for each RPC method (e.g., `agent.ts`, `sessions.ts`).
- `protocol/`: Defines the wire protocol and error codes.

### `src/memory`
**State Persistence:** Manages vector storage and session history.
- `manager.ts`: Core memory manager.
- `embeddings.ts`: Embedding generation (OpenAI, Voyage).
- `session-files.ts`: Handling of session storage files.

### `src/commands`
**CLI Entry Points:** Contains the logic for CLI commands.
- `agent.ts`: The `openclaw agent run` command implementation.
- `doctor.ts`: Migration and diagnostic tools.
- `status.command.ts`: System status checks.

### `src/infra`
**Infrastructure Utilities:** Low-level helpers and system integration.
- `agent-events.ts`: Event emitter for agent lifecycle events.
- `logging.ts`: Centralized logging configuration.
- `env.ts`: Environment variable normalization.

### `src/utils`
**Shared Utilities:** Common helper functions.
- `message-channel.ts`: Abstractions for different communication channels (Slack, Discord, CLI).
- `delivery-context.ts`: Context object for message delivery.

## Key Files Summary

| File Path | Description |
| :--- | :--- |
| `src/agents/pi-embedded-runner/run.ts` | **The Brain.** The main loop for the embedded agent execution. |
| `src/gateway/server-methods.ts` | **The API.** The central registry for all RPC methods. |
| `src/agents/openclaw-tools.ts` | **The Toolkit.** The factory that builds all tool instances. |
| `src/agents/subagent-registry.ts` | **The Manager.** Handles subagent spawning and tracking. |
