from unittest.mock import AsyncMock

import pytest

from kabot.cron.service import CronService
from kabot.cron.types import CronJob, CronPayload, CronSchedule, CronStore


def test_compute_next_run_wrapper_delegates_to_core(monkeypatch):
    from kabot.cron import service as cron_service_module

    called = {"schedule": None, "now_ms": None}

    def _fake_compute(schedule, now_ms):
        called["schedule"] = schedule
        called["now_ms"] = now_ms
        return 777

    monkeypatch.setattr("kabot.cron.core.scheduling.compute_next_run", _fake_compute)
    schedule = CronSchedule(kind="at", at_ms=123456789)
    result = cron_service_module._compute_next_run(schedule, 42)
    assert result == 777
    assert called["schedule"] is schedule
    assert called["now_ms"] == 42


def test_load_store_wrapper_delegates_to_core(monkeypatch, tmp_path):
    service = CronService(tmp_path / "jobs.json")
    expected = CronStore()

    def _fake_load(svc, *, max_run_history):
        assert svc is service
        assert max_run_history > 0
        return expected

    monkeypatch.setattr("kabot.cron.core.persistence.load_store", _fake_load)
    assert service._load_store() is expected


def test_save_store_wrapper_delegates_to_core(monkeypatch, tmp_path):
    service = CronService(tmp_path / "jobs.json")
    called = {"value": False}

    def _fake_save(svc, *, max_run_history):
        assert svc is service
        assert max_run_history > 0
        called["value"] = True

    monkeypatch.setattr("kabot.cron.core.persistence.save_store", _fake_save)
    service._save_store()
    assert called["value"] is True


@pytest.mark.asyncio
async def test_execute_job_wrapper_delegates_to_core(monkeypatch, tmp_path):
    service = CronService(tmp_path / "jobs.json")
    job = CronJob(
        id="abc12345",
        name="test",
        schedule=CronSchedule(kind="at", at_ms=1),
        payload=CronPayload(message="hello"),
    )
    service._store = CronStore(jobs=[job])

    called = {"job": None, "max_run_history": None}

    async def _fake_execute(svc, cron_job, *, max_run_history):
        assert svc is service
        called["job"] = cron_job
        called["max_run_history"] = max_run_history

    monkeypatch.setattr("kabot.cron.core.execution.execute_job", _fake_execute)
    await service._execute_job(job)
    assert called["job"] is job
    assert called["max_run_history"] > 0
