# Advanced Kabot Features Specification ðŸš€
*Based on Kabot "Gold Standard" Architecture - 2026-02-15*

This document outlines the design for adding enterprise-grade management features to Kabot, mirroring the capabilities found in Kabot.

## 1. Modular Slash Command System (`/switch`, `/status`) âš¡

**Goal**: Allow users to control Kabot via chat commands (e.g., changing models, checking status) without breaking the conversation flow.

### Architecture
Instead of hardcoding commands in the `AgentLoop`, we will introduce a `CommandRouter`.

- **Component**: `kabot.agent.router.CommandRouter`
- **Location**: `kabot/agent/router.py`
- **Logic**:
  - Intercepts messages starting with `/` before they reach the LLM.
  - Routes to registered command handlers.
  - Returns immediate system responses.

### Proposed Commands
| Command | Description | Implementation |
| :--- | :--- | :--- |
| `/switch <model>` | Switch active LLM model (e.g., `/switch gpt-4`) | Updates `ContextBuilder` config session-wide. |
| `/status` | Show extensive system health | Calls `StatusService` (see below). |
| `/restart` | Restart the Kabot process | Trigger `SystemControl.restart()`. |
| `/update` | Update Kabot software | Trigger `UpdateService.run()`. |
| `/benchmark` | Run speed/latency tests | Trigger `BenchmarkService.run()`. |
| `/help` | List available commands | Auto-generated from registry. |

---

## 2. Software Update System (`kbt update`) ðŸ”„

**Goal**: Enable Kabot to update itself from the git repository, handling dependencies and rebuilds automatically.

### Kabot Pattern
Kabot uses a CLI command (`kabot update`) that orchestrates a multi-step workflow.

### Implementation Plan
- **Service**: `kabot.infra.update.UpdateService`
- **Workflow**:
  1. **Git Pull**: `git pull origin main`
  2. **Dependency Check**: Detect `requirements.txt` changes.
  3. **Install**: `pip install -r requirements.txt` (if needed).
  4. **Migration**: Run `kabot doctor --fix` (Database upgrades).
  5. **Restart**: Restart the service.

---

## 3. Database & System Doctor (`kbt doctor`) ðŸ©º

**Goal**: Automatic diagnosis and repair of system state, database schemas, and configuration.

### Kabot Pattern
Kabot uses a "Doctor" concept that runs a series of checks and offers "Auto-Fix" solutions (including migrations).

### Implementation Plan
- **Service**: `kabot.core.doctor.DoctorService`
- **Checks**:
  - **Database Integrity**: Check if `sqlite` schema matches latest models.
  - **Auth**: Verify API keys and OAuth tokens (refresh validity).
  - **Network**: Check connectivity to OpenAI/Google/Gateway.
  - **Environment**: Verify required ENV vars.
- **Actions**:
  - `migrate_db()`: Apply Alembic or SQL-based migrations.
  - `repair_auth()`: Trigger OAuth refresh flows.

---

## 4. System Control & Network Management ðŸŽ›ï¸

**Goal**: low-level system control (restart modem, restart service).

### Implementation Plan
- **Service**: `kabot.infra.system.SystemControl`
- **Functions**:
  - `restart_service()`: Uses `systemctl restart kabot` (Linux) or `subprocess` (Windows/Docker).
  - `restart_network()`: Executes platform-specific network restart commands (e.g., `ipconfig /renew` or router API calls via `RouterTool`).
  - **Notification**: On startup, Kabot checks a "restart_flag" file. If present, it sends a "I'm back online! ðŸŸ¢" message to the last user.

---

## 5. Speed & Benchmarking (`/benchmark`) ðŸŽï¸

**Goal**: Measure and compare AI model performance.

### Implementation Plan
- **Service**: `kabot.tools.benchmark.BenchmarkTool`
- **Metrics**:
  - **TTFT (Time to First Token)**: Latency measurement.
  - **TPS (Tokens Per Second)**: Generation speed.
  - **Total Duration**: End-to-end request time.
- **Workflow**:
  1. Send standardized prompt ("Hello, test.") to selected models.
  2. Measure timing.
  3. Generate a Markdown table comparison.

```markdown
| Model | TTFT (ms) | TPS | Status |
| :--- | :--- | :--- | :--- |
| GPT-4o | 450ms | 80 | ðŸŸ¢ Fast |
| Gemini 1.5 | 800ms | 120 | ðŸš€ Turbo |
| Local LLM | 1200ms | 30 | ðŸ¢ Slow |
```

---

## Implementation Roadmap

### Phase 8: System Internals (New)
1. **Slash Command Router**: Implement `CommandRouter` in `loop.py`.
2. **Status & Benchmark**: Create `StatusService` and `BenchmarkTool`.
3. **Doctor & Update**: Create `DoctorService` and `UpdateService`.
4. **Integration**: Wire everything into the CLI and Agent Loop.


