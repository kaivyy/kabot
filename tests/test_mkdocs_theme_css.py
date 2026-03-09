from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRA_CSS = ROOT / "site_docs" / "assets" / "stylesheets" / "extra.css"
EXTRA_JS = ROOT / "site_docs" / "assets" / "javascripts" / "extra.js"


def _read_extra_css() -> str:
    return EXTRA_CSS.read_text(encoding="utf-8")


def _read_extra_js() -> str:
    return EXTRA_JS.read_text(encoding="utf-8")


def test_docs_header_is_sticky() -> None:
    css = _read_extra_css()

    assert ".md-header {" in css
    assert "position: sticky;" in css
    assert "top: 0;" in css


def test_docs_sidebars_are_sticky_on_desktop() -> None:
    css = _read_extra_css()

    assert "@media screen and (min-width: 60em)" in css
    assert "@media screen and (min-width: 76.25em)" in css
    assert ".md-sidebar,\n.md-content {" not in css
    assert ".md-sidebar--secondary .md-sidebar__scrollwrap" in css
    assert ".md-sidebar--primary .md-sidebar__scrollwrap" in css
    assert ".md-sidebar--secondary {" in css
    assert ".md-sidebar--primary {" in css
    assert "position: sticky;" in css
    assert "max-height: calc(100vh - var(--md-header-height)" in css
    assert "overflow-y: auto;" in css
    assert "backdrop-filter: blur(16px);" in css
    assert "border-color: var(--kabot-line-strong);" in css


def test_docs_fonts_use_restrained_hacker_stack() -> None:
    css = _read_extra_css()

    assert "IBM+Plex+Mono" in css
    assert "JetBrains+Mono" in css
    assert "'IBM Plex Mono'" in css
    assert "'JetBrains Mono'" in css
    assert "'Orbitron'" not in css


def test_docs_spacing_uses_refined_scale() -> None:
    css = _read_extra_css()

    assert "line-height: 1.72;" in css
    assert "max-width: 82ch;" in css
    assert "font-size: clamp(2.2rem, 1.8rem + 1vw, 3.1rem);" in css
    assert "font-size: clamp(1.45rem, 1.2rem + 0.55vw, 2rem);" in css


def test_docs_font_toggle_script_persists_mode() -> None:
    js = _read_extra_js()

    assert "kabot-docs-font-mode" in js
    assert "clean" in js
    assert "cyber" in js
    assert "Font: Clean" in js
    assert "Font: Cyber" in js
    assert "document$.subscribe" in js


def test_docs_mobile_rules_keep_header_compact() -> None:
    css = _read_extra_css()

    assert "@media screen and (max-width: 59.984375em)" in css
    assert "display: none;" in css
    assert "max-width: 100%;" in css
