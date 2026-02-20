"""NLP helpers for cron/reminder fallback parsing.

This module keeps parsing logic out of AgentLoop so reminder behavior is easier
to maintain and test in isolation.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Iterable

from kabot.agent.language.lexicon import (
    CRON_MANAGEMENT_OPS as LEXICON_CRON_MANAGEMENT_OPS,
    CRON_MANAGEMENT_TERMS as LEXICON_CRON_MANAGEMENT_TERMS,
    REMINDER_TERMS as LEXICON_REMINDER_TERMS,
    WEATHER_TERMS as LEXICON_WEATHER_TERMS,
)

REMINDER_KEYWORDS = (
    "remind",
    "reminder",
    "schedule",
    "alarm",
    "timer",
    "wake me",
    "ingatkan",
    "pengingat",
    "jadwalkan",
    "bangunkan",
    "set sekarang",
    "jadwal",
    "cron",
    "shift",
    # Malay
    "peringatan",
    "jadual",
    "tetapkan",
    "minit",
    # Thai
    "เตือน",
    "การเตือน",
    "ตั้งเตือน",
    "นาฬิกา",
    # Chinese
    "提醒",
    "日程",
    "闹钟",
    "定时",
)

WEATHER_KEYWORDS = (
    "weather",
    "temperature",
    "forecast",
    "cuaca",
    "suhu",
    "temperatur",
    "prakiraan",
    # Malay
    "ramalan",
    # Thai
    "อากาศ",
    "อุณหภูมิ",
    "พยากรณ์",
    # Chinese
    "天气",
    "气温",
    "温度",
    "预报",
)

CRON_MANAGEMENT_OPS = (
    "list",
    "lihat",
    "show",
    "hapus",
    "delete",
    "remove",
    "edit",
    "ubah",
    "update",
    # Malay
    "senarai",
    "padam",
    "kemas kini",
    # Thai
    "รายการ",
    "แสดง",
    "ลบ",
    "แก้ไข",
    "อัปเดต",
    # Chinese
    "列表",
    "查看",
    "显示",
    "删除",
    "移除",
    "编辑",
    "修改",
    "更新",
)
CRON_MANAGEMENT_TERMS = (
    "reminder",
    "pengingat",
    "jadwal",
    "cron",
    "shift",
    # Malay
    "peringatan",
    "jadual",
    # Thai
    "เตือน",
    "ตาราง",
    # Chinese
    "提醒",
    "日程",
    "计划",
)


# Use centralized multilingual lexicon across router/quality/fallback modules.
REMINDER_KEYWORDS = LEXICON_REMINDER_TERMS
WEATHER_KEYWORDS = LEXICON_WEATHER_TERMS
CRON_MANAGEMENT_OPS = LEXICON_CRON_MANAGEMENT_OPS
CRON_MANAGEMENT_TERMS = LEXICON_CRON_MANAGEMENT_TERMS


def required_tool_for_query(question: str, has_weather_tool: bool, has_cron_tool: bool) -> str | None:
    """Return required tool name for immediate-action prompts."""
    q_lower = (question or "").lower()
    if has_weather_tool and any(k in q_lower for k in WEATHER_KEYWORDS):
        return "weather"

    is_cron_mgmt = (
        has_cron_tool
        and any(op in q_lower for op in CRON_MANAGEMENT_OPS)
        and any(term in q_lower for term in CRON_MANAGEMENT_TERMS)
    )
    if is_cron_mgmt:
        return "cron"

    if has_cron_tool and any(k in q_lower for k in REMINDER_KEYWORDS):
        return "cron"
    return None


def extract_weather_location(question: str) -> str | None:
    """Extract probable weather location from user query."""
    def _normalize_location_candidate(value: str) -> str:
        cleaned = re.sub(
            r"(?i)\b(?:kota|city|kabupaten|regency|district|county|municipality|province|provinsi)\b$",
            "",
            value,
        ).strip(" .,!?:;")
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,!?:;")
        return cleaned

    text = (question or "").strip()
    if not text:
        return None

    match = re.search(r"(?i)\b(?:di|in)\s+([a-zA-Z][\w\s\-,'\.]{1,80})", text)
    if match:
        candidate = match.group(1).strip(" .,!?:;")
        candidate = re.sub(
            r"(?i)\b(right now|hari ini|today|saat ini|sekarang|now|right|berapa|how much)\b",
            "",
            candidate,
        ).strip(" .,!?:;")
        candidate = _normalize_location_candidate(candidate)
        if candidate:
            return " ".join(part.capitalize() for part in candidate.split())

    candidate = re.sub(
        r"(?i)\b(tolong|please|cek|check|semak|cuaca|weather|suhu|temperature|forecast|prakiraan|ramalan|hari ini|today|right now|sekarang|now|dong|ya|esok|berapa|how much|what is|what's|saat ini|right)\b|天气|气温|温度|预报|今天|现在|怎么样|如何|请|อากาศ|อุณหภูมิ|พยากรณ์|วันนี้|ตอนนี้|ช่วย|หน่อย|ครับ|ค่ะ",
        " ",
        text,
    )
    candidate = re.sub(r"\s+", " ", candidate).strip(" .,!?:;")
    candidate = _normalize_location_candidate(candidate)
    if not candidate:
        return None
    return " ".join(part.capitalize() for part in candidate.split())


def extract_reminder_message(question: str) -> str:
    """Extract reminder payload text from natural-language query."""
    text = (question or "").strip()
    if not text:
        return "Reminder"

    text = re.sub(r"(?i)^(tolong|please)\s+", "", text)
    text = re.sub(
        r"(?i)\b(remind(?: me)?(?: to)?|ingatkan(?: saya)?(?: untuk)?|buat(?:kan)? pengingat|pengingat|set(?: sekarang)?)\b",
        " ",
        text,
    )
    text = re.sub(
        r"(?i)\b(?:dalam|in)?\s*\d+\s*(menit|jam|detik|hari|min(?:ute)?s?|hours?|sec(?:ond)?s?|days?)\b(?:\s+lagi)?",
        " ",
        text,
    )
    text = re.sub(
        r"(?i)\b(?:setiap|tiap|every)\s+\d+\s*(detik|menit|jam|hari|sec(?:ond)?s?|min(?:ute)?s?|hours?|days?)\b(?:\s+sekali)?",
        " ",
        text,
    )
    text = re.sub(
        r"(?i)\b(?:setiap\s+hari|tiap\s+hari|every\s+day|daily)\b(?:\s*(?:jam|pukul|at))?\s*\d{1,2}(?::\d{2})?",
        " ",
        text,
    )
    text = re.sub(
        r"(?i)\b(?:setiap|tiap|every)\s+(?:senin|selasa|rabu|kamis|jumat|sabtu|minggu|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b(?:\s*(?:jam|pukul|at))?\s*\d{1,2}(?::\d{2})?",
        " ",
        text,
    )
    text = re.sub(r"(?i)\b(lagi|from now|sekarang|now)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .,!?:;")

    if not text:
        return "Reminder"
    if len(text) > 180:
        text = text[:180].rstrip()
    return text


def parse_time_token(token: str) -> tuple[int, int] | None:
    """Parse HH[:.]MM or HH token into (hour, minute)."""
    raw = (token or "").strip()
    if not raw:
        return None

    normalized = raw.replace(".", ":")
    if ":" in normalized:
        parts = normalized.split(":", 1)
        if len(parts) != 2:
            return None
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            return None
    else:
        try:
            hour = int(normalized)
        except ValueError:
            return None
        minute = 0

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


def extract_cycle_anchor_date(question: str) -> datetime:
    """Resolve cycle anchor date from natural-language hints."""
    now_local = datetime.now().astimezone()
    q_lower = (question or "").lower()

    explicit_iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", q_lower)
    if explicit_iso:
        try:
            date_part = datetime.strptime(explicit_iso.group(1), "%Y-%m-%d")
            return now_local.replace(
                year=date_part.year,
                month=date_part.month,
                day=date_part.day,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
        except ValueError:
            pass

    explicit_dmy = re.search(r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b", q_lower)
    if explicit_dmy:
        try:
            day = int(explicit_dmy.group(1))
            month = int(explicit_dmy.group(2))
            year = int(explicit_dmy.group(3))
            return now_local.replace(
                year=year,
                month=month,
                day=day,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
        except ValueError:
            pass

    if "lusa" in q_lower:
        return (now_local + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    if "besok" in q_lower or "tomorrow" in q_lower:
        return (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return now_local.replace(hour=0, minute=0, second=0, microsecond=0)


def extract_explicit_schedule_title(question: str) -> str | None:
    """Extract explicit schedule title from phrases like 'judul ...' or 'title ...'."""
    text = (question or "").strip()
    if not text:
        return None

    match = re.search(
        r'(?i)\b(?:judul|title|nama jadwal|schedule name)\b\s*[:=]?\s*[\"\']?([^\"\',;\n]+)',
        text,
    )
    if not match:
        return None
    title = re.sub(r"\s+", " ", match.group(1)).strip(" .,!?:;")
    return title or None


def extract_new_schedule_title(question: str) -> str | None:
    """Extract rename target from phrases like 'ubah judul jadi ...'."""
    text = (question or "").strip()
    if not text:
        return None
    match = re.search(
        r'(?i)\b(?:ubah judul|rename|rename to|judul baru|new title)\b(?:\s+grp_[a-z0-9_-]+)?\s*(?:jadi|to)\s*[\"\']?([^\"\',;\n]+)',
        text,
    )
    if not match:
        match = re.search(
            r'(?i)\b(?:ubah judul|rename|rename to|judul baru|new title)\b\s*[:=]\s*[\"\']?([^\"\',;\n]+)',
            text,
        )
    if not match:
        return None
    value = re.sub(r"\s+", " ", match.group(1)).strip(" .,!?:;")
    return value or None


def make_unique_schedule_title(base_title: str, existing_titles: Iterable[str]) -> str:
    """Ensure title uniqueness against current cron groups."""
    base = re.sub(r"\s+", " ", (base_title or "").strip())
    if not base:
        base = "Schedule"

    existing_lower = {title.casefold() for title in existing_titles if title}
    if base.casefold() not in existing_lower:
        return base

    idx = 2
    while True:
        candidate = f"{base} ({idx})"
        if candidate.casefold() not in existing_lower:
            return candidate
        idx += 1


def build_group_id(title: str, now_ms: int | None = None) -> str:
    """Build stable-ish unique group id from title + timestamp."""
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    if not slug:
        slug = "schedule"
    slug = slug[:24]
    stamp = now_ms if now_ms is not None else int(datetime.now().timestamp() * 1000)
    return f"grp_{slug}_{stamp % 1_000_000:06d}"


def extract_cycle_schedule(question: str) -> dict[str, Any] | None:
    """Extract complex repeating cycle schedules (shift/work/rest blocks)."""
    text = (question or "").strip()
    if not text:
        return None

    lowered = text.lower()
    if "selama" not in lowered:
        return None
    if not any(k in lowered for k in ("libur", "berulang", "repeat", "cycle", "siklus")):
        return None

    chunks = [
        chunk.strip(" .,!?:;")
        for chunk in re.split(
            r"(?i)\b(?:setelah itu|setelahnya|lalu|kemudian|dan besoknya|besoknya|terus)\b|[,;]",
            text,
        )
        if chunk and chunk.strip(" .,!?:;")
    ]
    if not chunks:
        return None

    segments: list[dict[str, Any]] = []
    for chunk in chunks:
        chunk_lower = chunk.lower()
        if "libur" in chunk_lower:
            off_match = re.search(r"(?i)\b(\d+)\s*hari\b", chunk)
            off_days = int(off_match.group(1)) if off_match else 1
            if off_days > 0:
                segments.append({"type": "off", "days": off_days})
            continue

        days_match = re.search(r"(?i)\b(\d+)\s*hari\b", chunk)
        if not days_match:
            continue
        days = int(days_match.group(1))
        if days <= 0:
            continue

        start_time: tuple[int, int] | None = None
        end_time: tuple[int, int] | None = None

        range_match = re.search(
            r"(?i)(\d{1,2}(?:[:.]\d{2})?)\s*(?:-|sampai|hingga|to)\s*(\d{1,2}(?:[:.]\d{2})?)",
            chunk,
        )
        if range_match:
            start_time = parse_time_token(range_match.group(1))
            end_time = parse_time_token(range_match.group(2))
        else:
            single_match = re.search(
                r"(?i)(?:jam|pukul|at)\s*(\d{1,2}(?:[:.]\d{2})?)",
                chunk,
            )
            if single_match:
                start_time = parse_time_token(single_match.group(1))
            else:
                bare_match = re.search(r"(?i)\b(\d{1,2}(?:[:.]\d{2})?)\b", chunk)
                if bare_match:
                    start_time = parse_time_token(bare_match.group(1))

        if not start_time:
            continue

        label = chunk
        label = re.sub(r"(?i)\b(\d{1,2}(?:[:.]\d{2})?)\s*(?:-|sampai|hingga|to)\s*(\d{1,2}(?:[:.]\d{2})?)\b", " ", label)
        label = re.sub(r"(?i)\b(?:jam|pukul|at)\s*\d{1,2}(?:[:.]\d{2})?\b", " ", label)
        label = re.sub(r"(?i)\b(?:selama|for)\s*\d+\s*hari\b", " ", label)
        label = re.sub(
            r"(?i)\b(?:ingatkan|ingatkan saya|jadwalkan|masuk|shift|kerja|hari ini|besok|tomorrow|lusa|berulang|repeat|terus)\b",
            " ",
            label,
        )
        label = re.sub(r"\s+", " ", label).strip(" .,!?:;")
        if not label:
            label = "Reminder"

        segments.append(
            {
                "type": "work",
                "days": days,
                "label": label,
                "start": start_time,
                "end": end_time,
            }
        )

    if not segments:
        return None

    period_days = sum(int(seg["days"]) for seg in segments)
    if period_days < 2:
        return None

    work_segments = [seg for seg in segments if seg["type"] == "work"]
    if not work_segments:
        return None

    anchor = extract_cycle_anchor_date(text)
    events: list[dict[str, str]] = []
    day_offset = 0
    for seg in segments:
        days = int(seg["days"])
        if seg["type"] == "off":
            day_offset += days
            continue

        start_h, start_m = seg["start"]
        end = seg.get("end")
        label = str(seg["label"])

        for idx in range(days):
            run_date = anchor + timedelta(days=day_offset + idx)
            start_dt = run_date.replace(hour=start_h, minute=start_m, second=0, microsecond=0)

            if end:
                end_h, end_m = end
                end_dt = run_date.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
                if end_dt <= start_dt:
                    end_dt += timedelta(days=1)
                window = f"{start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d}"
                events.append({"start_at": start_dt.isoformat(timespec="seconds"), "message": f"{label} mulai ({window})"})
                events.append({"start_at": end_dt.isoformat(timespec="seconds"), "message": f"{label} selesai ({window})"})
            else:
                events.append({"start_at": start_dt.isoformat(timespec="seconds"), "message": label})
        day_offset += days

    if not events:
        return None

    return {"period_days": period_days, "events": events}


def build_cycle_title(question: str, period_days: int, existing_titles: Iterable[str]) -> str:
    """Build human-friendly unique title for cycle schedules."""
    explicit_title = extract_explicit_schedule_title(question)
    if explicit_title:
        return make_unique_schedule_title(explicit_title, existing_titles)

    q_lower = (question or "").lower()
    if any(k in q_lower for k in ("shift", "pagi", "sore", "malam", "masuk")):
        base = f"Shift Cycle {period_days} Hari"
    else:
        base = f"Reminder Cycle {period_days} Hari"
    return make_unique_schedule_title(base, existing_titles)


def extract_recurring_schedule(question: str) -> dict[str, Any] | None:
    """Extract recurring cron schedule from natural-language query."""
    text = (question or "").strip()
    if not text:
        return None

    interval_match = re.search(
        r"(?i)\b(?:setiap|tiap|every)\s+(\d+)\s*(detik|menit|jam|hari|sec(?:ond)?s?|min(?:ute)?s?|hours?|days?)\b",
        text,
    )
    if interval_match:
        amount = int(interval_match.group(1))
        unit = interval_match.group(2).lower()
        if amount > 0:
            multiplier = 0
            if unit.startswith(("detik", "sec")):
                multiplier = 1
            elif unit.startswith(("menit", "min")):
                multiplier = 60
            elif unit.startswith(("jam", "hour")):
                multiplier = 3600
            elif unit.startswith(("hari", "day")):
                multiplier = 86400

            if multiplier > 0:
                return {"every_seconds": amount * multiplier, "one_shot": False}

    daily_match = re.search(
        r"(?i)\b(?:setiap\s+hari|tiap\s+hari|every\s+day|daily)\b(?:\s*(?:jam|pukul|at))?\s*(\d{1,2})(?::(\d{2}))?",
        text,
    )
    if daily_match:
        hour = int(daily_match.group(1))
        minute = int(daily_match.group(2) or "0")
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return {"cron_expr": f"{minute} {hour} * * *", "one_shot": False}

    weekday_map = {
        "minggu": 0,
        "sunday": 0,
        "senin": 1,
        "monday": 1,
        "selasa": 2,
        "tuesday": 2,
        "rabu": 3,
        "wednesday": 3,
        "kamis": 4,
        "thursday": 4,
        "jumat": 5,
        "friday": 5,
        "sabtu": 6,
        "saturday": 6,
    }
    weekly_match = re.search(
        r"(?i)\b(?:setiap|tiap|every)\s+(senin|selasa|rabu|kamis|jumat|sabtu|minggu|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b(?:\s*(?:jam|pukul|at))?\s*(\d{1,2})(?::(\d{2}))?",
        text,
    )
    if weekly_match:
        day = weekday_map.get(weekly_match.group(1).lower())
        hour = int(weekly_match.group(2))
        minute = int(weekly_match.group(3) or "0")
        if day is not None and 0 <= hour <= 23 and 0 <= minute <= 59:
            return {"cron_expr": f"{minute} {hour} * * {day}", "one_shot": False}

    return None
