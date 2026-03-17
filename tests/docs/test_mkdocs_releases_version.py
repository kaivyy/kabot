from pathlib import Path


def test_mkdocs_releases_0_6_8_entry():
    releases = Path("site_docs/reference/releases.md").read_text(encoding="utf-8")
    assert "## v0.6.8" in releases
    assert "kabot-0.6.8" in releases
