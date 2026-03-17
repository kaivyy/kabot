"""Fast local replies for narrow temporal/day-time chat prompts."""

from __future__ import annotations

from datetime import datetime, timedelta

from kabot.i18n.locale import detect_locale

_LOCALE_ALIASES = {
    "id": "id",
    "ms": "id",
    "en": "en",
    "zh": "zh",
    "ja": "ja",
    "th": "th",
}

_WEEKDAY_NAMES = {
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    "id": ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"),
    "zh": (
        "\u661f\u671f\u4e00",
        "\u661f\u671f\u4e8c",
        "\u661f\u671f\u4e09",
        "\u661f\u671f\u56db",
        "\u661f\u671f\u4e94",
        "\u661f\u671f\u516d",
        "\u661f\u671f\u65e5",
    ),
    "ja": (
        "\u6708\u66dc\u65e5",
        "\u706b\u66dc\u65e5",
        "\u6c34\u66dc\u65e5",
        "\u6728\u66dc\u65e5",
        "\u91d1\u66dc\u65e5",
        "\u571f\u66dc\u65e5",
        "\u65e5\u66dc\u65e5",
    ),
    "th": (
        "\u0e27\u0e31\u0e19\u0e08\u0e31\u0e19\u0e17\u0e23\u0e4c",
        "\u0e27\u0e31\u0e19\u0e2d\u0e31\u0e07\u0e04\u0e32\u0e23",
        "\u0e27\u0e31\u0e19\u0e1e\u0e38\u0e18",
        "\u0e27\u0e31\u0e19\u0e1e\u0e24\u0e2b\u0e31\u0e2a\u0e1a\u0e14\u0e35",
        "\u0e27\u0e31\u0e19\u0e28\u0e38\u0e01\u0e23\u0e4c",
        "\u0e27\u0e31\u0e19\u0e40\u0e2a\u0e32\u0e23\u0e4c",
        "\u0e27\u0e31\u0e19\u0e2d\u0e32\u0e17\u0e34\u0e15\u0e22\u0e4c",
    ),
}


def _resolve_locale(locale: str | None, text: str) -> str:
    raw = str(locale or detect_locale(text) or "en").strip().lower()
    base = raw.split("-", 1)[0]
    return _LOCALE_ALIASES.get(base, "en")


def _weekday_name(dt: datetime, locale: str) -> str:
    names = _WEEKDAY_NAMES.get(locale, _WEEKDAY_NAMES["en"])
    return names[dt.weekday()]


def _utc_offset_label(dt: datetime) -> str:
    offset = dt.utcoffset()
    total_minutes = int(offset.total_seconds() // 60) if offset is not None else 0
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def _timezone_label(dt: datetime) -> str:
    offset = _utc_offset_label(dt)
    name = str(dt.tzname() or "").strip()
    if name and any(ch.isalpha() for ch in name) and len(name) <= 8 and name.upper() not in {"UTC", "GMT", "LOCAL"}:
        return f"{name} ({offset})"
    return offset


def _render_weekday_reply(locale: str, relation: str, target: datetime) -> str:
    weekday = _weekday_name(target, locale)
    if locale == "zh":
        templates = {
            "today": f"\u4eca\u5929\u662f{weekday}\u3002",
            "tomorrow": f"\u660e\u5929\u662f{weekday}\u3002",
            "yesterday": f"\u6628\u5929\u662f{weekday}\u3002",
            "next_week": f"\u4ece\u73b0\u5728\u8d77\u4e00\u5468\u540e\u662f{weekday}\u3002",
        }
        return templates[relation]
    if locale == "ja":
        templates = {
            "today": f"\u4eca\u65e5\u306f{weekday}\u3067\u3059\u3002",
            "tomorrow": f"\u660e\u65e5\u306f{weekday}\u3067\u3059\u3002",
            "yesterday": f"\u6628\u65e5\u306f{weekday}\u3067\u3057\u305f\u3002",
            "next_week": f"\u4eca\u304b\u3089\u4e00\u9031\u9593\u5f8c\u306f{weekday}\u3067\u3059\u3002",
        }
        return templates[relation]
    if locale == "th":
        templates = {
            "today": f"\u0e27\u0e31\u0e19\u0e19\u0e35\u0e49\u0e04\u0e37\u0e2d{weekday}",
            "tomorrow": f"\u0e1e\u0e23\u0e38\u0e48\u0e07\u0e19\u0e35\u0e49\u0e04\u0e37\u0e2d{weekday}",
            "yesterday": f"\u0e40\u0e21\u0e37\u0e48\u0e2d\u0e27\u0e32\u0e19\u0e04\u0e37\u0e2d{weekday}",
            "next_week": f"\u0e2d\u0e35\u0e01\u0e2b\u0e19\u0e36\u0e48\u0e07\u0e2a\u0e31\u0e1b\u0e14\u0e32\u0e2b\u0e4c\u0e08\u0e32\u0e01\u0e15\u0e2d\u0e19\u0e19\u0e35\u0e49\u0e04\u0e37\u0e2d{weekday}",
        }
        return templates[relation]
    if locale == "id":
        templates = {
            "today": f"Hari ini {weekday}.",
            "tomorrow": f"Besok {weekday}.",
            "yesterday": f"Kemarin {weekday}.",
            "next_week": f"Satu minggu lagi hari {weekday}.",
        }
        return templates[relation]
    templates = {
        "today": f"Today is {weekday}.",
        "tomorrow": f"Tomorrow is {weekday}.",
        "yesterday": f"Yesterday was {weekday}.",
        "next_week": f"One week from now it will be {weekday}.",
    }
    return templates[relation]


def _render_time_reply(locale: str, current: datetime) -> str:
    clock = current.strftime("%H:%M")
    timezone_label = _timezone_label(current)
    if locale == "zh":
        return f"\u73b0\u5728\u65f6\u95f4\u662f {clock}\uff08{timezone_label}\uff09\u3002"
    if locale == "ja":
        return f"\u4eca\u306e\u6642\u523b\u306f {clock}\uff08{timezone_label}\uff09\u3067\u3059\u3002"
    if locale == "th":
        return f"\u0e15\u0e2d\u0e19\u0e19\u0e35\u0e49\u0e40\u0e27\u0e25\u0e32 {clock} ({timezone_label})"
    if locale == "id":
        return f"Sekarang pukul {clock} ({timezone_label})."
    return f"It is {clock} local time ({timezone_label})."


def _render_date_reply(locale: str, current: datetime) -> str:
    date_text = current.strftime("%Y-%m-%d")
    if locale == "zh":
        return f"\u4eca\u5929\u7684\u672c\u5730\u65e5\u671f\u662f {date_text}\u3002"
    if locale == "ja":
        return f"\u4eca\u65e5\u306e\u73fe\u5730\u65e5\u4ed8\u306f {date_text} \u3067\u3059\u3002"
    if locale == "th":
        return f"\u0e27\u0e31\u0e19\u0e17\u0e35\u0e48\u0e17\u0e49\u0e2d\u0e07\u0e16\u0e34\u0e48\u0e19\u0e15\u0e2d\u0e19\u0e19\u0e35\u0e49\u0e04\u0e37\u0e2d {date_text}"
    if locale == "id":
        return f"Tanggal lokal hari ini {date_text}."
    return f"Today's local date is {date_text}."


def _render_timezone_reply(locale: str, current: datetime) -> str:
    timezone_label = _timezone_label(current)
    if locale == "zh":
        return f"\u6211\u5f53\u524d\u4f7f\u7528\u7684\u672c\u5730\u65f6\u533a\u662f {timezone_label}\u3002"
    if locale == "ja":
        return f"\u73fe\u5728\u306e\u30ed\u30fc\u30ab\u30eb\u30bf\u30a4\u30e0\u30be\u30fc\u30f3\u306f {timezone_label} \u3067\u3059\u3002"
    if locale == "th":
        return f"\u0e40\u0e02\u0e15\u0e40\u0e27\u0e25\u0e32\u0e17\u0e49\u0e2d\u0e07\u0e16\u0e34\u0e48\u0e19\u0e15\u0e2d\u0e19\u0e19\u0e35\u0e49\u0e04\u0e37\u0e2d {timezone_label}"
    if locale == "id":
        return f"Zona waktu lokal saat ini {timezone_label}."
    return f"My current local timezone is {timezone_label}."


def _render_temporal_reply_for_intent(
    intent: str,
    *,
    locale: str,
    current: datetime,
) -> str | None:
    normalized_intent = str(intent or "").strip().lower()
    if normalized_intent == "day_next_week":
        return _render_weekday_reply(locale, "next_week", current + timedelta(days=7))
    if normalized_intent == "day_tomorrow":
        return _render_weekday_reply(locale, "tomorrow", current + timedelta(days=1))
    if normalized_intent == "day_yesterday":
        return _render_weekday_reply(locale, "yesterday", current - timedelta(days=1))
    if normalized_intent == "day_today":
        return _render_weekday_reply(locale, "today", current)
    if normalized_intent == "time_now":
        return _render_time_reply(locale, current)
    if normalized_intent == "date_today":
        return _render_date_reply(locale, current)
    if normalized_intent == "timezone":
        return _render_timezone_reply(locale, current)
    return None


def build_temporal_fast_reply(
    text: str,
    *,
    locale: str | None = None,
    now_local: datetime | None = None,
    semantic_intent: str | None = None,
) -> str | None:
    """Render a deterministic temporal reply from semantic intent only."""
    raw = str(text or "").strip()
    if not raw:
        return None

    normalized_intent = str(semantic_intent or "").strip().lower()
    if not normalized_intent or normalized_intent == "none":
        return None

    current = now_local or datetime.now().astimezone()
    resolved_locale = _resolve_locale(locale, raw)
    return _render_temporal_reply_for_intent(
        normalized_intent,
        locale=resolved_locale,
        current=current,
    )


__all__ = ["build_temporal_fast_reply"]
