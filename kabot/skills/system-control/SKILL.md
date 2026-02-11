---
metadata:
  kabot:
    emoji: 🧩
    description: Manage system lifecycle (restart/shutdown)
    created_with: skill-creator
---

# System-Control Skill

## Overview
Manage system lifecycle (restart/shutdown)

## Capabilities
- Restart the system (Exit code 42)
- Shutdown the system (Exit code 0)

## Usage
### Restart
```bash
python kabot/skills/system-control/scripts/restart.py
```

### Shutdown
```bash
python kabot/skills/system-control/scripts/shutdown.py
```
