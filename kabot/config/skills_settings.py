"""Helpers for canonical skills configuration handling.

Supports both canonical structure:
  skills.entries.<skill_key>...
and legacy flat structure:
  skills.<skill_name>.env...
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_RESERVED_KEYS = {
    "entries",
    "allow_bundled",
    "allowBundled",
    "load",
    "install",
    "limits",
}

_INSTALL_MODES = {"manual", "auto"}
_NODE_MANAGERS = {"npm", "pnpm", "yarn", "bun"}


def _coalesce(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping.get(key)
    return None


def _normalize_env_map(raw_env: Any) -> dict[str, str]:
    if not isinstance(raw_env, dict):
        return {}
    cleaned: dict[str, str] = {}
    for key, value in raw_env.items():
        env_key = str(key).strip()
        if not env_key:
            continue
        if value in (None, ""):
            continue
        cleaned[env_key] = str(value)
    return cleaned


def _normalize_skill_entry(raw_entry: Any) -> dict[str, Any]:
    if not isinstance(raw_entry, dict):
        return {}
    entry: dict[str, Any] = {}

    enabled = _coalesce(raw_entry, "enabled")
    if isinstance(enabled, bool):
        entry["enabled"] = enabled

    env_map = _normalize_env_map(_coalesce(raw_entry, "env"))
    if env_map:
        entry["env"] = env_map

    api_key = _coalesce(raw_entry, "api_key", "apiKey")
    if isinstance(api_key, str) and api_key.strip():
        entry["api_key"] = api_key.strip()

    cfg = _coalesce(raw_entry, "config")
    if isinstance(cfg, dict) and cfg:
        entry["config"] = deepcopy(cfg)

    return entry


def _normalize_install_settings(raw_install: Any) -> dict[str, Any]:
    install: dict[str, Any] = {
        "mode": "manual",
        "node_manager": "npm",
        "prefer_brew": True,
    }
    if not isinstance(raw_install, dict):
        return install

    mode_raw = str(_coalesce(raw_install, "mode") or "").strip().lower()
    if mode_raw in _INSTALL_MODES:
        install["mode"] = mode_raw

    manager_raw = str(_coalesce(raw_install, "node_manager", "nodeManager") or "").strip().lower()
    if manager_raw in _NODE_MANAGERS:
        install["node_manager"] = manager_raw

    prefer_brew = _coalesce(raw_install, "prefer_brew", "preferBrew")
    if isinstance(prefer_brew, bool):
        install["prefer_brew"] = prefer_brew

    return install


def normalize_skills_settings(raw_skills: Any) -> dict[str, Any]:
    """Normalize raw skills config into canonical dict.

    Canonical keys (snake_case in runtime):
    - entries: dict[str, dict]
    - allow_bundled: list[str] (optional)
    - load: { managed_dir?: str, extra_dirs?: list[str] } (optional)
    - install / limits (optional passthrough dict)
    """
    if not isinstance(raw_skills, dict):
        return {"entries": {}, "install": _normalize_install_settings({})}

    result: dict[str, Any] = {"entries": {}}

    # Legacy top-level format: skills.<skill_name> = {...}
    legacy_entries: dict[str, dict[str, Any]] = {}
    for key, value in raw_skills.items():
        if key in _RESERVED_KEYS:
            continue
        if isinstance(value, dict):
            normalized = _normalize_skill_entry(value)
            if normalized:
                legacy_entries[key] = normalized

    # Canonical entries block
    raw_entries = _coalesce(raw_skills, "entries")
    canonical_entries: dict[str, dict[str, Any]] = {}
    if isinstance(raw_entries, dict):
        for key, value in raw_entries.items():
            skill_key = str(key).strip()
            if not skill_key:
                continue
            canonical_entries[skill_key] = _normalize_skill_entry(value)

    merged_entries: dict[str, dict[str, Any]] = {}
    for key, value in legacy_entries.items():
        merged_entries[key] = deepcopy(value)
    for key, value in canonical_entries.items():
        base = merged_entries.get(key, {})
        merged = deepcopy(base)
        merged.update(value)
        if "env" in base or "env" in value:
            env_map = {}
            env_map.update(base.get("env", {}))
            env_map.update(value.get("env", {}))
            if env_map:
                merged["env"] = env_map
        merged_entries[key] = merged
    result["entries"] = merged_entries

    allow_bundled = _coalesce(raw_skills, "allow_bundled", "allowBundled")
    if isinstance(allow_bundled, list):
        cleaned = [str(v).strip() for v in allow_bundled if str(v).strip()]
        if cleaned:
            result["allow_bundled"] = cleaned

    load_cfg = _coalesce(raw_skills, "load")
    if isinstance(load_cfg, dict):
        load: dict[str, Any] = {}
        managed_dir = _coalesce(load_cfg, "managed_dir", "managedDir")
        if isinstance(managed_dir, str) and managed_dir.strip():
            load["managed_dir"] = managed_dir.strip()
        extra_dirs = _coalesce(load_cfg, "extra_dirs", "extraDirs")
        if isinstance(extra_dirs, list):
            cleaned_extra = [str(v).strip() for v in extra_dirs if str(v).strip()]
            if cleaned_extra:
                load["extra_dirs"] = cleaned_extra
        if load:
            result["load"] = load

    install_cfg = _coalesce(raw_skills, "install")
    result["install"] = _normalize_install_settings(install_cfg)

    limits_cfg = _coalesce(raw_skills, "limits")
    if isinstance(limits_cfg, dict) and limits_cfg:
        result["limits"] = deepcopy(limits_cfg)

    return result


def get_skills_entries(raw_skills: Any) -> dict[str, dict[str, Any]]:
    return normalize_skills_settings(raw_skills).get("entries", {})


def get_skill_entry(raw_skills: Any, skill_key: str) -> dict[str, Any]:
    key = str(skill_key or "").strip()
    if not key:
        return {}
    entries = get_skills_entries(raw_skills)
    return deepcopy(entries.get(key, {}))


def resolve_allow_bundled(raw_skills: Any) -> list[str]:
    normalized = normalize_skills_settings(raw_skills)
    allow = normalized.get("allow_bundled")
    if isinstance(allow, list):
        return list(allow)
    return []


def resolve_load_settings(raw_skills: Any) -> dict[str, Any]:
    normalized = normalize_skills_settings(raw_skills)
    load = normalized.get("load")
    if isinstance(load, dict):
        return deepcopy(load)
    return {}


def resolve_install_settings(raw_skills: Any) -> dict[str, Any]:
    normalized = normalize_skills_settings(raw_skills)
    install = normalized.get("install")
    if isinstance(install, dict):
        return deepcopy(install)
    return _normalize_install_settings({})


def iter_skill_env_pairs(raw_skills: Any) -> list[tuple[str, str, str]]:
    """Return [(skill_key, env_key, env_value), ...] from canonical+legacy config."""
    pairs: list[tuple[str, str, str]] = []
    for skill_key, entry in get_skills_entries(raw_skills).items():
        env_map = entry.get("env", {})
        if not isinstance(env_map, dict):
            continue
        for env_key, env_val in env_map.items():
            key = str(env_key).strip()
            if not key:
                continue
            if env_val in (None, ""):
                continue
            pairs.append((skill_key, key, str(env_val)))
    return pairs


def set_skill_entry_env(raw_skills: Any, skill_key: str, env_key: str, env_value: str) -> dict[str, Any]:
    """Set env key/value under canonical skills.entries.<skill_key>.env."""
    normalized = normalize_skills_settings(raw_skills)
    entries = normalized.setdefault("entries", {})

    key = str(skill_key or "").strip()
    env_name = str(env_key or "").strip()
    value = str(env_value or "")
    if not key or not env_name or not value:
        return normalized

    entry = entries.get(key)
    if not isinstance(entry, dict):
        entry = {}
        entries[key] = entry
    env_map = entry.get("env")
    if not isinstance(env_map, dict):
        env_map = {}
        entry["env"] = env_map
    env_map[env_name] = value
    return normalized


def set_skill_entry_enabled(
    raw_skills: Any,
    skill_key: str,
    enabled: bool,
    *,
    persist_true: bool = False,
) -> dict[str, Any]:
    """Set enabled flag in canonical entries.

    If enabled=True and persist_true=False, explicit enabled flag is removed
    to keep config compact (default behavior).
    """
    normalized = normalize_skills_settings(raw_skills)
    entries = normalized.setdefault("entries", {})
    key = str(skill_key or "").strip()
    if not key:
        return normalized

    entry = entries.get(key)
    if not isinstance(entry, dict):
        entry = {}
        entries[key] = entry

    if enabled:
        if persist_true:
            entry["enabled"] = True
        else:
            entry.pop("enabled", None)
    else:
        entry["enabled"] = False
    return normalized
