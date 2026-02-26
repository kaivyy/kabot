from pathlib import Path

from kabot.agent.skills import SkillsLoader


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
