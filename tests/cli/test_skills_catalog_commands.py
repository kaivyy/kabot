import json
from pathlib import Path

from typer.testing import CliRunner


def _write_catalog(path: Path, skills: list[dict]) -> None:
    path.write_text(json.dumps({"skills": skills}, indent=2), encoding="utf-8")


def test_skills_search_lists_catalog_matches(tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    catalog_path = tmp_path / "skills-catalog.json"
    _write_catalog(
        catalog_path,
        [
            {
                "slug": "stock-analysis",
                "name": "Stock Analysis",
                "description": "Analyze stocks and market data.",
                "install": {"path": str(tmp_path / "stock-analysis")},
                "tags": ["finance", "stocks"],
            }
        ],
    )

    result = runner.invoke(
        app,
        ["skills", "search", "stock", "--catalog-source", str(catalog_path)],
    )

    assert result.exit_code == 0
    assert "stock-analysis" in result.output
    assert "Analyze stocks and market data." in result.output


def test_skills_install_from_catalog_slug_uses_local_path_source(monkeypatch, tmp_path):
    from kabot.cli.commands import app
    from kabot.cli.skill_repo_installer import InstalledSkill
    from kabot.config.schema import Config

    runner = CliRunner()
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")
    cfg.skills = {"load": {"managed_dir": str(tmp_path / "managed-skills")}}

    catalog_path = tmp_path / "skills-catalog.json"
    local_skill_path = tmp_path / "manus-stock-analysis-1.0.0"
    _write_catalog(
        catalog_path,
        [
            {
                "slug": "stock-analysis",
                "name": "Stock Analysis",
                "description": "Analyze stocks and market data.",
                "install": {"path": str(local_skill_path)},
                "tags": ["finance", "stocks"],
            }
        ],
    )

    saved = {}
    captured = {}

    def _fake_save(updated, config_path=None):  # noqa: ANN001
        saved["config"] = updated
        saved["path"] = config_path

    def _fake_install(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        installed = Path(kwargs["target_dir"]) / "stock-analysis"
        installed.mkdir(parents=True, exist_ok=True)
        (installed / "SKILL.md").write_text("---\nname: stock-analysis\n---\n", encoding="utf-8")
        return InstalledSkill(
            repo_url=str(kwargs["source_path"]),
            selected_dir=Path("."),
            installed_dir=installed,
            skill_name="stock-analysis",
            skill_key="stock-analysis",
        )

    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.save_config", _fake_save)
    monkeypatch.setattr("kabot.cli.skill_repo_installer.install_skill_from_path", _fake_install)

    result = runner.invoke(
        app,
        [
            "skills",
            "install",
            "stock-analysis",
            "--catalog-source",
            str(catalog_path),
        ],
    )

    assert result.exit_code == 0
    assert "Installed skill" in result.output
    assert captured["source_path"] == str(local_skill_path)
    assert saved["config"].skills["entries"]["stock-analysis"]["enabled"] is True


def test_skills_install_from_catalog_slug_uses_remote_url_source(monkeypatch, tmp_path):
    from kabot.cli.commands import app
    from kabot.cli.skill_repo_installer import InstalledSkill
    from kabot.config.schema import Config

    runner = CliRunner()
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")
    cfg.skills = {"load": {"managed_dir": str(tmp_path / "managed-skills")}}

    catalog_path = tmp_path / "skills-catalog.json"
    _write_catalog(
        catalog_path,
        [
            {
                "slug": "binance-pro",
                "name": "Binance Pro",
                "description": "Crypto workflow skill from a public registry.",
                "install": {"url": "https://skills.example.invalid/binance-pro.skill"},
                "tags": ["finance", "crypto"],
            }
        ],
    )

    saved = {}
    captured = {}

    def _fake_save(updated, config_path=None):  # noqa: ANN001
        saved["config"] = updated
        saved["path"] = config_path

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
            "binance-pro",
            "--catalog-source",
            str(catalog_path),
        ],
    )

    assert result.exit_code == 0
    assert "Installed skill" in result.output
    assert captured["source_url"] == "https://skills.example.invalid/binance-pro.skill"
    assert saved["config"].skills["entries"]["binance-pro"]["enabled"] is True
