from pathlib import Path

from kabot.agent.skills import SkillsLoader


def _write_skill(skill_root: Path, skill_name: str, body: str) -> None:
    skill_dir = skill_root / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: test skill\n---\n\n{body}\n",
        encoding="utf-8",
    )


def test_match_skills_does_not_auto_load_irrelevant_tool_skills(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    matches = loader.match_skills("jadi tools mu yang bermasalah?", profile="GENERAL")
    assert "mcporter" not in matches
    assert "sherpa-onnx-tts" not in matches


def test_match_skills_supports_thai_keywords(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(workspace / "skills", "cleanup-th", "ล้างแคช ดิสก์ ลบไฟล์ชั่วคราว")

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    matches = loader.match_skills("ช่วยล้างแคชดิสก์ให้หน่อย", profile="GENERAL")

    assert any(m.startswith("cleanup-th") for m in matches)


def test_match_skills_prioritizes_explicit_skill_name(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(workspace / "skills", "clawra-selfie", "generate selfie image")
    _write_skill(
        workspace / "skills",
        "generic-image",
        "generate selfie image portrait photo camera selfie image generator edit create",
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    matches = loader.match_skills(
        "please use clawra-selfie skill to generate selfie image portrait photo now",
        profile="GENERAL",
    )

    assert matches
    assert any(m.startswith("generic-image") for m in matches)
    assert matches[0].startswith("clawra-selfie")


def test_match_skills_preserves_explicit_digit_heavy_full_name_match(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(workspace / "skills", "1password", "vault credential manager")
    _write_skill(
        workspace / "skills",
        "password-helper",
        "password vault credential manager login secure account",
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    matches = loader.match_skills(
        "please use 1password skill for this password vault login task",
        profile="GENERAL",
    )

    assert matches
    assert any(m.startswith("password-helper") for m in matches)
    assert matches[0].startswith("1password")


def test_list_skills_uses_snapshot_cache(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(workspace / "skills", "cached-skill", "cached summary check")

    calls = {"count": 0}

    def _validate_skill(_skill_dir: Path):
        calls["count"] += 1
        return []

    monkeypatch.setattr("kabot.agent.skills.validate_skill", _validate_skill)

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    first = loader.list_skills(filter_unavailable=True)
    second = loader.list_skills(filter_unavailable=True)

    assert first
    assert second
    assert calls["count"] == 1
