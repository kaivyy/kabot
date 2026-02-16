# Phase 9: Architecture Overhaul (OpenClaw Parity) 🏗️

This phase focuses on refactoring Kabot's core architecture to match the robust, scalable patterns found in the OpenClaw codebase.

## 1. Input Adaptors (Decoupling Channel Logic)

**Goal**: Separate the "Channel" (Whatsapp, Web, Slack) specific logic from the "Agent" logic.
**Current State**: Webhook handlers likely parse JSON deeply and call agent functions directly.
**Target State**:
-   **Monitors**: Each channel has a `Monitor` class that listens for events.
-   **Normalization**: Converts raw events into a standardized `MsgContext` (Pydantic model).
-   **Dispatcher**: A central service receives `MsgContext` and routes it to the correct Agent Session.

### Tasks
-   [ ] Define `MsgContext` schema (Sender, Body, Timestamp, Metadata).
-   [ ] Create `WebMonitor` (for current Dashboard/WebChat).
-   [ ] Refactor `gateway/api/webhooks.py` to use `dispatcher.dispatch(msg_context)`.

## 2. Directives System (Dynamic Control)

**Goal**: Allow power users/admins to control agent behavior *within* the chat stream.
**Current State**: Behavior is set via static config files or restart.
**Target State**: Supported inline commands parsed from the message body.
-   `/think on`: Enable chain-of-thought for this turn.
-   `/verbose`: output debug logs to chat.
-   `/model gpt-4`: Force a specific model for this turn.

### Tasks
-   [ ] Create `DirectiveParser` regex logic.
-   [ ] Update `AgentLoop` to check for directives before execution.
-   [ ] Implement state modifiers for the current Session.

## 3. Heartbeat Injection (Smart Background Tasks)

**Goal**: Make the agent "aware" of background events naturally.
**Current State**: Cron jobs fire specific task functions. The agent doesn't see the result in its chat context unless explicitly programmed.
**Target State**:
-   **System Events**: Cron jobs or long-running tasks push a "System Message" into the `MsgContext` stream.
-   **Reaction**: The Agent sees this message (e.g., "[System] Daily Summary Ready") and decides how to present it to the user.

### Tasks
-   [ ] Update `CronService` to produce `SystemEvents`.
-   [ ] Update `ContextBuilder` to fetch pending System Events.

## 4. Resilience (Auth & Fallback)

**Goal**: Zero downtime due to API limits.
**Current State**: Single API key per provider. Failure = Error.
**Target State**:
-   **Key Rotation**: `AuthManager` holds a list of keys and rotates on 429/401 errors.
-   **Model Fallback**: If "gpt-4" fails, automatically try "gpt-3.5" or "claude-3-haiku".

### Tasks
-   [ ] Update `config.json` schema to support key lists.
-   [ ] Implement `rotate_key()` in `AuthManager`.
-   [ ] Add fallback logic to `ModelRegistry`.
