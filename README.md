<div align="center">
  <img src="kabot_logo.png" alt="kabot" width="200">
  <h1>Kabot 🐈</h1>
  <p>
    <b>Resilient Memory. Methodical Execution. Native Reasoning.</b>
  </p>
  <p>
    <a href="https://pypi.org/project/kabot-ai/"><img src="https://img.shields.io/pypi/v/kabot-ai?style=flat-square" alt="PyPI"></a>
    <img src="https://img.shields.io/badge/python-3.11+-blue.svg?style=flat-square" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
    <a href="#"><img src="https://img.shields.io/badge/Telegram-Bot-blue?style=flat-square&logo=telegram&logoColor=white" alt="Telegram"></a>
    <a href="#"><img src="https://img.shields.io/badge/Discord-Bot-5865F2?style=flat-square&logo=discord&logoColor=white" alt="Discord"></a>
    <a href="#"><img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker"></a>
  </p>
</div>

---

**Kabot** is a _personal AI assistant_ engineered for **resilience**, **complex task execution**, and **long-term memory**. It isn't just a chatbot; it's an autonomous agent that runs on your own hardware, remembering context across restarts and methodically planning its actions.

It bridges the gap between simple chatbots and autonomous software engineers. While typical agents operate blindly, Kabot implements a **Methodical Engineering Workflow** (Brainstorm → Plan → Execute) and relies on a proprietary **Hybrid Memory Architecture** (SQLite + Vector) to handle long-running projects without "amnesia".

If you want a personal, single-user assistant that feels local, fast, and always-on, this is it.

[Website](https://kabot.ai) · [Docs](docs/) · [Getting Started](#quick-start) · [Telegram](https://t.me/kabot_support) · [FAQ](#faq)

---

## 🚀 Quick Start

**Runtime**: Python 3.11+
Tested on Windows (WSL2), macOS, and Linux (Ubuntu/Debian).

### Option 1: Automatic Install (Recommended)

**Linux / macOS / WSL2:**
```bash
curl -fsSL https://raw.githubusercontent.com/kaivyy/kabot/main/install.sh | bash
# Follow the on-screen wizard to set API keys
```

**Windows (PowerShell):**
```powershell
iwr -useb https://raw.githubusercontent.com/kaivyy/kabot/main/install.ps1 | iex
```

### Termux (Android)
Turn your phone into an AI server.
1.  **Install Dependencies**:
    ```bash
    pkg update && pkg upgrade
    pkg install python git clang make libjpeg-turbo freetype rust
    termux-setup-storage
    ```
2.  **Install Kabot**:
    ```bash
    git clone https://github.com/kaivyy/kabot.git
    cd kabot
    pip install -e .
    ```
3.  **Run**: `kabot gateway`

### Option 2: Manual Developer Install

Prefer `uv` or `poetry` for dependency management, but `pip` works fine.

```bash
git clone https://github.com/kaivyy/kabot.git
cd kabot
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .

# Run the interactive setup wizard
kabot config

# Start the Gateway
kabot gateway
```

### Chatting
Once the gateway is running, you can talk to Kabot via:
*   **CLI**: `kabot agent -m "Hello"` (Fastest for testing)
*   **Telegram**: DM your bot.
*   **Discord**: Mention the bot in a channel.

---

## 🔥 Core Capabilities

### 🧠 **Autonomous Reasoning**
Kabot doesn't just answer; it thinks.
*   **`/think` Mode**: Forces the agent to output its reasoning process (`Chain-of-Thought`) before taking action. Great for complex refactoring or architectural decisions.
*   **Self-Correction**: If a tool fails (e.g., syntax error in a generated script), Kabot reads the error, analyzes it, and attempts a fix automatically up to 5 times.
*   **Planning**: Specifically designed for "multi-step" tasks. Ask it to "Plan a new module", and it will generate a `task.md` file and execute it step-by-step.

### 🛡️ **Enterprise Resilience**
Built for robustness and strict security in Python.
*   **Crash Sentinel**: Kabot writes a "sentinel file" before processing each message. If the host machine loses power or crashes, Kabot detects the unclean shutdown on the next boot and offers to resume the exact session state.
*   **Session Locking**: Uses `PIDLock` (process-based locking) to ensure atomic writes to the session database, preventing corruption even if multiple cron jobs fire simultaneously.
*   **Persistent Subagents**: Delegate tasks like "Research this library" to background agents. These subagents persist their state to disk (`.json` registry), so they survive system reboots and can be queried days later.

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

---

## 🔌 Multi-Channel Instances

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
│     localhost:18790           │
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

#### 3. Hybrid Memory
Located in `kabot/memory/`. It solves the "context window limit" problem.
*   **Vector Store**: Semantic search for fuzzy concepts ("What did we discuss about architecture?").
*   **SQL Store**: Exact matching for facts ("What is the API key for Stripe?").
*   **Summarizer**: Automatically condenses old conversation turns into summaries to save tokens.

#### 4. Doctor (Self-Healing)
Located in `kabot/core/doctor.py`. A diagnostic engine that runs on startup.
*   Checks database integrity.
*   Validates API keys.
*   Verifies Python environment dependencies.
*   **Auto-Fix**: Can automatically reinstall missing pip packages or rebuild corrupted config files.

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

Special thanks to the open-source community and projects like **OpenClaw** that inspired our resilience architecture.

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/kaivyy">@kaivyy</a>
</p>
