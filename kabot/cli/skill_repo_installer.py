"""Install external skill packs from git repositories."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
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


def _extract_frontmatter_meta(skill_md: Path) -> tuple[str, str]:
    """Extract best-effort skill metadata (name, description) from frontmatter/body."""
    fallback_name = skill_md.parent.name
    fallback_desc = ""
    try:
        content = skill_md.read_text(encoding="utf-8")
    except OSError:
        return fallback_name, fallback_desc

    text = content.strip()
    if not text:
        return fallback_name, fallback_desc

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            body = parts[2].strip()
            name = fallback_name
            description = ""
            for line in frontmatter.splitlines():
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                clean_key = key.strip().lower()
                clean_val = value.strip().strip('"').strip("'")
                if clean_key == "name" and clean_val:
                    name = clean_val
                if clean_key == "description" and clean_val:
                    description = clean_val
            if not description:
                description = body.splitlines()[0].strip() if body else ""
            return name, description

    first_line = text.splitlines()[0].strip()
    return fallback_name, first_line


def _candidate_score(repo_root: Path, candidate_dir: Path) -> int:
    """Heuristic score for UX ordering of multi-skill candidates."""
    try:
        rel = candidate_dir.resolve().relative_to(repo_root.resolve())
        rel_str = str(rel).replace("\\", "/").lower()
    except ValueError:
        rel_str = candidate_dir.name.lower()

    depth = len([part for part in rel_str.split("/") if part])
    score = 100 - (depth * 5)
    if rel_str == "skill":
        score += 120
    elif rel_str.startswith("skill/"):
        score += 90
    if rel_str.startswith("skills/"):
        score += 80
    if "/skill" in rel_str:
        score += 20
    return score


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


def _copy_installed_skill(
    *,
    source_label: str,
    repo_root: Path,
    selected: Path,
    target_dir: Path,
    skill_name: str | None,
    overwrite: bool,
) -> InstalledSkill:
    target = Path(target_dir).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)

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
        repo_url=source_label,
        selected_dir=selected_relative,
        installed_dir=destination,
        skill_name=skill_slug,
        skill_key=skill_key,
    )


def install_skill_from_path(
    *,
    source_path: str | Path,
    target_dir: Path,
    subdir: str | None,
    skill_name: str | None,
    overwrite: bool,
) -> InstalledSkill:
    """Install a skill from a local directory or packaged archive."""
    source_value = Path(source_path).expanduser().resolve()
    if not source_value.exists():
        raise ValueError(f"Skill source not found: {source_value}")

    def _install_from_repo_root(repo_root: Path) -> InstalledSkill:
        candidates = discover_skill_dirs(repo_root)
        selected = resolve_skill_source_dir(repo_root, candidates, subdir)
        return _copy_installed_skill(
            source_label=str(source_value),
            repo_root=repo_root,
            selected=selected,
            target_dir=target_dir,
            skill_name=skill_name,
            overwrite=overwrite,
        )

    if source_value.is_dir():
        return _install_from_repo_root(source_value)

    suffix = source_value.suffix.lower()
    if suffix not in {".skill", ".zip"}:
        raise ValueError(f"Unsupported local skill source: {source_value}")

    with tempfile.TemporaryDirectory(prefix="kabot-skill-local-") as tmp:
        extract_root = Path(tmp) / "extracted"
        extract_root.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(source_value, "r") as bundle:
                bundle.extractall(extract_root)
        except zipfile.BadZipFile as exc:
            raise ValueError(f"Invalid skill archive: {source_value}") from exc
        return _install_from_repo_root(extract_root)


def install_skill_from_url(
    *,
    source_url: str,
    target_dir: Path,
    subdir: str | None,
    skill_name: str | None,
    overwrite: bool,
) -> InstalledSkill:
    """Download and install a skill bundle from any URL."""
    url_value = str(source_url).strip()
    if not url_value:
        raise ValueError("Skill URL is required.")

    suffix = Path(url_value.split("?", 1)[0]).suffix.lower()
    if suffix not in {".skill", ".zip"}:
        raise ValueError(f"Unsupported remote skill source: {url_value}")

    with tempfile.TemporaryDirectory(prefix="kabot-skill-url-") as tmp:
        archive_path = Path(tmp) / f"downloaded{suffix}"
        try:
            with urllib.request.urlopen(url_value, timeout=20) as response:  # noqa: S310
                archive_path.write_bytes(response.read())
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Failed to download skill archive: {url_value}") from exc
        return install_skill_from_path(
            source_path=archive_path,
            target_dir=target_dir,
            subdir=subdir,
            skill_name=skill_name,
            overwrite=overwrite,
        )


def list_skill_candidates_from_git(repo_url: str, ref: str | None = None) -> list[str]:
    """Clone repo to temp dir and return discovered SKILL.md candidate subdirs."""
    details = list_skill_candidate_details_from_git(repo_url, ref)
    return [str(item.get("subdir") or "").strip() for item in details if str(item.get("subdir") or "").strip()]


def list_skill_candidate_details_from_git(repo_url: str, ref: str | None = None) -> list[dict[str, object]]:
    """Clone repo to temp dir and return discovered candidate subdirs with metadata/ranking."""
    repo_value = str(repo_url).strip()
    if not repo_value:
        raise ValueError("Repository URL/path is required.")

    with tempfile.TemporaryDirectory(prefix="kabot-skill-candidates-") as tmp:
        clone_root = Path(tmp) / "repo"
        repo_root = clone_skill_repo(repo_value, ref, clone_root)
        candidates = discover_skill_dirs(repo_root)
        detailed: list[dict[str, object]] = []
        for candidate in candidates:
            skill_md = candidate / "SKILL.md"
            name, description = _extract_frontmatter_meta(skill_md)
            subdir = _relative(repo_root, candidate)
            detailed.append(
                {
                    "subdir": subdir,
                    "name": name or candidate.name,
                    "description": description or "",
                    "score": _candidate_score(repo_root, candidate),
                }
            )
        detailed.sort(
            key=lambda item: (
                -int(item.get("score") or 0),
                str(item.get("subdir") or "").lower(),
            )
        )
        return detailed
