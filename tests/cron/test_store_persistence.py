"""Tests for cron store persistence guarantees."""

import json
import shutil
import uuid
from pathlib import Path

from kabot.cron.service import CronService
from kabot.cron.types import CronSchedule


def _make_temp_dir() -> Path:
    root = Path.cwd() / ".tmp-test-cron-store"
    root.mkdir(parents=True, exist_ok=True)
    case_dir = root / f"case-{uuid.uuid4().hex[:8]}"
    case_dir.mkdir(parents=True, exist_ok=True)
    return case_dir


def test_save_store_avoids_direct_write_to_target_file(monkeypatch):
    """Saving should avoid direct writes to the target file to prevent corruption."""
    case_dir = _make_temp_dir()
    store_path = case_dir / "jobs.json"
    service = CronService(store_path)
    service.add_job(
        name="test",
        schedule=CronSchedule(kind="every", every_ms=60_000),
        message="hello",
    )

    original_write_text = Path.write_text

    def flaky_write_text(self, data, *args, **kwargs):
        if self == store_path:
            # Simulate truncate+crash behavior of non-atomic direct writes.
            original_write_text(self, "{", *args, **kwargs)
            raise OSError("simulated target write failure")
        return original_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", flaky_write_text)

    # Atomic implementations should not write directly to store_path.
    try:
        service._save_store()
        parsed = json.loads(store_path.read_text())
        assert "jobs" in parsed
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)
