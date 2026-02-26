from pathlib import Path
import sys

from kabot.agent.skills import SkillsLoader


def _write_skill(skill_root: Path, skill_name: str, metadata_json: str) -> None:
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


def test_entries_env_satisfies_required_env(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    builtin = tmp_path / "builtin"
    builtin.mkdir()

    _write_skill(
        builtin,
        "needs_env",
        '{"kabot":{"requires":{"bins":[],"env":["MY_TEST_KEY"]}}}',
    )

    loader = SkillsLoader(
        workspace=workspace,
        builtin_skills_dir=builtin,
        skills_config={
            "entries": {
                "needs_env": {
                    "env": {
                        "MY_TEST_KEY": "from-config",
                    }
                }
            }
        },
    )

    all_skills = loader.list_skills(filter_unavailable=False)
    info = next(s for s in all_skills if s["name"] == "needs_env")

    assert info["eligible"] is True
    assert info["missing"]["env"] == []


def test_disabled_entry_marks_skill_ineligible(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    builtin = tmp_path / "builtin"
    builtin.mkdir()

    _write_skill(
        builtin,
        "disabled_skill",
        '{"kabot":{"requires":{"bins":[],"env":[]}}}',
    )

    loader = SkillsLoader(
        workspace=workspace,
        builtin_skills_dir=builtin,
        skills_config={
            "entries": {
                "disabled_skill": {
                    "enabled": False,
                }
            }
        },
    )

    all_skills = loader.list_skills(filter_unavailable=False)
    info = next(s for s in all_skills if s["name"] == "disabled_skill")

    assert info["disabled"] is True
    assert info["eligible"] is False
    assert loader.list_skills(filter_unavailable=True) == []


def test_allow_bundled_blocks_bundled_skill(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    builtin = tmp_path / "builtin"
    builtin.mkdir()

    _write_skill(
        builtin,
        "blocked_bundled",
        '{"kabot":{"requires":{"bins":[],"env":[]}}}',
    )

    loader = SkillsLoader(
        workspace=workspace,
        builtin_skills_dir=builtin,
        skills_config={
            "allow_bundled": ["allowed_skill"],
        },
    )

    all_skills = loader.list_skills(filter_unavailable=False)
    info = next(s for s in all_skills if s["name"] == "blocked_bundled")

    assert info["blocked_by_allowlist"] is True
    assert info["eligible"] is False
    assert loader.list_skills(filter_unavailable=True) == []


def test_skill_key_entry_env_is_used_for_requirements(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    builtin = tmp_path / "builtin"
    builtin.mkdir()

    _write_skill(
        builtin,
        "named_skill",
        '{"kabot":{"skillKey":"alias-key","requires":{"bins":[],"env":["ALIAS_ENV"]}}}',
    )

    loader = SkillsLoader(
        workspace=workspace,
        builtin_skills_dir=builtin,
        skills_config={
            "entries": {
                "alias-key": {
                    "env": {
                        "ALIAS_ENV": "set-via-skill-key",
                    }
                }
            }
        },
    )

    all_skills = loader.list_skills(filter_unavailable=False)
    info = next(s for s in all_skills if s["name"] == "named_skill")

    assert info["skill_key"] == "alias-key"
    assert info["eligible"] is True
    assert info["missing"]["env"] == []


def test_install_metadata_legacy_cmd_normalized_to_list(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    builtin = tmp_path / "builtin"
    builtin.mkdir()

    _write_skill(
        builtin,
        "legacy_install_skill",
        '{"kabot":{"requires":{"bins":["demo-cli"],"env":[]},"install":{"cmd":"pip install demo-cli","label":"Install demo-cli"}}}',
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    all_skills = loader.list_skills(filter_unavailable=False)
    info = next(s for s in all_skills if s["name"] == "legacy_install_skill")

    assert isinstance(info["install"], list)
    assert len(info["install"]) == 1
    spec = info["install"][0]
    assert spec["kind"] == "cmd"
    assert spec["cmd"] == "pip install demo-cli"


def test_install_metadata_list_is_filtered_by_installer_os(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    builtin = tmp_path / "builtin"
    builtin.mkdir()

    current_os = sys.platform
    _write_skill(
        builtin,
        "os_filtered_install_skill",
        (
            '{"kabot":{"requires":{"bins":["demo-cli"],"env":[]},"install":['
            '{"id":"current","kind":"cmd","cmd":"install-current","os":["'
            + current_os
            + '"]},'
            '{"id":"other","kind":"cmd","cmd":"install-other","os":["__never__"]}'
            ']}}'
        ),
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    all_skills = loader.list_skills(filter_unavailable=False)
    info = next(s for s in all_skills if s["name"] == "os_filtered_install_skill")

    assert len(info["install"]) == 1
    assert info["install"][0]["id"] == "current"
