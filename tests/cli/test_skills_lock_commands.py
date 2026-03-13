from pathlib import Path
import json

from typer.testing import CliRunner


def test_skills_install_records_workspace_lock_entry(monkeypatch, tmp_path):
    from kabot.cli.commands import app
    from kabot.cli.skill_repo_installer import InstalledSkill
    from kabot.config.schema import Config

    runner = CliRunner()
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")

    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.save_config", lambda *args, **kwargs: None)

    def _fake_install(**kwargs):  # noqa: ANN003
        installed = Path(kwargs["target_dir"]) / "binance-pro"
        installed.mkdir(parents=True, exist_ok=True)
        (installed / "SKILL.md").write_text("---\nname: binance-pro\n---\n", encoding="utf-8")
        return InstalledSkill(
            repo_url=str(kwargs["source_path"]),
            selected_dir=Path("."),
            installed_dir=installed,
            skill_name="binance-pro",
            skill_key="binance-pro",
        )

    monkeypatch.setattr("kabot.cli.skill_repo_installer.install_skill_from_path", _fake_install)

    source_path = tmp_path / "binance-pro-1.0.0"
    source_path.mkdir(parents=True, exist_ok=True)

    result = runner.invoke(
        app,
        [
            "skills",
            "install",
            "--path",
            str(source_path),
            "--target",
            "workspace",
        ],
    )

    assert result.exit_code == 0
    lock_path = cfg.workspace_path / ".kabot" / "skills-lock.json"
    assert lock_path.exists()
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    entry = payload["skills"]["binance-pro"]
    assert entry["skill_name"] == "binance-pro"
    assert entry["source_type"] == "path"
    assert entry["source_path"] == str(source_path)


def test_skills_list_reads_workspace_lock_entries(monkeypatch, tmp_path):
    from kabot.cli.commands import app
    from kabot.config.schema import Config

    runner = CliRunner()
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")
    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)

    lock_dir = cfg.workspace_path / ".kabot"
    lock_dir.mkdir(parents=True, exist_ok=True)
    (lock_dir / "skills-lock.json").write_text(
        (
            '{\n'
            '  "version": 1,\n'
            '  "skills": {\n'
            '    "binance-pro": {\n'
            '      "skill_name": "binance-pro",\n'
            '      "skill_key": "binance-pro",\n'
            '      "target": "workspace",\n'
            '      "source_type": "path",\n'
            '      "source_path": "C:/skills/binance-pro-1.0.0",\n'
            '      "installed_dir": "C:/workspace/skills/binance-pro"\n'
            '    }\n'
            '  }\n'
            '}\n'
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["skills", "list", "--target", "workspace"])

    assert result.exit_code == 0
    assert "binance-pro" in result.output
    assert "path" in result.output


def test_skills_update_reinstalls_from_workspace_lock(monkeypatch, tmp_path):
    from kabot.cli.commands import app
    from kabot.cli.skill_repo_installer import InstalledSkill
    from kabot.config.schema import Config

    runner = CliRunner()
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")
    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.save_config", lambda *args, **kwargs: None)

    lock_dir = cfg.workspace_path / ".kabot"
    lock_dir.mkdir(parents=True, exist_ok=True)
    source_path = tmp_path / "binance-pro-1.0.0"
    source_path.mkdir(parents=True, exist_ok=True)
    (lock_dir / "skills-lock.json").write_text(
        json.dumps(
            {
                "version": 1,
                "skills": {
                    "binance-pro": {
                        "skill_name": "binance-pro",
                        "skill_key": "binance-pro",
                        "target": "workspace",
                        "source_type": "path",
                        "source_path": str(source_path),
                        "installed_dir": "C:/workspace/skills/binance-pro",
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    captured = {}

    def _fake_install(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        installed = Path(kwargs["target_dir"]) / "binance-pro"
        installed.mkdir(parents=True, exist_ok=True)
        (installed / "SKILL.md").write_text("---\nname: binance-pro\n---\n", encoding="utf-8")
        return InstalledSkill(
            repo_url=str(kwargs["source_path"]),
            selected_dir=Path("."),
            installed_dir=installed,
            skill_name="binance-pro",
            skill_key="binance-pro",
        )

    monkeypatch.setattr("kabot.cli.skill_repo_installer.install_skill_from_path", _fake_install)

    result = runner.invoke(app, ["skills", "update", "binance-pro", "--target", "workspace"])

    assert result.exit_code == 0
    assert captured["source_path"] == str(source_path)
    assert captured["target_dir"] == cfg.workspace_path / "skills"
    assert "Updated skill" in result.output
