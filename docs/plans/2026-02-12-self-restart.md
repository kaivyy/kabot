# Self-Restart Watchdog Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable Kabot to self-restart and auto-recover from crashes using a wrapper script architecture.

**Architecture:** Create shell/batch wrapper scripts that monitor the Python process exit code. Code 42 triggers immediate restart (user requested), non-zero codes trigger restart with backoff (crash recovery), code 0 exits. Implement a new `system-control` skill to trigger these codes.

**Tech Stack:** Bash, Batch/PowerShell, Python.

---

### Task 1: Create System Control Skill

**Files:**
- Create: `kabot/skills/system-control/SKILL.md`
- Create: `kabot/skills/system-control/scripts/restart.py`
- Create: `kabot/skills/system-control/scripts/shutdown.py`

**Step 1: Create skill structure using skill-creator**

```bash
python kabot/skills/skill-creator/scripts/init_skill.py system-control
```

**Step 2: Implement restart script**

Create `kabot/skills/system-control/scripts/restart.py` that exits with code 42.

```python
import sys
import time

print("🔄 Initiating restart sequence...")
time.sleep(1) # Give UI time to show message
sys.exit(42)
```

**Step 3: Implement shutdown script**

Create `kabot/skills/system-control/scripts/shutdown.py` that exits with code 0.

```python
import sys
print("🛑 Shutting down...")
sys.exit(0)
```

**Step 4: Document skill**

Update `kabot/skills/system-control/SKILL.md` to explain usage.

**Step 5: Commit**

```bash
git add kabot/skills/system-control/
git commit -m "feat: add system-control skill for restart/shutdown"
```

### Task 2: Create Linux Watchdog Wrapper

**Files:**
- Create: `start_kabot.sh`

**Step 1: Write shell script**

Create `start_kabot.sh` with the loop logic:

```bash
#!/bin/bash

# Kabot Watchdog Script
echo "🦅 Starting Kabot Watchdog..."

while true; do
    python3 -m kabot gateway
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ Kabot stopped normally."
        break
    elif [ $EXIT_CODE -eq 42 ]; then
        echo "🔄 Restarting Kabot (User Request)..."
        sleep 1
    else
        echo "⚠️ Kabot crashed with code $EXIT_CODE. Restarting in 5s..."
        sleep 5
    fi
done
```

**Step 2: Make executable**

```bash
chmod +x start_kabot.sh
```

**Step 3: Commit**

```bash
git add start_kabot.sh
git commit -m "feat: add linux watchdog script"
```

### Task 3: Create Windows Watchdog Wrapper

**Files:**
- Create: `start_kabot.bat`

**Step 1: Write batch script**

Create `start_kabot.bat` with equivalent logic:

```batch
@echo off
title Kabot Watchdog
echo 🦅 Starting Kabot Watchdog...

:loop
python -m kabot gateway
if %ERRORLEVEL% EQU 0 (
    echo ✅ Kabot stopped normally.
    goto end
)
if %ERRORLEVEL% EQU 42 (
    echo 🔄 Restarting Kabot (User Request)...
    timeout /t 1 /nobreak >nul
    goto loop
)

echo ⚠️ Kabot crashed. Restarting in 5s...
timeout /t 5 /nobreak
goto loop

:end
pause
```

**Step 2: Commit**

```bash
git add start_kabot.bat
git commit -m "feat: add windows watchdog script"
```

### Task 4: Update Documentation

**Files:**
- Modify: `README.md`

**Step 1: Add usage instructions**

Update `README.md` "Running" section to recommend using the wrapper scripts for production.

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update running instructions with watchdog"
```
