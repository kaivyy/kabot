# Install Kabot

## Requirements

- Python 3.11 or newer
- Internet access for model APIs and package install
- A supported OS:
  - Windows
  - macOS
  - Linux
  - Termux on Android

## Standard Install

```bash
pip install -U kabot
```

If `pip` is not on your path:

```bash
python -m pip install -U kabot
```

## Windows

### Recommended

```powershell
py -m pip install -U kabot
```

### Tips

- Use PowerShell, Windows Terminal, or a UTF-8 capable shell.
- If you use virtual environments, activate them before running Kabot.
- For direct one-shot commands with non-ASCII prompts, modern UTF-8 shells work best.

## macOS

```bash
python3 -m pip install -U kabot
```

Tips:
- Use a virtual environment if you do local development.
- If Homebrew Python is installed, prefer that Python explicitly.

## Linux

```bash
python3 -m pip install -U kabot
```

Tips:
- On Debian/Ubuntu, make sure `python3-venv` is available if you want a virtual environment.
- For long-running installs, use a dedicated user rather than root.

For a fuller Linux/macOS bootstrap, prefer the one-command installer from the README. It now:
- ensures `beautifulsoup4` is present in Kabot's venv,
- installs the Python `playwright` package when missing,
- runs `python -m playwright install chromium` automatically.

If you need a lighter install without browser bootstrap:

```bash
KABOT_SKIP_BROWSER_BOOTSTRAP=1 curl -fsSL https://raw.githubusercontent.com/kaivyy/kabot/main/install.sh | bash
```

## Termux

```bash
pkg update && pkg upgrade
pkg install python git clang make libjpeg-turbo freetype rust
pip install -U pip
pip install -U kabot
```

Read the full [Termux guidance](../guide/troubleshooting.md#termux-and-low-ram-notes) before using hybrid memory on low-RAM devices.

## Developer Install

Use this only if you want to change source code locally.

```bash
git clone https://github.com/kaivyy/kabot.git
cd kabot
python -m venv .venv
```

Activate:

```bash
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

Then install editable mode:

```bash
pip install -e .
```

## Optional Docs Tooling

If you want to build this docs site locally:

```bash
pip install ".[docs]"
mkdocs serve
```

## Verify Install

```bash
kabot --help
python -m kabot.cli.commands --version
```

If both commands work, continue to [First Run](first-run.md).
