"""Locale detection helpers for multilingual user-facing messages."""

from __future__ import annotations

import re

_THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
_CJK_RE = re.compile(r"[\u4E00-\u9FFF]")

_ID_MARKERS = (
    "ingatkan",
    "jadwal",
    "pengingat",
    "hapus",
    "ubah",
    "tolong",
    "besok",
    "cuaca",
    "suhu",
    "libur",
    "jadwalkan",
    "setiap",
    "tiap",
    "menit",
)

_MS_MARKERS = (
    "jadual",
    "peringatan",
    "esok",
    "minit",
    "padam",
    "kemas kini",
    "sila",
    "syif",
    "ramalan",
)

_EN_MARKERS = (
    "remind",
    "reminder",
    "schedule",
    "weather",
    "temperature",
    "delete",
    "update",
    "tomorrow",
    "today",
)


def _score_markers(content: str, markers: tuple[str, ...]) -> int:
    return sum(1 for marker in markers if marker in content)


def detect_locale(text: str | None) -> str:
    """Detect language for user-facing responses."""
    content = (text or "").strip().lower()
    if not content:
        return "en"

    if _THAI_RE.search(content):
        return "th"
    if _CJK_RE.search(content):
        return "zh"

    id_score = _score_markers(content, _ID_MARKERS)
    ms_score = _score_markers(content, _MS_MARKERS)
    en_score = _score_markers(content, _EN_MARKERS)

    if id_score == 0 and ms_score == 0 and en_score == 0:
        return "en"

    if ms_score == id_score and ms_score > 0:
        if any(marker in content for marker in ("jadual", "peringatan", "minit", "esok", "kemas kini", "padam")):
            return "ms"
        if any(marker in content for marker in ("jadwal", "pengingat", "besok", "setiap", "tiap")):
            return "id"

    if ms_score > id_score and ms_score >= en_score:
        return "ms"
    if id_score >= ms_score and id_score >= en_score:
        return "id"
    return "en"

