from pathlib import Path

from typer.testing import CliRunner


def test_skills_install_updates_config_and_targets_managed_dir(monkeypatch, tmp_path):
    from kabot.cli.commands import app
    from kabot.cli.skill_repo_installer import InstalledSkill
    from kabot.config.schema import Config

    runner = CliRunner()
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")
    cfg.skills = {"load": {"managed_dir": str(tmp_path / "managed-skills")}}

    saved = {}

    def _fake_save(updated, config_path=None):  # noqa: ANN001
        saved["config"] = updated
        saved["path"] = config_path

    captured = {}

    def _fake_install(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        installed = Path(kwargs["target_dir"]) / "clawra-selfie"
        installed.mkdir(parents=True, exist_ok=True)
        (installed / "SKILL.md").write_text("---\nname: clawra-selfie\n---\n", encoding="utf-8")
        return InstalledSkill(
            repo_url=str(kwargs["repo_url"]),
            selected_dir=Path("skill"),
            installed_dir=installed,
            skill_name="clawra-selfie",
            skill_key="clawra-selfie",
        )

    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.save_config", _fake_save)
    monkeypatch.setattr("kabot.cli.skill_repo_installer.install_skill_from_git", _fake_install)

    result = runner.invoke(app, ["skills", "install", "--git", "https://github.com/example/clawra.git"])

    assert result.exit_code == 0
    assert "Installed skill" in result.output
    assert captured["target_dir"] == tmp_path / "managed-skills"
    assert saved["config"].skills["entries"]["clawra-selfie"]["enabled"] is True


def test_skills_install_workspace_target(monkeypatch, tmp_path):
    from kabot.cli.commands import app
    from kabot.cli.skill_repo_installer import InstalledSkill
    from kabot.config.schema import Config

    runner = CliRunner()
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")

    captured = {}

    def _fake_install(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        installed = Path(kwargs["target_dir"]) / "sample-skill"
        installed.mkdir(parents=True, exist_ok=True)
        (installed / "SKILL.md").write_text("---\nname: sample-skill\n---\n", encoding="utf-8")
        return InstalledSkill(
            repo_url=str(kwargs["repo_url"]),
            selected_dir=Path("skill"),
            installed_dir=installed,
            skill_name="sample-skill",
            skill_key="sample-skill",
        )

    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.save_config", lambda *args, **kwargs: None)
    monkeypatch.setattr("kabot.cli.skill_repo_installer.install_skill_from_git", _fake_install)

    result = runner.invoke(
        app,
        ["skills", "install", "--git", "https://github.com/example/sample.git", "--target", "workspace"],
    )

    assert result.exit_code == 0
    assert captured["target_dir"] == cfg.workspace_path / "skills"
