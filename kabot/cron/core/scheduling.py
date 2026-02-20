"""Scheduling and timer helpers for CronService."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from kabot.cron.types import CronSchedule


def now_ms() -> int:
    return int(time.time() * 1000)


def compute_next_run(schedule: CronSchedule, now_ms_value: int) -> int | None:
    """Compute next run time in ms."""
    if schedule.kind == "at":
        return schedule.at_ms if schedule.at_ms and schedule.at_ms > now_ms_value else None

    if schedule.kind == "every":
        if not schedule.every_ms or schedule.every_ms <= 0:
            return None
        anchor = schedule.start_at_ms
        if anchor is not None:
            if now_ms_value <= anchor:
                next_run = anchor
            else:
                elapsed = now_ms_value - anchor
                steps = (elapsed + schedule.every_ms - 1) // schedule.every_ms
                next_run = anchor + (steps * schedule.every_ms)
        else:
            # Backward-compatible behavior: first run is interval from "now".
            next_run = now_ms_value + schedule.every_ms
        logger.debug(
            f"Computing every: now={now_ms_value}, interval={schedule.every_ms}, "
            f"anchor={anchor} -> next={next_run}"
        )
        return next_run

    if schedule.kind == "cron" and schedule.expr:
        try:
            from croniter import croniter

            cron = croniter(schedule.expr, time.time())
            next_time = cron.get_next()
            return int(next_time * 1000)
        except Exception:
            return None

    return None


def recompute_next_runs(service: Any) -> None:
    """Recompute next run times for all enabled jobs."""
    if not service._store:
        return
    now_value = now_ms()
    for job in service._store.jobs:
        if job.enabled:
            job.state.next_run_at_ms = compute_next_run(job.schedule, now_value)


def get_next_wake_ms(service: Any) -> int | None:
    """Get the earliest next run time across all jobs."""
    if not service._store:
        return None
    times = [j.state.next_run_at_ms for j in service._store.jobs if j.enabled and j.state.next_run_at_ms]
    logger.debug(f"Next wake candidates: {times}")
    return min(times) if times else None


def get_due_jobs(service: Any, now_ms_value: int | None = None):
    """Return currently due jobs from in-memory store."""
    if not service._store:
        return []
    now_value = now_ms_value if now_ms_value is not None else now_ms()
    return [
        j for j in service._store.jobs
        if j.enabled and j.state.next_run_at_ms and now_value >= j.state.next_run_at_ms
    ]


def arm_timer(service: Any) -> None:
    """Schedule the next timer tick."""
    if service._timer_task:
        service._timer_task.cancel()

    next_wake = get_next_wake_ms(service)
    if not next_wake or not service._running:
        return

    delay_ms = max(0, next_wake - now_ms())
    delay_s = delay_ms / 1000

    async def tick():
        await asyncio.sleep(delay_s)
        if service._running:
            await service._on_timer()

    service._timer_task = asyncio.create_task(tick())
