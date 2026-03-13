import json
from pathlib import Path

from typer.testing import CliRunner


def _write_skill(
    skill_dir: Path,
    *,
    name: str = "sample-skill",
    description: str = "A sample external skill.",
    homepage: str = "https://example.com/sample-skill",
) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                f'description: "{description}"',
                f"homepage: {homepage}",
                "---",
                "",
                "# Sample Skill",
                "",
                "Do the sample thing.",
            ]
        ),
        encoding="utf-8",
    )
    (skill_dir / "references").mkdir(exist_ok=True)
    (skill_dir / "references" / "notes.md").write_text("reference", encoding="utf-8")


def test_skills_pack_creates_bundle(tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    skill_dir = tmp_path / "sample-skill"
    bundle_dir = tmp_path / "dist"
    _write_skill(skill_dir)

    result = runner.invoke(
        app,
        ["skills", "pack", str(skill_dir), "--output-dir", str(bundle_dir)],
    )

    assert result.exit_code == 0
    assert (bundle_dir / "sample-skill.skill").exists()
    assert "Created skill bundle" in result.output


def test_skills_publish_creates_catalog_entry_and_bundle(tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    skill_dir = tmp_path / "sample-skill"
    catalog_path = tmp_path / "catalog.json"
    bundle_dir = tmp_path / "bundles"
    _write_skill(skill_dir)

    result = runner.invoke(
        app,
        [
            "skills",
            "publish",
            str(skill_dir),
            "--catalog-source",
            str(catalog_path),
            "--bundle-dir",
            str(bundle_dir),
            "--version",
            "1.0.0",
            "--tags",
            "latest,finance",
        ],
    )

    assert result.exit_code == 0
    bundle_path = bundle_dir / "sample-skill-1.0.0.skill"
    assert bundle_path.exists()
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert payload["skills"][0]["slug"] == "sample-skill"
    assert payload["skills"][0]["install"]["path"] == str(bundle_path)
    assert payload["skills"][0]["version"] == "1.0.0"
    assert payload["skills"][0]["tags"] == ["latest", "finance"]


def test_skills_publish_can_emit_url_install_spec(tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    skill_dir = tmp_path / "sample-skill"
    catalog_path = tmp_path / "catalog.json"
    bundle_dir = tmp_path / "bundles"
    _write_skill(skill_dir)

    result = runner.invoke(
        app,
        [
            "skills",
            "publish",
            str(skill_dir),
            "--catalog-source",
            str(catalog_path),
            "--bundle-dir",
            str(bundle_dir),
            "--version",
            "1.0.0",
            "--bundle-url-base",
            "https://skills.example.invalid/public",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert (
        payload["skills"][0]["install"]["url"]
        == "https://skills.example.invalid/public/sample-skill-1.0.0.skill"
    )


def test_skills_sync_scans_roots_and_publishes_skills(tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    root = tmp_path / "workspace"
    catalog_path = tmp_path / "catalog.json"
    bundle_dir = tmp_path / "bundles"
    _write_skill(root / "skills" / "alpha-skill", name="alpha-skill", description="Alpha skill.")
    _write_skill(root / "skills" / "beta-skill", name="beta-skill", description="Beta skill.")

    result = runner.invoke(
        app,
        [
            "skills",
            "sync",
            "--catalog-source",
            str(catalog_path),
            "--bundle-dir",
            str(bundle_dir),
            "--root",
            str(root),
            "--all",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    slugs = {entry["slug"] for entry in payload["skills"]}
    assert slugs == {"alpha-skill", "beta-skill"}
    assert (bundle_dir / "alpha-skill-1.0.0.skill").exists()
    assert (bundle_dir / "beta-skill-1.0.0.skill").exists()


def test_skills_sync_skips_invalid_skills_and_keeps_valid_ones(tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    root = tmp_path / "workspace"
    catalog_path = tmp_path / "catalog.json"
    bundle_dir = tmp_path / "bundles"
    _write_skill(root / "skills" / "alpha-skill", name="alpha-skill", description="Alpha skill.")
    broken_dir = root / "skills" / "broken-skill"
    broken_dir.mkdir(parents=True, exist_ok=True)
    (broken_dir / "SKILL.md").write_text("# Broken Skill\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "skills",
            "sync",
            "--catalog-source",
            str(catalog_path),
            "--bundle-dir",
            str(bundle_dir),
            "--root",
            str(root),
            "--all",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    slugs = {entry["slug"] for entry in payload["skills"]}
    assert slugs == {"alpha-skill"}
    assert "Skipping invalid skill" in result.output
