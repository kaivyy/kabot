from pathlib import Path


def test_changelog_has_0_6_8_entry():
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [0.6.8] - 2026-03-17" in changelog
