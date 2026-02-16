# OpenClaw Architecture Overview

## High-Level Design

OpenClaw operates as a distributed system of agents, even when running locally. It consists of three main components:

1.  **The CLI (Command Line Interface)**: The entry point for users (`openclaw agent run`). It handles argument parsing and initializes the runtime environment.
2.  **The Agent Runtime**: The core logic that executes the "Think-Act" loop. It manages the context window, tools, and model interactions.
3.  **The Gateway**: A central server that manages communication between agents, the CLI, and external integrations (webhooks, etc.). It exposes a JSON-RPC API.

## Core Interaction Loop

The heart of OpenClaw is the `runEmbeddedPiAgent` function in `src/agents/pi-embedded-runner/run.ts`. The loop operates as follows:

1.  **Initialization**:
    *   Resolves configuration (Global -> Agent -> Session).
    *   Loads the "Skills Snapshot" (tools available to the agent).
    *   Initializes the "Context Window Guard" to prevent token overflow.

2.  **The "Think-Act" Cycle**:
    *   **Prompt Construction**: Builds the system prompt and user message.
    *   **Model Execution**: Calls the LLM (Anthropic, OpenAI, etc.).
    *   **Tool Execution**: If the model requests a tool call, the runtime executes it via the `pi-tools` layer.
    *   **Response Handling**: The model's response is parsed and sent to the output channel (CLI, Slack, Discord).

3.  **Advanced Features**:
    *   **Auto-Compaction**: If the context window fills up, the agent automatically summarizes older messages to free up space.
    *   **Auth Profile Rotation**: If an API key fails (rate limit, error), the agent automatically rotates to the next available key.
    *   **Model Fallback**: If the primary model fails, it falls back to a secondary model (e.g., Claude 3.5 Sonnet -> GPT-4o).

## Data Flow

Data flows through the system in a structured way:

*   **Input**: User commands -> CLI -> Agent Runtime.
*   **State**: Session Store (JSON files) -> In-Memory Cache -> Disk Persistence.
*   **Output**: Agent Runtime -> Gateway -> Output Channel (CLI/Chat Platform).

## Input & Orchestration

### 1. Channel Ingestion (Input Adaptors)

Each channel (e.g., `src/web`, `src/slack`) implements an **Input Adaptor** pattern.
-   **Monitoring**: Functions like `monitorWebInbox` (in `src/web/inbound/monitor.ts`) listen for raw protocol events.
-   **Normalization**: Raw events are converted into a standardized `MsgContext` object.
-   **Dispatch**: The normalized context is passed to `dispatchInboundMessage` for processing.

### 2. The Core Loop (Orchestration)
The heart of OpenClaw is the "Think-Act" loop, orchestrated by `src/auto-reply/reply/dispatch-from-config.ts`.
1.  **Directives**: `get-reply-directives.ts` parses commands like `/think` or `/verbose` and determines if a reply is needed.
2.  **Decision**: `getReplyFromConfig` evaluates triggers (mentions, DMs) to decide *if* the agent should run.
3.  **Execution**: If triggered, `runEmbeddedPiAgent` is called to execute the agent's logic.
4.  **Plugins**: The `src/plugins` system allows extending this loop via hooks (`message_received`, `tool_call`).

## Subagent System

OpenClaw supports hierarchical agents ("Subagents").

*   **Spawning**: An agent can spawn a subagent using the `sessions.spawn` tool.
*   **Lifecycle**: The parent agent tracks the child's status (start, running, end).
*   **Communication**: The parent can "wait" for the child to complete and receive its output.
*   **Persistence**: Subagent runs are saved to `src/agents/subagent-registry.store.ts` to survive restarts.
