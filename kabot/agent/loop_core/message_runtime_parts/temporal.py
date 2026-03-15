"""Fast local replies for narrow temporal/day-time chat prompts."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

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
    "zh": ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"),
    "ja": ("月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"),
    "th": ("วันจันทร์", "วันอังคาร", "วันพุธ", "วันพฤหัสบดี", "วันศุกร์", "วันเสาร์", "วันอาทิตย์"),
}

_DAY_QUERY_RE = re.compile(
    r"(?i)\b(what day|day is it)\b|"
    r"星期几|星期幾|周几|周幾|何曜日|ตอนนี้วันอะไร|วันนี้วันอะไร"
)
_TOMORROW_DAY_RE = re.compile(
    r"(?i)\b(tomorrow.*day|what day.*tomorrow)\b|明天星期|明日.*曜日|พรุ่งนี้.*วัน"
)
_YESTERDAY_DAY_RE = re.compile(
    r"(?i)\b(yesterday.*day|what day.*yesterday)\b|昨天星期|昨日.*曜日|เมื่อวาน.*วัน"
)
_NEXT_WEEK_DAY_RE = re.compile(
    r"(?i)\b(what day.*next week|next week.*day)\b|"
    r"一周后|一週後|一週間|สัปดาห์หน้า.*วัน"
)
_TIME_QUERY_RE = re.compile(
    r"(?i)\b(what time)\b|现在几点|現在幾點|何時|กี่โมง"
)
_DATE_QUERY_RE = re.compile(
    r"(?i)\b(what date|date today)\b|今天几号|今天幾號|何日|วันที่เท่าไร"
)
_TIMEZONE_QUERY_RE = re.compile(
    r"(?i)\b(timezone|time zone|utc\s*[+-]?\s*\d{1,2}(?::?\d{2})?)\b|"
    r"时区|時區|タイムゾーン|เขตเวลา|โซนเวลา"
)


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


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
            "today": f"今天是{weekday}。",
            "tomorrow": f"明天是{weekday}。",
            "yesterday": f"昨天是{weekday}。",
            "next_week": f"从现在起一周后是{weekday}。",
        }
        return templates[relation]
    if locale == "ja":
        templates = {
            "today": f"今日は{weekday}です。",
            "tomorrow": f"明日は{weekday}です。",
            "yesterday": f"昨日は{weekday}でした。",
            "next_week": f"今から一週間後は{weekday}です。",
        }
        return templates[relation]
    if locale == "th":
        templates = {
            "today": f"วันนี้คือ{weekday}",
            "tomorrow": f"พรุ่งนี้คือ{weekday}",
            "yesterday": f"เมื่อวานคือ{weekday}",
            "next_week": f"อีกหนึ่งสัปดาห์จากตอนนี้คือ{weekday}",
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
        return f"现在时间是 {clock}（{timezone_label}）。"
    if locale == "ja":
        return f"今の時刻は {clock}（{timezone_label}）です。"
    if locale == "th":
        return f"ตอนนี้เวลา {clock} ({timezone_label})"
    return f"It is {clock} local time ({timezone_label})."


def _render_date_reply(locale: str, current: datetime) -> str:
    date_text = current.strftime("%Y-%m-%d")
    if locale == "zh":
        return f"今天的本地日期是 {date_text}。"
    if locale == "ja":
        return f"今日の現地日付は {date_text} です。"
    if locale == "th":
        return f"วันที่ท้องถิ่นตอนนี้คือ {date_text}"
    return f"Today's local date is {date_text}."


def _render_timezone_reply(locale: str, current: datetime) -> str:
    timezone_label = _timezone_label(current)
    if locale == "zh":
        return f"我当前使用的本地时区是 {timezone_label}。"
    if locale == "ja":
        return f"現在のローカルタイムゾーンは {timezone_label} です。"
    if locale == "th":
        return f"เขตเวลาท้องถิ่นตอนนี้คือ {timezone_label}"
    return f"My current local timezone is {timezone_label}."


def build_temporal_fast_reply(
    text: str,
    *,
    locale: str | None = None,
    now_local: datetime | None = None,
) -> str | None:
    """Return a local deterministic reply for narrow temporal questions."""
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return None

    current = now_local or datetime.now().astimezone()
    resolved_locale = _resolve_locale(locale, raw)

    if _NEXT_WEEK_DAY_RE.search(raw):
        return _render_weekday_reply(resolved_locale, "next_week", current + timedelta(days=7))
    if _TOMORROW_DAY_RE.search(raw):
        return _render_weekday_reply(resolved_locale, "tomorrow", current + timedelta(days=1))
    if _YESTERDAY_DAY_RE.search(raw):
        return _render_weekday_reply(resolved_locale, "yesterday", current - timedelta(days=1))
    if _DAY_QUERY_RE.search(raw):
        return _render_weekday_reply(resolved_locale, "today", current)
    if _TIME_QUERY_RE.search(raw):
        return _render_time_reply(resolved_locale, current)
    if _DATE_QUERY_RE.search(raw):
        return _render_date_reply(resolved_locale, current)
    if _TIMEZONE_QUERY_RE.search(raw) and ("?" in raw or "？" in raw or "what" in normalized):
        return _render_timezone_reply(resolved_locale, current)
    return None
from kabot.i18n.locale import detect_locale
