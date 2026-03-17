from pathlib import Path


def test_readme_has_whats_new_0_6_7() -> None:
    readme_path = Path(__file__).resolve().parents[2] / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8")

    assert "What's New In v0.6.7" in readme_text
