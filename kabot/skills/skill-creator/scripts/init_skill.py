#!/usr/bin/env python3
"""
Initialize a new skill directory with a standard Kabot structure.

Usage:
    python init_skill.py <skill_name>
    python init_skill.py <skill_name> --target /custom/path
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _resolve_workspace_skills_dir(workspace_path: str | Path | None) -> Path | None:
    """Return <workspace>/skills when the workspace path exists and is ready to use."""
    if not workspace_path:
        return None
    workspace = Path(workspace_path).expanduser()
    skills_dir = workspace / "skills"
    if skills_dir.exists():
        return skills_dir
    return None


def _load_configured_skills_dir() -> Path | None:
    """Resolve the configured workspace skills dir without hard-failing outside Kabot."""
    env_override = os.environ.get("KABOT_WORKSPACE_PATH") or os.environ.get("KABOT_WORKSPACE")
    if env_override:
        env_skills = _resolve_workspace_skills_dir(env_override)
        if env_skills:
            return env_skills

    try:
        from kabot.config.loader import load_config
    except Exception:
        return None

    try:
        cfg = load_config()
    except Exception:
        return None

    return _resolve_workspace_skills_dir(cfg.workspace_path)


def find_skills_dir() -> Path | None:
    """Find the best skills directory, preferring the active workspace over builtin skills."""
    configured = _load_configured_skills_dir()
    if configured:
        return configured

    current = Path.cwd()
    if (current / "skills").exists():
        return current / "skills"
    if (current / "kabot" / "skills").exists():
        return current / "kabot" / "skills"

    script_dir = Path(__file__).resolve().parent
    for parent in [script_dir] + list(script_dir.parents):
        candidate = parent / "kabot" / "skills"
        if candidate.exists():
            return candidate
        if parent.name == "kabot" and (parent / "skills").exists():
            return parent / "skills"
    return None


def _build_skill_markdown(name: str) -> str:
    title = name.replace("-", " ").replace("_", " ").title()
    description = f"Describe when to use {name} and what it does."
    return f"""---
name: {name}
description: "{description}"
metadata:
  kabot:
    emoji: "🧩"
    description: "{description}"
    created_with: skill-creator
---

# {title}

## Overview
Explain the outcome this skill owns and the problem it solves.

## When to Use
- Trigger when the user clearly asks for this capability.
- Trigger when the workflow strongly matches this skill's responsibility.

## When Not to Use
- Do not use this skill for unrelated tasks.
- Prefer a more specific skill when one already exists.

## Instructions
1. Clarify the goal only when key details are still missing.
2. Prefer built-in Kabot tools before inventing manual workarounds.
3. Read files from `references/` only when they are relevant.
4. Run scripts from `scripts/` when deterministic execution is useful.
5. Be explicit about required credentials, binaries, or setup.

## References
- `references/README.md` for docs, examples, API notes, and domain rules.

## Scripts
- `scripts/main.py` for deterministic helper logic when needed.

## Assets
- `assets/README.md` for templates, payload samples, icons, or boilerplate output files.
"""


def _build_script_template(name: str) -> str:
    title = name.replace("-", " ").replace("_", " ").title()
    return f'''#!/usr/bin/env python3
"""Main script for {name} skill."""
import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(description="{title} skill")
    parser.add_argument("action", choices=["help"], help="Action to perform")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    try:
        result = {{"status": "success", "action": args.action}}
        print(json.dumps(result, indent=2))
    except Exception as exc:
        print(json.dumps({{"status": "error", "message": str(exc)}}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
'''


def init_skill(name: str, target_dir: Path):
    """Create a new skill directory with standard structure."""
    skill_dir = target_dir / name

    if skill_dir.exists():
        print(f"Error: Skill '{name}' already exists at {skill_dir}")
        sys.exit(1)

    print(f"Creating skill '{name}' at {skill_dir}...")
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "assets").mkdir(exist_ok=True)
    (skill_dir / "references").mkdir(exist_ok=True)
    (skill_dir / "scripts").mkdir(exist_ok=True)

    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(_build_skill_markdown(name), encoding="utf-8")

    (skill_dir / "assets" / "README.md").write_text(
        "# Assets\n\nAdd templates, payload samples, icons, or output files here.\n",
        encoding="utf-8",
    )
    (skill_dir / "references" / "README.md").write_text(
        "# References\n\nAdd API documentation, examples, and guides here.\n",
        encoding="utf-8",
    )
    (skill_dir / "scripts" / "main.py").write_text(
        _build_script_template(name),
        encoding="utf-8",
    )

    print("[ok] Skill initialized successfully!")
    print(f"   [file] {skill_md}")
    print(f"   [dir]  {skill_dir / 'assets/'}")
    print(f"   [dir]  {skill_dir / 'references/'}")
    print(f"   [dir]  {skill_dir / 'scripts/'}")
    print("")
    print("Next steps:")
    print("   1. Edit SKILL.md with the real workflow and trigger guidance")
    print("   2. Add docs or examples to references/ (if needed)")
    print("   3. Add templates or payload samples to assets/ (if needed)")
    print("   4. Implement logic in scripts/main.py (if needed)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Initialize a new Kabot skill",
        epilog=(
            "By default, skills are created in the active workspace skills directory when "
            "available. If no workspace skills dir can be resolved, the script falls back "
            "to the local kabot/skills/ directory."
        ),
    )
    parser.add_argument("name", help="Name of the skill (kebab-case, e.g. 'meta-threads')")
    parser.add_argument(
        "--target",
        "-t",
        help="Custom target directory for the skill (overrides auto-detection).",
        default=None,
    )
    args = parser.parse_args()

    if args.target:
        target = Path(args.target)
        target.mkdir(parents=True, exist_ok=True)
        print(f"[target] Using custom target directory: {target}")
    else:
        target = find_skills_dir()
        if target:
            print(f"[target] Auto-detected skills directory: {target}")
        else:
            print("Error: Could not find a usable skills directory.")
            print("  Create <workspace>/skills, run from a repo/workspace root, or use --target.")
            sys.exit(1)

    init_skill(args.name, target)
