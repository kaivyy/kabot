<div align="center">
  <img src="kabotimage.png" alt="kabot" style="width:100%;max-width:100%;height:auto;display:block;">
  <h1>Kabot 🐺</h1>
  <p>
    <b>Resilient Memory. Methodical Execution. Native Reasoning.</b>
  </p>
  <p>
    <a href="https://pypi.org/project/kabot/"><img src="https://img.shields.io/pypi/v/kabot?style=for-the-badge" alt="PyPI"></a>
    <img src="https://img.shields.io/badge/python-3.11+-blue.svg?style=for-the-badge" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License">
    <a href="#"><img src="https://img.shields.io/badge/Telegram-Bot-blue?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram"></a>
    <a href="#"><img src="https://img.shields.io/badge/Discord-Bot-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a>
    <a href="#"><img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"></a>
  </p>
</div>

---

> **Kabot** is a _personal AI assistant_ engineered for **resilience**, **complex task execution**, and **long-term memory**. It isn't just a chatbot; it's an autonomous agent that runs on your own hardware, remembering context across restarts and methodically planning its actions.
> 
> It bridges the gap between simple chatbots and autonomous software engineers. While typical agents operate blindly, Kabot implements a **Methodical Engineering Workflow** (Brainstorm → Plan → Execute) and relies on a proprietary **Hybrid Memory Architecture** (Smart Routing + LLM Episodic Extraction + Vector) to handle long-running projects with hyper-efficient token usage and zero "amnesia".

If you want a personal, single-user assistant that feels local, fast, and always-on, this is it.

[Website](https://kabot.ai) · [Docs](https://kaivyy.github.io/kabot/) · [How-To-Use](HOW_TO_USE.MD) · [Getting Started](#-quick-start) · [Telegram](https://t.me/kabot_support) · [FAQ](#faq)

---

## What's New In v0.6.5-rc1

- **Session-first continuity** so file navigation, delivery reuse, and one-shot CLI follow-ups stay grounded in `working_directory`, `delivery_route`, and transcript state instead of stale breadcrumbs.
- **Multilingual, user-language replies** with English internal guidance, lighter parser dependence, and stronger continuity for profile, memory, weather, and research turns.
- **External skill lifecycle and registry flow** with install/search/info/list/update/pack/publish/sync support for folders, bundles, git repos, URLs, and JSON catalogs.
- **Cross-platform runtime hardening** across browser screenshots, media ingress, cleanup, daemon/service setup, special directories, and system info on Windows, macOS, and Linux.

If you are upgrading from `0.6.4`, the two most important changes are:
- Kabot now treats session/runtime state as the primary anchor for file work, so separate chat turns and one-shot CLI runs stay much more coherent.
- Delivery, navigation, and artifact follow-ups are now more evidence-based and much less likely to drift into stale parser-era path reuse.

---

## 📑 Table of Contents

- [🚀 Quick Start](#-quick-start)
- [🤖 Multi-Agent Orchestration](#-multi-agent-orchestration)
- [🔌 Multi-Channel Instances](#-multi-channel-instances)
- [🛠️ Operations & Plugin Lifecycle](#️-operations--plugin-lifecycle)
- [🏗️ Architecture](#️-architecture)
- [🤖 Supported Models](#-supported-models)
- [⚙️ Configuration Reference](#️-configuration-reference)
- [⚡ Slash Commands & Directives](#-slash-commands--directives)
- [🎛️ Model Management Tutorial](#️-model-management-tutorial)
- [🔒 Security](#-security)
- [🤝 Development & Contributing](#-development--contributing)
- [📜 Star History](#-star-history)
- [🙌 Community](#-community)

---

## 🚀 Quick Start

**Runtime**: Python 3.11+  
Tested on Windows, macOS, Linux (Ubuntu/Debian), and Termux.

### Beginner Quick Path (Recommended)

If you are new, follow this exact flow:

1. **Install Kabot**
2. **Run setup wizard** (`kabot config`)
3. **Start Kabot** (`kabot gateway`)
4. **Test chat** (`kabot agent -m "Hello"`)

No need to clone repo for normal usage.

Recommended optional step for `v0.6.5-rc1`:

5. **Inspect MCP availability** (`kabot mcp status`)

### 1) Install Kabot

**Universal (recommended for most users):**
```bash
pip install kabot
```

If `pip` is not found, run with Python:
```bash
python -m pip install kabot
```

If you already installed Kabot before and want to upgrade:
```bash
pip install -U kabot
```

### 1b) One-Command Auto Installer (Optional)

Use this if you want automatic environment setup.  
Installer scripts auto-detect runtime profile (macOS/Linux/WSL/Windows/Termux/headless) and prepare sane defaults.

**Linux / macOS / WSL2**
```bash
curl -fsSL https://raw.githubusercontent.com/kaivyy/kabot/main/install.sh | bash
```

**Windows (PowerShell)**
```powershell
iwr -useb https://raw.githubusercontent.com/kaivyy/kabot/main/install.ps1 | iex
```

### 2) First Setup (Required Once)

```bash
kabot config
```

In wizard:
- choose your AI provider,
- paste API key/token,
- save config.

Notes:
- `Google Suite` in setup wizard is Kabot's native Google auth path. It does not require npm, Node.js, or `gog`.
- `Skills` in setup wizard manages skill config, env keys, and manual dependency install plans. It does not auto-run npm/brew installs for you.
- `MCP` is now a first-class runtime capability. Use config plus `kabot mcp ...` commands to inspect what is really available instead of relying on prompt-only assumptions.
- When setup wizard syncs built-in skills, it is copying skill definitions (`SKILL.md`) into the workspace. That is separate from installing third-party runtimes or logging into external services.

### 3) Start Kabot

```bash
kabot gateway
```

### 4) Test Quickly

```bash
kabot agent -m "Hello Kabot"
```

### 4 Commands You Should Remember

```bash
kabot config       # open setup wizard
kabot gateway      # run the bot gateway
kabot doctor --fix # auto-diagnose and repair common issues
kabot doctor routing # validate routing/guard sanity before deploy
kabot mcp status   # inspect configured MCP servers
```

### Python-Native MCP Quickstart

Kabot `0.6.5-rc1` ships a Python-native MCP runtime. That means MCP is no longer just an instruction trick; Kabot can attach real MCP servers per session and expose only the capabilities that actually exist.

Useful commands:

```bash
kabot mcp status
kabot mcp example-config
kabot mcp inspect local_echo
```

Minimal config shape:

```json
{
  "mcp": {
    "enabled": true,
    "servers": {
      "local_echo": {
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "kabot.mcp.dev.echo_server"]
      }
    }
  }
}
```

Why this matters:
- Kabot now knows which MCP tools are real for the current session.
- MCP resources and prompts can be pulled into a turn without pretending they are ordinary files.
- follow-up continuity stays stronger, so MCP context is reused when helpful but does not override a newer clear user request.

### Runtime Token Mode (Boros vs Hemat)

Default is `boros` (richer context, higher token usage).

Quick toggle without opening full wizard:

```bash
kabot config --token-mode boros
kabot config --token-mode hemat
```

Shortcut toggle:

```bash
kabot config --token-saver     # ON  -> hemat
kabot config --no-token-saver  # OFF -> boros
```

You can also set this from setup wizard:
`kabot config` -> `Tools & Sandbox` -> `Runtime Token Mode`.

### Core-Only Manual Install (Minimal Footprint)

If you prefer isolated venv install:

```bash
python3 -m venv ~/.kabot/venv
source ~/.kabot/venv/bin/activate
pip install -U pip
pip install kabot
kabot config
kabot gateway
```

Notes:
- `kabot` from PyPI is enough for runtime operation.
- WhatsApp bridge and node-based skill installers still require **Node.js + npm**.
- Bridge source is bundled and prepared under `~/.kabot/bridge` on first local bridge setup.

### Termux (Android)

```bash
pkg update && pkg upgrade
pkg install python git clang make libjpeg-turbo freetype rust
termux-setup-storage
pip install -U pip
pip install kabot
kabot config
kabot gateway
```

### Developer Install (Optional)

Use this only if you want to modify source code:

```bash
git clone https://github.com/kaivyy/kabot.git
cd kabot
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
kabot config
kabot gateway
```

Gateway runtime notes:
- `kabot gateway` now defaults to `config.gateway.port` from setup/config.
- Use `kabot gateway --port <N>` to override for one run.
- If gateway bind mode is set to `tailscale`, Kabot activates Tailscale Serve at startup and keeps gateway bind on loopback for safer exposure.
- If `gateway.tailscale=true` (with non-tailscale bind mode), Kabot activates Tailscale Funnel at startup.
- Lightweight dashboard is available at `/dashboard` (SSR + HTMX, low-RAM friendly).
  - richer operator panels are now available in the same surface:
    - Chat panel (runtime prompt send + live log auto-refresh, now with SSE stream),
      with per-message model controls:
      - provider selector (all registered providers),
      - model override input (`provider/model` or alias),
      - model suggestions now auto-refresh by selected provider (from runtime model registry snapshot),
      - fallback builder UI (add/remove chips) with provider-aware suggestions,
      - channel/chat target passthrough for advanced operator routing.
    - Sessions panel (recent session list + clear/delete actions, instant panel refresh after action),
    - Nodes panel (runtime/channel node view + start/stop/restart actions, state-aware button disable, instant panel refresh after action),
    - Config panel (safe token-mode quick edit + config snapshot),
    - Control panel (runtime control actions).
  - JSON endpoints:
    - `/dashboard/api/status`
    - `/dashboard/api/chat/history`
    - `/dashboard/api/chat/stream` (SSE)
    - `/dashboard/api/sessions`
    - `POST /dashboard/api/sessions` (`sessions.clear` / `sessions.delete`)
    - `/dashboard/api/nodes`
    - `POST /dashboard/api/nodes` (`nodes.start` / `nodes.stop` / `nodes.restart`)
    - `/dashboard/api/config`
  - `POST /dashboard/api/chat` accepts optional model routing args:
    - `provider`
    - `model`
    - `fallbacks` (comma-separated string or list)
    - `channel`
    - `chat_id`
- `gateway.auth_token` supports scoped mode:
  - Plain: `my-token` (legacy full access)
  - Scoped: `my-token|operator.read,operator.write,ingress.write`
  - `operator.read` is required for dashboard/status routes.
  - `operator.write` is required for dashboard control routes (`/dashboard/api/control`, `/dashboard/partials/control` POST).
  - `ingress.write` is required for webhook ingress routes.
  - Scope shortcuts are supported: `operator.*`, `ingress.*`, `<family>.admin`, `*`.
  - `operator.write` also grants read-only dashboard access.
- Dashboard access:
  - No gateway auth token: open `http://127.0.0.1:<port>/dashboard`
  - With gateway auth token: open `http://127.0.0.1:<port>/dashboard?token=<your-token>`
  - For API clients, you can still use header auth: `Authorization: Bearer <your-token>`
  - Query-token auth is intentionally limited to `/dashboard*` routes (not webhook ingress).

### Chatting
Once the gateway is running, you can talk to Kabot via:
*   **CLI**: `kabot agent -m "Hello"` (Fastest for testing)
*   **Telegram**: DM your bot.
*   **Discord**: Mention the bot in a channel.

### AI-Driven, But Grounded

Recent runtime work makes Kabot behave more like a serious coding/operator agent:

- if the user asks a normal question, Kabot should answer directly,
- if the user asks for a real side effect, Kabot should choose tools or skills,
- if the user follows up with `yes continue` or `lanjut`, Kabot should continue the pending task instead of guessing a new tool,
- if delivery or execution cannot be verified, Kabot should fail honestly instead of pretending the task is already done.

That balance matters more than "always use tools" or "never use tools". Kabot is designed to stay AI-driven while still being evidence-based.

---

*   **Persistent Subagents**: Delegate tasks like "Research this library" to background agents. These subagents persist their state to disk (`.json` registry), so they survive system reboots and can be queried days later.

### 💾 **Hybrid Memory Architecture**
Unlike typical stateless agents, Kabot is completely **stateful** and amnesia-proof, employing a military-grade memory system that exceeds standard solutions like Mem0.
*   **Two-Tier Persistence**: Blends a relational SQLite database for episodic memory (maintaining exact parent-child conversation trees, auto-extracted facts, and metacognitive lessons) with a ChromaDB vector store for semantic knowledge.
*   **Smart Routing & Retrieval**: Uses a query-intent classifier to route to the correct memory store (episodic/knowledge/hybrid) and fuses vector search with BM25 keyword-matching.
*   **Reranker & Token Guard**: Employs a rigorous three-stage filtering pipeline (Threshold ≥0.6, Top-K, and Hard Token Limit) to reduce context window bloat by up to 72% and eliminate hallucinations.
*   **Self-Maintenance**: Asynchronous `EpisodicExtractor` automatically mines preferences and facts post-chat, while a scheduled `MemoryPruner` performs garbage collection on stale data (>30 days).

### 🔌 **Universal Connectivity**
One brain, many bodies. Kabot acts as a central control plane.

| Platform | Features | Setup Guide |
| :--- | :--- | :--- |
| **Telegram** | Full rich chat, voice notes, file sharing | [Setup Guide](#telegram-setup) |
| **Discord** | Channel/DM support, detailed embeds | [Setup Guide](#discord-setup) |
| **Slack** | Workspace integration, thread support | [Setup Guide](#slack-setup) |
| **WhatsApp** | (Beta) Via local bridge | [Setup Guide](#whatsapp-setup) |
| **CLI** | Real-time terminal chat for local debugging | Built-in |

---

## 🤖 Multi-Agent Orchestration
<details><summary><b>Click to expand</b></summary>

Kabot supports two advanced multi-agent systems that can work independently or together, enabling sophisticated task execution and context separation.

### System 1: Standard Multi-Agent (Context Separation)

Multiple independent agents with separate contexts, each specialized for different domains or purposes.

**Key Features:**
- **Separate Contexts**: Each agent maintains its own conversation history and memory
- **Per-Agent Configuration**: Custom model, workspace, and tool restrictions per agent
- **Message Routing**: Automatic routing based on channel/platform via bindings
- **Session Isolation**: Each agent has isolated session storage

**Use Cases:**
- Separate work/personal/family contexts
- Domain-specific agents (coding/research/writing)
- Multi-user scenarios with different access levels
- Testing different models for the same task

**CLI Commands:**
```bash
# List all configured agents
kabot agents list

# Add a new agent
kabot agents add work --model anthropic/claude-3-5-sonnet-20241022 --workspace ~/work

# Delete an agent
kabot agents delete work

# Bind agent to specific channel
# Edit config.json to add bindings:
{
  "agents": {
    "bindings": [
      {"agent_id": "work", "channel": "telegram", "chat_id": "123456"},
      {"agent_id": "personal", "channel": "discord"}
    ]
  }
}
```

**Example Configuration:**
```json
{
  "agents": {
    "list": [
      {
        "id": "work",
        "name": "Work Assistant",
        "model": "anthropic/claude-3-5-sonnet-20241022",
        "workspace": "~/work",
        "default": false
      },
      {
        "id": "personal",
        "name": "Personal Assistant",
        "model": "openai/gpt-4o",
        "workspace": "~/personal",
        "default": true
      }
    ],
    "bindings": [
      {"agent_id": "work", "channel": "telegram", "chat_id": "work_chat_id"},
      {"agent_id": "personal", "channel": "discord"}
    ]
  }
}
```

**Per-Agent Model Switching:**

Kabot now supports per-agent model assignment, allowing you to:
- Use **one model for multiple agents** (cost-effective for similar tasks)
- Use **different models for different agents** (optimize for specific use cases)

**Example 1: One Model for Multiple Agents**
```json
{
  "agents": {
    "list": [
      {"id": "work", "model": null, "default": false},
      {"id": "personal", "model": null, "default": false},
      {"id": "family", "model": null, "default": true}
    ]
  }
}
```
All three agents will use the global default model (e.g., Claude Sonnet), but maintain separate conversation histories.

**Example 2: Different Models for Different Agents**
```json
{
  "agents": {
    "list": [
      {"id": "coding", "model": "anthropic/claude-3-5-sonnet-20241022", "default": false},
      {"id": "writing", "model": "openai/gpt-4o", "default": false},
      {"id": "quick", "model": "groq/llama3-70b", "default": true}
    ],
    "bindings": [
      {"agent_id": "coding", "channel": "telegram", "chat_id": "coding_chat"},
      {"agent_id": "writing", "channel": "telegram", "chat_id": "writing_chat"},
      {"agent_id": "quick", "channel": "telegram", "chat_id": "quick_chat"}
    ]
  }
}
```
Each agent uses a model optimized for its purpose: Claude for coding, GPT-4o for writing, Llama3 for quick queries.

**How It Works:**
- When a message arrives, Kabot resolves which agent should handle it via bindings
- If the agent has a `model` override, that model is used
- If `model` is `null` or not set, the global default model is used
- Model switching happens automatically per message

### System 2: Collaborative Orchestration (Role-Based Collaboration)

Multiple agents with specialized roles work together on a single task, combining their strengths for complex problem-solving.

**Roles:**
- **Master**: Coordinates tasks and makes high-level decisions (default: GPT-4o)
- **Brainstorming**: Generates ideas and explores approaches (default: Claude Sonnet)
- **Executor**: Executes code and performs operations (default: Kimi K2.5)
- **Verifier**: Reviews code and validates results (default: Claude Sonnet)

**Key Features:**
- **Agent-to-Agent Communication**: Peer-to-peer messaging via MessageBus
- **Task Delegation**: Master agent distributes work to specialized agents
- **Result Aggregation**: Combines outputs from multiple agents
- **Quality Control**: Built-in verification and review workflow

**Use Cases:**
- Complex coding tasks requiring multiple perspectives
- Brainstorming → Implementation → Review workflows
- Tasks benefiting from different model strengths
- Quality-critical projects needing verification

**CLI Commands:**
```bash
# Enable collaborative mode
kabot mode set multi

# Check current mode
kabot mode status

# Disable collaborative mode (back to single-agent)
kabot mode set single
```

**Example Workflow:**
```
User: "Implement user authentication with JWT"
  ↓
Master Agent: Analyzes request, breaks down task
  ↓
Brainstorming Agent: Proposes 3 implementation approaches
  ↓
Master Agent: Selects best approach (JWT with refresh tokens)
  ↓
Executor Agent: Implements code, writes tests
  ↓
Verifier Agent: Reviews code, checks security
  ↓
Master Agent: Aggregates results → Returns to user
```

### System 3: Autonomous Sub-agents (Background Delegation)

Kabot can spawn lightweight, specialized sub-agents to handle long-running or complex background tasks while the main agent remains responsive to your immediate chats.

**Key Features:**
- **Background Execution:** Delegate heavy research, coding, or data processing tasks without blocking your main conversation.
- **Isolated Context:** Each sub-agent runs with a laser-focused objective and its own memory, preventing context pollution in your main chat.
- **Persistent Registry:** Sub-agent states are saved to disk (`.json`). If the server restarts, they resume where they left off.
- **Safety Limits:** Built-in safeguards (`maxSpawnDepth`, `maxChildrenPerAgent`) prevent infinite spawning loops and control resource usage.

**Use Cases:**
- "Research these 5 URLs in the background and give me a summary when done."
- "Start a sub-agent to monitor this error log and figure out what caused the crash."

**How It Works:**
The main agent uses the internal `spawn` tool to spin up a sub-agent worker. Once the worker finishes the task, it reports the final result back to the main agent's context or directly to your chat.

### Combining All Systems


Both systems work together seamlessly:
- **Multiple agents** (System 1) can each use **collaborative mode** (System 2)
- Example: "work" agent uses multi-agent mode for complex tasks, "personal" agent uses single-agent mode for simple queries

**Configuration Example:**
```json
{
  "agents": {
    "list": [
      {"id": "work", "model": "anthropic/claude-3-5-sonnet-20241022", "default": true},
      {"id": "research", "model": "openai/gpt-4o", "default": false}
    ]
  }
}
```

Then set mode per user:
```bash
# Work agent uses collaborative mode
kabot mode set multi --user-id user:telegram:work_chat

# Research agent uses single mode
kabot mode set single --user-id user:telegram:research_chat
```

### When to Use Each System

| Scenario | Recommended System |
| :--- | :--- |
| Separate work/personal contexts | Standard (System 1) |
| Complex multi-step coding tasks | Collaborative (System 2) |
| Testing different models | Standard (System 1) |
| Quality-critical projects | Collaborative (System 2) |
| Multi-user deployment | Standard (System 1) |
| Brainstorming + Implementation | Collaborative (System 2) |
| Simple queries | Single-agent (default) |

**Documentation:**
- [Multi-Agent System Details](docs/multi-agent.md)
- [Collaborative Orchestration Guide](docs/collaborative-orchestration.md)

</details>

---

## 🔌 Multi-Channel Instances

<details><summary><b>Click to expand</b></summary>

Run multiple bot instances per platform with different configurations and agent bindings.

### Overview

Kabot supports running multiple bots per platform simultaneously (e.g., 4 Telegram bots, 4 Discord bots). Each instance has:
- **Unique ID**: Identifies the bot instance (e.g., "work_bot", "personal_bot")
- **Type-specific config**: Token, credentials, and platform-specific settings
- **Agent binding**: Optional routing to specific agents for context separation
- **Independent operation**: Each instance runs as a separate bot with its own connection

### Configuration

**Via Setup Wizard:**
```bash
kabot config
# Navigate to: Channels → Manage Channel Instances
# Use Add/Edit/Delete or Quick Add Multiple for batch setup
```

**Via config.json:**
```json
{
  "channels": {
    "instances": [
      {
        "id": "work_bot",
        "type": "telegram",
        "enabled": true,
        "config": {
          "token": "123456:ABC-DefGhIjKlMnOpQrStUvWxYz",
          "allow_from": []
        },
        "agent_binding": "work"
      },
      {
        "id": "personal_bot",
        "type": "telegram",
        "enabled": true,
        "config": {
          "token": "789012:XYZ-AbcDefGhIjKlMnOpQrStUv",
          "allow_from": []
        },
        "agent_binding": "personal"
      },
      {
        "id": "team_discord",
        "type": "discord",
        "enabled": true,
        "config": {
          "token": "MTA5...",
          "allow_from": []
        },
        "agent_binding": "work"
      }
    ]
  }
}
```

### Supported Channel Types

| Type | Configuration Fields | Notes |
| :--- | :--- | :--- |
| **telegram** | `token`, `allow_from`, `proxy` | Get token from @BotFather |
| **discord** | `token`, `allow_from`, `gateway_url`, `intents` | Get token from Discord Developer Portal |
| **whatsapp** | `bridge_url`, `allow_from` | Requires WhatsApp bridge setup |
| **slack** | `bot_token`, `app_token`, `mode` | Socket mode supported |

### Use Cases

**1. Work/Personal Separation**
```json
{
  "instances": [
    {"id": "work_bot", "type": "telegram", "agent_binding": "work"},
    {"id": "personal_bot", "type": "telegram", "agent_binding": "personal"}
  ]
}
```
- Different Telegram bots for work and personal use
- Each routes to its own agent with separate context
- No conversation mixing between work and personal

**2. Multi-Team Deployment**
```json
{
  "instances": [
    {"id": "team_a_tele", "type": "telegram", "agent_binding": "team_a"},
    {"id": "team_b_tele", "type": "telegram", "agent_binding": "team_b"},
    {"id": "team_a_discord", "type": "discord", "agent_binding": "team_a"}
  ]
}
```
- Multiple teams using the same Kabot server
- Each team has dedicated bot instances
- Agent bindings ensure context isolation

**3. Testing and Production**
```json
{
  "instances": [
    {"id": "prod_bot", "type": "telegram", "enabled": true},
    {"id": "test_bot", "type": "telegram", "enabled": true}
  ]
}
```
- Separate bots for production and testing
- Test new features without affecting production users
- Easy enable/disable for maintenance

### High-Volume Setup (4-6+ Bots)

For fast setup of many bots:

```bash
kabot config
# Channels → Manage Channel Instances → Quick Add Multiple
```

You can:
- Create multiple Telegram/Discord/Slack/WhatsApp instances in one flow
- Auto-create dedicated agent per bot
- Set model override for newly created agents
- Keep one shared default model for all bots if preferred

### Channel Instance Routing

Messages are routed using the format: `type:id`

Example:
- `telegram:work_bot` → Work Telegram bot instance
- `telegram:personal_bot` → Personal Telegram bot instance
- `discord:team_discord` → Team Discord bot instance

Routing notes:
- Base binding `channel: telegram` matches `telegram:<instance_id>`
- Exact instance binding `channel: telegram:work_bot` has higher priority
- Instance `agent_binding` is enforced at runtime for session/model routing

### Backward Compatibility

Legacy single-instance configs continue to work:
```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "legacy:TOKEN"
    }
  }
}
```
- Legacy configs are processed after instances
- Both can coexist in the same configuration
- Gradual migration path available

</details>

---

## 🛠️ Operations & Plugin Lifecycle

### Environment Check

Use `env-check` to verify runtime profile and recommended gateway mode:

```bash
kabot env-check
kabot env-check --verbose
```

This reports platform flags (`windows/macos/linux/wsl/termux/vps/headless`) and whether `local` or `remote` mode is recommended.

### Remote Bootstrap

Use `remote-bootstrap` to generate/apply service startup guidance:

```bash
# Linux
kabot remote-bootstrap --platform linux --service systemd --dry-run
kabot remote-bootstrap --platform linux --service systemd --apply

# macOS
kabot remote-bootstrap --platform macos --service launchd --dry-run
kabot remote-bootstrap --platform macos --service launchd --apply

# Windows (Task Scheduler)
kabot remote-bootstrap --platform windows --service windows --apply

# Termux
kabot remote-bootstrap --platform termux --service auto --dry-run
```

Service behavior:
- `kabot gateway` in terminal is a foreground process (closing terminal stops it).
- For persistent background operation, enable service via wizard (`kabot config` → `Auto-start`) or `kabot remote-bootstrap --apply`.
- After service is installed and started, Kabot keeps running even if your SSH/terminal session closes.

### Service Stop/Disable (Quick Reference)

```bash
# Linux (systemd user)
systemctl --user stop kabot
systemctl --user disable kabot

# macOS (launchd)
launchctl stop com.kabot.agent
launchctl unload -w ~/Library/LaunchAgents/com.kabot.agent.plist

# Windows (Task Scheduler, CMD/PowerShell)
schtasks /End /TN kabot
schtasks /Change /TN kabot /Disable

# Termux
sv down kabot
sv-disable kabot
```

### Plugin Lifecycle Commands

Kabot now supports full plugin lifecycle operations:

```bash
# List installed plugins
kabot plugins list

# Install from local directory
kabot plugins install --source /path/to/plugin

# Install from git with pinned ref (tag/branch/commit)
kabot plugins install --git https://example.com/repo.git --ref v1.2.3

# Update plugin (uses tracked source by default)
kabot plugins update --target my_plugin

# Enable/disable
kabot plugins disable --target my_plugin
kabot plugins enable --target my_plugin

# Diagnose plugin health
kabot plugins doctor
kabot plugins doctor --target my_plugin

# Scaffold a new dynamic plugin
kabot plugins scaffold --target meta_bridge

# Remove plugin
kabot plugins remove --target my_plugin --yes
```

Update safety:
- Plugin updates use rollback protection.
- If update fails, previous plugin version is automatically restored.

### Auth Parity Diagnostics

Use this command to validate OAuth/API handler parity across providers and aliases:

```bash
kabot auth parity
```

### Meta Threads and Instagram Integrations

Kabot now supports Meta outbound actions and verified webhook ingress:

- Outbound tool: `meta_graph` (Threads create/publish, Instagram media create/publish)
- Verified webhook routes: `GET /webhooks/meta` and `POST /webhooks/meta`
- Signature validation: `X-Hub-Signature-256` with app secret

See full setup and examples in `docs/integrations/meta-threads-instagram.md`.

### Freedom Mode (Trusted Environment)

If you want "do anything" behavior for private/trusted deployments:

- Setup wizard:
  - `kabot config`
  - `Tools & Sandbox`
  - Enable `Freedom mode`

This mode:
- enables `exec` auto approval,
- disables HTTP target guard restrictions for `web_fetch`,
- keeps defaults available to switch back to secure mode.

</details>

---

## 🏗️ Architecture

Kabot operates on a **Gateway-Agent** model, decoupling the "brain" from the "body".

```
Telegram / Discord / Slack / WhatsApp / CLI
               │
               ▼
┌───────────────────────────────┐
│            Gateway            │
│       (Control Plane)         │
│   localhost:<gateway.port>    │
│   (Event Bus + Adapters)      │
└──────────────┬────────────────┘
               │
               ├─ Agent Loop (Reasoning Engine)
               │   ├─ Planner
               │   ├─ Tool Executor
               │   └─ Critic
               │
               ├─ Hybrid Memory (SQLite + Vector)
               │   ├─ Short Term (Context Window)
               │   └─ Long Term (ChromaDB)
               │
               ├─ Cron Service (Scheduling)
               │   └─ Persistent Job Queue
               │
               └─ Subagent Registry (Background Tasks)
```

### Key Subsystems

#### 1. Gateway (Control Plane)
The central nervous system. It normalizes all incoming messages (regardless of platform) into a standard `MsgContext` object. It handles routing, rate limiting, and session affinity.

#### 2. Agent Loop (The Brain)
The core execution engine found in `kabot/agent/loop.py`. It implements a ReAct (Reason + Act) loop:
1.  **Observe**: Read user input + memory.
2.  **Reason**: Generate a thought process (internal monologue).
3.  **Act**: Execute a tool (File IO, Web Search, Code Execution).
4.  **Reflect**: Analyze tool output.
5.  **Repeat**: Until the task is done.

Recent runtime hardening added:
- stronger turn categorization (`chat`, `action`, `contextual_action`, `command`)
- continuity resolution that prefers recent answer/tool evidence over weak parser guesses
- unified completion evidence so "done" claims are checked against real artifact/delivery proof

#### 3. MCP Session Runtime
Located in `kabot/mcp/`. This layer lets Kabot attach MCP servers per session, discover real tools/resources/prompts, and expose them through the runtime without hallucinating availability.

Key properties:
*   **Session-scoped**: MCP capabilities are attached to a session, not globally improvised.
*   **Python-native**: Kabot itself does not need Node.js just to act as the MCP client.
*   **Grounded**: tool names are namespaced (`mcp.<server>.<tool>`) and only available when the server is actually configured and attached.

#### 4. Hybrid Memory
Located in `kabot/memory/`. It solves the "context window limit" problem.
*   **Vector Store**: Semantic search for fuzzy concepts ("What did we discuss about architecture?").
*   **SQL Store**: Exact matching for facts ("What is the API key for Stripe?").
*   **Summarizer**: Automatically condenses old conversation turns into summaries to save tokens.

#### 5. Doctor (Self-Healing)
Located in `kabot/core/doctor.py`. A diagnostic engine that runs on startup.
*   Checks database integrity.
*   Validates API keys.
*   Verifies Python environment dependencies.
*   **Auto-Fix**: Can automatically reinstall missing pip packages or rebuild corrupted config files.
*   **Agent Smoke Matrix**: `kabot doctor smoke-agent` runs multilingual temporal/filesystem smoke probes and can enforce latency gates.

**Smoke examples:**
```bash
# Default multilingual smoke probes
kabot doctor smoke-agent

# JSON output + latency gates for fast one-shot flows
kabot doctor smoke-agent --smoke-json \
  --smoke-max-context-build-ms 1000 \
  --smoke-max-first-response-ms 1000

# Skill-focused smoke in multiple locales
kabot doctor smoke-agent \
  --smoke-skill weather \
  --smoke-skill-locales en,id,zh,ja,th

# Add a local Python MCP echo verification
kabot doctor smoke-agent --smoke-mcp-local-echo
```

---

## 🤖 Supported Models

Kabot's **ModelRegistry** abstracts away the differences between providers. You can switch models instantly via the `/switch` command without restarting.

### Commercial Models (Cloud)
| Provider | Models | Best For | Pricing |
| :--- | :--- | :--- | :--- |
| **Anthropic** | `claude-3-5-sonnet`, `claude-3-opus`, `haiku` | 🥇 **Coding & Reasoning** | $$$ |
| **OpenAI** | `gpt-4o`, `gpt-4-turbo`, `o1-preview`, `o1-mini` | 🥈 **General Logic** | $$$ |
| **Google** | `gemini-1.5-pro`, `gemini-1.5-flash` | 🥉 **Huge Context (2M)** | $ |
| **DeepSeek** | `deepseek-chat`, `deepseek-coder` | 💸 **Cost Performance** | ¢ |
| **Groq** | `llama3-70b`, `mixtral-8x7b` | ⚡ **Instant Speed (500t/s)** | 🆓 |

### Local Models (Offline)
Kabot supports **Ollama** and **LM Studio** out of the box.
*   **Ollama**: `llama3`, `mistral`, `qwen2.5-coder`
*   **Configuration**: Point `api_base` to `http://localhost:11434`.

---

## ⚙️ Configuration Reference

Configuration is stored in `config.json` in your workspace root.
You can edit this manually or use `kabot config`.

Runtime dictionaries stay outside `config.json` so the main config stays small.
Example: learned weather aliases are written to `~/.kabot/weather_aliases.json` after successful native-script weather resolutions such as `東京 -> Tokyo`.

### 1. Telegram Setup
**Get Token**: Talk to `@BotFather` on Telegram.
```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "bot_token": "1234567890:ABC-DefGhIjKlMnOpQrStUvWxYz",
      "allowed_users": [12345678]  // Your User ID (get via @userinfobot)
    }
  }
}
```

### 2. Discord Setup
**Get Token**: [Discord Developer Portal](https://discord.com/developers/applications).
**Privileged Intents**: Enable "Message Content Intent".
```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "bot_token": "MTA5...",
      "allowed_users": ["YOUR_DISCORD_USER_ID"]
    }
  }
}
```

### 3. LLM Setup (Anthropic Example)
```json
{
  "llm": {
    "provider": "anthropic",
    "model": "claude-3-5-sonnet-20240620",
    "api_key": "sk-ant-...",
    "temperature": 0.7,
    "max_tokens": 4096
  }
}
```

---

## ⚡ Slash Commands & Directives

Control Kabot's behavior directly from the chat.

**System Commands:**
*   `/help` - Show available commands.
*   `/status` - Check CPU, RAM, and Agent health.
*   `/switch <model>` - Change the active LLM (e.g., `/switch gpt4`).
*   `/doctor` - Run self-diagnostics and auto-fix config issues.
*   `/update` - Update Kabot to the latest version (git pull + restart).
*   `/restart` - Restart the agent process.
*   `/clip <text>` - Copy text to the host clipboard (Windows/WSL).
*   `/sysinfo` - Show detailed system information.

**Directives (Power User Tags):**
Unlock hidden capabilities by adding these tags to your message.
*   `/think` - **Chain of Thought**: Forces the agent to output its reasoning process before acting. Highly recommended for complex coding tasks.
*   `/verbose` - **Debug Mode**: Shows full tool outputs and token usage stats.
*   `/elevated` - **Admin Mode**: Bypasses "Are you sure?" confirmations for file edits and shell commands.
*   `/json` - Forces the final response to be valid JSON.
*   `/notools` - Prevents the agent from using any tools (pure chat).

---

## 🎛️ Model Management Tutorial

<details><summary><b>Click to expand</b></summary>

Complete guide for switching models, setting up OAuth, and managing multiple AI providers.

### Quick Start: Set OpenAI as Default

**Method 1: Via CLI (Permanent)**
```bash
# Set default model globally
kabot models set openai/gpt-4o
kabot models set gpt-4o  # Short form

# Verify the change
kabot models list --current
```

**Method 2: Via Chat Commands (Session)**
```bash
# In Telegram/Discord/WhatsApp chat
/switch openai/gpt-4o
/switch gpt-4o
/switch  # Check current model
```

### OAuth Setup for OpenAI (ChatGPT Subscription)

**Step 1: Run Setup Wizard**
```bash
kabot config
```

**Step 2: Navigate to OAuth Setup**
```
→ Model / Auth (Providers, Keys, OAuth)
→ Provider Login (Setup API Keys/OAuth)
→ OpenAI - GPT-4o, o1-preview, etc.
→ Browser Login (OAuth) - ChatGPT subscription login
```

**Step 3: Complete Browser Authentication**
- Browser opens automatically for OAuth flow
- Login with your ChatGPT account credentials
- Grant permissions when prompted
- Return to terminal when complete

**Step 4: Set Default Model**
```
→ Select Default Model (Browse Registry)
→ Filter models by provider: openai
→ Select: gpt-4o (Recommended)
```

**Troubleshooting OAuth:**
```bash
# If OAuth fails, try manual setup
kabot config
→ Model / Auth → Provider Login → OpenAI → Manual Setup

# Check OAuth token status
kabot doctor  # Validates all credentials
```

### Bot Commands Reference

**Model Switching Commands:**
```bash
# Switch model for current chat session
/switch openai/gpt-4o          # OpenAI GPT-4o
/switch anthropic/claude-sonnet-4-5  # Claude Sonnet
/switch groq/llama-3.1-70b     # Groq Llama (fast)
/switch deepseek/deepseek-coder # DeepSeek Coder

# Per-message model override (doesn't change default)
/model gpt-4o Explain quantum computing
/model groq/llama-3.1-8b Quick question about Python
```

**Model Information Commands:**
```bash
# List all available models
/models list

# Show current model
/switch

# Model usage statistics
/usage
/usage --days 7
/usage --provider openai
```

**Configuration Commands:**
```bash
# Set configuration values via chat
/config set agents.defaults.model "openai/gpt-4o"
/config get agents.defaults.model
/config list providers
```

### Multi-Provider Setup

**Supported Providers:**
| Provider | Setup Method | Best For | Cost |
|----------|--------------|----------|------|
| **OpenAI** | OAuth/API Key | General purpose, coding | $$$ |
| **Anthropic** | API Key | Complex reasoning, analysis | $$$ |
| **Groq** | API Key | Fast responses (500+ tok/s) | 🆓 |
| **DeepSeek** | API Key | Code generation, math | ¢ |
| **Google** | API Key | Large context (2M tokens) | $ |
| **OpenRouter** | API Key | 100+ models via gateway | $ |

**Configuration Example:**
```json
{
  "providers": {
    "openai": {
      "profiles": {
        "default": {
          "oauthToken": "eyJhbGciOiJSUzI1NiIs...",
          "tokenType": "oauth"
        }
      },
      "activeProfile": "default",
      "fallbacks": ["groq/llama-3.1-70b"]
    },
    "groq": {
      "apiKey": "gsk_...",
      "fallbacks": []
    },
    "anthropic": {
      "apiKey": "sk-ant-...",
      "fallbacks": ["openai/gpt-4o"]
    }
  }
}
```

### Use Case Optimization

**Task-Specific Model Selection:**
```bash
# Coding tasks → DeepSeek Coder
/switch deepseek/deepseek-coder
# "Write a Python web scraper"

# Fast responses → Groq
/switch groq/llama-3.1-8b
# "What's 2+2?"

# Complex analysis → Claude
/switch anthropic/claude-opus-4-5
# "Analyze this business strategy document"

# Creative writing → GPT-4o
/switch openai/gpt-4o
# "Write a short story about AI"
```

**Cost Optimization Strategy:**
```bash
# Development/Testing (Free/Cheap)
/switch groq/llama-3.1-8b        # Free tier
/switch deepseek/deepseek-chat    # Very cheap

# Production (Premium)
/switch openai/gpt-4o            # High quality
/switch anthropic/claude-opus-4-5 # Best reasoning
```

### Advanced Configuration

**Fallback Chain Setup:**
```json
{
  "agents": {
    "defaults": {
      "model": "openai/gpt-4o",
      "fallbacks": [
        "anthropic/claude-sonnet-4-5",
        "groq/llama-3.1-70b"
      ]
    }
  }
}
```

**Per-Agent Model Assignment:**
```json
{
  "agents": {
    "list": [
      {
        "id": "coding",
        "model": "deepseek/deepseek-coder",
        "workspace": "~/code"
      },
      {
        "id": "writing",
        "model": "openai/gpt-4o",
        "workspace": "~/docs"
      },
      {
        "id": "quick",
        "model": "groq/llama-3.1-8b",
        "workspace": "~/temp"
      }
    ],
    "bindings": [
      {"agent_id": "coding", "channel": "telegram", "chat_id": "coding_chat"},
      {"agent_id": "writing", "channel": "discord"},
      {"agent_id": "quick", "channel": "telegram", "chat_id": "quick_chat"}
    ]
  }
}
```

### CLI Model Management

**List and Discovery:**
```bash
# List all available models
kabot models list

# Filter by provider
kabot models list --provider openai
kabot models list --provider anthropic

# Show premium models only
kabot models list --premium

# Get detailed model info
kabot models info gpt-4o
kabot models info claude-sonnet-4-5

# Scan for new models
kabot models scan
```

**Model Configuration:**
```bash
# Set primary model
kabot models set openai/gpt-4o

# Set with fallbacks
kabot models set anthropic/claude-sonnet-4-5 --fallback groq/llama-3.1-70b

# Reset to default
kabot models reset
```

### Troubleshooting

**Common Issues:**

**1. "No API key configured" Error:**
```bash
# Check provider configuration
kabot doctor

# Check deterministic routing guard matrix
kabot doctor routing

# Verify OAuth token
kabot config
→ Model / Auth → Provider Login → OpenAI → Check Status

# Manual API key setup
export OPENAI_API_KEY="sk-..."
```

**2. Model Not Found:**
```bash
# Update model registry
kabot models scan

# Check available models
kabot models list --provider openai

# Use full model name
/switch openai/gpt-4o  # Not just "gpt-4o"
```

**3. OAuth Token Expired:**
```bash
# Re-authenticate
kabot config
→ Model / Auth → Provider Login → OpenAI → Browser Login

# Check token status
kabot auth status openai
```

**4. Unicode/Emoji Display Issues (Windows):**
```bash
# Use Windows Terminal or PowerShell
# Or set environment variables:
set PYTHONIOENCODING=utf-8
setx PYTHONIOENCODING utf-8  # Permanent
```

**5. Provider Priority Issues:**
```bash
# Check current provider matching
kabot models list --current

# Force specific provider
/switch openai/gpt-4o  # Explicit provider prefix

# Clear conflicting API keys
kabot config
→ Model / Auth → Remove unused providers
```

### Best Practices

**1. Default Setup Recommendation:**
- **Primary**: OpenAI (OAuth) for general use
- **Coding**: DeepSeek for programming tasks
- **Fast**: Groq for quick responses
- **Backup**: Anthropic for complex reasoning

**2. Security:**
- Use OAuth when available (no API key exposure)
- Store API keys in environment variables
- Use `allowed_users` for public channels

**3. Cost Management:**
- Start with free tiers (Groq, DeepSeek free tier)
- Use cheaper models for testing/development
- Reserve premium models for production

**4. Performance:**
- Use Groq for speed-critical applications
- Use Claude/GPT-4o for quality-critical tasks
- Set appropriate fallback chains

</details>

---

## 🔒 Security

Kabot is effectively a **remote shell** wrapped in an LLM. Security is paramount.

### Trust Model
*   **Default**: Single-user, trusted mode. The configured user has full access to the file system and shell.
*   **Allowlisting**: You **MUST** configure `allowed_users` in `config.json` for public channels (Telegram/Discord). Messages from unknown users are logged but ignored.

### Docker Sandboxing (Recommended)
For maximum security, especially if you plan to let Kabot execute code freely, run it inside Docker.

```bash
# Build the image
docker build -t kabot .

# Run with volume mapping
docker run -d \
  --name kabot \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config.json:/app/config.json \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  kabot
```
Because Kabot is "stateful" (SQLite DB), mapping the `/data` volume is critical.

---

## 🤝 Development & Contributing

We welcome contributions! Kabot is open-source and community-driven.

**Development Setup:**
1.  Fork the repository.
2.  Install dependencies: `pip install -r requirements.txt && pip install -r requirements-dev.txt`
3.  Run tests: `pytest tests/`
4.  Run linter: `ruff check .`

**Branching Strategy:**
*   `main`: Stable releases.
*   `dev`: Active development branch.

Please adhere to the coding style (Black/Ruff) and include tests for new features.

---

## 📜 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=kaivyy/kabot&type=date)](https://star-history.com/#kaivyy/kabot&Date)

---

## 🙌 Community

Join the discussion, get support, or show off your subagents.

*   [GitHub Issues](https://github.com/kaivyy/kabot/issues) for bug reports.
*   [Telegram Group](https://t.me/kabot_support) for live support.
*   [Discussions](https://github.com/kaivyy/kabot/discussions) for feature requests.

Special thanks to the open-source community and projects like **Kabot** that inspired our resilience architecture.

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/kaivyy">@kaivyy</a>
</p>

