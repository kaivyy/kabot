#!/usr/bin/env python3
"""
Initialize a new skill directory with standard structure.
Usage: python init_skill.py <skill_name>
"""
import sys
import argparse
from pathlib import Path

def init_skill(name: str, base_dir: Path = None):
    # Determine base skills directory
    if not base_dir:
        # Assume we are running from inside a skill or root
        # Try to find 'kabot/skills'
        current = Path.cwd()
        if (current / "kabot" / "skills").exists():
            base_dir = current / "kabot" / "skills"
        elif current.name == "skills":
            base_dir = current
        else:
            # Fallback for development
            base_dir = Path("kabot/skills")

    skill_dir = base_dir / name

    if skill_dir.exists():
        print(f"Error: Skill '{name}' already exists at {skill_dir}")
        sys.exit(1)

    # Create structure
    print(f"Creating skill '{name}' at {skill_dir}...")
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "references").mkdir(exist_ok=True)
    (skill_dir / "scripts").mkdir(exist_ok=True)

    # Create SKILL.md template
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(f"""---
metadata:
  kabot:
    emoji: 🧩
    description: Description for {name}
    created_with: skill-creator
---

# {name.title()} Skill

## Overview
Brief description of what this skill does.

## Capabilities
- Capability 1
- Capability 2

## Usage
Explain how to use this skill.
""", encoding="utf-8")

    # Create placeholder reference
    (skill_dir / "references" / "examples.md").write_text("# Examples\n\nAdd examples here.", encoding="utf-8")

    print(f"✅ Skill initialized successfully!")
    print(f"  - {skill_md}")
    print(f"  - {skill_dir}/references/")
    print(f"  - {skill_dir}/scripts/")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize a new Kabot skill")
    parser.add_argument("name", help="Name of the skill (kebab-case)")
    args = parser.parse_args()

    init_skill(args.name)
