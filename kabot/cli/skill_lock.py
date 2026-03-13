"""Record installed skills so they can be listed and updated later."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kabot.cli.skill_repo_installer import InstalledSkill

_LOCK_VERSION = 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_skill_lock_path(*, workspace: Path, target: str) -> Path:
    normalized_target = str(target or "").strip().lower()
    if normalized_target == "workspace":
        return workspace / ".kabot" / "skills-lock.json"
    return Path.home() / ".kabot" / "skills-lock.json"


def load_skill_lock(lock_path: Path) -> dict[str, Any]:
    path = Path(lock_path).expanduser()
    if not path.exists():
        return {"version": _LOCK_VERSION, "skills": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": _LOCK_VERSION, "skills": {}}
    if not isinstance(payload, dict):
        return {"version": _LOCK_VERSION, "skills": {}}
    skills = payload.get("skills")
    if not isinstance(skills, dict):
        skills = {}
    return {
        "version": int(payload.get("version") or _LOCK_VERSION),
        "skills": skills,
    }


def save_skill_lock(lock_path: Path, payload: dict[str, Any]) -> None:
    path = Path(lock_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = {
        "version": int(payload.get("version") or _LOCK_VERSION),
        "skills": payload.get("skills") if isinstance(payload.get("skills"), dict) else {},
    }
    path.write_text(json.dumps(normalized, indent=2, sort_keys=True), encoding="utf-8")


def record_installed_skill(
    *,
    lock_path: Path,
    installed: InstalledSkill,
    target: str,
    source_type: str,
    source_value: str,
    catalog_slug: str = "",
    catalog_source: str = "",
    ref: str = "",
    subdir: str = "",
) -> None:
    payload = load_skill_lock(lock_path)
    skills = payload.setdefault("skills", {})
    if not isinstance(skills, dict):
        skills = {}
        payload["skills"] = skills

    key = str(installed.skill_key or installed.skill_name).strip() or str(installed.skill_name).strip()
    now = _utc_now_iso()
    previous = skills.get(key) if isinstance(skills.get(key), dict) else {}
    created_at = str(previous.get("created_at") or now)
    skills[key] = {
        "skill_name": installed.skill_name,
        "skill_key": key,
        "target": str(target or "").strip().lower() or "managed",
        "source_type": str(source_type or "").strip().lower(),
        "source_value": str(source_value or "").strip(),
        "catalog_slug": str(catalog_slug or "").strip().lower(),
        "catalog_source": str(catalog_source or "").strip(),
        "ref": str(ref or "").strip(),
        "subdir": str(subdir or "").strip(),
        "selected_dir": str(installed.selected_dir),
        "installed_dir": str(installed.installed_dir),
        "created_at": created_at,
        "updated_at": now,
    }
    source_type_value = str(source_type or "").strip().lower()
    if source_type_value == "path":
        skills[key]["source_path"] = str(source_value or "").strip()
    elif source_type_value == "url":
        skills[key]["source_url"] = str(source_value or "").strip()
    elif source_type_value == "git":
        skills[key]["repo_url"] = str(source_value or "").strip()
    save_skill_lock(lock_path, payload)


def list_locked_skills(lock_path: Path) -> list[dict[str, Any]]:
    payload = load_skill_lock(lock_path)
    skills = payload.get("skills")
    if not isinstance(skills, dict):
        return []
    rows: list[dict[str, Any]] = []
    for key, value in skills.items():
        if not isinstance(value, dict):
            continue
        row = dict(value)
        row.setdefault("skill_key", key)
        row.setdefault("skill_name", key)
        rows.append(row)
    rows.sort(key=lambda item: str(item.get("skill_key") or item.get("skill_name") or "").lower())
    return rows


def get_locked_skill(lock_path: Path, slug: str) -> dict[str, Any] | None:
    normalized = str(slug or "").strip().lower()
    if not normalized:
        return None
    for item in list_locked_skills(lock_path):
        if str(item.get("skill_key") or "").strip().lower() == normalized:
            return item
        if str(item.get("skill_name") or "").strip().lower() == normalized:
            return item
    return None
