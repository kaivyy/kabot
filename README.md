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

[Website](https://kabot.ai) · [Docs](docs/) · [Architecture](docs/openclaw-analysis/openclaw-deepest-architecture.md) · [Getting Started](#quick-start) · [Telegram](https://t.me/kabot_support) · [FAQ](#faq)

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
Inspired by [OpenClaw](https://openclaw.ai)'s robustness but built for Python.
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
