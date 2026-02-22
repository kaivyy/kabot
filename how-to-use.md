# The Ultimate Beginner's Guide to Kabot

Welcome to **Kabot**, your personal, locally-hosted AI assistant framework designed to become your ultimate "Second Brain." Kabot allows you to build highly intelligent AI agents that work for you 24/7 on your local machine (like a Mac Mini, PC, or VPS). You can even create distributed teams of specialized agents (like your own personal "MHA Squad").

This tutorial is written specifically for beginners. It will guide you step-by-step on how to run, configure, and maximize all of Kabot's features—no coding experience required!

---

## 1. Initializing Kabot (Your First Boot)

If this is the very first time you are running Kabot on your machine, you must initialize its core folders and databases.

Open your Terminal (Command Prompt/PowerShell on Windows, or Terminal on Mac/Linux) and type:

```bash
kabot onboard
```

**What does this do?**
This command safely creates the foundational folder structure for Kabot's "brain." It creates a hidden folder named `.kabot` in your user directory (for example, `C:\Users\Username\.kabot\` on Windows or `~/.kabot/` on Mac/Linux). Kabot stores all of its memory databases, configurations, and secure tokens inside this localized folder to ensure your data stays 100% private.

---

## 2. Configuring Your Agents (The Setup Wizard)

This is Kabot's secret weapon. Instead of forcing you to edit complex configuration files or code, Kabot provides a beautifully interactive, user-friendly Configuration Menu right in your terminal.

To summon the settings menu, type this command:

```bash
kabot config
```
*(Note: You can also use the command `kabot setup`—they do the exact same thing).*

Once you hit `Enter`, the interactive **Configuration Menu** will appear. Use your keyboard arrows to navigate. Let's break down exactly what every option does and how to use it:

### a) Workspace (Set path + sessions)
*   **What it does:** Defines the specific "identity" and memory bank of the AI agent you are currently talking to. You can easily create multiple distinct agents.
*   **How to use it:** If you want a specialized team (e.g., a financial advisor, a parenting coach, a coding assistant), you create different workspaces. For example, create a workspace named "Momo" for finance and another named "Aizawa" for parenting. *Crucially, each workspace has its own isolated memory.* Aizawa will not remember Momo's conversations, keeping contexts clean and hyper-specialized.

### b) Model / Auth (Providers, Keys, OAuth)
*   **What it does:** Connects Kabot to its "Main Brain" (the LLM API, such as Claude, Gemini, or OpenAI) and securely stores your API keys.
*   **How to use it:** Kabot utilizes an intelligent routing system (OpenRouter and LiteLLM). Simply input your OpenRouter API key here. Kabot features a **Smart Router** that can automatically route casual conversations to cheaper models (like Gemini Flash) while routing complex coding/analysis tasks to highly intelligent models (like Claude 3.5 Sonnet). This maximizes intelligence while drastically reducing your API costs.

### c) Tools & Sandbox (Search, Docker, Shell)
*   **What it does:** Gives physical superpowers to your agent. Without tools, Kabot is just a chatbot. With tools, Kabot becomes a proactive assistant.
*   **How to use it:** Here, you toggle access to Kabot's abilities. You can grant it permission to type Terminal commands, read files on your hard drive, or utilize the *Advanced Web Explorer* (giving the agent the ability to autonomously open a browser, click links, and scrape structured data from the internet).

### d) Skills (Install & Configure)
*   **What it does:** Injects "SOPs" (Standard Operating Procedures) or foundational expertise directly into the agent's initial prompt.
*   **How to use it:** Useful if you download custom third-party "Skill Files" (Markdown scripts) that teach Kabot exactly how to behave or format its responses for specific career roles.

### e) Google Suite (Auth & Credentials)
*   **What it does:** Grants Kabot secure, native access to act on behalf of your Google Account.
*   **How to use it:** Once authorized, Kabot can send emails, schedule Calendar meetings, and even read from or create files in Google Drive and Google Docs. 
    *   **The Process:** You will need to provide the path to a `google_credentials.json` file (downloaded from your Google Cloud Console). Kabot will then automatically open a browser tab asking you to click "Allow". Once allowed, the token is saved privately, and Kabot will never ask you to log in again.

### f) Channels (Telegram, WhatsApp, Slack)
*   **What it does:** Connects Kabot's brain to your mobile phone so you don't have to stay glued to your computer terminal.
*   **How to use it:** You can insert your Telegram Bot Token or WhatsApp configuration here. Once connected, your family or business partners can simply text the bot on Telegram, and Kabot will process the requests on your local server and reply directly to their phones! 

### g) Auto-start (Enable boot-up service)
*   **What it does:** Ensures Kabot automatically starts running in the background whenever you turn on or restart your computer/server (via systemd on Linux, PM2, etc.).

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

## 4. Two Powerful Shortcut Commands (Advanced CLI)

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
