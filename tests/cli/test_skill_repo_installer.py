from pathlib import Path

import pytest

from kabot.cli.skill_repo_installer import (
    install_skill_from_git,
    resolve_skill_source_dir,
)


def _write_skill(root: Path, name: str, body: str = "sample") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                "description: sample skill",
                "---",
                "",
                body,
            ]
        ),
        encoding="utf-8",
    )


def test_resolve_skill_source_dir_prefers_skill_subdir():
    repo_root = Path("C:/tmp/unused")
    # The actual path object does not need to exist for selection logic assertions
    # when we pass explicit candidates.
    candidates = [repo_root, repo_root / "skill"]
    selected = resolve_skill_source_dir(repo_root, candidates, subdir=None)
    assert selected == repo_root / "skill"


def test_resolve_skill_source_dir_requires_subdir_for_ambiguous_repo(tmp_path):
    repo_root = tmp_path / "repo"
    foo = repo_root / "foo"
    bar = repo_root / "bar"
    _write_skill(foo, "foo")
    _write_skill(bar, "bar")

    candidates = [foo, bar]
    with pytest.raises(ValueError, match="--subdir"):
        resolve_skill_source_dir(repo_root, candidates, subdir=None)


def test_install_skill_from_git_copies_selected_skill_tree(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo-src"
    _write_skill(repo_root, "root-skill", body="root-body")
    _write_skill(repo_root / "skill", "clawra-selfie", body="nested-body")
    (repo_root / "skill" / "scripts").mkdir(parents=True, exist_ok=True)
    (repo_root / "skill" / "scripts" / "run.sh").write_text("echo hi", encoding="utf-8")

    def _fake_clone(repo_url: str, ref: str | None, clone_root: Path) -> Path:
        _ = repo_url, ref, clone_root
        return repo_root

    monkeypatch.setattr("kabot.cli.skill_repo_installer.clone_skill_repo", _fake_clone)

    target_dir = tmp_path / "managed-skills"
    result = install_skill_from_git(
        repo_url="https://example.com/fake.git",
        target_dir=target_dir,
        ref=None,
        subdir=None,
        skill_name=None,
        overwrite=False,
    )

    assert result.skill_name == "clawra-selfie"
    assert result.installed_dir == target_dir / "clawra-selfie"
    assert (result.installed_dir / "SKILL.md").exists()
    assert (result.installed_dir / "scripts" / "run.sh").exists()
