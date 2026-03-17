from pathlib import Path


def test_mkdocs_releases_0_6_7_entry():
    releases_path = (
        Path(__file__).resolve().parents[2]
        / "site_docs"
        / "reference"
        / "releases.md"
    )
    content = releases_path.read_text(encoding="utf-8")
    assert "## v0.6.7" in content
    assert "kabot-0.6.7" in content
