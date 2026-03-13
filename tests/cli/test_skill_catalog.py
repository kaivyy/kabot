import json
from pathlib import Path

from kabot.cli.skill_catalog import (
    load_skill_catalog,
    resolve_catalog_skill,
    search_skill_catalog,
)


def _write_catalog(path: Path, skills: list[dict]) -> None:
    path.write_text(json.dumps({"skills": skills}, indent=2), encoding="utf-8")


def test_load_skill_catalog_from_local_json(tmp_path):
    catalog_path = tmp_path / "skills-catalog.json"
    _write_catalog(
        catalog_path,
        [
            {
                "slug": "stock-analysis",
                "name": "Stock Analysis",
                "description": "Analyze market data and company profiles.",
                "install": {"path": str(tmp_path / "stock-analysis")},
                "tags": ["finance", "stocks"],
            }
        ],
    )

    entries = load_skill_catalog(str(catalog_path))

    assert len(entries) == 1
    assert entries[0]["slug"] == "stock-analysis"
    assert entries[0]["name"] == "Stock Analysis"
    assert entries[0]["install"]["path"] == str(tmp_path / "stock-analysis")


def test_search_skill_catalog_matches_slug_name_description_and_tags(tmp_path):
    catalog_path = tmp_path / "skills-catalog.json"
    _write_catalog(
        catalog_path,
        [
            {
                "slug": "stock-analysis",
                "name": "Stock Analysis",
                "description": "Analyze stocks, company profiles, and technical trends.",
                "install": {"path": str(tmp_path / "stock-analysis")},
                "tags": ["finance", "market", "technical-analysis"],
            },
            {
                "slug": "weather",
                "name": "Weather",
                "description": "Get current weather and forecast data.",
                "install": {"path": str(tmp_path / "weather")},
                "tags": ["forecast"],
            },
        ],
    )

    results = search_skill_catalog("technical market stocks", source=str(catalog_path))

    assert results
    assert results[0]["slug"] == "stock-analysis"


def test_resolve_catalog_skill_finds_slug_case_insensitively(tmp_path):
    catalog_path = tmp_path / "skills-catalog.json"
    _write_catalog(
        catalog_path,
        [
            {
                "slug": "stock-analysis",
                "name": "Stock Analysis",
                "description": "Analyze stocks.",
                "install": {"path": str(tmp_path / "stock-analysis")},
            }
        ],
    )

    resolved = resolve_catalog_skill("Stock-Analysis", source=str(catalog_path))

    assert resolved is not None
    assert resolved["slug"] == "stock-analysis"
