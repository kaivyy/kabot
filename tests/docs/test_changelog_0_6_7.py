from pathlib import Path


def test_changelog_has_0_6_7_entry() -> None:
    changelog_path = Path(__file__).resolve().parents[2] / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert "## [0.6.7] - 2026-03-17" in changelog_text
