"""Install external skill packs from git repositories."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from kabot.utils.skill_validator import validate_skill


_IGNORED_PARTS = {".git", ".hg", ".svn", "node_modules", ".venv", "__pycache__"}


@dataclass(frozen=True)
class InstalledSkill:
    repo_url: str
    selected_dir: Path
    installed_dir: Path
    skill_name: str
    skill_key: str


def clone_skill_repo(repo_url: str, ref: str | None, clone_root: Path) -> Path:
    """Clone a git repository into clone_root and optionally checkout a ref."""
    cmd = ["git", "clone", "--depth", "1", repo_url, str(clone_root)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise ValueError(f"Failed to clone repo: {stderr or repo_url}")

    if ref:
        checkout = subprocess.run(
            ["git", "-C", str(clone_root), "checkout", ref],
            capture_output=True,
            text=True,
        )
        if checkout.returncode != 0:
            stderr = checkout.stderr.strip() or checkout.stdout.strip()
            raise ValueError(f"Failed to checkout ref '{ref}': {stderr or 'unknown git error'}")
    return clone_root


def discover_skill_dirs(repo_root: Path) -> list[Path]:
    """Find directories that contain SKILL.md, skipping common junk folders."""
    candidates: list[Path] = []
    for skill_md in repo_root.rglob("SKILL.md"):
        if any(part in _IGNORED_PARTS for part in skill_md.parts):
            continue
        candidates.append(skill_md.parent)
    deduped = sorted({path.resolve() for path in candidates}, key=lambda p: str(p).lower())
    return deduped


def _relative(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def resolve_skill_source_dir(repo_root: Path, candidates: list[Path], subdir: str | None) -> Path:
    """Resolve which candidate should be installed from this repository."""
    if subdir:
        target = (repo_root / subdir).resolve()
        if (target / "SKILL.md").exists():
            return target
        raise ValueError(f"Invalid --subdir '{subdir}': SKILL.md not found.")

    if not candidates:
        raise ValueError("No SKILL.md found in repository.")

    if len(candidates) == 1:
        return candidates[0]

    # Prefer a conventional "skill/" folder for external packs (e.g. clawra).
    named_skill = [p for p in candidates if p.name.lower() == "skill"]
    if len(named_skill) == 1:
        return named_skill[0]

    # Prefer single direct child inside "skills/" if unambiguous.
    in_skills = [p for p in candidates if p.parent.name.lower() == "skills"]
    if len(in_skills) == 1:
        return in_skills[0]

    rel = ", ".join(_relative(repo_root, p) for p in candidates)
    raise ValueError(
        "Multiple skill folders found in repo. "
        f"Use --subdir to choose one. Candidates: {rel}"
    )


def _slugify(text: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", text.strip())
    clean = re.sub(r"-{2,}", "-", clean).strip("-_")
    return clean.lower() or "external-skill"


def _extract_frontmatter_name(skill_md: Path) -> str | None:
    try:
        content = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None

    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None

    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip().lower() != "name":
            continue
        parsed = value.strip().strip('"').strip("'")
        return parsed or None
    return None


def _derive_skill_identity(selected_dir: Path, skill_name: str | None) -> tuple[str, str]:
    if skill_name and skill_name.strip():
        normalized = _slugify(skill_name)
        return normalized, normalized

    parsed = _extract_frontmatter_name(selected_dir / "SKILL.md")
    if parsed:
        normalized = _slugify(parsed)
        return normalized, normalized

    fallback = selected_dir.name
    normalized = _slugify(fallback)
    return normalized, normalized


def install_skill_from_git(
    *,
    repo_url: str,
    target_dir: Path,
    ref: str | None,
    subdir: str | None,
    skill_name: str | None,
    overwrite: bool,
) -> InstalledSkill:
    """Clone external repo and install selected skill folder into target_dir."""
    repo_value = str(repo_url).strip()
    if not repo_value:
        raise ValueError("Repository URL/path is required.")

    target = Path(target_dir).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="kabot-skill-") as tmp:
        clone_root = Path(tmp) / "repo"
        repo_root = clone_skill_repo(repo_value, ref, clone_root)
        candidates = discover_skill_dirs(repo_root)
        selected = resolve_skill_source_dir(repo_root, candidates, subdir)
        selected_relative = Path(_relative(repo_root, selected))
        skill_slug, skill_key = _derive_skill_identity(selected, skill_name)

        destination = target / skill_slug
        if destination.exists():
            if not overwrite:
                raise ValueError(f"Skill destination already exists: {destination}")
            shutil.rmtree(destination, ignore_errors=True)

        shutil.copytree(selected, destination)
        errors = validate_skill(destination)
        if errors:
            shutil.rmtree(destination, ignore_errors=True)
            raise ValueError("; ".join(errors))

    return InstalledSkill(
        repo_url=repo_value,
        selected_dir=selected_relative,
        installed_dir=destination,
        skill_name=skill_slug,
        skill_key=skill_key,
    )
