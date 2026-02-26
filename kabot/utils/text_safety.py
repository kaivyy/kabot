"""Text safety helpers for cross-channel UTF-8 compatibility."""

from __future__ import annotations

from typing import Any


def ensure_utf8_text(value: Any) -> str:
    """
    Return a UTF-8 encodable string.

    Unpaired surrogates and other invalid sequences are replaced so downstream
    transports/storage layers never raise UnicodeEncodeError.
    """
    text = "" if value is None else str(value)
    try:
        text.encode("utf-8")
        return text
    except UnicodeEncodeError:
        return text.encode("utf-8", errors="replace").decode("utf-8")
