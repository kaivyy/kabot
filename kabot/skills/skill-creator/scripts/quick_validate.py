#!/usr/bin/env python3
"""
Quick validation helper for Kabot skills.

Usage:
    python quick_validate.py <path/to/skill-dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

from kabot.utils.skill_validator import validate_skill as _validate_skill_impl


def validate_skill_quick(skill_path: str | Path) -> tuple[bool, str]:
    path = Path(skill_path)
    errors = _validate_skill_impl(path)
    if errors:
        return False, "; ".join(errors)
    return True, "Skill is valid!"


def validate_skill(skill_path: str | Path) -> tuple[bool, str]:
    return validate_skill_quick(skill_path)


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1:
        print("Usage: python quick_validate.py <path/to/skill-dir>")
        return 1

    valid, message = validate_skill_quick(args[0])
    print(message)
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
