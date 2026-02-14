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
