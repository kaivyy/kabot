"""Backup helpers for Kabot configuration archives."""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

_CONFIG_EXCLUDED_DIRS = {
    "__pycache__",
    ".pytest_cache",
    "backups",
    "logs",
    "sessions",
    "vector_db",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _should_include_file(source_dir: Path, path: Path, *, only_config: bool) -> bool:
    if not only_config:
        return True
    rel_path = path.relative_to(source_dir)
    parent_parts = {part.lower() for part in rel_path.parts[:-1]}
    return not bool(parent_parts & _CONFIG_EXCLUDED_DIRS)


def create_backup(
    source_dir: str | Path,
    dest_dir: str | Path | None = None,
    *,
    only_config: bool = True,
) -> str:
    """Create a zip backup archive and return its path."""
    source_path = Path(source_dir).expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Source config dir {source_path} not found")
    if not source_path.is_dir():
        raise NotADirectoryError(f"Source config dir {source_path} is not a directory")

    destination = (
        Path(dest_dir).expanduser().resolve()
        if dest_dir is not None
        else source_path / "backups"
    )
    destination.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = destination / f"kabot_backup_{timestamp}.zip"

    files_to_archive: list[tuple[Path, str]] = []
    for path in sorted(source_path.rglob("*")):
        if not path.is_file():
            continue
        if not _should_include_file(source_path, path, only_config=only_config):
            continue
        files_to_archive.append((path, path.relative_to(source_path).as_posix()))

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(source_path),
        "only_config": only_config,
        "files": [],
    }

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, arcname in files_to_archive:
            archive.write(path, arcname)
            manifest["files"].append(
                {
                    "path": arcname,
                    "size": path.stat().st_size,
                    "sha256": _sha256_file(path),
                }
            )
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))

    return str(archive_path)
