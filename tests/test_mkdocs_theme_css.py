from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRA_CSS = ROOT / "site_docs" / "assets" / "stylesheets" / "extra.css"
EXTRA_JS = ROOT / "site_docs" / "assets" / "javascripts" / "extra.js"
INDEX_DOC = ROOT / "site_docs" / "index.md"


def _read_extra_css() -> str:
    return EXTRA_CSS.read_text(encoding="utf-8")


def _read_extra_js() -> str:
    return EXTRA_JS.read_text(encoding="utf-8")


def _read_index_doc() -> str:
    return INDEX_DOC.read_text(encoding="utf-8")


def test_docs_header_is_sticky() -> None:
    css = _read_extra_css()

    assert ".md-header {" in css
    assert "position: sticky;" in css
    assert "top: 0;" in css
    assert ".md-header.kabot-header-scrolled {" in css
    assert "border-bottom-color: var(--kabot-line-strong);" in css


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
    assert ".md-sidebar--primary.kabot-is-stuck .md-sidebar__scrollwrap" in css
    assert ".md-sidebar--secondary.kabot-is-stuck .md-sidebar__scrollwrap" in css


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
    assert "kabot-is-stuck" in js
    assert "kabot-header-scrolled" in js
    assert "querySelectorAll(\".md-sidebar--primary, .md-sidebar--secondary\")" in js
    assert "window.scrollY > 8" in js


def test_docs_mobile_rules_keep_header_compact() -> None:
    css = _read_extra_css()

    assert "@media screen and (max-width: 59.984375em)" in css
    assert "display: none;" in css
    assert "max-width: 100%;" in css
    assert "-webkit-overflow-scrolling: touch;" in css
    assert ".md-nav--primary .md-nav__link" in css
    assert "min-height: 2.4rem;" in css
    assert ".md-sidebar--primary {" in css
    assert "backdrop-filter: blur(18px);" in css
    assert ".md-nav--primary .md-nav__title" in css
    assert "text-transform: uppercase;" in css
    assert ".md-nav--primary .md-nav[aria-expanded=\"true\"]" in css
    assert "transition: opacity 180ms ease, transform 180ms ease;" in css


def test_homepage_hero_no_longer_shows_cyberpunk_badge() -> None:
    index = _read_index_doc()

    assert "Cyberpunk Docs" not in index
    assert '<span class="kabot-badge">' not in index


def test_font_toggle_is_more_compact() -> None:
    css = _read_extra_css()

    assert "font-size: 0.62rem;" in css
    assert "padding: 0.3rem 0.56rem;" in css
    assert "letter-spacing: 0.04em;" in css
    assert "margin-left: 0.5rem;" in css


def test_sidebar_spacing_is_more_refined() -> None:
    css = _read_extra_css()

    assert ".md-nav--primary > .md-nav__list {" in css
    assert "gap: 0.24rem;" in css
    assert "padding: 0.18rem 0.28rem 0.46rem;" in css
    assert ".md-nav--primary .md-nav__source {" in css
    assert ".md-nav--primary .md-nav__link {" in css
    assert "border-radius: 12px;" in css


def test_sidebar_brand_title_has_extra_breathing_room() -> None:
    css = _read_extra_css()

    assert ".md-nav--primary > .md-nav__title {" in css
    assert "margin-top: 0.06rem;" in css
    assert "margin-bottom: 0.16rem;" in css
    assert "padding: 0.66rem 0.72rem 0.58rem;" in css
    assert "line-height: 1.22;" in css
    assert "gap: 0.46rem;" in css


def test_sidebar_active_item_uses_elegant_highlight() -> None:
    css = _read_extra_css()

    assert ".md-nav--primary .md-nav__link--active," in css
    assert "background: linear-gradient(90deg, rgba(0, 255, 200, 0.16), rgba(0, 255, 200, 0.03));" in css
    assert "box-shadow: inset 0 0 0 1px rgba(0, 255, 200, 0.16);" in css
    assert "font-weight: 600;" in css


def test_homepage_hero_spacing_is_balanced_after_badge_removal() -> None:
    css = _read_extra_css()

    assert ".kabot-hero {" in css
    assert "padding: 1.92rem 1.88rem 1.72rem;" in css
    assert ".kabot-hero > :first-child {" in css
    assert "margin-top: 0;" in css
    assert ".kabot-hero > :last-child {" in css
    assert "margin-bottom: 0;" in css
    assert ".kabot-hero p {" in css
    assert "max-width: 54ch;" in css
    assert ".kabot-callout {" in css
    assert "margin-top: 0.78rem;" in css
