"""Lightweight policy checks for CronService resource safety."""

from __future__ import annotations

from typing import Iterable

from kabot.cron.types import CronJob, CronSchedule

DEFAULT_MAX_JOBS_PER_DESTINATION = 300


def _schedule_signature(schedule: CronSchedule) -> tuple:
    return (
        schedule.kind,
        schedule.at_ms,
        schedule.every_ms,
        schedule.start_at_ms,
        schedule.expr,
        schedule.tz,
    )


def _destination_match(job: CronJob, *, channel: str, to: str) -> bool:
    return bool(job.enabled and job.payload.channel == channel and job.payload.to == to)


def count_jobs_for_destination(jobs: Iterable[CronJob], *, channel: str, to: str) -> int:
    """Count enabled jobs for a destination."""
    return sum(1 for job in jobs if _destination_match(job, channel=channel, to=to))


def has_duplicate_job(
    jobs: Iterable[CronJob],
    *,
    schedule: CronSchedule,
    message: str,
    channel: str,
    to: str,
    delete_after_run: bool,
) -> bool:
    """Detect duplicate active job payload+scheduling for same destination."""
    candidate = (
        (message or "").strip(),
        _schedule_signature(schedule),
        bool(delete_after_run),
    )
    for job in jobs:
        if not _destination_match(job, channel=channel, to=to):
            continue
        existing = (
            (job.payload.message or "").strip(),
            _schedule_signature(job.schedule),
            bool(job.delete_after_run),
        )
        if existing == candidate:
            return True
    return False

