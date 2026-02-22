"""Tests for cron run history behavior."""

import pytest

from kabot.cron.service import MAX_RUN_HISTORY, CronService
from kabot.cron.types import CronSchedule


@pytest.mark.asyncio
async def test_run_history_records_multiple_runs(tmp_path):
    store_path = tmp_path / "jobs.json"

    async def on_job(job):
        return f"ok:{job.id}"

    service = CronService(store_path, on_job=on_job)
    job = service.add_job(
        name="history-test",
        schedule=CronSchedule(kind="every", every_ms=60_000),
        message="ping",
    )

    await service.run_job(job.id, force=True)
    await service.run_job(job.id, force=True)
    await service.run_job(job.id, force=True)

    history = service.get_run_history(job.id)
    assert len(history) == 3
    assert all(run["status"] == "ok" for run in history)
    assert all("duration_ms" in run for run in history)


@pytest.mark.asyncio
async def test_run_history_tracks_error_and_success(tmp_path):
    store_path = tmp_path / "jobs.json"
    attempts = {"count": 0}

    async def on_job(_job):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("boom")
        return "ok"

    service = CronService(store_path, on_job=on_job)
    job = service.add_job(
        name="error-history",
        schedule=CronSchedule(kind="every", every_ms=60_000),
        message="ping",
    )

    await service.run_job(job.id, force=True)
    await service.run_job(job.id, force=True)

    history = service.get_run_history(job.id)
    assert len(history) == 2
    assert history[0]["status"] == "error"
    assert "boom" in (history[0].get("error") or "")
    assert history[1]["status"] == "ok"


@pytest.mark.asyncio
async def test_run_history_is_bounded_and_persisted(tmp_path):
    store_path = tmp_path / "jobs.json"

    async def on_job(_job):
        return "ok"

    service = CronService(store_path, on_job=on_job)
    job = service.add_job(
        name="bounded-history",
        schedule=CronSchedule(kind="every", every_ms=60_000),
        message="ping",
    )

    for _ in range(MAX_RUN_HISTORY + 7):
        await service.run_job(job.id, force=True)

    history = service.get_run_history(job.id)
    assert len(history) == MAX_RUN_HISTORY

    reloaded = CronService(store_path)
    persisted_history = reloaded.get_run_history(job.id)
    assert len(persisted_history) == MAX_RUN_HISTORY
    assert all(run["status"] == "ok" for run in persisted_history)
