from pathlib import Path

import pytest

from kabot.agent.skills import SkillsLoader


@pytest.fixture(autouse=True)
def _isolate_home(monkeypatch, tmp_path):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)


def _write_skill(skill_root: Path, skill_name: str, body: str, metadata_json: str | None = None) -> None:
    skill_dir = skill_root / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        f"name: {skill_name}",
        "description: test skill",
    ]
    if metadata_json:
        lines.append(f"metadata: '{metadata_json}'")
    lines.extend(
        [
            "---",
            "",
            body,
        ]
    )
    (skill_dir / "SKILL.md").write_text("\n".join(lines), encoding="utf-8")


def test_skills_precedence_workspace_over_managed_over_builtin(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True)
    managed = tmp_path / "managed"
    managed.mkdir(parents=True)

    _write_skill(workspace / "skills", "shared", "workspace-version")
    _write_skill(managed, "shared", "managed-version")
    _write_skill(builtin, "shared", "builtin-version")

    loader = SkillsLoader(
        workspace=workspace,
        builtin_skills_dir=builtin,
        skills_config={"load": {"managed_dir": str(managed)}},
    )

    all_skills = loader.list_skills(filter_unavailable=False)
    shared = next(s for s in all_skills if s["name"] == "shared")

    assert shared["source"] == "workspace"
    assert "workspace" in shared["path"]
    assert "workspace-version" in (loader.load_skill("shared") or "")


def test_skills_precedence_managed_over_builtin(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True)
    managed = tmp_path / "managed"
    managed.mkdir(parents=True)

    _write_skill(managed, "shared", "managed-version")
    _write_skill(builtin, "shared", "builtin-version")

    loader = SkillsLoader(
        workspace=workspace,
        builtin_skills_dir=builtin,
        skills_config={"load": {"managed_dir": str(managed)}},
    )

    all_skills = loader.list_skills(filter_unavailable=False)
    shared = next(s for s in all_skills if s["name"] == "shared")

    assert shared["source"] == "managed"
    assert "managed" in shared["path"]
    assert "managed-version" in (loader.load_skill("shared") or "")


def test_skills_precedence_builtin_over_extra(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True)
    extra = tmp_path / "extra"
    extra.mkdir(parents=True)

    _write_skill(builtin, "shared", "builtin-version")
    _write_skill(extra, "shared", "extra-version")

    loader = SkillsLoader(
        workspace=workspace,
        builtin_skills_dir=builtin,
        skills_config={"load": {"extra_dirs": [str(extra)]}},
    )

    all_skills = loader.list_skills(filter_unavailable=False)
    shared = next(s for s in all_skills if s["name"] == "shared")

    assert shared["source"] == "builtin"
    assert "builtin-version" in (loader.load_skill("shared") or "")


def test_skills_list_dedupes_name_collisions_across_all_roots(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True)
    managed = tmp_path / "managed"
    managed.mkdir(parents=True)
    extra = tmp_path / "extra"
    extra.mkdir(parents=True)
    fake_home = tmp_path / "home"
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    _write_skill(extra, "collision", "extra-version")
    _write_skill(builtin, "collision", "builtin-version")
    _write_skill(managed, "collision", "managed-version")
    _write_skill(fake_home / ".agents" / "skills", "collision", "personal-version")
    _write_skill(workspace / ".agents" / "skills", "collision", "project-version")
    _write_skill(workspace / "skills", "collision", "workspace-version")

    loader = SkillsLoader(
        workspace=workspace,
        builtin_skills_dir=builtin,
        skills_config={"load": {"managed_dir": str(managed), "extra_dirs": [str(extra)]}},
    )

    all_skills = loader.list_skills(filter_unavailable=False)
    collisions = [s for s in all_skills if s["name"] == "collision"]

    assert len(collisions) == 1
    assert collisions[0]["source"] == "workspace"
    assert "workspace-version" in (loader.load_skill("collision") or "")


def test_skills_precedence_workspace_over_project_agents_over_personal_agents(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True)
    managed = tmp_path / "managed"
    managed.mkdir(parents=True)
    extra = tmp_path / "extra"
    extra.mkdir(parents=True)

    fake_home = tmp_path / "home"
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    _write_skill(extra, "shared", "extra-version")
    _write_skill(builtin, "shared", "builtin-version")
    _write_skill(managed, "shared", "managed-version")
    _write_skill(fake_home / ".agents" / "skills", "shared", "personal-agents-version")
    _write_skill(workspace / ".agents" / "skills", "shared", "project-agents-version")
    _write_skill(workspace / "skills", "shared", "workspace-version")

    loader = SkillsLoader(
        workspace=workspace,
        builtin_skills_dir=builtin,
        skills_config={"load": {"managed_dir": str(managed), "extra_dirs": [str(extra)]}},
    )

    all_skills = loader.list_skills(filter_unavailable=False)
    shared = next(s for s in all_skills if s["name"] == "shared")

    assert shared["source"] == "workspace"
    assert "workspace-version" in (loader.load_skill("shared") or "")


def test_skills_precedence_project_agents_over_personal_agents_when_workspace_missing(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True)

    fake_home = tmp_path / "home"
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    _write_skill(fake_home / ".agents" / "skills", "shared", "personal-agents-version")
    _write_skill(workspace / ".agents" / "skills", "shared", "project-agents-version")
    _write_skill(builtin, "shared", "builtin-version")

    loader = SkillsLoader(
        workspace=workspace,
        builtin_skills_dir=builtin,
        skills_config={},
    )

    all_skills = loader.list_skills(filter_unavailable=False)
    shared = next(s for s in all_skills if s["name"] == "shared")

    assert shared["source"] == "agents-project"
    assert "project-agents-version" in (loader.load_skill("shared") or "")


def test_match_skills_hot_reload_after_skill_file_update(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True)
    managed = tmp_path / "managed"
    managed.mkdir(parents=True)

    _write_skill(workspace / "skills", "rotation-helper", "oldstorm oldcloud")

    loader = SkillsLoader(
        workspace=workspace,
        builtin_skills_dir=builtin,
        skills_config={"load": {"managed_dir": str(managed)}},
    )

    initial_matches = loader.match_skills("please oldstorm oldcloud now", profile="GENERAL")
    assert any(match.startswith("rotation-helper") for match in initial_matches)

    _write_skill(workspace / "skills", "rotation-helper", "newstorm newcloud")

    updated_matches = loader.match_skills("please newstorm newcloud now", profile="GENERAL")
    assert any(match.startswith("rotation-helper") for match in updated_matches)


def test_match_skills_hot_reload_after_new_skill_added(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True)
    managed = tmp_path / "managed"
    managed.mkdir(parents=True)

    _write_skill(workspace / "skills", "base-skill", "alphaone alphatwo")

    loader = SkillsLoader(
        workspace=workspace,
        builtin_skills_dir=builtin,
        skills_config={"load": {"managed_dir": str(managed)}},
    )
    _ = loader.match_skills("alphaone alphatwo", profile="GENERAL")

    _write_skill(workspace / "skills", "added-skill", "betastorm betacloud")

    matches = loader.match_skills("betastorm betacloud", profile="GENERAL")
    assert any(match.startswith("added-skill") for match in matches)


def test_match_skills_hot_reload_after_skill_removed(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True)
    managed = tmp_path / "managed"
    managed.mkdir(parents=True)

    _write_skill(workspace / "skills", "temporary-skill", "removeme tokenized")

    loader = SkillsLoader(
        workspace=workspace,
        builtin_skills_dir=builtin,
        skills_config={"load": {"managed_dir": str(managed)}},
    )

    initial_matches = loader.match_skills("removeme tokenized", profile="GENERAL")
    assert any(match.startswith("temporary-skill") for match in initial_matches)

    skill_dir = workspace / "skills" / "temporary-skill"
    for child in skill_dir.iterdir():
        child.unlink()
    skill_dir.rmdir()

    matches_after_removal = loader.match_skills("removeme tokenized", profile="GENERAL")
    assert not any(match.startswith("temporary-skill") for match in matches_after_removal)
