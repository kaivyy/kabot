"""Time parsing utilities for cron scheduling."""

import re
import time
from datetime import datetime, timedelta, timezone

# Relative time patterns (Bahasa Indonesia + English)
_RELATIVE_PATTERNS = [
    # Indonesian
    (r"(\d+)\s*menit", lambda m: int(m.group(1)) * 60 * 1000),
    (r"(\d+)\s*jam", lambda m: int(m.group(1)) * 3600 * 1000),
    (r"(\d+)\s*detik", lambda m: int(m.group(1)) * 1000),
    (r"(\d+)\s*hari", lambda m: int(m.group(1)) * 86400 * 1000),
    # English
    (r"(?:in\s+)?(\d+)\s*min(?:ute)?s?", lambda m: int(m.group(1)) * 60 * 1000),
    (r"(?:in\s+)?(\d+)\s*hours?", lambda m: int(m.group(1)) * 3600 * 1000),
    (r"(?:in\s+)?(\d+)\s*sec(?:ond)?s?", lambda m: int(m.group(1)) * 1000),
    (r"(?:in\s+)?(\d+)\s*days?", lambda m: int(m.group(1)) * 86400 * 1000),
]

_REMINDER_INTENT_PATTERN = re.compile(
    r"\b(ingatkan(?:\s+saya)?|remind me|set reminder|set a reminder|buat pengingat|pasang pengingat)\b",
    re.IGNORECASE,
)

_REMINDER_CONNECTOR_PATTERN = re.compile(
    r"\b(lagi|dalam|ke|untuk|to|in|after)\b",
    re.IGNORECASE,
)


def parse_absolute_time_ms(value: str) -> int | None:
    """Parse an ISO-8601 or datetime string into milliseconds since epoch."""
    try:
        if "T" in value:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M")
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        return None


def parse_relative_time_ms(value: str) -> int | None:
    """Parse a relative time string (e.g. '5 menit', 'in 30 minutes') into ms offset."""
    for pattern, converter in _RELATIVE_PATTERNS:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            return converter(match)
    return None


def parse_reminder_request(text: str) -> dict[str, int | str] | None:
    """Parse reminder intent with relative time; return offset_ms/message or None."""
    if not text or not _REMINDER_INTENT_PATTERN.search(text):
        return None

    offset_ms = parse_relative_time_ms(text)
    if offset_ms is None:
        return None

    message = _REMINDER_INTENT_PATTERN.sub(" ", text)
    for pattern, _ in _RELATIVE_PATTERNS:
        message = re.sub(pattern, " ", message, flags=re.IGNORECASE)
    message = _REMINDER_CONNECTOR_PATTERN.sub(" ", message)
    message = re.sub(r"\s+", " ", message).strip()

    if not message:
        message = "Pengingat"

    return {"offset_ms": offset_ms, "message": message}
