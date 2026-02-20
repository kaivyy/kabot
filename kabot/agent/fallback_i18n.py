"""Backward-compatible i18n facade for fallback logic."""

from __future__ import annotations

from typing import Any

from kabot.i18n.catalog import tr as _tr
from kabot.i18n.locale import detect_locale


def detect_language(text: str | None) -> str:
    """Backward-compatible alias used by existing modules/tests."""
    return detect_locale(text)


def t(key: str, text: str | None = None, **kwargs: Any) -> str:
    """Backward-compatible translation entrypoint."""
    return _tr(key, text=text, **kwargs)

