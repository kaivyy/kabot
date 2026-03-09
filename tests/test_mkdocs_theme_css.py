from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRA_CSS = ROOT / "site_docs" / "assets" / "stylesheets" / "extra.css"


def _read_extra_css() -> str:
    return EXTRA_CSS.read_text(encoding="utf-8")


def test_docs_header_is_sticky() -> None:
    css = _read_extra_css()

    assert ".md-header {" in css
    assert "position: sticky;" in css
    assert "top: 0;" in css


def test_docs_sidebars_are_sticky_on_desktop() -> None:
    css = _read_extra_css()

    assert "@media screen and (min-width: 60em)" in css
    assert "@media screen and (min-width: 76.25em)" in css
    assert ".md-sidebar--secondary .md-sidebar__scrollwrap" in css
    assert ".md-sidebar--primary .md-sidebar__scrollwrap" in css
    assert "max-height: calc(100vh - var(--md-header-height)" in css
    assert "overflow-y: auto;" in css
    assert "backdrop-filter: blur(16px);" in css
    assert "border-color: var(--kabot-line-strong);" in css
