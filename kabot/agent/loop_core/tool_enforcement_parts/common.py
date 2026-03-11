"""Shared text-shape helpers for tool enforcement."""

from __future__ import annotations

import re


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _is_low_information_followup(value: str, *, max_tokens: int = 6, max_chars: int = 64) -> bool:
    """
    Detect short confirmation/follow-up turns without language-specific keywords.

    This keeps behavior multilingual and avoids parsing stale assistant metadata
    as fresh user intent.
    """
    normalized = _normalize_text(value)
    if not normalized:
        return False
    if len(normalized) > max_chars:
        return False
    tokens = [part for part in normalized.split(" ") if part]
    if len(tokens) == 0 or len(tokens) > max_tokens:
        return False
    if any(mark in value for mark in ("?", "？", "¿", "؟")):
        return False
    if re.search(r"(https?://|www\.)", normalized):
        return False
    if re.search(r"[@#]\w+", normalized):
        return False
    if re.search(r"\d{4,}", normalized):
        return False
    return True


def _looks_like_verbose_non_query_text(value: str) -> bool:
    """
    Detect assistant-style/stale metadata blobs that are unlikely to be direct user queries.

    This intentionally uses structural signals (length + sentence/list formatting)
    to stay language-agnostic.
    """
    raw = str(value or "").strip()
    if not raw:
        return False
    normalized = _normalize_text(raw)
    if len(normalized) < 80:
        return False
    tokens = [part for part in normalized.split(" ") if part]
    if len(tokens) < 14:
        return False
    sentence_like = raw.count(".") + raw.count("!") + raw.count("?") >= 2
    structured = any(marker in raw for marker in ("\n", "•", "|"))
    return sentence_like or structured
