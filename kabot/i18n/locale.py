"""Locale detection helpers for multilingual user-facing messages."""

from __future__ import annotations

import re

_THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
_CJK_RE = re.compile(r"[\u4E00-\u9FFF]")
_JAPANESE_RE = re.compile(r"[\u3040-\u309F\u30A0-\u30FF]")
_KOREAN_RE = re.compile(r"[\uAC00-\uD7AF\u1100-\u11FF]")

_ID_MARKERS = (
    "ingatkan",
    "jadwal",
    "pengingat",
    "hapus",
    "ubah",
    "besok",
    "cuaca",
    "suhu",
    "libur",
    "jadwalkan",
    "setiap",
    "tiap",
    "menit",
    "periksa",
    "cek",
    "perbarui",
    "pasang",
    # colloquial/day-to-day Indonesian markers
    "lumayan",
    "ternyata",
    "banget",
    "gimana",
    "aku",
    "kamu",
    "saya",
    "berapa",
    "sekarang",
    "harga",
)

_MS_MARKERS = (
    "jadual",
    "peringatan",
    "tetapkan",
    "esok",
    "minit",
    "padam",
    "kemas kini",
    "sila",
    "syif",
    "ramalan",
    "semak",
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
    "check",
    "install",
    "upgrade",
)

_ES_MARKERS = (
    "recordar",
    "recordatorio",
    "horario",
    "clima",
    "temperatura",
    "eliminar",
    "actualizar",
    "mañana",
    "hoy",
    "verificar",
    "instalar",
)

_FR_MARKERS = (
    "rappeler",
    "rappel",
    "horaire",
    "météo",
    "température",
    "supprimer",
    "mettre à jour",
    "demain",
    "aujourd'hui",
    "vérifier",
    "installer",
)


def _score_markers(content: str, markers: tuple[str, ...]) -> int:
    return sum(1 for marker in markers if marker in content)


def detect_locale(text: str | None) -> str:
    """Detect language for user-facing responses."""
    content = (text or "").strip().lower()
    if not content:
        return "en"

    # Check for character-based languages first
    if _THAI_RE.search(content):
        return "th"
    if _KOREAN_RE.search(content):
        return "ko"
    if _JAPANESE_RE.search(content):
        return "ja"
    if _CJK_RE.search(content):
        return "zh"

    # Score marker-based languages
    id_score = _score_markers(content, _ID_MARKERS)
    ms_score = _score_markers(content, _MS_MARKERS)
    en_score = _score_markers(content, _EN_MARKERS)
    es_score = _score_markers(content, _ES_MARKERS)
    fr_score = _score_markers(content, _FR_MARKERS)

    if all(score == 0 for score in [id_score, ms_score, en_score, es_score, fr_score]):
        return "en"

    # Handle ID/MS ambiguity
    if ms_score == id_score and ms_score > 0:
        if any(marker in content for marker in ("jadual", "peringatan", "minit", "esok", "kemas kini", "padam")):
            return "ms"
        if any(marker in content for marker in ("jadwal", "pengingat", "besok", "setiap", "tiap")):
            return "id"

    # Return language with highest score
    scores = {
        "id": id_score,
        "ms": ms_score,
        "en": en_score,
        "es": es_score,
        "fr": fr_score,
    }
    return max(scores, key=scores.get)
