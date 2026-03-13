#!/usr/bin/env python3
"""
Package a Kabot skill directory into a distributable .skill bundle.

Usage:
    python package_skill.py <path/to/skill-dir> [output-dir]
"""

from __future__ import annotations

import sys
import zipfile
import importlib.util
from pathlib import Path

try:
    from quick_validate import validate_skill_quick
except ModuleNotFoundError:
    _VALIDATE_PATH = Path(__file__).with_name("quick_validate.py")
    _VALIDATE_SPEC = importlib.util.spec_from_file_location(
        "skill_creator_package_quick_validate",
        _VALIDATE_PATH,
    )
    _VALIDATE_MODULE = importlib.util.module_from_spec(_VALIDATE_SPEC)
    assert _VALIDATE_SPEC and _VALIDATE_SPEC.loader
    _VALIDATE_SPEC.loader.exec_module(_VALIDATE_MODULE)
    validate_skill_quick = _VALIDATE_MODULE.validate_skill_quick

_EXCLUDED_DIRS = {".git", ".svn", ".hg", "__pycache__", "node_modules"}


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def package_skill(skill_path: str | Path, output_dir: str | Path | None = None) -> Path | None:
    skill_root = Path(skill_path).resolve()
    if not skill_root.exists():
        print(f"[ERROR] Skill folder not found: {skill_root}")
        return None
    if not skill_root.is_dir():
        print(f"[ERROR] Path is not a directory: {skill_root}")
        return None

    skill_md = skill_root / "SKILL.md"
    if not skill_md.exists():
        print(f"[ERROR] SKILL.md not found in {skill_root}")
        return None

    valid, message = validate_skill_quick(skill_root)
    if not valid:
        print(f"[ERROR] Validation failed: {message}")
        return None
    print(f"[OK] {message}")

    skill_name = skill_root.name
    dist_root = Path.cwd() if output_dir is None else Path(output_dir).resolve()
    dist_root.mkdir(parents=True, exist_ok=True)
    archive_path = dist_root / f"{skill_name}.skill"

    try:
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as bundle:
            for file_path in skill_root.rglob("*"):
                if file_path.is_symlink():
                    print(f"[WARN] Skipping symlink: {file_path}")
                    continue
                if not file_path.is_file():
                    continue

                rel_parts = file_path.relative_to(skill_root).parts
                if any(part in _EXCLUDED_DIRS for part in rel_parts):
                    continue

                resolved = file_path.resolve()
                if not _is_within(resolved, skill_root):
                    print(f"[ERROR] File escapes skill root: {file_path}")
                    return None
                if resolved == archive_path.resolve():
                    print(f"[WARN] Skipping output archive: {file_path}")
                    continue

                arcname = Path(skill_name) / file_path.relative_to(skill_root)
                bundle.write(file_path, arcname)
                print(f"  Added: {arcname}")
    except Exception as exc:
        print(f"[ERROR] Error creating .skill file: {exc}")
        return None

    print(f"[OK] Created skill bundle: {archive_path}")
    return archive_path


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        print("Usage: python package_skill.py <path/to/skill-dir> [output-dir]")
        return 1

    result = package_skill(args[0], args[1] if len(args) > 1 else None)
    return 0 if result is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
