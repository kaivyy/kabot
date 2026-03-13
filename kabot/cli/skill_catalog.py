"""Public skill catalog helpers."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

_DEFAULT_TIMEOUT_SECONDS = 10


def _builtin_catalog_path() -> Path:
    return Path(__file__).with_name("skill_catalog_builtin.json")


def _load_catalog_payload(source: str | None = None) -> dict[str, Any]:
    normalized = str(source or "").strip()
    if not normalized or normalized.lower() == "builtin":
        return json.loads(_builtin_catalog_path().read_text(encoding="utf-8"))

    source_path = Path(normalized).expanduser()
    if source_path.exists():
        return json.loads(source_path.read_text(encoding="utf-8"))

    if normalized.startswith(("http://", "https://")):
        with urllib.request.urlopen(normalized, timeout=_DEFAULT_TIMEOUT_SECONDS) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))

    raise ValueError(f"Catalog source not found: {normalized}")


def _normalize_catalog_entry(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    slug = str(raw.get("slug") or "").strip().lower()
    name = str(raw.get("name") or slug).strip()
    description = str(raw.get("description") or "").strip()
    if not slug or not name or not description:
        return None

    install = raw.get("install")
    if not isinstance(install, dict):
        return None

    normalized_install: dict[str, str] = {}
    for key in ("git", "path", "url", "ref", "subdir"):
        value = str(install.get(key) or "").strip()
        if value:
            normalized_install[key] = value
    if not any(key in normalized_install for key in ("git", "path", "url")):
        return None

    tags = raw.get("tags")
    normalized_tags = [str(tag).strip() for tag in tags if str(tag).strip()] if isinstance(tags, list) else []

    return {
        "slug": slug,
        "name": name,
        "description": description,
        "homepage": str(raw.get("homepage") or "").strip(),
        "tags": normalized_tags,
        "install": normalized_install,
    }


def load_skill_catalog(source: str | None = None) -> list[dict[str, Any]]:
    payload = _load_catalog_payload(source)
    skills = payload.get("skills") if isinstance(payload, dict) else None
    if not isinstance(skills, list):
        return []
    return [entry for raw in skills if (entry := _normalize_catalog_entry(raw))]


def search_skill_catalog(
    query: str,
    *,
    source: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    entries = load_skill_catalog(source)
    normalized = str(query or "").strip().lower()
    if not normalized:
        return entries[: max(1, limit)]

    query_tokens = [token for token in normalized.replace("-", " ").split() if token]
    scored: list[tuple[float, dict[str, Any]]] = []
    for entry in entries:
        slug = str(entry.get("slug") or "").lower()
        name = str(entry.get("name") or "").lower()
        description = str(entry.get("description") or "").lower()
        tags = [str(tag).lower() for tag in entry.get("tags") or []]
        score = 0.0
        if normalized == slug:
            score += 10.0
        for token in query_tokens:
            if token in slug:
                score += 4.0
            if token in name:
                score += 3.0
            if token in description:
                score += 1.5
            if any(token in tag for tag in tags):
                score += 1.0
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda item: (item[0], item[1]["slug"]), reverse=True)
    return [entry for _, entry in scored[: max(1, limit)]]


def resolve_catalog_skill(slug: str, *, source: str | None = None) -> dict[str, Any] | None:
    normalized = str(slug or "").strip().lower()
    if not normalized:
        return None
    for entry in load_skill_catalog(source):
        if str(entry.get("slug") or "").strip().lower() == normalized:
            return entry
    return None
