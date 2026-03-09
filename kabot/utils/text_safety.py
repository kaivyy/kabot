"""Text safety helpers for cross-channel UTF-8 compatibility."""

from __future__ import annotations

from typing import Any

_MOJIBAKE_MARKERS = (
    "Ãƒ",
    "Ã‚",
    "Ã¢â‚¬",
    "Ã Â¸",
    "Ã£â€š",
    "Ã¬â€ž",
    "ðŸ",
    "âœ",
    "â€”",
    "è¯·",
    "æŠ€",
    "å¤„",
    "ãƒ",
    "à¸",
)


def _mojibake_score(text: str) -> int:
    value = str(text or "")
    marker_hits = sum(value.count(marker) for marker in _MOJIBAKE_MARKERS)
    suspicious_chars = sum(
        1
        for ch in value
        if ("\u0080" <= ch <= "\u009f") or ("\u00c0" <= ch <= "\u00ff")
    )
    return (marker_hits * 4) + suspicious_chars


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


def repair_common_mojibake_text(value: Any) -> str:
    """
    Best-effort repair for CLI text already garbled by shell/codepage decoding.

    This intentionally stays conservative: clean Unicode is returned unchanged,
    and we only accept a repair candidate when it clearly lowers the mojibake
    marker score.
    """
    text = ensure_utf8_text(value)
    base_score = _mojibake_score(text)
    if base_score < 4:
        return text

    best = text
    best_score = base_score
    for source_encoding in ("latin1", "cp1252"):
        try:
            candidate = text.encode(source_encoding).decode("utf-8")
        except Exception:
            continue
        candidate = ensure_utf8_text(candidate)
        candidate_score = _mojibake_score(candidate)
        if candidate_score < best_score:
            best = candidate
            best_score = candidate_score

    return best
