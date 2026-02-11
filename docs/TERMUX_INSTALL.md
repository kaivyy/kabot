# Running Kabot on Android (Termux)

This guide explains how to run Kabot on an Android device using Termux.

## Prerequisites

1.  **Android Device**: A phone or tablet running Android 7.0 or higher.
2.  **F-Droid**: It is recommended to install Termux from F-Droid, not the Play Store (which is outdated).
3.  **Storage**: At least 2GB of free space.
4.  **RAM**: At least 4GB RAM is recommended (see Troubleshooting for low-RAM devices).

## Installation Steps

### 1. Install Termux and API
1.  Download and install [F-Droid](https://f-droid.org/).
2.  Search for "Termux" in F-Droid and install it.
3.  Search for "Termux:API" in F-Droid and install it.
4.  Open Termux and update packages:
    ```bash
    pkg update && pkg upgrade
    ```
5.  Install `termux-api` package inside Termux:
    ```bash
    pkg install termux-api
    ```

### 2. Install Dependencies
Install Python, Git, and build tools:
```bash
pkg install python git rust binutils build-essential cmake clang
```

### 3. Clone Kabot Repository
```bash
git clone https://github.com/yourusername/kabot.git
cd kabot
```

### 4. Create Virtual Environment
It's best practice to use a virtual environment:
```bash
python -m venv venv
source venv/bin/activate
```

### 5. Install Python Requirements
This step may take a while as some packages need to be compiled on the device.
```bash
pip install -r requirements.txt
```

If `cryptography` fails to build, try:
```bash
export CARGO_BUILD_TARGET=aarch64-linux-android
pip install cryptography
```

### 6. Configuration
Copy the example config and edit it:
```bash
cp config.example.yaml config.yaml
nano config.yaml
```
-   Set your LLM provider API keys.
-   Configure channels (e.g., WhatsApp, Telegram).

### 7. Run Kabot
```bash
python -m kabot
```

## Running in Background

To keep Kabot running when the screen is off, you need to acquire a wake lock.

1.  Pull down the notification bar.
2.  Tap "Acquire wakelock" in the Termux notification.
    *   *Alternatively, run `termux-wake-lock` in the terminal.*
3.  Disable battery optimizations for Termux in your Android settings (Settings > Apps > Termux > Battery > Unrestricted).

## Troubleshooting

### "Killed" or Out of Memory Errors
If Kabot crashes with "Killed" or consumes too much RAM, it might be due to the Hybrid Memory system (BM25), which builds an in-memory index of all messages.

**Solution**: Disable Hybrid Memory in `config.yaml`.

Edit `config.yaml`:
```yaml
agents:
  defaults:
    model: "anthropic/claude-3-haiku"
  # Disable BM25 to save RAM
  enable_hybrid_memory: false
```

This will force Kabot to use only Vector Search (ChromaDB) which is more memory-efficient on disk but slightly less accurate for keyword matching.

### "Rust compiler not found"
Ensure you installed `rust` via `pkg install rust`.

### Slow Performance
-   Use lighter models (e.g., Haiku, Gemini Flash) instead of Opus/Sonnet.
-   Disable `auto_planner` if not needed.
-   Ensure `enable_hybrid_memory: false` is set.
