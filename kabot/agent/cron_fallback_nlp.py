"""NLP helpers for cron/reminder fallback parsing.

This module keeps parsing logic out of AgentLoop so reminder behavior is easier
to maintain and test in isolation.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Iterable

from kabot.agent.cron_fallback_parts.intent_scoring import (
    _INTENT_AMBIGUITY_DELTA,
    _INTENT_MIN_SCORE,
    _INTENT_STRONG_SCORE,
    _RAM_CAPACITY_MARKERS,
    _RAM_USAGE_MARKERS,
    _PERSONAL_HR_CALC_RE,
    _STOCK_TRACKING_MARKERS,
    _WEATHER_WIND_MARKERS,
    CRON_MANAGEMENT_OPS,
    CRON_MANAGEMENT_TERMS,
    CRYPTO_KEYWORDS,
    REMINDER_KEYWORDS,
    STOCK_KEYWORDS,
    WEATHER_KEYWORDS,
    ToolIntentScore,
    _contains_any,
    _looks_like_meta_skill_or_workflow_prompt,
    _normalize_query,
    looks_like_meta_skill_or_workflow_prompt,
    score_required_tool_intents,
)

__all__ = [
    "CRON_MANAGEMENT_OPS",
    "CRON_MANAGEMENT_TERMS",
    "CRYPTO_KEYWORDS",
    "REMINDER_KEYWORDS",
    "STOCK_KEYWORDS",
    "ToolIntentScore",
    "WEATHER_KEYWORDS",
    "_INTENT_AMBIGUITY_DELTA",
    "_INTENT_MIN_SCORE",
    "_INTENT_STRONG_SCORE",
    "looks_like_meta_skill_or_workflow_prompt",
    "required_tool_for_query",
    "extract_weather_location",
]

_SAVE_MEMORY_EXPLICIT_RE = re.compile(
    r"(?i)\b("
    r"save to memory|simpan di memori|simpan ke memori|simpan di memory|simpan ke memory|"
    r"save this memory|remember this|commit to memory|masukkan ke memori|masukkan ke memory|"
    r"tolong ingat|ingat ini|ingat bahwa|"
    r"call me|panggil aku|panggil saya|"
    r"kalau aku tanya siapa aku|jika aku tanya siapa aku|if i ask who am i"
    r")\b"
)


def required_tool_for_query(
    question: str,
    has_weather_tool: bool,
    has_cron_tool: bool,
    has_system_info_tool: bool = False,
    has_cleanup_tool: bool = False,
    has_speedtest_tool: bool = False,
    has_process_memory_tool: bool = False,
    has_save_memory_tool: bool = False,
    has_stock_tool: bool = False,
    has_stock_analysis_tool: bool = False,
    has_crypto_tool: bool = False,
    has_server_monitor_tool: bool = False,
    has_web_search_tool: bool = False,
    has_read_file_tool: bool = False,
    has_list_dir_tool: bool = False,
    has_check_update_tool: bool = False,
    has_system_update_tool: bool = False,
) -> str | None:
    """Return deterministic required-tool routing with intent confidence gating."""
    q_lower = _normalize_query(question)
    if _looks_like_meta_skill_or_workflow_prompt(question):
        return None
    if (
        has_save_memory_tool
        and _SAVE_MEMORY_EXPLICIT_RE.search(question)
        and not _PERSONAL_HR_CALC_RE.search(q_lower)
    ):
        return "save_memory"
    if (
        has_system_info_tool
        and _contains_any(q_lower, _RAM_CAPACITY_MARKERS)
        and not _contains_any(q_lower, _RAM_USAGE_MARKERS)
    ):
        return "get_system_info"

    ranked = score_required_tool_intents(
        question,
        has_weather_tool=has_weather_tool,
        has_cron_tool=has_cron_tool,
        has_system_info_tool=has_system_info_tool,
        has_cleanup_tool=has_cleanup_tool,
        has_speedtest_tool=has_speedtest_tool,
        has_process_memory_tool=has_process_memory_tool,
        has_stock_tool=has_stock_tool,
        has_stock_analysis_tool=has_stock_analysis_tool,
        has_crypto_tool=has_crypto_tool,
        has_server_monitor_tool=has_server_monitor_tool,
        has_web_search_tool=has_web_search_tool,
        has_read_file_tool=has_read_file_tool,
        has_list_dir_tool=has_list_dir_tool,
        has_check_update_tool=has_check_update_tool,
        has_system_update_tool=has_system_update_tool,
    )
    if not ranked:
        return None

    best = ranked[0]
    if best.score < _INTENT_MIN_SCORE:
        return None

    # Tracking/history queries should favor analysis over quote-only stock tool.
    if best.tool == "stock":
        stock_analysis_candidate = next((item for item in ranked if item.tool == "stock_analysis"), None)
        if (
            stock_analysis_candidate
            and stock_analysis_candidate.score >= 0.8
            and _contains_any(q_lower, _STOCK_TRACKING_MARKERS, fuzzy_latin=True)
        ):
            return "stock_analysis"

    if len(ranked) > 1:
        second = ranked[1]
        if (
            best.score < _INTENT_STRONG_SCORE
            and (best.score - second.score) < _INTENT_AMBIGUITY_DELTA
        ):
            return None

    return best.tool


def extract_weather_location(question: str) -> str | None:
    """Extract probable weather location from user query."""

    def _strip_weather_terms(value: str) -> str:
        cleaned = str(value or "")
        weather_terms = tuple(sorted(set((*WEATHER_KEYWORDS, *_WEATHER_WIND_MARKERS)), key=len, reverse=True))
        for term in weather_terms:
            marker = str(term or "").strip()
            if not marker:
                continue
            if re.fullmatch(r"[a-z0-9 ]+", marker):
                cleaned = re.sub(rf"(?i)\b{re.escape(marker)}\b", " ", cleaned)
            else:
                cleaned = cleaned.replace(marker, " ")
        return cleaned

    def _format_location(value: str) -> str:
        out_parts: list[str] = []
        for part in str(value or "").split():
            if re.fullmatch(r"[a-z][a-z\-']*", part):
                out_parts.append(part.capitalize())
            else:
                out_parts.append(part)
        return " ".join(out_parts).strip()

    def _strip_conversational_prefix(value: str) -> str:
        cleaned = value
        prefix_pattern = (
            r"(?i)^(?:"
            r"ya|iya|ok|oke|sip|"
            r"tolong|please|coba|cek|check|semak|"
            r"gimana|bagaimana|kenapa|kok|kalau|kalo|"
            r"bisakah|bisa|could|can|why|what(?:'s| is)|"
            r"dong|deh|nih"
            r")\b[\s,.:;-]*"
        )
        while True:
            updated = re.sub(prefix_pattern, "", cleaned).strip()
            if updated == cleaned:
                break
            cleaned = updated
        return cleaned

    def _normalize_location_candidate(value: str) -> str:
        cleaned = _strip_conversational_prefix(value)
        cleaned = re.split(
            r"(?i)[?!\n]|(?:\s+-\s+)|\b(?:kan|karena|soalnya|but|tapi|however)\b",
            cleaned,
            maxsplit=1,
        )[0]
        cleaned = re.sub(
            r"(?i)\b(?:right now|hari ini|today|saat ini|sekarang|now|right|berapa|how much|what(?:'s| is)|derajat|degree|degrees|celsius|fahrenheit)\b",
            " ",
            cleaned,
        )
        cleaned = _strip_weather_terms(cleaned)
        multilingual_fillers = (
            "天気",
            "天气",
            "อากาศ",
            "の",
            "どうですか",
            "どう",
            "今日",
            "いま",
            "今",
            "今天",
            "现在",
            "怎麼樣",
            "怎么样",
            "怎样",
            "วันนี้",
            "ตอนนี้",
            "เป็นยังไง",
            "ยังไง",
            "？",
        )
        for marker in multilingual_fillers:
            cleaned = cleaned.replace(marker, " ")
        cleaned = re.sub(
            r"(?i)\b\d+(?:[-–]\d+)?\s*(?:jam|hours?|hari|days?|minggu|weeks?)\b(?:\s+(?:ke|depan|ahead))?",
            " ",
            cleaned,
        )
        cleaned = re.sub(r"(?i)\b(?:ke depan|ahead|per jam|hourly)\b", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,!?:;")
        cleaned = re.sub(
            r"(?i)\b(?:kota|city|kabupaten|regency|district|county|municipality|province|provinsi)\b$",
            " ",
            cleaned,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,!?:;")

        edge_fillers = {
            "ya", "iya", "ok", "oke", "sip", "tolong", "please", "coba", "cek", "check",
            "semak", "gimana", "bagaimana", "kenapa", "kok", "kalau", "kalo", "bisa", "bisakah",
            "can", "could", "why", "dong", "deh", "nih", "kan", "udah", "sudah", "pasti",
            "itu", "yang", "di", "in", "apa", "ga", "gak", "ngga", "nggak", "enggak", "tidak",
            "天", "气", "風", "风",
        }
        relational_non_locations = {
            "atas",
            "bawah",
            "dalam",
            "luar",
            "sini",
            "situ",
            "sana",
        }
        forecast_non_locations = {
            "prediksi",
            "forecast",
            "prakiraan",
            "ramalan",
            "jam",
            "hour",
            "hours",
            "hari",
            "day",
            "days",
            "minggu",
            "week",
            "weeks",
            "ke",
            "depan",
            "ahead",
            "per",
            "besok",
            "tomorrow",
            "lusa",
            "nanti",
        }
        tokens = [tok for tok in cleaned.split() if tok]
        while tokens and tokens[0].lower() in edge_fillers:
            tokens.pop(0)
        while tokens and tokens[-1].lower() in edge_fillers:
            tokens.pop()
        if tokens and tokens[0].lower() in relational_non_locations:
            return ""
        if tokens and tokens[0].lower() in {"prediksi", "forecast", "prakiraan", "ramalan"}:
            return ""
        if tokens and all(
            token.lower() in forecast_non_locations
            or bool(re.fullmatch(r"\d+(?:[-–]\d+)?", token))
            for token in tokens
        ):
            return ""
        if len(tokens) > 8:
            return ""
        if len(tokens) == 1:
            attached_di = re.fullmatch(r"(?i)di([a-z][a-z\-']{2,})", tokens[0])
            if attached_di:
                tokens[0] = attached_di.group(1)
        candidate = " ".join(tokens).strip(" .,!?:;")
        if len(candidate) > 80 or re.search(r"[\(\):]", candidate):
            return ""
        if re.fullmatch(
            r"(?i)\d+(?:[.,]\d+)?\s*(?:km/?h|kph|m/?s|mph|kt|kts|knots?|°|deg(?:ree)?s?)?",
            candidate,
        ):
            return ""
        return candidate

    text = (question or "").strip()
    if not text:
        return None

    patterns = (
        r"(?i)\b(?:di|in)\s+([^\W\d_][\w\s\-,'\.]{1,120})",
        r"(?i)\b(?:cuaca|weather|suhu|temperature|forecast|prakiraan|ramalan|prediksi|derajat|degree|degrees|celsius|fahrenheit)\b(?:\s+(?:di|in))?\s+([^\W\d_][\w\s\-,'\.]{1,120})",
    )

    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        candidate = _normalize_location_candidate(match.group(1))
        if candidate:
            return _format_location(candidate)

    candidate = re.sub(
        r"(?i)\b(tolong|please|cek|check|semak|cuaca|weather|suhu|temperature|forecast|prakiraan|ramalan|prediksi|derajat|degree|degrees|celsius|fahrenheit|hari ini|today|right now|sekarang|now|dong|ya|esok|berapa|how much|what is|what's|saat ini|right|gimana|bagaimana|kenapa|kok|kalau|kalo|coba|can|could|why|bisa|bisakah)\b",
        " ",
        text,
    )
    candidate = re.sub(r"\s+", " ", candidate).strip(" .,!?:;")
    candidate = _strip_weather_terms(candidate)
    candidate = _normalize_location_candidate(candidate)
    if not candidate:
        return None
    return _format_location(candidate)


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
