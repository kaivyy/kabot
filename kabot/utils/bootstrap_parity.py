"""Bootstrap file parity checks for workspace consistency."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_REQUIRED_BOOTSTRAP_FILES = [
    "AGENTS.md",
    "SOUL.md",
    "USER.md",
]


def _default_stub_content(filename: str) -> str:
    stem = filename.replace(".md", "").strip() or "BOOTSTRAP"
    return f"# {stem}\n\nTODO: define {stem} guidance for this agent workspace.\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_baseline_dir(path_like: str | Path | None) -> Path | None:
    if path_like is None:
        return None
    if isinstance(path_like, Path):
        p = path_like.expanduser()
    else:
        text = str(path_like).strip()
        if not text:
            return None
        p = Path(text).expanduser()
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    return p


@dataclass
class BootstrapParityPolicy:
    """Policy defining required bootstrap files and baseline behavior."""

    enabled: bool = True
    required_files: list[str] = field(default_factory=lambda: list(DEFAULT_REQUIRED_BOOTSTRAP_FILES))
    baseline_dir: Path | None = None
    enforce_hash: bool = False


def policy_from_config(config: Any | None) -> BootstrapParityPolicy:
    """Build parity policy from runtime config with safe fallbacks."""
    if config is None or not hasattr(config, "bootstrap"):
        return BootstrapParityPolicy()

    bootstrap = getattr(config, "bootstrap")
    required = list(getattr(bootstrap, "required_files", []) or DEFAULT_REQUIRED_BOOTSTRAP_FILES)
    baseline_dir = _resolve_baseline_dir(getattr(bootstrap, "baseline_dir", None))
    enforce_hash = bool(getattr(bootstrap, "enforce_hash", False))
    enabled = bool(getattr(bootstrap, "enabled", True))

    return BootstrapParityPolicy(
        enabled=enabled,
        required_files=required,
        baseline_dir=baseline_dir,
        enforce_hash=enforce_hash,
    )


def check_bootstrap_parity(workspace: Path, policy: BootstrapParityPolicy) -> list[dict[str, Any]]:
    """Check bootstrap file consistency for a workspace."""
    if not policy.enabled:
        return []

    report: list[dict[str, Any]] = []
    baseline_dir = policy.baseline_dir
    for filename in policy.required_files:
        workspace_file = workspace / filename
        baseline_file = (baseline_dir / filename) if baseline_dir else None

        status = "OK"
        detail = f"Present: {workspace_file}"
        issue = ""

        if not workspace_file.exists():
            status = "CRITICAL"
            detail = f"Missing bootstrap file: {workspace_file}"
            issue = "missing_bootstrap_file"
        elif policy.enforce_hash:
            if baseline_file is None or not baseline_file.exists():
                status = "WARN"
                detail = f"Baseline missing for hash enforcement: {filename}"
                issue = "baseline_missing"
            else:
                workspace_hash = _sha256(workspace_file)
                baseline_hash = _sha256(baseline_file)
                if workspace_hash != baseline_hash:
                    status = "WARN"
                    detail = f"Hash mismatch against baseline: {filename}"
                    issue = "bootstrap_hash_mismatch"

        report.append(
            {
                "item": f"Bootstrap:{filename}",
                "file": filename,
                "status": status,
                "detail": detail,
                "issue": issue,
                "path": workspace_file,
                "baseline_path": baseline_file,
            }
        )
    return report


def apply_bootstrap_fixes(
    workspace: Path,
    policy: BootstrapParityPolicy,
    *,
    sync_mismatch: bool = False,
) -> list[str]:
    """Apply non-destructive bootstrap fixes and optional mismatch sync."""
    if not policy.enabled:
        return []

    workspace.mkdir(parents=True, exist_ok=True)
    changes: list[str] = []
    baseline_dir = policy.baseline_dir

    for filename in policy.required_files:
        workspace_file = workspace / filename
        baseline_file = (baseline_dir / filename) if baseline_dir else None

        if not workspace_file.exists():
            if baseline_file is not None and baseline_file.exists():
                workspace_file.write_text(baseline_file.read_text(encoding="utf-8"), encoding="utf-8")
                changes.append(f"Created {filename} from baseline")
            else:
                workspace_file.write_text(_default_stub_content(filename), encoding="utf-8")
                changes.append(f"Created {filename} with default stub")
            continue

        if not (sync_mismatch and policy.enforce_hash):
            continue
        if baseline_file is None or not baseline_file.exists():
            continue
        if _sha256(workspace_file) == _sha256(baseline_file):
            continue

        workspace_file.write_text(baseline_file.read_text(encoding="utf-8"), encoding="utf-8")
        changes.append(f"Synchronized {filename} from baseline")

    return changes
