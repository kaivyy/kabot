import pytest

from kabot.cron.service import CronService
from kabot.cron.types import CronSchedule


def test_cron_rejects_duplicate_one_shot_for_same_destination(tmp_path):
    service = CronService(tmp_path / "jobs.json", max_jobs_per_destination=10)
    schedule = CronSchedule(kind="at", at_ms=1_800_000_000_000)

    service.add_job(
        name="Drink Water",
        schedule=schedule,
        message="drink water",
        deliver=True,
        channel="telegram",
        to="12345",
        delete_after_run=True,
    )

    with pytest.raises(ValueError, match="duplicate"):
        service.add_job(
            name="Drink Water Again",
            schedule=schedule,
            message="drink water",
            deliver=True,
            channel="telegram",
            to="12345",
            delete_after_run=True,
        )


def test_cron_enforces_max_jobs_per_destination(tmp_path):
    service = CronService(tmp_path / "jobs.json", max_jobs_per_destination=1)

    service.add_job(
        name="Shift Reminder A",
        schedule=CronSchedule(kind="every", every_ms=60_000),
        message="shift-a",
        deliver=True,
        channel="telegram",
        to="worker-1",
    )

    with pytest.raises(ValueError, match="limit"):
        service.add_job(
            name="Shift Reminder B",
            schedule=CronSchedule(kind="every", every_ms=120_000),
            message="shift-b",
            deliver=True,
            channel="telegram",
            to="worker-1",
        )
