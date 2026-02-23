# The Ultimate Beginner's Guide to Kabot

Welcome to **Kabot**, your personal, locally-hosted AI assistant framework designed to become your ultimate "Second Brain." Kabot allows you to build highly intelligent AI agents that work for you 24/7 on your local machine (like a Mac Mini, PC, or VPS). You can even create distributed teams of specialized agents tailored to different roles.

This tutorial is written specifically for beginners. It will guide you step-by-step on how to run, configure, and maximize all of Kabot's features—no coding experience required!

---

## 1. Initializing Kabot (Your First Boot)

If this is the very first time you are running Kabot on your machine, you must initialize its core folders and databases.

Open your Terminal (Command Prompt/PowerShell on Windows, or Terminal on Mac/Linux) and type:

```bash
kabot setup
```

**What does this do?**
This command safely creates the foundational folder structure for Kabot's "brain." It creates a hidden folder named `.kabot` in your user directory (for example, `C:\Users\Username\.kabot\` on Windows or `~/.kabot/` on Mac/Linux). Kabot stores all of its memory databases, configurations, and secure tokens inside this localized folder to ensure your data stays 100% private.

---

## 2. Configuring Your Agents (The Setup Wizard)

This is Kabot's secret weapon. Instead of forcing you to edit complex configuration files or code, Kabot provides a beautifully interactive, user-friendly Configuration Menu right in your terminal.

To summon the settings menu, type one of these commands:

```bash
kabot setup
```

```bash
kabot config
```

```bash
kabot config --edit
```

Once you hit `Enter`, the interactive **Configuration Menu** will appear. Use your keyboard arrows to navigate. Let's break down exactly what every option does and how to use it:

### a) Workspace (Set path + sessions)
*   **What it does:** Defines the specific "identity" and memory bank of the AI agent you are currently talking to. You can easily create multiple distinct agents.
*   **How to use it:** If you want a specialized team (e.g., a finance agent, a parenting agent, a coding agent), you create different workspaces. For example, create a workspace named "finance" and another named "parenting." *Crucially, each workspace has its own isolated memory.* Each agent stays focused on its own context.

### b) Model / Auth (Providers, Keys, OAuth)
*   **What it does:** Connects Kabot to its "Main Brain" (the LLM API, such as Claude, Gemini, or OpenAI) and securely stores your API keys.
*   **How to use it:** Select your provider/model and add your API key (OpenAI, Anthropic, OpenRouter, Groq, etc.). Kabot supports fallbacks, so you can set a primary model and a backup model if the first one fails. For quick switches in chat, use `/switch <model>`.

### c) Memory (Backend, Embeddings, Database)
*   **What it does:** Controls how Kabot remembers conversations, facts, and user preferences. It is the core of Kabot's "Second Brain".
*   **How to use it:** You can switch between different memory engines depending on your machine's capabilities:
    *   **Hybrid (Recommended):** The most powerful engine using vector embeddings for semantic intelligence.
    *   **SQLite Only:** A lightweight mode utilizing keyword searches without embeddings (perfect for Termux or Raspberry Pi).
    *   **Disabled:** Turns off the memory system entirely for a stateless chat experience.

### d) Tools & Sandbox (Search, Docker, Shell)
*   **What it does:** Gives physical superpowers to your agent. Without tools, Kabot is just a chatbot. With tools, Kabot becomes a proactive assistant.
*   **How to use it:** Here, you toggle access to Kabot's abilities. You can grant it permission to type Terminal commands, read files on your hard drive, or use web search and fetch tools. Docker sandboxing can be enabled for safer command execution.

### e) Skills (Install & Configure)
*   **What it does:** Injects "SOPs" (Standard Operating Procedures) or foundational expertise directly into the agent's initial prompt.
*   **How to use it:** Useful if you download custom third-party "Skill Files" (Markdown scripts) that teach Kabot exactly how to behave or format its responses for specific career roles.

### f) Google Suite (Auth & Credentials)
*   **What it does:** Grants Kabot secure, native access to act on behalf of your Google Account.
*   **How to use it:** Once authorized, Kabot can send emails, schedule Calendar meetings, and read/create files in Google Drive and Google Docs via the Google integrations. 
    *   **The Process:** Provide the path to a `google_credentials.json` file (downloaded from your Google Cloud Console). Kabot opens a browser tab for consent, then stores the token locally. You can also run `kabot google-auth <path>` for the fastest setup.

### g) Channels (Telegram, WhatsApp, Slack)
*   **What it does:** Connects Kabot's brain to your mobile phone so you don't have to stay glued to your computer terminal.
*   **How to use it:** You can insert your Telegram Bot Token or WhatsApp configuration here. Once connected, your family or business partners can simply text the bot on Telegram, and Kabot will process the requests on your local server and reply directly to their phones! 

### h) Auto-start (Enable boot-up service)
*   **What it does:** Ensures Kabot automatically starts running in the background whenever you turn on or restart your computer/server (systemd on Linux, launchd on macOS, Task Scheduler on Windows, Termux on Android).

### i) Doctor (Health Check)
*   **What it does:** Runs an automatic system diagnostic. If Kabot isn't responding or throws an error, click this menu to instantly check if an API connection is broken or if a local database file is corrupted.

---

## 3. Starting an Interactive Chat

Once you have configured your model and API keys using the wizard, it's time to start chatting!

**To send a quick, one-off command:**
```bash
kabot agent -m "Hello Kabot, please schedule a daily standup meeting in my calendar for tomorrow morning."
```

**To open the Interactive Chat Room:**
If you simply type `kabot agent` without the `-m` message flag, you will enter the **Interactive Shell**. This functions exactly like the ChatGPT interface, but right inside your command-line terminal.

---

## 4. Chat-Based Learning (Learn from Attachments)

This is one of Kabot's most intuitive features. Instead of using the command line, you can simply "send" knowledge to your agent via chat (Telegram, WhatsApp, etc.).

*   **How to use it:**
    1. Attach a document (.pdf, .md, .txt, or .csv) to your message in the chat app.
    2. Add a message like: *"Please memorize this document"* or *"Learn this guide"*.
    3. Kabot will detect the file and use the `knowledge_learn` tool.
    4. Once processed, Kabot will confirm: *"Success! I have learned knowledge chunks from [filename]."*
*   **What happens?** The agent autonomously reads, chunks, and injects the document into its permanent memory. From that point on, across all future sessions, that agent will have that knowledge at its fingertips.

---

## 5. AI-as-Developer: Dynamic Automation

Kabot isn't just a chatbot; it's a **Dynamic AI Developer**. Kabot doesn't rely solely on hardcoded tools. Instead, it can build its own tools and automations on the fly based on your desires.

*   **How to use it:**
    *   **Ask for anything:** *"Bikin script untuk cek harga bursa tiap 10 menit"* or *"Automate server monitoring and alert me if CPU > 90%"*.
    *   **Kabot Executes:** Kabot will write the script (`write_file`), run it immediately to verify (`exec`), and then schedule it as a recurring background task (`cron`).
    *   **Verification:** Kabot follows a strict **Execute-and-Verify** discipline. It won't just tell you it wrote a file; it will run it and confirm the actual results or logs back to you.
    *   **Dynamic Learning:** If a script fails, Kabot will diagnose and fix the code autonomously without you needing to manually edit files.

### Advanced AI-as-Developer Features (v0.5.4)

Kabot now includes sophisticated backend systems that prevent common AI agent failures and enhance reliability:

**Tool Loop Detection**
- Automatically detects when AI gets stuck calling the same tool repeatedly
- **Warning threshold**: 10 identical calls - logs warning but allows execution
- **Critical threshold**: 20 identical calls - blocks execution and returns error
- **Ping-pong detection**: Identifies alternating tool patterns (e.g., read_file ↔ write_file)
- **Example**: If AI calls `exec ls` 20 times with same params, Kabot blocks it and explains the loop

**Tool Policy Profiles**
- Control which tools are available based on use case
- **Profiles available**:
  - `minimal`: Only session status (safest)
  - `coding`: Filesystem, web, memory (no automation/runtime)
  - `messaging`: Sessions, memory, Google suite, weather
  - `analysis`: Stocks, crypto, weather, web (no filesystem/runtime)
  - `full`: All tools available (default)
- **Tool groups**: `@fs` (filesystem), `@runtime` (exec/spawn), `@web`, `@memory`, `@automation` (cron), `@google`, `@analysis`, `@system`
- **Owner-only tools**: `cron`, `exec`, `spawn`, `cleanup_system` require owner permission

**Enhanced Error Classification**
- Intelligent categorization of API errors for smarter recovery
- **Categories**: billing, rate_limit, auth, timeout, format, model_not_found, unknown
- **Auto-retry**: Rate limits and timeouts trigger automatic retry
- **Auto-fallback**: Billing, auth, and model errors trigger model fallback
- **Example**: 429 rate limit → rotate API key → retry; 401 auth → fallback to secondary model

**Context Management** (Already Active)
- **Context Window Guard**: Prevents crashes from small context windows (blocks < 16K tokens, warns < 32K)
- **Auto-Compaction**: Summarizes old messages when context overflows (keeps recent 10 exchanges)
- **Result Truncation**: Caps tool results at 30% of context window to prevent bloat

---

## 6. Server & Resource Monitoring

Kabot now comes with powerful, cross-platform server monitoring built right in. It works on Windows, Linux/VPS, macOS, and even Android (Termux).

*   **Real-Time Status:** Simply ask *"monitor server"*, *"cek cpu"*, or *"status pc"* to get an instant snapshot of:
    *   **CPU Load %**
    *   **RAM Usage** (Total, Used, Free in GB)
    *   **Disk Usage** (per drive/partition)
    *   **Uptime** & **Network I/O** (on supported systems)
*   **Slash Commands:** Use `/sysinfo` for hardware specs or `/status` for a quick health check.
*   **Custom Alerts:** Using the **AI-as-Developer** behavior mentioned above, you can ask Kabot to set up custom alerts: *"Monitor RAM and alert me if free space < 1GB"*. Kabot will build the watchdog script and schedule it for you.
---

## 7. System Health & Maintenance (Advanced CLI)

Kabot ships with self-diagnostics so you can quickly verify if your setup is healthy.

### KABOT DOCTOR (Health Check + Auto Fix)
*   **When to use it:** When Kabot is acting weird, credentials fail, or you want a full health report.
*   **The Command (read-only):**
    ```bash
    kabot doctor
    ```
*   **The Command (auto-fix critical issues):**
    ```bash
    kabot doctor --fix
    ```
*   **Optional (sync bootstrap files):**
    ```bash
    kabot doctor --fix --bootstrap-sync
    ```
*   **What happens?** Kabot checks config integrity, workspace setup, and runtime dependencies, then prints a clear health report. With `--fix`, it auto-repairs critical issues.

---

## 8. Auto-Update System

Kabot includes a chatbot-accessible auto-update system that allows you to check for updates and update Kabot through natural language conversation.

### Checking for Updates

Simply ask Kabot in natural language:
- "Periksa apakah ada update baru?"
- "Check for updates"
- "Is there a new version available?"

Kabot will use the `check_update` tool to:
- Detect your installation method (git clone or pip install)
- Check GitHub releases for the latest version
- Compare with your current version
- Report commits behind (for git installations)

**Example response:**
```
Current version: 0.5.2
Latest version: 0.5.3
Installation method: git
Commits behind: 5
Update available: Yes
Release URL: https://github.com/kaivyy/kabot/releases/tag/v0.5.3
```

### Updating Kabot

Once you confirm an update is available, tell Kabot:
- "Update program"
- "Update Kabot"
- "Install the update"

Kabot will:
1. Verify your working tree is clean (git only)
2. Execute the update (git pull or pip upgrade)
3. Install dependencies
4. Ask for restart confirmation
5. Restart if confirmed

**For git installations:**
- Runs `git fetch origin` and `git pull origin main`
- Requires clean working tree (no uncommitted changes)

**For pip installations:**
- Runs `pip install --upgrade kabot-ai`

**Restart process:**
- Kabot creates a platform-specific restart script
- Waits 2 seconds for graceful shutdown
- Restarts Kabot automatically
- Notifies you when complete

### Anti-Hallucination Design

The update system is designed to prevent AI hallucination:
- Tools return structured JSON data (not prose)
- GitHub API is the source of truth for releases
- Git commands verify actual repository state
- All operations are logged
- No fake data is generated on API failures

---

## 9. Two Powerful Shortcut Commands (Advanced CLI)

While the Setup Wizard (`kabot setup` / `kabot config`) covers 99% of your needs, Kabot offers two specialized command-line shortcuts for advanced "Power Users".

### KABOT TRAIN (The Auto-Onboarding System)
*   **When to use it:** When you want to instantly inject massive amounts of knowledge (like a 300-page book) into your agent's permanent memory without spending hours typing manual prompts.
*   **The Command:**
    ```bash
    kabot train C:\Path\To\Your\Parenting_Guide.pdf --workspace parenting
    ```
*   **What happens?** Kabot uses its internal Document Parser to read the entire PDF, Markdown, or TXT file. It chunks the text into AI-friendly paragraphs and injects this knowledge directly into the Vector Database (ChromaDB) of the specified workspace (`parenting`). From the very next second, that agent will answer questions as an expert on that material.

### KABOT GOOGLE-AUTH (Rapid OAuth Setup)
*   **When to use it:** If you skipped the Setup Wizard and want a fast track to authorizing your Google Suite integrations (Drive, Docs, Mail, Calendar).
*   **The Command:** 
    ```bash
    kabot google-auth C:\Downloads\my_google_credentials.json
    ```
*   **What happens?** Instead of navigating menus, this command instantly grabs your downloaded API key, opens the secure Google Consent screen in your browser, and locks the permanent authentication token directly into Kabot's memory. *(If you are deploying on a headless VPS/Linux server without a screen, see the Advanced FAQ on how to authorize first on a laptop and transfer the `token.json` file securely to the server).*

---

## 10. Chat Slash Commands (Quick Controls)

Inside the chat (CLI, Telegram, WhatsApp, etc.) you can control Kabot using slash commands.

**Core commands:**
*   `/help` — list available commands.
*   `/status` — system snapshot (CPU/RAM, provider, model, uptime).
*   `/switch <model>` — switch active LLM model (example: `/switch openai/gpt-4o`).
*   `/doctor` — run diagnostics from chat (same as CLI doctor).
*   `/benchmark` — quick model performance benchmark.
*   `/sysinfo` — detailed system info.
*   `/uptime` — show how long Kabot has been running.
*   `/clip <text>` — copy text to system clipboard (where supported).

**Admin commands (restricted):**
*   `/update` — pull updates and restart (admin only).
*   `/restart` — restart Kabot process (admin only).

**Example:**
```
/status
/switch anthropic/claude-3-5-sonnet-20241022
/doctor
```

---

## 11. Complete Tools Reference

Kabot includes 36 built-in tools that give AI powerful capabilities. Here's the complete reference:

### **Filesystem Tools**
- **read_file** - Read file contents
  - Example: "Read the config.yaml file"
- **write_file** - Create or overwrite files
  - Example: "Write a Python script to fetch Bitcoin prices"
- **edit_file** - Edit existing files with find/replace
  - Example: "Change the API endpoint in config.py"
- **list_dir** - List directory contents
  - Example: "Show me all files in the src folder"

### **Shell & Execution**
- **exec** - Execute shell commands (with CommandFirewall protection)
  - Example: "Run pytest tests/test_memory.py"
  - Security: Requires approval for destructive commands
- **spawn** - Create background subagents for long-running tasks
  - Example: "Spawn a subagent to monitor logs continuously"

### **Automation & Scheduling**
- **cron** - Schedule reminders and recurring tasks
  - Actions: add, list, list_groups, remove, remove_group, update, update_group, run, runs, status
  - Example: "Remind me to drink water every hour"
  - Example: "Create a daily backup job at 2 AM"
  - Supports: one-shot reminders, recurring intervals, cron expressions, grouped schedules

### **Memory & Knowledge**
- **save_memory** - Save facts to long-term memory
  - Example: "Remember that I prefer dark mode"
- **get_memory** - Retrieve saved memories
  - Example: "What do you remember about my preferences?"
- **memory_search** - Semantic search across all memories
  - Example: "Search for conversations about Python"
- **knowledge_learn** - Learn from documents (PDF, MD, TXT, CSV)
  - Example: "Learn this 300-page manual" (attach file)

### **Web & Internet**
- **web_search** - Search the web (DuckDuckGo)
  - Example: "Search for latest React 19 features"
- **web_fetch** - Fetch and parse web pages
  - Example: "Fetch the content from https://example.com/docs"
- **browser** - Advanced web automation (Playwright)
  - Example: "Navigate to GitHub and screenshot the trending page"

### **Google Suite Integration**
- **gmail** - Send and read emails
  - Example: "Send an email to team@company.com with meeting notes"
- **google_calendar** - Manage calendar events
  - Example: "Schedule a standup meeting tomorrow at 9 AM"
- **google_docs** - Create and edit Google Docs
  - Example: "Create a new doc with project requirements"
- **google_drive** - Upload and manage Drive files
  - Example: "Upload report.pdf to my Drive"

### **Financial & Market Data**
- **stock** - Real-time stock prices (Yahoo Finance)
  - Example: "What's the current price of AAPL?"
  - Supports: Multiple tickers, real-time data
- **crypto** - Cryptocurrency prices (CoinGecko)
  - Example: "Check Bitcoin and Ethereum prices"
- **stock_analysis** - Advanced stock analysis with charts
  - Example: "Analyze TSLA stock performance over the last month"

### **System Monitoring**
- **server_monitor** - Monitor CPU, RAM, disk, network
  - Example: "Check server status"
  - Cross-platform: Windows, Linux, macOS, Termux
- **get_system_info** - Get hardware specifications
  - Example: "Show system info"
- **get_process_memory** - Check Kabot's memory usage
  - Example: "How much RAM is Kabot using?"
- **speedtest** - Test internet speed
  - Example: "Run a speed test"

### **Weather & Environment**
- **weather** - Get weather forecasts
  - Example: "What's the weather in Jakarta?"
  - Auto-detects location from context

### **Utilities**
- **message** - Send messages to other sessions/agents
  - Example: "Send a message to the finance agent"
- **autoplanner** - Autonomous multi-step task execution
  - Example: "Read file.txt and count lines" (auto-creates plan)
- **image_gen** - Generate AI images (if configured)
  - Example: "Generate an image of a sunset over mountains"
- **cleanup_system** - Clean up temporary files and caches
  - Example: "Clean up old log files"

### **Update System**
- **check_update** - Check for Kabot updates
  - Example: "Periksa apakah ada update baru?"
- **system_update** - Update and restart Kabot
  - Example: "Update Kabot to the latest version"

### **Advanced Tools**
- **meta_graph** - Query knowledge graph
  - Example: "Show me all related concepts to 'authentication'"

---

## 12. Skills System (70+ Skills)

Kabot includes a powerful Skills System with 70+ pre-built skills for complex workflows. Skills are auto-matched based on your message keywords.

### **What are Skills?**
Skills are markdown-based SOPs (Standard Operating Procedures) that teach Kabot how to handle complex, multi-step workflows. Unlike tools (which perform single actions), skills orchestrate entire workflows.

### **Workflow Chains**
Skills can chain together for complex tasks:
- **brainstorming** → writing-plans → executing-plans
- **systematic-debugging** → test-driven-development
- **executing-plans** → finishing-a-development-branch
- **requesting-code-review** → finishing-a-development-branch

### **Core Development Skills**
- **brainstorming** - Design & requirements exploration before coding
  - Auto-triggers: "create feature", "build component", "add functionality"
- **writing-plans** - Create detailed implementation plans with TDD
  - Auto-triggers: After brainstorming, or "create plan"
- **executing-plans** - Execute plans in batches with checkpoints
  - Auto-triggers: "execute plan", "implement plan"
- **finishing-a-development-branch** - Complete work (merge/PR/cleanup)
  - Auto-triggers: After executing-plans completes
- **systematic-debugging** - Deep debugging with execution flow analysis
  - Auto-triggers: "debug", "fix bug", "error", "not working"
- **test-driven-development** - TDD workflow (test → implement → verify)
  - Auto-triggers: "write tests", "TDD", "test first"
- **requesting-code-review** - Request code review with context
  - Auto-triggers: "review my code", "code review"
- **using-git-worktrees** - Isolated git worktrees for features
  - Auto-triggers: "create worktree", "isolate branch"

### **Integration Skills (40+ available)**
- **discord** - Discord bot integration
- **spotify** - Spotify playback control
- **1password** - 1Password CLI integration
- **github** - GitHub operations (issues, PRs, releases)
- **tmux** - Tmux session management
- **apple-notes** - Apple Notes integration
- **apple-reminders** - Apple Reminders integration
- **bear-notes** - Bear Notes integration
- **bluebubbles** - iMessage via BlueBubbles
- **blogwatcher** - Blog monitoring
- **camsnap** - Webcam snapshots
- **canvas** - Canvas LMS integration
- **download-manager** - Download management
- **ev-car** - EV car integration
- **file-sender** - File transfer automation
- **gifgrep** - GIF search
- **healthcheck** - Health monitoring
- **mcporter** - Minecraft server management
- **oracle** - Oracle database operations
- **sherpa-onnx-tts** - Text-to-speech
- And 20+ more...

### **How Skills Auto-Match**
Kabot automatically detects relevant skills based on keywords in your message:

```
User: "I need to build a new authentication system"
Kabot: [Auto-matches "brainstorming" skill]
Kabot: "I'm using the brainstorming skill to design this system."
```

### **Manual Skill Invocation**
You can also manually invoke skills:
```
User: "Use the systematic-debugging skill to fix this error"
```

### **Skills Location**
- Built-in skills: `kabot/skills/`
- Custom skills: `~/.kabot/workspaces/<workspace>/skills/`

---

## 13. Advanced Features

### **Command Firewall (Security)**
Kabot includes a sophisticated security layer for shell command execution:

**Policy Modes:**
- **deny** - Block all commands (safest)
- **ask** - Require approval for each command
- **allowlist** - Only allow whitelisted commands

**Configuration:**
```yaml
# ~/.kabot/command_approvals.yaml
policy: ask
allowlist:
  - "git status"
  - "git diff"
  - "pytest tests/*"
denylist:
  - "rm -rf"
  - "sudo *"
```

**Interactive Approval:**
When policy is "ask", Kabot will prompt:
```
Command requires approval: git commit -m "fix bug"
Reply with /approve <id> to run once, or /deny <id> to reject.
```

### **Hook System (Lifecycle Events)**
Kabot supports 12 lifecycle hooks for custom automation:

**Available Hooks:**
- `ON_STARTUP` - When Kabot starts
- `ON_SHUTDOWN` - When Kabot stops
- `ON_MESSAGE_RECEIVED` - Before processing message
- `PRE_LLM_CALL` - Before calling LLM
- `POST_LLM_CALL` - After LLM responds
- `ON_TOOL_CALL` - Before tool execution
- `ON_TOOL_RESULT` - After tool execution
- `ON_ERROR` - When error occurs
- `ON_MEMORY_SAVE` - When saving to memory
- `ON_MEMORY_SEARCH` - When searching memory
- `ON_SESSION_START` - New session created
- `ON_SESSION_END` - Session closed

**Example Hook:**
```python
# ~/.kabot/hooks/log_tool_calls.py
def on_tool_call(tool_name, params):
    with open("tool_log.txt", "a") as f:
        f.write(f"{tool_name}: {params}\n")
```

### **Plugin System**
Kabot supports dynamic plugins for extending functionality:

**Plugin Structure:**
```
~/.kabot/plugins/
  my_plugin/
    __init__.py
    plugin.yaml
    tools/
      custom_tool.py
```

**Plugin Registration:**
Plugins are auto-loaded from `~/.kabot/plugins/` on startup.

### **Subagent Architecture**
Kabot supports spawning background subagents for parallel task execution:

**Features:**
- Persistent registry (survives restarts)
- Depth limits (prevent infinite recursion)
- Concurrent limits (max 5 parallel subagents)
- Background task execution

**Usage:**
```
User: "Spawn a subagent to monitor logs while I work on the code"
Kabot: [Uses spawn tool]
Kabot: "✅ Subagent spawned (ID: sub_abc123). It will monitor logs and report back."
```

### **Auth Rotation (Zero-Downtime)**
Kabot supports multiple API keys per provider with automatic rotation:

**Configuration:**
```yaml
# config.yaml
provider: openai
api_keys:
  - sk-key1...
  - sk-key2...
  - sk-key3...
```

**Behavior:**
- On 429 rate limit → rotate to next key
- On 401 auth error → rotate to next key
- 60-second cooldown per failed key

### **Model Fallback Cascade**
Automatic fallback to secondary models on failure:

**Configuration:**
```yaml
model: claude-3-5-sonnet-20241022
fallback_models:
  - gpt-4o
  - gemini-pro
```

**Behavior:**
- Primary model fails → try gpt-4o
- gpt-4o fails → try gemini-pro
- All fail → return error to user

### **Context Window Guard**
Prevents crashes from context overflow:

**Thresholds:**
- **< 16K tokens** - Block (too small for Kabot)
- **< 32K tokens** - Warning (may overflow)
- **> 80% full** - Auto-compact history

**Auto-Compaction:**
- Summarizes old messages
- Keeps recent 10 exchanges
- Preserves tool calls and results

### **Tool Result Truncation**
Prevents tool results from bloating context:

**Rules:**
- Max 30% of context window per tool result
- Truncates with "... (truncated: N more chars)"
- Preserves structure (JSON, XML, etc.)

---

## Congratulations!
You are now fully equipped to unleash Kabot. You have mastered:
- Setup Wizard & Configuration
- 36 Built-in Tools
- 70+ Skills System
- Advanced Features (Firewall, Hooks, Plugins, Subagents)
- Auto-Update System
- AI-as-Developer Capabilities

Start experimenting! Use `kabot config` to partition your agents by role, teach them with `kabot train`, leverage skills for complex workflows, and watch your productivity level up.
