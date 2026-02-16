# OpenClaw Codebase Analysis Plan

## Goal
Create comprehensive documentation for the OpenClaw codebase to serve as a reference for Kabot development.

## Documentation Structure

### 1. [Architecture Overview](architecture-overview.md)
- **High-Level Design**: Interaction between CLI, Agent Process, Gateway, and Subagents.
- **Core Loops**: The lifecycle of an agent run (`runEmbeddedPiAgent`).
- **Data Flow**: How messages and tool implementations flow through the system.

### 2. [Directory Map](directory-map.md)
- **src/agents**: Core logic, tools, subagent management.
- **src/gateway**: Server, RPC protocol, connection handling.
- **src/memory**: Vector store, embeddings, session state.
- **src/commands**: CLI entry points.
- **src/infra**: Infrastructure utilities (events, logging, env).

### 3. [Key Subsystems](key-subsystems.md)
- **The Gateway**: RPC method dispatch, authorization scopes, WebSocket handling.
- **Agent Runtime**: Context guards, auto-compaction, model fallback strategies, auth profile rotation.
- **Subagent System**: Registry, lifecycle tracking, cross-process "await" mechanism.
- **Tooling**: `openclaw-tools.ts` factory, policies, and plugin integration.

### 4. [Implementation Patterns](implementation-patterns.md)
- **Error Handling**: `FailoverError`, `assistant-error` classification.
- **State Management**: Session stores, file-based persistence.
- **Configuration**: Zod schemas, defaults, overlay system (Global -> Agent -> Session).

## Execution Steps
1. Create `docs/openclaw-analysis/architecture-overview.md`.
2. Create `docs/openclaw-analysis/directory-map.md`.
3. Create `docs/openclaw-analysis/key-subsystems.md`.
4. Create `docs/openclaw-analysis/implementation-patterns.md`.
