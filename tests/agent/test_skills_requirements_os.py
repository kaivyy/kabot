import sys

from kabot.agent.skills import SkillsLoader


def _write_skill(skill_root, skill_name: str, metadata_json: str) -> None:
    skill_dir = skill_root / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {skill_name}",
                "description: test skill",
                f"metadata: '{metadata_json}'",
                "---",
                "",
                "test body",
            ]
        ),
        encoding="utf-8",
    )


def test_list_skills_marks_top_level_os_as_unsupported(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    builtin = tmp_path / "builtin"
    builtin.mkdir()

    unsupported = "darwin" if sys.platform == "win32" else "win32"
    _write_skill(
        builtin,
        "sample_os_blocked",
        f'{{"kabot":{{"os":["{unsupported}"],"requires":{{"bins":[],"env":[]}}}}}}',
    )

    loader = SkillsLoader(workspace, builtin_skills_dir=builtin)
    all_skills = loader.list_skills(filter_unavailable=False)
    skill = next(s for s in all_skills if s["name"] == "sample_os_blocked")

    assert skill["eligible"] is False
    assert skill["missing"]["os"] == [unsupported]
    assert loader.list_skills(filter_unavailable=True) == []


def test_list_skills_accepts_common_os_aliases(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    builtin = tmp_path / "builtin"
    builtin.mkdir()

    if sys.platform == "win32":
        required = "windows"
    elif sys.platform == "darwin":
        required = "macos"
    else:
        required = "linux"

    _write_skill(
        builtin,
        "sample_os_allowed",
        f'{{"kabot":{{"os":["{required}"],"requires":{{"bins":[],"env":[]}}}}}}',
    )

    loader = SkillsLoader(workspace, builtin_skills_dir=builtin)
    all_skills = loader.list_skills(filter_unavailable=False)
    skill = next(s for s in all_skills if s["name"] == "sample_os_allowed")

    assert skill["eligible"] is True
    assert skill["missing"]["os"] == []
