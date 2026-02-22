# The Ultimate Beginner's Guide to Kabot

Welcome to **Kabot**, your personal, locally-hosted AI assistant framework designed to become your ultimate "Second Brain." Kabot allows you to build highly intelligent AI agents that work for you 24/7 on your local machine (like a Mac Mini, PC, or VPS). You can even create distributed teams of specialized agents (like your own personal "MHA Squad").

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

To summon the settings menu, type this command:

```bash
kabot setup
```

Once you hit `Enter`, the interactive **Configuration Menu** will appear. Use your keyboard arrows to navigate. Let's break down exactly what every option does and how to use it:

### a) Workspace (Set path + sessions)
*   **What it does:** Defines the specific "identity" and memory bank of the AI agent you are currently talking to. You can easily create multiple distinct agents.
*   **How to use it:** If you want a specialized team (e.g., a financial advisor, a parenting coach, a coding assistant), you create different workspaces. For example, create a workspace named "Momo" for finance and another named "Aizawa" for parenting. *Crucially, each workspace has its own isolated memory.* Aizawa will not remember Momo's conversations, keeping contexts clean and hyper-specialized.

### b) Model / Auth (Providers, Keys, OAuth)
*   **What it does:** Connects Kabot to its "Main Brain" (the LLM API, such as Claude, Gemini, or OpenAI) and securely stores your API keys.
*   **How to use it:** Select your provider/model and add your API key (OpenAI, Anthropic, OpenRouter, Groq, etc.). Kabot supports fallbacks, so you can set a primary model and a backup model if the first one fails. For quick switches in chat, use `/switch <model>`.

### c) Tools & Sandbox (Search, Docker, Shell)
*   **What it does:** Gives physical superpowers to your agent. Without tools, Kabot is just a chatbot. With tools, Kabot becomes a proactive assistant.
*   **How to use it:** Here, you toggle access to Kabot's abilities. You can grant it permission to type Terminal commands, read files on your hard drive, or use web search and fetch tools. Docker sandboxing can be enabled for safer command execution.

### d) Skills (Install & Configure)
*   **What it does:** Injects "SOPs" (Standard Operating Procedures) or foundational expertise directly into the agent's initial prompt.
*   **How to use it:** Useful if you download custom third-party "Skill Files" (Markdown scripts) that teach Kabot exactly how to behave or format its responses for specific career roles.

### e) Google Suite (Auth & Credentials)
*   **What it does:** Grants Kabot secure, native access to act on behalf of your Google Account.
*   **How to use it:** Once authorized, Kabot can send emails, schedule Calendar meetings, and read/create files in Google Drive and Google Docs via the Google integrations. 
    *   **The Process:** Provide the path to a `google_credentials.json` file (downloaded from your Google Cloud Console). Kabot opens a browser tab for consent, then stores the token locally. You can also run `kabot google-auth <path>` for the fastest setup.

### f) Channels (Telegram, WhatsApp, Slack)
*   **What it does:** Connects Kabot's brain to your mobile phone so you don't have to stay glued to your computer terminal.
*   **How to use it:** You can insert your Telegram Bot Token or WhatsApp configuration here. Once connected, your family or business partners can simply text the bot on Telegram, and Kabot will process the requests on your local server and reply directly to their phones! 

### g) Auto-start (Enable boot-up service)
*   **What it does:** Ensures Kabot automatically starts running in the background whenever you turn on or restart your computer/server (systemd on Linux, launchd on macOS, Task Scheduler on Windows, Termux on Android).

### h) Doctor (Health Check)
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

## 5. Two Powerful Shortcut Commands (Advanced CLI)

While the Setup Wizard (`kabot config`) covers 99% of your needs, Kabot offers two specialized command-line shortcuts for advanced "Power Users".

### KABOT TRAIN (The Auto-Onboarding System)
*   **When to use it:** When you want to instantly inject massive amounts of knowledge (like a 300-page book) into your agent's permanent memory without spending hours typing manual prompts.
*   **The Command:**
    ```bash
    kabot train C:\Path\To\Your\Parenting_Guide.pdf --workspace Aizawa
    ```
*   **What happens?** Kabot uses its internal Document Parser to read the entire PDF, Markdown, or TXT file. It chunks the text into AI-friendly paragraphs and forcefully injects this knowledge directly into the Vector Database (ChromaDB) of the specified workspace (`Aizawa`). From the very next second, Aizawa will answer questions as an absolute expert on that book!

### KABOT GOOGLE-AUTH (Rapid OAuth Setup)
*   **When to use it:** If you skipped the Setup Wizard and want a fast track to authorizing your Google Suite integrations (Drive, Docs, Mail, Calendar).
*   **The Command:** 
    ```bash
    kabot google-auth C:\Downloads\my_google_credentials.json
    ```
*   **What happens?** Instead of navigating menus, this command instantly grabs your downloaded API key, opens the secure Google Consent screen in your browser, and locks the permanent authentication token directly into Kabot's memory. *(If you are deploying on a headless VPS/Linux server without a screen, see the Advanced FAQ on how to authorize first on a laptop and transfer the `token.json` file securely to the server).*

---

## Congratulations!
You are now fully equipped to unleash Kabot. You have mastered The Smart Router, The Setup Wizard, Auto-Onboarding, and Google Suite Integration. 

Start experimenting! Use `kabot config` to partition your diverse agents (All Might, Hawk, Deku), teach them with `kabot train`, and watch as your personal AI squad transforms your daily workflow!
