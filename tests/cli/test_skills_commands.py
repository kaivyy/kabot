from pathlib import Path

from typer.testing import CliRunner


def test_skills_install_updates_config_and_targets_managed_dir(monkeypatch, tmp_path):
    from kabot.cli.commands import app
    from kabot.cli.skill_repo_installer import InstalledSkill
    from kabot.config.schema import Config, SkillsConfig

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
    assert isinstance(saved["config"].skills, SkillsConfig)


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


def test_skills_install_from_local_path_updates_config(monkeypatch, tmp_path):
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
        installed = Path(kwargs["target_dir"]) / "manus-stock-analysis"
        installed.mkdir(parents=True, exist_ok=True)
        (installed / "SKILL.md").write_text("---\nname: manus-stock-analysis\n---\n", encoding="utf-8")
        return InstalledSkill(
            repo_url=str(kwargs["source_path"]),
            selected_dir=Path("."),
            installed_dir=installed,
            skill_name="manus-stock-analysis",
            skill_key="manus-stock-analysis",
        )

    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.save_config", _fake_save)
    monkeypatch.setattr("kabot.cli.skill_repo_installer.install_skill_from_path", _fake_install)

    result = runner.invoke(
        app,
        [
            "skills",
            "install",
            "--path",
            str(tmp_path / "manus-stock-analysis-1.0.0"),
        ],
    )

    assert result.exit_code == 0
    assert "Installed skill" in result.output
    assert captured["target_dir"] == tmp_path / "managed-skills"
    assert saved["config"].skills["entries"]["manus-stock-analysis"]["enabled"] is True


def test_skills_install_from_remote_url_updates_config(monkeypatch, tmp_path):
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
        installed = Path(kwargs["target_dir"]) / "binance-pro"
        installed.mkdir(parents=True, exist_ok=True)
        (installed / "SKILL.md").write_text("---\nname: binance-pro\n---\n", encoding="utf-8")
        return InstalledSkill(
            repo_url=str(kwargs["source_url"]),
            selected_dir=Path("."),
            installed_dir=installed,
            skill_name="binance-pro",
            skill_key="binance-pro",
        )

    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.save_config", _fake_save)
    monkeypatch.setattr("kabot.cli.skill_repo_installer.install_skill_from_url", _fake_install)

    result = runner.invoke(
        app,
        [
            "skills",
            "install",
            "--url",
            "https://skills.example.invalid/binance-pro.skill",
        ],
    )

    assert result.exit_code == 0
    assert "Installed skill" in result.output
    assert captured["source_url"] == "https://skills.example.invalid/binance-pro.skill"
    assert captured["target_dir"] == tmp_path / "managed-skills"
    assert saved["config"].skills["entries"]["binance-pro"]["enabled"] is True


def test_skills_install_blocks_when_trust_mode_rejects_signer(monkeypatch, tmp_path):
    from kabot.cli.commands import app
    from kabot.cli.skill_repo_installer import InstalledSkill
    from kabot.config.schema import Config

    runner = CliRunner()
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")
    cfg.security.trust_mode.enabled = True
    cfg.security.trust_mode.verify_skill_manifest = True
    cfg.security.trust_mode.allowed_signers = ["trusted-signer"]

    def _fake_install(**kwargs):  # noqa: ANN003
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
    monkeypatch.setattr(
        "kabot.utils.skill_validator.validate_skill_trust",
        lambda *args, **kwargs: (False, "Signer 'evil' is not trusted"),
    )

    result = runner.invoke(app, ["skills", "install", "--git", "https://github.com/example/sample.git"])

    assert result.exit_code == 1
    assert "trust mode" in result.output.lower()


def test_skills_install_respects_onboarding_auto_enable_false(monkeypatch, tmp_path):
    from kabot.cli.commands import app
    from kabot.cli.skill_repo_installer import InstalledSkill
    from kabot.config.schema import Config

    runner = CliRunner()
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")
    cfg.skills = {
        "onboarding": {
            "auto_enable_after_install": False,
            "auto_prompt_env": False,
            "soul_injection_mode": "disabled",
        }
    }

    saved = {}

    def _fake_save(updated, config_path=None):  # noqa: ANN001
        saved["config"] = updated
        saved["path"] = config_path

    def _fake_install(**kwargs):  # noqa: ANN003
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
    monkeypatch.setattr("kabot.config.loader.save_config", _fake_save)
    monkeypatch.setattr("kabot.cli.skill_repo_installer.install_skill_from_git", _fake_install)

    result = runner.invoke(app, ["skills", "install", "--git", "https://github.com/example/sample.git"])

    assert result.exit_code == 0
    assert "Auto-enable after install is OFF" in result.output
    entries = saved["config"].skills["entries"]
    assert "sample-skill" not in entries or entries["sample-skill"].get("enabled") is not True


def test_skills_install_onboarding_applies_env_and_soul_injection(monkeypatch, tmp_path):
    from kabot.cli.commands import app
    from kabot.cli.skill_repo_installer import InstalledSkill
    from kabot.config.schema import Config

    runner = CliRunner()
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")
    cfg.skills = {
        "onboarding": {
            "auto_enable_after_install": True,
            "auto_prompt_env": True,
            "soul_injection_mode": "auto",
        }
    }

    saved = {}

    def _fake_save(updated, config_path=None):  # noqa: ANN001
        saved["config"] = updated
        saved["path"] = config_path

    def _fake_install(**kwargs):  # noqa: ANN003
        installed = Path(kwargs["target_dir"]) / "sample-skill"
        installed.mkdir(parents=True, exist_ok=True)
        (installed / "SKILL.md").write_text("---\nname: sample-skill\n---\n", encoding="utf-8")
        (installed / "soul-injection.md").write_text("## Sample Skill Persona\nUse sample-skill when asked.", encoding="utf-8")
        return InstalledSkill(
            repo_url=str(kwargs["repo_url"]),
            selected_dir=Path("skill"),
            installed_dir=installed,
            skill_name="sample-skill",
            skill_key="sample-skill",
        )

    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.save_config", _fake_save)
    monkeypatch.setattr("kabot.cli.skill_repo_installer.install_skill_from_git", _fake_install)
    monkeypatch.setattr("kabot.cli.commands._collect_skill_env_requirements", lambda *args, **kwargs: ["FAL_KEY"])
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: "fal_test_123")

    result = runner.invoke(app, ["skills", "install", "--git", "https://github.com/example/sample.git"])

    assert result.exit_code == 0
    saved_cfg = saved["config"]
    assert saved_cfg.skills["entries"]["sample-skill"]["enabled"] is True
    assert saved_cfg.skills["entries"]["sample-skill"]["env"]["FAL_KEY"] == "fal_test_123"
    soul_file = Path(saved_cfg.agents.defaults.workspace).expanduser() / "SOUL.md"
    assert soul_file.exists()
    assert "Sample Skill Persona" in soul_file.read_text(encoding="utf-8")
