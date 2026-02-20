"""Execution helpers for CronService jobs."""

from __future__ import annotations

from typing import Any

from loguru import logger

from kabot.cron.core.scheduling import compute_next_run, now_ms
from kabot.cron.types import CronJob


async def execute_job(service: Any, job: CronJob, *, max_run_history: int) -> None:
    """Execute a single job and update job state/history."""
    start_ms = now_ms()
    logger.info(f"Cron: executing job '{job.name}' ({job.id})")

    try:
        if service.on_job:
            await service.on_job(job)

        job.state.last_status = "ok"
        job.state.last_error = None
        logger.info(f"Cron: job '{job.name}' completed")

    except Exception as e:
        job.state.last_status = "error"
        job.state.last_error = str(e)
        logger.error(f"Cron: job '{job.name}' failed: {e}")

    end_ms = now_ms()
    job.state.last_run_at_ms = start_ms
    job.updated_at_ms = now_ms()
    run_entry = {
        "run_at_ms": start_ms,
        "status": job.state.last_status,
        "error": job.state.last_error,
        "duration_ms": max(0, end_ms - start_ms),
    }
    history = list(job.state.run_history or [])
    history.append(run_entry)
    job.state.run_history = history[-max_run_history:]

    if job.delete_after_run or job.schedule.kind == "at":
        if job.delete_after_run:
            logger.info(f"Cron: deleting job '{job.name}' after successful run")
            if service._store:
                service._store.jobs = [j for j in service._store.jobs if j.id != job.id]
        else:
            logger.info(f"Cron: disabling one-shot job '{job.name}'")
            job.enabled = False
            job.state.next_run_at_ms = None
    else:
        job.state.next_run_at_ms = compute_next_run(job.schedule, now_ms())
