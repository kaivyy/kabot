import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

from kabot.agent.skills_matching import (
    WORKFLOW_CHAINS,
    _extract_keywords,
    looks_like_explicit_skill_use_request,
    normalize_skill_reference_name,
)

_EXPLICIT_SKILL_FAST_PATH_FILLERS = {"request", "task", "permintaan", "tolong", "please", "ini", "that", "this"}


def iter_skill_roots_with_source(loader: Any) -> list[tuple[Path, str]]:
    roots: list[tuple[Path, str]] = [
        (loader.workspace_skills, "workspace"),
        (loader.project_agents_skills, "agents-project"),
        (loader.personal_agents_skills, "agents-personal"),
    ]
    if loader.managed_skills:
        roots.append((loader.managed_skills, "managed"))
    if loader.builtin_skills:
        roots.append((loader.builtin_skills, "builtin"))
    roots.extend((extra_dir, "extra") for extra_dir in loader.extra_skill_dirs)
    return roots


def iter_unique_skill_candidates(loader: Any):
    seen_names: set[str] = set()
    for root, source in iter_skill_roots_with_source(loader):
        if not root.exists():
            continue
        for skill_dir in root.iterdir():
            if not skill_dir.is_dir():
                continue
            name = skill_dir.name
            if name in seen_names:
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            seen_names.add(name)
            yield name, skill_file, source


def parse_frontmatter_metadata(content: str) -> dict:
    if not content.startswith("---"):
        return {}
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    yaml_text = match.group(1)
    try:
        import yaml
        return yaml.safe_load(yaml_text) or {}
    except ImportError:
        metadata = {}
        for line in yaml_text.split("\n"):
            if ":" in line and not line.strip().startswith("{") and not line.strip().startswith("}"):
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip('"\'')
        return metadata
    except Exception:
        return {}


def get_skill_metadata_from_file(_loader: Any, skill_file: Path) -> dict:
    try:
        content = skill_file.read_text(encoding="utf-8")
    except OSError:
        return {}
    return parse_frontmatter_metadata(content)


def build_skill_status(loader: Any, name: str, skill_file: Path, source: str) -> dict:
    meta = get_skill_metadata_from_file(loader, skill_file)
    effective_meta = dict(meta) if isinstance(meta, dict) else {}
    skill_meta = loader._parse_kabot_metadata(meta.get("metadata", "")) if isinstance(meta, dict) else {}
    if isinstance(skill_meta, dict):
        effective_meta.update(skill_meta)

    install_specs = loader._normalize_install_specs(effective_meta.get("install", {}))
    skill_key = str(effective_meta.get("skillKey") or name).strip() or name
    skill_cfg = loader._skill_entries.get(skill_key, {})
    if not isinstance(skill_cfg, dict):
        skill_cfg = {}
    disabled = skill_cfg.get("enabled") is False
    blocked_by_allowlist = (
        source == "builtin"
        and len(loader._allow_bundled) > 0
        and name not in loader._allow_bundled
        and skill_key not in loader._allow_bundled
    )
    requires = effective_meta.get("requires", {})
    if not isinstance(requires, dict):
        requires = {}
    entry_env = skill_cfg.get("env", {})
    if not isinstance(entry_env, dict):
        entry_env = {}
    entry_api_key = str(skill_cfg.get("api_key") or "").strip()
    primary_env = effective_meta.get("primaryEnv")
    missing_bins = [str(binary) for binary in requires.get("bins", []) if not shutil.which(str(binary))]
    missing_env = []
    for raw_env in requires.get("env", []):
        env_name = str(raw_env).strip()
        if not env_name:
            continue
        env_satisfied = bool(os.environ.get(env_name) or entry_env.get(env_name))
        if not env_satisfied and entry_api_key and primary_env == env_name:
            env_satisfied = True
        if not env_satisfied:
            missing_env.append(env_name)
    missing_os = loader._missing_os(effective_meta)
    return {
        "name": name,
        "eligible": not missing_bins and not missing_env and not missing_os and not disabled and not blocked_by_allowlist,
        "disabled": disabled,
        "blocked_by_allowlist": blocked_by_allowlist,
        "missing": {"bins": missing_bins, "env": missing_env, "os": missing_os},
        "install": install_specs,
    }


def get_skill_status(loader: Any, name: str) -> dict | None:
    normalized = normalize_skill_reference_name(name)
    if not normalized:
        return None
    for skill_name, skill_file, source in iter_unique_skill_candidates(loader):
        if skill_name == normalized:
            return build_skill_status(loader, skill_name, skill_file, source)
    return None


def get_always_skills(loader: Any) -> list[str]:
    roots_snapshot = loader._compute_roots_snapshot()
    now = time.time()
    if loader._always_skills_cache:
        cached_at, cached_snapshot, cached_items = loader._always_skills_cache
        if cached_snapshot == roots_snapshot and (now - cached_at) <= loader._list_cache_ttl_seconds:
            return list(cached_items)

    result: list[str] = []
    for name, skill_file, source in iter_unique_skill_candidates(loader):
        meta = get_skill_metadata_from_file(loader, skill_file)
        effective_meta = dict(meta) if isinstance(meta, dict) else {}
        skill_meta = loader._parse_kabot_metadata(meta.get("metadata", "")) if isinstance(meta, dict) else {}
        if isinstance(skill_meta, dict):
            effective_meta.update(skill_meta)
        if not (bool(effective_meta.get("always")) or bool(meta.get("always"))):
            continue
        if build_skill_status(loader, name, skill_file, source).get("eligible"):
            result.append(name)

    loader._always_skills_cache = (now, roots_snapshot, list(result))
    return result


def match_explicit_skill_fast_path(loader: Any, *, message: str, message_lower: str, max_results: int) -> list[str] | None:
    if not looks_like_explicit_skill_use_request(message):
        return None

    matched_name = ""
    for skill_name, _skill_file, _source in iter_unique_skill_candidates(loader):
        if re.search(rf"(?<![\w-]){re.escape(skill_name.lower())}(?![\w-])", message_lower):
            matched_name = skill_name
            break
    if not matched_name:
        return None

    residual_keywords = _extract_keywords(message)
    residual_keywords -= _extract_keywords(matched_name.replace("-", " ").replace("_", " "))
    residual_keywords -= _EXPLICIT_SKILL_FAST_PATH_FILLERS
    if len(residual_keywords) > 1:
        return None

    selected = [matched_name]
    for chain_skill in WORKFLOW_CHAINS.get(matched_name, []):
        if chain_skill not in selected and len(selected) < max_results + 2:
            selected.append(chain_skill)

    validated = []
    for skill_name in selected:
        status = get_skill_status(loader, skill_name)
        if status and status.get("eligible"):
            validated.append(skill_name)
        else:
            missing = loader._format_skill_unavailability(status) if status else "requirements not met"
            validated.append(f"{skill_name} [NEEDS: {missing}]")
    return validated[:max_results + 2]
