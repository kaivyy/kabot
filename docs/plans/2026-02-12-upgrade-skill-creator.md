# Advanced Skill-Creator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade Kabot's `skill-creator` to match OpenClaw's advanced version, enabling self-improvement and high-quality skill generation with progressive disclosure patterns.

**Architecture:** Adopt the "Progressive Disclosure" pattern for skills: small main `SKILL.md` (<500 lines) + `references/` folder for docs + `scripts/` for logic. Implement standard metadata validation.

**Tech Stack:** Python (for tooling), Markdown (for instructions).

---

### Task 1: Analyze & Backup Existing Skill-Creator

**Files:**
- Read: `kabot/skills/skill-creator/SKILL.md` (to understand current state)
- Backup: `kabot/skills.backup/skill-creator/`

**Step 1: Create backup of current skill**

```bash
mkdir -p kabot/skills.backup/skill-creator
cp -r kabot/skills/skill-creator/* kabot/skills.backup/skill-creator/ || echo "No existing skill to backup"
```

**Step 2: Read current implementation**

```bash
cat kabot/skills/skill-creator/SKILL.md
```

**Step 3: Commit backup**

```bash
git add kabot/skills.backup/
git commit -m "chore: backup existing skill-creator before upgrade"
```

### Task 2: Implement Metadata Standards & Validation

**Files:**
- Create: `kabot/utils/skill_validator.py`
- Modify: `kabot/agent/skills.py`

**Step 1: Create skill validator module**

Create `kabot/utils/skill_validator.py` that checks:
- `SKILL.md` exists and is < 500 lines
- Frontmatter contains `kabot` metadata (emoji, description)
- Folder structure follows standard (references/, scripts/)

```python
import yaml
import re
from pathlib import Path

def validate_skill(skill_path: Path) -> list[str]:
    errors = []
    skill_md = skill_path / "SKILL.md"

    if not skill_md.exists():
        return ["Missing SKILL.md"]

    content = skill_md.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Rule 1: Conciseness
    if len(lines) > 500:
        errors.append(f"SKILL.md is too long ({len(lines)} lines). Max 500 lines. Move details to references/.")

    # Rule 2: Metadata
    if not content.startswith("---"):
        errors.append("Missing frontmatter metadata")

    return errors
```

**Step 2: Update SkillsLoader to use validation**

Modify `kabot/agent/skills.py` to optionally warn about invalid skills during loading (without blocking execution).

**Step 3: Commit**

```bash
git add kabot/utils/skill_validator.py kabot/agent/skills.py
git commit -m "feat: add skill validation logic"
```

### Task 3: Port Advanced Skill-Creator Instructions

**Files:**
- Overwrite: `kabot/skills/skill-creator/SKILL.md`
- Create: `kabot/skills/skill-creator/references/workflows.md`
- Create: `kabot/skills/skill-creator/references/output-patterns.md`

**Step 1: Write main SKILL.md**

Write a concise `SKILL.md` that acts as the "Brain" of the skill creator. It should:
- Define the "Progressive Disclosure" philosophy.
- Instruct the agent to ALWAYS create `references/` for long docs.
- Instruct the agent to ALWAYS put logic in `scripts/`.

**Step 2: Write Reference Docs**

Create `kabot/skills/skill-creator/references/workflows.md` containing the step-by-step workflow for creating a skill:
1. Analysis (Brainstorming)
2. Structure Setup (mkdir)
3. Drafting SKILL.md
4. Validation

**Step 3: Commit**

```bash
git add kabot/skills/skill-creator/
git commit -m "feat: upgrade skill-creator with progressive disclosure pattern"
```

### Task 4: Create Skill Generation Tooling

**Files:**
- Create: `kabot/skills/skill-creator/scripts/init_skill.py`

**Step 1: Create initialization script**

Create a Python script that automates the boilerplate creation.

```python
# kabot/skills/skill-creator/scripts/init_skill.py
import sys
import os
from pathlib import Path

def init_skill(name):
    base = Path(f"kabot/skills/{name}")
    base.mkdir(parents=True, exist_ok=True)
    (base / "references").mkdir(exist_ok=True)
    (base / "scripts").mkdir(exist_ok=True)

    (base / "SKILL.md").write_text(f"""---
metadata:
  kabot:
    emoji: 🧩
    description: {name} skill
---

# {name}

## Overview
Brief description.

## Workflow
1. Step 1
2. Step 2
""")
    print(f"Created skill structure at {base}")

if __name__ == "__main__":
    init_skill(sys.argv[1])
```

**Step 2: Commit**

```bash
git add kabot/skills/skill-creator/scripts/
git commit -m "feat: add skill initialization script"
```

### Task 5: Verify & Self-Improvement Test

**Files:**
- None (Test execution)

**Step 1: Test the new skill**

Ask Kabot to create a *new* skill using the *new* skill-creator.
"Create a simple `joke-teller` skill using the skill-creator."

**Step 2: Verify structure**

Check if `kabot/skills/joke-teller` has:
- `SKILL.md` (Short)
- `references/` (Optional)
- `scripts/` (Optional)

**Step 3: Cleanup test skill**

```bash
rm -rf kabot/skills/joke-teller
```
