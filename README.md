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

#### 👁️ Vision & 🗣️ Voice
Kabot is now multi-modal.
- **Vision**: Send screenshots of errors or UI mockups, and Kabot will analyze them using GPT-4o or Claude 3.5 Sonnet.
- **Voice**: Send voice notes on Telegram/WhatsApp, and Kabot will listen (Whisper) and reply with spoken audio (TTS).

#### 🔄 Autonomous Loop
Self-healing execution mode. If a task fails, Kabot automatically analyzes the error, attempts a fix, and retries up to 5 times before asking for help.

#### 🔑 Multi-Method Authentication (v2.0)
Kabot supports flexible authentication beyond simple API keys.
- **Smart OAuth**: Securely login via your browser with automatic port detection and VPS support.
- **Secret Extraction**: Automatically discover credentials from local CLI tools (e.g., Google Gemini CLI).
- **Multi-Profile**: Manage multiple accounts (Personal/Work) per provider.

#### 🐳 Docker Sandbox
Enterprise-grade security. Run all shell commands inside an isolated Docker container to prevent accidental system damage.

#### 🧠 Hybrid Resilient Memory
Solves the "amnesia" problem inherent in LLMs.
- **Dual-Layer Storage**: Combines **ChromaDB** (Semantic/Vector) for fuzzy concept retrieval with **SQLite** (Structured) for exact fact retention.

#### 🏷️ Smart Model Management
- **Smart Resolver**: Use aliases (`sonnet`, `gpt4`) or short names.
- **Fallback Chain**: Automatic switching to backup models if the primary model fails.
- **Dynamic Discovery**: Scan provider APIs to find the latest models.

#### 🔌 Universal Integration
Deploy your agent anywhere. Kabot acts as a central brain connected to multiple interfaces.

| Platform | Features | Setup |
|----------|----------|-------|
| **Telegram** | Full chat, file sharing, voice notes | `@BotFather` token |
| **Discord** | Channel/DM support, rich embeds | Bot Token |
| **Slack** | Workspace integration, thread support | App Token + Bot Token |
| **WhatsApp** | (Beta) Via local bridge | QR Code Login |
| **Email** | SMTP/IMAP for async tasks | Gmail/Credentials |

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

#### 1. Modular Setup Wizard
Run the professional interactive wizard to configure everything:
```bash
kabot setup
```

#### 2. Authentication via CLI
Directly configure specific providers:
```bash
kabot auth login <provider>
```

---
<p align="center">Built with ❤️ by <a href="https://github.com/kaivyy">@kaivyy</a></p>
