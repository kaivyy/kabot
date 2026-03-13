"""Helpers for pack/publish/sync flows over generic local JSON skill catalogs."""

from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kabot.agent.skills_parts.runtime import parse_frontmatter_metadata
from kabot.cli.skill_repo_installer import discover_skill_dirs
from kabot.utils.skill_validator import validate_skill

_EXCLUDED_DIRS = {".git", ".svn", ".hg", "__pycache__", "node_modules"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slugify(text: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(text or "").strip())
    clean = re.sub(r"-{2,}", "-", clean).strip("-_")
    return clean.lower() or "external-skill"


def _skill_body_first_line(content: str) -> str:
    text = str(content or "")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2]
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def _catalog_entry_sort_key(entry: dict[str, Any]) -> str:
    return str(entry.get("slug") or "").strip().lower()


def resolve_catalog_write_path(catalog_source: str | Path) -> Path:
    path = Path(str(catalog_source or "").strip()).expanduser()
    if not str(path):
        raise ValueError("A local --catalog-source file path is required.")
    if str(catalog_source).strip().lower() == "builtin":
        raise ValueError("Publishing requires a writable local catalog file, not builtin.")
    if str(catalog_source).startswith(("http://", "https://")):
        raise ValueError("Publishing requires a writable local catalog file, not a URL.")
    return path


def load_registry_catalog(catalog_path: Path) -> dict[str, Any]:
    path = Path(catalog_path).expanduser()
    if not path.exists():
        return {
            "catalog_name": path.stem or "local-public",
            "generated_at": _utc_now_iso(),
            "skills": [],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid catalog JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Catalog JSON must be an object.")
    skills = payload.get("skills")
    if not isinstance(skills, list):
        payload["skills"] = []
    return payload


def save_registry_catalog(catalog_path: Path, payload: dict[str, Any]) -> None:
    path = Path(catalog_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = dict(payload)
    normalized["generated_at"] = _utc_now_iso()
    skills = normalized.get("skills")
    if not isinstance(skills, list):
        skills = []
    normalized["skills"] = sorted(
        [entry for entry in skills if isinstance(entry, dict)],
        key=_catalog_entry_sort_key,
    )
    path.write_text(json.dumps(normalized, indent=2, sort_keys=False), encoding="utf-8")


def read_skill_catalog_metadata(skill_dir: Path) -> dict[str, str]:
    root = Path(skill_dir).expanduser().resolve()
    skill_md = root / "SKILL.md"
    if not skill_md.exists():
        raise ValueError(f"SKILL.md not found in {root}")
    try:
        content = skill_md.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Unable to read SKILL.md: {exc}") from exc
    meta = parse_frontmatter_metadata(content)
    if not isinstance(meta, dict):
        meta = {}
    display_name = str(meta.get("name") or root.name).strip() or root.name
    slug = _slugify(display_name or root.name)
    description = str(meta.get("description") or "").strip() or _skill_body_first_line(content)
    homepage = str(meta.get("homepage") or "").strip()
    return {
        "slug": slug,
        "name": display_name,
        "description": description,
        "homepage": homepage,
    }


def package_skill_bundle(
    skill_dir: Path,
    *,
    output_dir: Path,
    bundle_name: str | None = None,
) -> Path:
    root = Path(skill_dir).expanduser().resolve()
    errors = validate_skill(root)
    if errors:
        raise ValueError("; ".join(errors))
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Skill folder not found: {root}")

    output_root = Path(output_dir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    archive_name = str(bundle_name or f"{root.name}.skill").strip() or f"{root.name}.skill"
    if not archive_name.endswith(".skill"):
        archive_name = f"{archive_name}.skill"
    archive_path = output_root / archive_name

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as bundle:
        for file_path in root.rglob("*"):
            if file_path.is_symlink() or not file_path.is_file():
                continue
            rel_parts = file_path.relative_to(root).parts
            if any(part in _EXCLUDED_DIRS for part in rel_parts):
                continue
            arcname = Path(root.name) / file_path.relative_to(root)
            bundle.write(file_path, arcname)
    return archive_path


def publish_skill_to_catalog(
    skill_dir: Path,
    *,
    catalog_source: str | Path,
    bundle_dir: Path,
    slug: str = "",
    name: str = "",
    version: str = "",
    description: str = "",
    homepage: str = "",
    tags: list[str] | None = None,
    changelog: str = "",
    bundle_url_base: str = "",
) -> tuple[dict[str, Any], Path]:
    metadata = read_skill_catalog_metadata(Path(skill_dir))
    slug_value = _slugify(slug or metadata["slug"])
    name_value = str(name or metadata["name"]).strip() or slug_value
    description_value = str(description or metadata["description"]).strip()
    if not description_value:
        raise ValueError(f"Skill '{slug_value}' is missing a description.")
    homepage_value = str(homepage or metadata["homepage"]).strip()
    version_value = str(version or "1.0.0").strip() or "1.0.0"
    tag_values = [str(tag).strip() for tag in (tags or ["latest"]) if str(tag).strip()]
    if not tag_values:
        tag_values = ["latest"]

    bundle_name = f"{slug_value}-{version_value}.skill"
    bundle_path = package_skill_bundle(Path(skill_dir), output_dir=Path(bundle_dir), bundle_name=bundle_name)

    install: dict[str, str]
    url_base = str(bundle_url_base or "").strip().rstrip("/")
    if url_base:
        install = {"url": f"{url_base}/{bundle_name}"}
    else:
        install = {"path": str(bundle_path)}

    entry = {
        "slug": slug_value,
        "name": name_value,
        "description": description_value,
        "homepage": homepage_value,
        "tags": tag_values,
        "version": version_value,
        "changelog": str(changelog or "").strip(),
        "published_at": _utc_now_iso(),
        "install": install,
    }

    catalog_path = resolve_catalog_write_path(catalog_source)
    payload = load_registry_catalog(catalog_path)
    skills = [item for item in payload.get("skills", []) if isinstance(item, dict)]
    replaced = False
    for index, existing in enumerate(skills):
        if str(existing.get("slug") or "").strip().lower() == slug_value:
            skills[index] = entry
            replaced = True
            break
    if not replaced:
        skills.append(entry)
    payload["skills"] = skills
    save_registry_catalog(catalog_path, payload)
    return entry, bundle_path


def sync_skill_roots_to_catalog(
    *,
    roots: list[Path],
    catalog_source: str | Path,
    bundle_dir: Path,
    default_version: str = "1.0.0",
    tags: list[str] | None = None,
    bundle_url_base: str = "",
    dry_run: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    discovered: dict[str, Path] = {}
    skipped: list[dict[str, str]] = []
    for raw_root in roots:
        root = Path(raw_root).expanduser().resolve()
        if not root.exists():
            continue
        for skill_dir in discover_skill_dirs(root):
            try:
                metadata = read_skill_catalog_metadata(skill_dir)
                errors = validate_skill(skill_dir)
                if errors:
                    skipped.append({"path": str(skill_dir), "reason": "; ".join(errors)})
                    continue
            except ValueError as exc:
                skipped.append({"path": str(skill_dir), "reason": str(exc)})
                continue
            discovered.setdefault(metadata["slug"], skill_dir)

    entries: list[dict[str, Any]] = []
    for slug in sorted(discovered):
        skill_dir = discovered[slug]
        metadata = read_skill_catalog_metadata(skill_dir)
        entry = {
            "slug": metadata["slug"],
            "name": metadata["name"],
            "description": metadata["description"],
            "homepage": metadata["homepage"],
            "version": str(default_version or "1.0.0").strip() or "1.0.0",
            "tags": [str(tag).strip() for tag in (tags or ["latest"]) if str(tag).strip()] or ["latest"],
            "skill_dir": str(skill_dir),
        }
        entries.append(entry)
        if dry_run:
            continue
        try:
            publish_skill_to_catalog(
                skill_dir,
                catalog_source=catalog_source,
                bundle_dir=bundle_dir,
                slug=entry["slug"],
                name=entry["name"],
                version=entry["version"],
                description=entry["description"],
                homepage=entry["homepage"],
                tags=entry["tags"],
                bundle_url_base=bundle_url_base,
            )
        except ValueError as exc:
            skipped.append({"path": str(skill_dir), "reason": str(exc)})
            continue
    return entries, skipped
