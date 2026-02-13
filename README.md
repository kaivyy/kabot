<div align="center">
  <img src="kabot_logo.png" alt="kabot" width="120">
  <h1>Kabot 🐈</h1>
  <p>
    <b>Resilient Memory. Methodical Execution. Native Reasoning.</b>
  </p>
  <p>
    <a href="https://pypi.org/project/kabot-ai/"><img src="https://img.shields.io/pypi/v/kabot-ai" alt="PyPI"></a>
    <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
</div>

---

### Overview

**Kabot** is an advanced AI agent framework engineered for reliability and complex task execution. It bridges the gap between simple chatbots and autonomous software engineers.

Unlike typical agents that operate blindly, Kabot implements a **Methodical Engineering Workflow** (Brainstorm → Plan → Execute) and relies on a proprietary **Hybrid Memory Architecture** to maintain context over long-running projects.

It is designed to be your **24/7 Pair Programmer** and **DevOps Assistant**, accessible directly from your favorite chat apps.

### 🔥 Core Capabilities

#### 👁️ Vision & 🗣️ Voice (New in v0.2.0)
Kabot is now multi-modal.
- **Vision**: Send screenshots of errors or UI mockups, and Kabot will analyze them using GPT-4o or Claude 3.5 Sonnet.
- **Voice**: Send voice notes on Telegram/WhatsApp, and Kabot will listen (Whisper) and reply with spoken audio (TTS).

#### 🔄 Autonomous Loop
Self-healing execution mode. If a task fails, Kabot automatically analyzes the error, attempts a fix, and retries up to 5 times before asking for help.
```bash
python kabot/skills/autonomous-task/scripts/run_loop.py --goal "Fix the bug"
```

#### 🔐 Multi-Method Authentication (New in v1.0.0)
Kabot supports flexible authentication beyond simple API keys.
- **OAuth (Browser Login)**: Securely login via your browser for OpenAI and Google accounts.
- **Setup Tokens**: Use tokens from provider-specific CLIs (e.g., Anthropic).
- **Subscription Plans**: Dedicated support for Kimi Code and MiniMax Coding subscriptions.
- **VPS Ready**: Built-in support for remote/headless environments.

#### 🛡️ Docker Sandbox
Enterprise-grade security. Run all shell commands inside an isolated Docker container to prevent accidental system damage.
*(Requires Docker Desktop)*

#### 🧠 Hybrid Resilient Memory
Solves the "amnesia" problem inherent in LLMs.
- **Dual-Layer Storage**: Combines **ChromaDB** (Semantic/Vector) for fuzzy concept retrieval with **SQLite** (Structured) for exact fact retention.

#### ⏰ Smart Cron & Reminders
Enhanced scheduling with automatic cleanup to prevent infinite loops.
- **One-shot Reminders**: Use the `one_shot` flag to automatically delete jobs after execution.
- **Improved Reliability**: Service-level synchronization prevents memory-to-disk overwrite bugs.
- **Chat Command**: "Bangunkan saya dalam 5 menit (sekali saja)" → Kabot sets a one-shot task.
- **Context Awareness**: Intelligently manages token budgets to preserve critical memories while discarding noise.

#### 🧭 Structured "Guided Workflow"
Kabot doesn't just guess; it follows engineering best practices.
- **Phase 1: Discovery**: Proactive brainstorming to clarify ambiguous requirements.
- **Phase 2: Architecture**: Generates technical plans before writing a single line of code.
- **Phase 3: Execution**: Writes, tests, and fixes code autonomously using a robust toolset.

#### 🛡️ Production-Grade Safety
- **Shell Guard**: Regex-based filtering and high-risk command blocking to prevent accidental damage.
- **Token Budgeting**: Dynamic context window management prevents API crashes on large projects.
- **Smart Feedback**: "Live Activity Stream" broadcasts real-time status updates (reading, editing, searching) to the user.

#### 🔌 Universal Integration

Deploy your agent anywhere. Kabot acts as a central brain connected to multiple interfaces.

| Platform | Features | Setup |
|----------|----------|-------|
| **Telegram** | Full chat, file sharing, voice notes | `@BotFather` token |
| **Discord** | Channel/DM support, rich embeds | Bot Token |
| **Slack** | Workspace integration, thread support | App Token + Bot Token |
| **WhatsApp** | (Beta) Via local bridge | QR Code Login |
| **Email** | SMTP/IMAP for async tasks | Gmail/Outlook credentials |
| **CLI** | Direct terminal access | Included by default |

### 🤖 Supported AI Models

Kabot is provider-agnostic. You can switch models instantly via `config.json` or the setup wizard.

| Provider | Recommended Models | Best For |
|----------|-------------------|----------|
| **OpenRouter** | `anthropic/claude-3.5-sonnet`, `openai/gpt-4o` | **Best Overall** (Speed + Intelligence) |
| **DeepSeek** | `deepseek-r1`, `deepseek-chat` | **Reasoning** & Coding Tasks |
| **Anthropic** | `claude-3-opus`, `claude-3-sonnet` | Complex Writing & Analysis |
| **Google** | `gemini-1.5-pro` | Long Context (2M tokens) |
| **Groq** | `llama-3-70b` | **Ultra-Fast** Responses |
| **Local (vLLM)** | `llama-3`, `mistral`, `qwen` | Privacy & Offline Use |

---

### ⚡ One-Line Install

**Linux / macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/kaivyy/kabot/main/install.sh | bash
```

**Windows (PowerShell):**
```powershell
iwr -useb https://raw.githubusercontent.com/kaivyy/kabot/main/install.ps1 | iex
```

### 🛠️ Configuration

#### 1. Authentication via CLI (Preferred)
The most secure and flexible way to configure your AI providers:
```bash
kabot auth login <provider>
```
Supported providers include `openai`, `anthropic`, `google`, `kimi`, `minimax`, and `ollama`. See [Authentication Guide](docs/authentication.md) for details.

#### 2. Interactive Wizard
Alternatively, run the full setup wizard for models and channels:
```bash
kabot setup
```
This will guide you through provider selection, API keys, and channel setup.

#### 2. Manual Configuration (`config.json`)
You can also edit the configuration file manually at `~/.kabot/config.json`.

**Example Config:**
```json
{
  "agents": {
    "defaults": {
      "model": "openrouter/anthropic/claude-3.5-sonnet",
      "max_tokens": 8192,
      "temperature": 0.7
    },
    "models": {
      "custom": {
        "my-local-model": {
          "context_window": 32000
        }
      }
    }
  },
  "providers": {
    "openrouter": {
      "api_key": "sk-or-v1-..."
    },
    "openai": {
      "api_key": "sk-..."
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "123456:ABC-DEF...",
      "allow_from": ["123456789"]
    }
  }
}
```

### 🚀 Running (Production)

To enable **Auto-Restart** and **Crash Recovery**, use the provided watchdog scripts instead of running Python directly.

**Windows:**
```powershell
.\start_kabot.bat
```

**Linux / macOS:**
```bash
./start_kabot.sh
```

*(These scripts will automatically restart Kabot if it crashes or if you use the `/restart` command)*

### 🚀 Running (Manual)
For debugging or development:
```bash
kabot gateway
```

Or run interactively in the terminal:

```bash
kabot agent -m "Hello!"
```

---
<p align="center">Built with ❤️ by <a href="https://github.com/kaivyy">@kaivyy</a></p>
