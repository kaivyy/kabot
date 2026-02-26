# The Ultimate Beginner's Guide to Kabot

Welcome to **Kabot**, your personal, locally-hosted AI assistant framework designed to become your ultimate "Second Brain." Kabot allows you to build highly intelligent AI agents that work for you 24/7 on your local machine (like a Mac Mini, PC, or VPS). You can even create distributed teams of specialized agents tailored to different roles.

This tutorial is written specifically for beginners. It will guide you step-by-step on how to run, configure, and maximize all of Kabot's featuresâ€”no coding experience required!

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
*   **How to use it (simple mode flow):**
    *   Open **Model/Auth** and choose **Provider Login (Auto model + fallback)**.
    *   Paste API key or OAuth token for any provider you want.
    *   Kabot auto-builds a primary + fallback model chain from your connected providers.
    *   If you prefer, choose **Select Default Model (Optional manual override)** and pick from the full model catalog.
    *   You can still type a custom model manually (`provider/model`) any time.
*   **Provider coverage (Kabot-aligned):**
    *   OpenAI, OpenAI Codex, Anthropic, Gemini, Groq, DeepSeek, Mistral, Moonshot, MiniMax, DashScope/Qwen, Zhipu.
    *   OpenRouter, Kilo Gateway, Together, Venice, Hugging Face, Qianfan, NVIDIA.
    *   xAI, Cerebras, OpenCode Zen, Xiaomi MiMo, Volcano Engine, BytePlus.
    *   Synthetic, Cloudflare AI Gateway, Vercel AI Gateway.
*   **Fallback behavior:** Kabot supports fallback chains, so if your primary model fails (rate-limit/auth/outage), it automatically tries the next configured model. If you use an OpenAI/OpenAI-Codex primary model and leave fallback chain empty, Kabot can auto-inject Groq fallback at runtime when a Groq key is available. For quick switches in chat, use `/switch <model>`.
*   **Catalog parity note:** Kabot now ships broad Kabot-aligned model refs, including extended Venice/Together/Kilo/OpenCode/Synthetic and coding endpoints (`volcengine-plan/*`, `byteplus-plan/*`).

### c) Memory (Backend, Embeddings, Database)
*   **What it does:** Controls how Kabot remembers conversations, facts, and user preferences. It is the core of Kabot's "Second Brain".
*   **How to use it:** You can switch between different memory engines depending on your machine's capabilities:
    *   **Hybrid (Recommended):** The most powerful engine using ChromaDB + SQLite + BM25 for semantic search with vector embeddings.
    *   **SQLite Only:** A lightweight mode utilizing keyword searches without embeddings (perfect for Termux or Raspberry Pi).
    *   **Disabled:** Turns off the memory system entirely for a stateless chat experience.
*   **See Section 8a** below for comprehensive memory system documentation.

### d) Tools & Sandbox (Search, Docker, Shell)
*   **What it does:** Gives physical superpowers to your agent. Without tools, Kabot is just a chatbot. With tools, Kabot becomes a proactive assistant.
*   **How to use it:** Here, you toggle access to Kabot's abilities. You can grant it permission to type Terminal commands, read files on your hard drive, or use web search and fetch tools. Docker sandboxing can be enabled for safer command execution.
*   **Web search providers:** `web_search` supports Brave, Perplexity, Grok, and Kimi. In setup wizard tools menu, you can input each API key and choose default search provider automatically.

### d1) Gateway (Port, Host, Bindings)
*   **What it does:** Controls how Kabot exposes webhook/gateway endpoints on your machine/server.
*   **How to use it:** In Gateway setup, choose bind mode, port, auth token, and optional Tailscale funnel.
*   **HSTS option:** For HTTPS deployments (or HTTPS reverse proxy), you can enable `Strict-Transport-Security` header and set custom value from Gateway setup.

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
- **Ping-pong detection**: Identifies alternating tool patterns (e.g., read_file â†” write_file)
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
- **Example**: 429 rate limit â†’ rotate API key â†’ retry; 401 auth â†’ fallback to secondary model

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

## 8a. Memory System Architecture (Advanced)

Kabot's memory system is the foundation of its "Second Brain" capabilities. It allows the AI to remember conversations, learn facts, and maintain context across sessions. The memory system is modular and swappable, allowing you to choose the backend that best fits your hardware and use case.

### Memory Backends

Kabot supports three memory backends that you can switch between via `kabot config` or by editing `config.json`:

#### 1. Hybrid (Default - Recommended)

**What it is:** The most powerful memory engine combining ChromaDB (vector database), SQLite (metadata), and BM25 (keyword search) with semantic embeddings.

**Best for:**
- Desktop/laptop with 4GB+ RAM
- Users who want the most intelligent semantic search
- Production deployments where memory quality matters

**Features:**
- Semantic search using vector embeddings
- Hybrid ranking (combines semantic + keyword scores)
- Smart routing (automatically chooses episodic vs knowledge search)
- Reranking for optimal result quality
- Temporal decay (prefers recent memories)
- MMR diversity (avoids redundant results)

**Configuration:**
```json
{
  "memory": {
    "backend": "hybrid",
    "embedding_provider": "sentence",
    "embedding_model": "all-MiniLM-L6-v2",
    "enable_hybrid_search": true
  }
}
```

**Embedding Providers:**
- `sentence` (default): Uses sentence-transformers locally (no API cost)
- `ollama`: Uses Ollama server for embeddings (requires Ollama running)

**Important: Hugging Face Integration**

Embedding models are automatically downloaded from **Hugging Face Hub** (https://huggingface.co). **No account or login required!**

When you first start Kabot with hybrid memory, you'll see this warning:
```
Loading sentence-transformers model: all-MiniLM-L6-v2
Warning: You are sending unauthenticated requests to the HF Hub.
Loading weights: 100%|â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆ| 103/103 [00:00<00:00, 1843.23it/s]
```

**This warning is normal and can be ignored!** The model downloads successfully without authentication.

- **Download size**: ~90MB (first run only)
- **Cache location**: `~/.cache/huggingface/hub/` (Linux/Mac) or `C:\Users\Username\.cache\huggingface\hub\` (Windows)
- **RAM usage**: ~200-300MB when loaded
- **No re-download**: Subsequent runs load from cache instantly

**Optional**: Set `HF_TOKEN` environment variable for faster downloads (not required):
```bash
export HF_TOKEN="your_token_here"  # Linux/Mac
$env:HF_TOKEN="your_token_here"    # Windows PowerShell
```

#### Auto-Unload Timeout

Control when the embedding model automatically unloads from RAM:

```json
{
  "memory": {
    "backend": "hybrid",
    "auto_unload_timeout": 300
  }
}
```

- `auto_unload_timeout`: Seconds of idle time before model unloads (default: 300 = 5 minutes)
- Set to `0` to disable auto-unload (model stays in RAM)
- Model reloads automatically on next search (transparent to user)
- Reduces idle RAM from ~800MB to ~250MB

#### 2. SQLite Only (Lightweight)

**What it is:** A lightweight memory backend using only SQLite with keyword-based search (no embeddings, no ChromaDB).

**Best for:**
- Termux on Android
- Raspberry Pi or low-resource devices
- Users who want minimal dependencies
- Quick prototyping without heavy setup

**Features:**
- SQL LIKE keyword search
- Low memory footprint
- No external dependencies
- Fast startup time

**Configuration:**
```json
{
  "memory": {
    "backend": "sqlite_only"
  }
}
```

**Trade-offs:**
- No semantic understanding (searches for exact keywords only)
- Cannot find related concepts (e.g., searching "car" won't find "vehicle")
- Less intelligent than hybrid mode

#### 3. Disabled (Stateless)

**What it is:** A no-op memory backend that discards all data. Kabot becomes completely stateless.

**Best for:**
- Privacy-focused users who don't want any data stored
- Temporary sessions or demos
- Testing scenarios

**Configuration:**
```json
{
  "memory": {
    "backend": "disabled"
  }
}
```

**Behavior:**
- All memory operations return empty results
- No data is written to disk
- Each conversation starts fresh with no context

### Memory Operations

Regardless of which backend you choose, Kabot supports these core memory operations:

#### Conversation Memory
- **Automatic:** Every message you send is automatically stored
- **Context retrieval:** Recent messages are loaded for each response
- **Session isolation:** Each workspace has its own conversation history

#### Fact Memory
- **Manual storage:** Use "Remember that I prefer dark mode" in chat
- **Automatic extraction:** Kabot can extract facts from conversations
- **Categories:** Facts are organized by category (preferences, knowledge, etc.)

#### Memory Search
- **Natural language:** Ask "What did I say about my project?"
- **Tool-based:** Kabot automatically searches memory when relevant
- **Filtered:** Can search within a specific session or globally

#### Manual Resource Management

Explicitly unload memory resources to free RAM:

```python
# Unload embedding model and ChromaDB
memory.unload_resources()

# Check memory stats
stats = memory.get_memory_stats()
print(f"Model loaded: {stats['embedding']['model_loaded']}")
```

Use cases:
- Before long idle periods
- After batch processing
- When switching to different tasks

### Switching Memory Backends

**Via Setup Wizard:**
```bash
kabot config
```
Select "Memory" from the menu, then choose your preferred backend.

**Via config.json:**
Edit `~/.kabot/config.json` (or `C:\Users\Username\.kabot\config.json` on Windows):
```json
{
  "memory": {
    "backend": "hybrid"  // or "sqlite_only" or "disabled"
  }
}
```

**Restart required:** After changing backends, restart Kabot for changes to take effect.

### Memory Statistics

Check your memory system health:
```bash
kabot doctor
```

This shows:
- Backend type in use
- Number of messages stored
- Number of facts stored
- Number of sessions
- Database health status

### Advanced: Custom Embedding Models

For hybrid mode, you can specify a custom embedding model:

```json
{
  "memory": {
    "backend": "hybrid",
    "embedding_provider": "sentence",
    "embedding_model": "all-mpnet-base-v2"
  }
}
```

**Popular models:**
- `all-MiniLM-L6-v2` (default): Fast, 384 dimensions, good quality
- `all-mpnet-base-v2`: Slower, 768 dimensions, best quality
- `paraphrase-multilingual-MiniLM-L12-v2`: Multilingual support

### Memory Backend Comparison

| Feature | Hybrid | SQLite Only | Disabled |
|---------|--------|-------------|----------|
| Semantic search | âœ… Yes | âŒ No | âŒ No |
| Keyword search | âœ… Yes | âœ… Yes | âŒ No |
| Memory footprint | ~500MB | ~50MB | 0MB |
| Startup time | ~5s | <1s | <1s |
| Dependencies | ChromaDB, sentence-transformers | None | None |
| Best for | Production | Low-resource | Privacy |

### Troubleshooting

**"ChromaDB import error"**
- Switch to `sqlite_only` backend if you can't install ChromaDB
- Or install dependencies: `pip install chromadb sentence-transformers`

**"Memory search returns no results"**
- Check backend is not `disabled`
- For `sqlite_only`, use exact keywords (not semantic queries)
- Run `kabot doctor` to check database health

**"High memory usage"**
- Switch from `hybrid` to `sqlite_only` to reduce RAM usage
- Or use `disabled` for zero memory footprint

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
*   `/help` â€” list available commands.
*   `/status` â€” system snapshot (CPU/RAM, provider, model, uptime).
*   `/switch <model>` â€” switch active LLM model (example: `/switch openai/gpt-4o`).
*   `/doctor` â€” run diagnostics from chat (same as CLI doctor).
*   `/benchmark` â€” quick model performance benchmark.
*   `/sysinfo` â€” detailed system info.
*   `/uptime` â€” show how long Kabot has been running.
*   `/clip <text>` â€” copy text to system clipboard (where supported).

**Admin commands (restricted):**
*   `/update` â€” pull updates and restart (admin only).
*   `/restart` â€” restart Kabot process (admin only).

**Example:**
```
/status
/switch anthropic/claude-3-5-sonnet-20241022
/doctor
```

---

## 10a. Adding New Models (Complete Guide)

This section explains exactly how to add and use new AI models in Kabot, from beginner-friendly setup to developer-level extension.

### A) Easiest Way (No Coding): Add model via Setup Wizard

1. Open setup:
```bash
kabot config
```
2. Go to **Model/Auth**.
3. Choose **Provider Login (Auto model + fallback)** and enter API key/OAuth for your provider.
4. Choose **Select Default Model (Optional manual override)**.
5. Either:
   - pick from catalog/browser, or
   - choose **Enter Model ID or Alias Manually** and type `provider/model`.

Examples you can type manually:
- `openai/gpt-4o`
- `anthropic/claude-3-5-sonnet-20241022`
- `together/moonshotai/Kimi-K2.5`
- `venice/llama-3.3-70b`
- `huggingface/deepseek-ai/DeepSeek-R1`
- `qianfan/deepseek-v3.2`
- `nvidia/nvidia/llama-3.1-nemotron-70b-instruct`
- `synthetic/hf:MiniMaxAI/MiniMax-M2.1`
- `cloudflare-ai-gateway/claude-sonnet-4-5`
- `vercel-ai-gateway/anthropic/claude-opus-4.6`

### B) Quick Runtime Switch (Without reopening setup)

Inside chat:
```text
/switch provider/model
```
Example:
```text
/switch venice/llama-3.3-70b
```

### C) Manual Config Edit (Power User, still no code changes)

Config location:
- Windows: `C:\Users\<YourUser>\.kabot\config.json`
- Linux/macOS: `~/.kabot/config.json`

Open quickly:
```bash
kabot config --edit
```

Set primary + fallback chain:
```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "together/moonshotai/Kimi-K2.5",
        "fallbacks": [
          "venice/llama-3.3-70b",
          "huggingface/deepseek-ai/DeepSeek-R1"
        ]
      }
    }
  }
}
```

Then restart Kabot so the new defaults are loaded.

### D) How to Add a Completely New Provider/Model in Code (Developer)

If the provider is not yet supported in Kabot, add it in these files:

1. **Provider runtime metadata**
- File: `kabot/providers/registry.py`
- Add a `ProviderSpec` with:
  - `name`
  - `env_key`
  - `default_api_base`
  - prefix behavior (`litellm_prefix` or gateway mode)

2. **Config schema**
- File: `kabot/config/schema.py`
- Add provider field in `ProvidersConfig`, e.g.:
```python
newprovider: ProviderConfig = Field(default_factory=ProviderConfig)
```

3. **Auth menu + handler**
- Files:
  - `kabot/auth/menu.py`
  - `kabot/auth/handlers/simple.py`
  - `kabot/auth/manager.py`
- Add provider entry in `AUTH_PROVIDERS`.
- Add `SimpleKeyHandler` subclass.
- Add alias mapping (optional, recommended).

4. **Model catalog (for setup browser UX)**
- File: `kabot/providers/catalog.py`
- Add entries to `KABOT_PARITY_MODELS` (uses helper `_parity_model(...)`).
- Add optional aliases in `populate_registry(...)`.

5. **Model status badge (optional)**
- File: `kabot/providers/model_status.py`
- `CATALOG_ONLY` is auto-synced from `STATIC_MODEL_CATALOG`.
- Add only `WORKING_MODELS` overrides if you have explicit verification data.

6. **Tests**
- Extend:
  - `tests/providers/test_registry.py`
  - `tests/auth/test_menu.py`
  - `tests/auth/test_manager.py`
  - `tests/providers/test_model_status.py`
  - `tests/cli/test_setup_wizard_default_model.py`

Run verification:
```bash
pytest tests/providers/test_registry.py tests/providers/test_model_status.py tests/auth/test_menu.py tests/auth/test_manager.py tests/cli/test_setup_wizard_default_model.py tests/config/test_agent_config.py -q
```

### E) Troubleshooting New Model Not Working

- **Error: provider not found**
  - Model prefix is not registered in `registry.py` or `schema.py`.
- **Error: authentication failed / 401**
  - Wrong API key or wrong provider key field in config.
- **Model exists but not shown in setup browser**
  - Not added to `catalog.py` yet (you can still enter manually).
- **Model selected but routes to wrong provider**
  - Check prefix and provider matching logic in `config/schema.py`.

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
- **web_search** - Search the web (Brave / Perplexity / Grok / Kimi)
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
- **brainstorming** â†’ writing-plans â†’ executing-plans
- **systematic-debugging** â†’ test-driven-development
- **executing-plans** â†’ finishing-a-development-branch
- **requesting-code-review** â†’ finishing-a-development-branch

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
- **test-driven-development** - TDD workflow (test â†’ implement â†’ verify)
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

### **Skills Source Layers**
Kabot checks skill folders in deterministic order. Lowest priority is loaded first, highest priority can override name conflicts:
1. `skills.load.extraDirs` (optional external packs)
2. Bundled skills (`kabot/skills`)
3. Managed shared skills (`skills.load.managedDir`, default `~/.kabot/skills`)
4. Personal agents skills (`~/.agents/skills`)
5. Workspace agents skills (`<workspace>/.agents/skills`)
6. Workspace direct skills (`<workspace>/skills`)

If a skill name exists in multiple locations, the highest layer above wins.

### **Skills Config (`skills.entries`)**
Kabot now supports per-skill config using canonical structure:

```json
{
  "skills": {
    "allowBundled": ["github", "cron"],
    "load": {
      "managedDir": "~/.kabot/skills",
      "extraDirs": ["~/my-skill-pack/skills"]
    },
    "install": {
      "mode": "manual",
      "nodeManager": "npm",
      "preferBrew": true
    },
    "entries": {
      "notion": {
        "enabled": true,
        "env": {
          "NOTION_API_KEY": "your-key"
        }
      },
      "trello": {
        "enabled": false
      }
    }
  }
}
```

Notes:
- `entries.<skill>.enabled=false` disables that skill.
- `entries.<skill>.env` is injected automatically at runtime (if env var is not already set).
- `install.mode` defaults to `manual`: setup wizard only generates install commands (it does not run them automatically).
- `install.nodeManager` is used when a selected skill has node-based installer metadata.
- `install.preferBrew` affects installer recommendation order.
- Legacy flat config (e.g. `skills.notion.env`) is still supported for backward compatibility.

### **Installer Metadata (`metadata.kabot.install`)**
Skill installer metadata supports both legacy and canonical formats:

Legacy single command:
```json
{
  "metadata": {
    "kabot": {
      "install": { "cmd": "pip install some-tool" }
    }
  }
}
```

Canonical list format (recommended):
```json
{
  "metadata": {
    "kabot": {
      "install": [
        { "kind": "node", "package": "@org/cli", "os": ["windows", "linux", "macos"] },
        { "kind": "brew", "formula": "jq", "os": ["macos"] },
        { "kind": "go", "module": "github.com/org/tool@latest" },
        { "kind": "uv", "package": "nano-pdf" },
        { "kind": "download", "url": "https://example.com/releases/tool.zip" },
        { "kind": "cmd", "cmd": "python -m pip install tool" }
      ]
    }
  }
}
```

Wizard behavior:
- Shows installable skills with checkbox + per-skill hint.
- If node installers are selected, asks preferred node manager (`npm`/`pnpm`/`yarn`/`bun`).
- Prints manual install plan per skill (cross-platform aware), then returns to setup flow.

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
Kabot: "âœ… Subagent spawned (ID: sub_abc123). It will monitor logs and report back."
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
- On 429 rate limit â†’ rotate to next key
- On 401 auth error â†’ rotate to next key
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
- Primary model fails â†’ try gpt-4o
- gpt-4o fails â†’ try gemini-pro
- All fail â†’ return error to user

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


