"""Schedule parsing and formatting helpers for cron tool operations."""

from __future__ import annotations

import re
import time
from datetime import datetime

from kabot.cron.types import CronSchedule


def generate_group_id(title: str) -> str:
    """Generate stable-ish unique group id from title + timestamp."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not slug:
        slug = "schedule"
    slug = slug[:24]
    return f"grp_{slug}_{int(time.time() * 1000) % 1_000_000:06d}"


def build_schedule(
    at_time: str = "",
    every_seconds: int | None = None,
    start_at: str | None = None,
    cron_expr: str | None = None,
    allow_empty: bool = False,
) -> tuple[CronSchedule | None, str | None]:
    """Build schedule object from user params."""
    if at_time:
        try:
            if "T" in at_time:
                dt = datetime.fromisoformat(at_time.replace("Z", "+00:00"))
            else:
                dt = datetime.strptime(at_time, "%Y-%m-%d %H:%M")
            at_ms = int(dt.timestamp() * 1000)
            return CronSchedule(kind="at", at_ms=at_ms), None
        except ValueError:
            return None, "Error: invalid at_time format. Use 'YYYY-MM-DD HH:MM' or ISO format"

    if every_seconds:
        start_at_ms: int | None = None
        if start_at:
            try:
                if "T" in start_at:
                    start_dt = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
                else:
                    start_dt = datetime.strptime(start_at, "%Y-%m-%d %H:%M")
                start_at_ms = int(start_dt.timestamp() * 1000)
            except ValueError:
                return None, "Error: invalid start_at format. Use 'YYYY-MM-DD HH:MM' or ISO format"
        return CronSchedule(kind="every", every_ms=every_seconds * 1000, start_at_ms=start_at_ms), None

    if cron_expr:
        return CronSchedule(kind="cron", expr=cron_expr), None

    if allow_empty:
        return None, None
    return None, "Error: either at_time, every_seconds, or cron_expr is required"


def format_timestamp(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d %H:%M")
