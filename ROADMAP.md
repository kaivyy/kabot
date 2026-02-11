# 🗺️ Roadmap: Journey to v0.2.0

**Theme:** "Autonomous Agent Expansion & Multi-Modal"

Building on the solid foundation of v0.1.0, the next major release focuses on making Kabot capable of seeing, hearing, and working autonomously with greater resilience.

## 🌟 Phase 1: Multi-Modal Capabilities (Eyes & Ears)
Currently, Kabot is text-only. In v0.2.0, it will perceive the world.

- [ ] **Vision Support**: Native integration with `GPT-4o` / `Claude 3.5 Sonnet` / `Gemini 1.5 Pro` to analyze images.
  - *Use Case*: Send a screenshot of a UI bug -> Kabot analyzes the layout and suggests CSS fixes.
  - *Use Case*: Send a diagram -> Kabot converts it to Mermaid.js or code.
- [ ] **Voice Interface**: Integration with `OpenAI Whisper` (STT) and high-quality TTS engines.
  - *Use Case*: Send a voice note on Telegram "Create a login endpoint" -> Kabot transcribes and executes the task.

## 🤖 Phase 2: Autonomous Task Loop (Loop Mode)
Enable Kabot to work in long-running cycles without constant user supervision.

- [ ] **Autonomous Loop**: New `--loop` flag to allow the agent to self-correct errors up to N times.
- [ ] **Smart Self-Correction**: If a shell command fails, Kabot automatically reads the `stderr`, analyzes the error, and attempts a fix.
- [ ] **Periodic Reporting**: Instead of spamming the chat, the agent sends summarized progress updates ("Attempt 3/5: Fixing dependency conflict...").

## 🛡️ Phase 3: Isolated Sandboxing (Docker)
Advanced security for public or multi-user deployments.

- [ ] **Docker Driver for ExecTool**: Option to run all shell commands inside ephemeral Docker containers.
  - *Benefit*: Even if the agent runs `rm -rf /`, the host system remains safe.
- [ ] **Workspace Isolation**: Strict filesystem isolation where each user/session gets a dedicated, jailed workspace directory.

## 🔌 Phase 4: Ecosystem Expansion
- [ ] **MCP (Model Context Protocol)**: Support for Anthropic's open standard to connect external tools (PostgreSQL, Google Drive, Linear, etc.).
- [ ] **Web Dashboard (Lite)**: A lightweight FastAPI + React/HTMX dashboard to:
  - View memory graph and stored facts.
  - Manage scheduled Cron jobs.
  - Monitor API usage and token costs.

---

## 📅 Target Release: Q2 2026

*Note: This roadmap is subject to change based on community feedback and AI advancements.*
