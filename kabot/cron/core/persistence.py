"""Persistence helpers for CronService store load/save."""

from __future__ import annotations

import json
import os
from typing import Any

from loguru import logger

from kabot.cron.types import CronJob, CronJobState, CronPayload, CronSchedule, CronStore
from kabot.utils.pid_lock import PIDLock


def load_store(service: Any, *, max_run_history: int) -> CronStore:
    """Load jobs from disk into service._store."""
    if service._store:
        return service._store

    if service.store_path.exists():
        try:
            data = json.loads(service.store_path.read_text())
            jobs = []
            for item in data.get("jobs", []):
                state_data = item.get("state", {})
                persisted_history = state_data.get("runs")
                run_history = persisted_history if isinstance(persisted_history, list) else []
                if not run_history and state_data.get("lastRunAtMs"):
                    run_history = [{
                        "run_at_ms": state_data.get("lastRunAtMs"),
                        "status": state_data.get("lastStatus"),
                        "error": state_data.get("lastError"),
                    }]
                run_history = run_history[-max_run_history:]

                jobs.append(CronJob(
                    id=item["id"],
                    name=item["name"],
                    enabled=item.get("enabled", True),
                    schedule=CronSchedule(
                        kind=item["schedule"]["kind"],
                        at_ms=item["schedule"].get("atMs"),
                        every_ms=item["schedule"].get("everyMs"),
                        start_at_ms=item["schedule"].get("startAtMs"),
                        expr=item["schedule"].get("expr"),
                        tz=item["schedule"].get("tz"),
                    ),
                    payload=CronPayload(
                        kind=item["payload"].get("kind", "agent_turn"),
                        message=item["payload"].get("message", ""),
                        deliver=item["payload"].get("deliver", False),
                        channel=item["payload"].get("channel"),
                        to=item["payload"].get("to"),
                        group_id=item["payload"].get("groupId"),
                        group_title=item["payload"].get("groupTitle"),
                    ),
                    state=CronJobState(
                        next_run_at_ms=state_data.get("nextRunAtMs"),
                        last_run_at_ms=state_data.get("lastRunAtMs"),
                        last_status=state_data.get("lastStatus"),
                        last_error=state_data.get("lastError"),
                        run_history=run_history,
                    ),
                    created_at_ms=item.get("createdAtMs", 0),
                    updated_at_ms=item.get("updatedAtMs", 0),
                    delete_after_run=item.get("deleteAfterRun", False),
                ))
            service._store = CronStore(jobs=jobs)
        except Exception as e:
            logger.warning(f"Failed to load cron store: {e}")
            service._store = CronStore()
    else:
        service._store = CronStore()

    return service._store


def save_store(service: Any, *, max_run_history: int) -> None:
    """Persist service._store to disk atomically."""
    if not service._store:
        return

    service.store_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "version": service._store.version,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "enabled": job.enabled,
                "schedule": {
                    "kind": job.schedule.kind,
                    "atMs": job.schedule.at_ms,
                    "everyMs": job.schedule.every_ms,
                    "startAtMs": job.schedule.start_at_ms,
                    "expr": job.schedule.expr,
                    "tz": job.schedule.tz,
                },
                "payload": {
                    "kind": job.payload.kind,
                    "message": job.payload.message,
                    "deliver": job.payload.deliver,
                    "channel": job.payload.channel,
                    "to": job.payload.to,
                    "groupId": job.payload.group_id,
                    "groupTitle": job.payload.group_title,
                },
                "state": {
                    "nextRunAtMs": job.state.next_run_at_ms,
                    "lastRunAtMs": job.state.last_run_at_ms,
                    "lastStatus": job.state.last_status,
                    "lastError": job.state.last_error,
                    "runs": (job.state.run_history or [])[-max_run_history:],
                },
                "createdAtMs": job.created_at_ms,
                "updatedAtMs": job.updated_at_ms,
                "deleteAfterRun": job.delete_after_run,
            }
            for job in service._store.jobs
        ],
    }

    payload = json.dumps(data, indent=2)
    temp_path = service.store_path.with_suffix(service.store_path.suffix + ".tmp")

    with PIDLock(service.store_path):
        temp_path.write_text(payload)
        os.replace(temp_path, service.store_path)
