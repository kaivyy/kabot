# Restart Memory Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow Kabot to persist a "pending message" across restarts so it can notify the user ("I'm back!") after a restart or model change.

**Architecture:**
1.  **Persistence:** Save pending messages to `RESTART_PENDING.json` before shutting down.
2.  **Startup Check:** On startup (in `commands.py` or `gateway`), check for this file.
3.  **Delivery:** If found, send the message to the stored chat_id and delete the file.
4.  **Integration:** Update `system-control` skill to write this file before exiting.

**Tech Stack:** Python, JSON.

---

### Task 1: Implement Restart State Manager

**Files:**
- Create: `kabot/utils/restart.py`

**Step 1: Create RestartManager class**

Create a utility class to handle saving/loading restart state.

```python
import json
from pathlib import Path
from typing import Optional, Dict
from loguru import logger

class RestartManager:
    def __init__(self, workspace: Path):
        self.state_file = workspace / "RESTART_PENDING.json"

    def schedule_restart(self, chat_id: str, channel: str, message: str):
        """Save restart state to file."""
        data = {
            "chat_id": chat_id,
            "channel": channel,
            "message": message
        }
        self.state_file.write_text(json.dumps(data))
        logger.info(f"Scheduled restart message for {channel}:{chat_id}")

    def check_and_recover(self) -> Optional[Dict[str, str]]:
        """Check for pending restart message, return it, and clear file."""
        if not self.state_file.exists():
            return None

        try:
            data = json.loads(self.state_file.read_text())
            self.state_file.unlink() # Clear immediately
            return data
        except Exception as e:
            logger.error(f"Failed to recover restart state: {e}")
            return None
```

**Step 2: Commit**

```bash
git add kabot/utils/restart.py
git commit -m "feat: add RestartManager utility"
```

---

### Task 2: Integrate Startup Check

**Files:**
- Modify: `kabot/cli/commands.py`

**Step 1: Add recovery logic to gateway**

In `gateway()` function, initialize `RestartManager` and check for pending messages *after* the agent loop starts but *before* the main loop blocks.

```python
    # ... inside gateway() ...

    # Initialize Restart Manager
    from kabot.utils.restart import RestartManager
    restart_manager = RestartManager(config.workspace_path)

    # Check for pending messages
    pending = restart_manager.check_and_recover()
    if pending:
        # We need to wait for agent/channels to be ready.
        # Best way is to schedule a one-off task or just await send directly if bus is ready.
        async def send_welcome_back():
            await asyncio.sleep(5) # Wait for channels to connect
            from kabot.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=pending["channel"],
                chat_id=pending["chat_id"],
                content=pending["message"]
            ))

        asyncio.create_task(send_welcome_back())
```

**Step 2: Commit**

```bash
git add kabot/cli/commands.py
git commit -m "feat: integrate restart recovery in gateway"
```

---

### Task 3: Implement Smart Restart Skill

**Files:**
- Create/Modify: `kabot/skills/system-control/restart.py`
- Create/Modify: `kabot/skills/system-control/SKILL.md`

**Step 1: Create restart script**

Create `restart.py` that accepts arguments for the "welcome back" message.

```python
import sys
import argparse
from pathlib import Path

# Import RestartManager (need to adjust path or run as module)
# Easier: just write the JSON directly here to avoid import issues from standalone script
import json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat-id", required=True)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--message", default="I'm back online!")
    args = parser.parse_args()

    # Assume workspace is at standard location or pass it
    workspace = Path.home() / ".kabot" / "workspace"
    state_file = workspace / "RESTART_PENDING.json"

    data = {
        "chat_id": args.chat_id,
        "channel": args.channel,
        "message": args.message
    }

    state_file.write_text(json.dumps(data))
    print(f"Restart scheduled. Sending: {args.message}")

    # Exit with code 42 to trigger watchdog restart
    sys.exit(42)

if __name__ == "__main__":
    main()
```

**Step 2: Create SKILL.md**

Define the skill interface so the LLM knows how to use it.

```markdown
# System Control

Control the bot's lifecycle.

## Commands

### Restart
Restart the bot process. Use this when configuration changes (like model updates) need to be applied.

`python kabot/skills/system-control/restart.py --chat-id <chat_id> --channel <channel> --message "I'm back with the new model!"`

### Shutdown
Stop the bot completely.

`python kabot/skills/system-control/shutdown.py`
```

**Step 3: Commit**

```bash
git add kabot/skills/system-control/
git commit -m "feat: add smart restart skill"
```
