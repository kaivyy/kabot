"""Cron service for scheduling agent tasks."""

import asyncio
import hashlib
import hmac
import json as _json
import uuid
from pathlib import Path
from typing import Any, Callable, Coroutine

import httpx
from loguru import logger

from kabot.cron.core import execution as core_execution
from kabot.cron.core import persistence as core_persistence
from kabot.cron.core import scheduling as core_scheduling
from kabot.cron import policies as core_policies
from kabot.cron.types import (
    CronDeliveryConfig,
    CronJob,
    CronJobState,
    CronPayload,
    CronSchedule,
    CronStore,
)

MAX_RUN_HISTORY = 20


def _now_ms() -> int:
    return core_scheduling.now_ms()


def _compute_next_run(schedule: CronSchedule, now_ms: int) -> int | None:
    return core_scheduling.compute_next_run(schedule, now_ms)


async def _deliver_webhook(
    url: str,
    job_id: str,
    job_name: str,
    output: str,
    secret: str = "",
) -> bool:
    """Send cron result to external webhook endpoint."""
    body = _json.dumps({"job_id": job_id, "job_name": job_name, "output": output})
    headers = {"Content-Type": "application/json"}
    if secret:
        signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        headers["X-Kabot-Signature"] = f"sha256={signature}"

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, content=body, headers=headers)
        return 200 <= response.status_code < 300


class CronService:
    """Service for managing and executing scheduled jobs."""
    
    def __init__(
        self,
        store_path: Path,
        on_job: Callable[[CronJob], Coroutine[Any, Any, str | None]] | None = None,
        *,
        max_jobs_per_destination: int = core_policies.DEFAULT_MAX_JOBS_PER_DESTINATION,
        dedup_enabled: bool = True,
    ):
        self.store_path = store_path
        self.on_job = on_job  # Callback to execute job, returns response text
        self.max_jobs_per_destination = max(0, int(max_jobs_per_destination))
        self.dedup_enabled = bool(dedup_enabled)
        self._store: CronStore | None = None
        self._timer_task: asyncio.Task | None = None
        self._running = False
    
    def _load_store(self) -> CronStore:
        return core_persistence.load_store(self, max_run_history=MAX_RUN_HISTORY)
    
    def _save_store(self) -> None:
        core_persistence.save_store(self, max_run_history=MAX_RUN_HISTORY)
    
    async def start(self) -> None:
        """Start the cron service."""
        self._running = True
        self._load_store()
        self._recompute_next_runs()
        self._save_store()
        self._arm_timer()
        logger.info(f"Cron service started with {len(self._store.jobs if self._store else [])} jobs")
    
    def stop(self) -> None:
        """Stop the cron service."""
        self._running = False
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None
    
    def _recompute_next_runs(self) -> None:
        core_scheduling.recompute_next_runs(self)
    
    def _get_next_wake_ms(self) -> int | None:
        return core_scheduling.get_next_wake_ms(self)
    
    def _arm_timer(self) -> None:
        core_scheduling.arm_timer(self)
    
    async def _on_timer(self) -> None:
        """Handle timer tick - run due jobs."""
        if not self._store:
            return
        
        now = _now_ms()
        logger.debug(f"Cron tick: now={now}")

        due_jobs = core_scheduling.get_due_jobs(self, now_ms_value=now)
        
        if due_jobs:
            logger.info(f"Cron: found {len(due_jobs)} due jobs")

        for job in due_jobs:
            await self._execute_job(job)
        
        self._save_store()
        self._arm_timer()
    
    async def _execute_job(self, job: CronJob) -> None:
        await core_execution.execute_job(self, job, max_run_history=MAX_RUN_HISTORY)
    
    # ========== Public API ==========
    
    def list_jobs(self, include_disabled: bool = False) -> list[CronJob]:
        """List all jobs."""
        store = self._load_store()
        jobs = store.jobs if include_disabled else [j for j in store.jobs if j.enabled]
        return sorted(jobs, key=lambda j: j.state.next_run_at_ms or float('inf'))
    
    def add_job(
        self,
        name: str,
        schedule: CronSchedule,
        message: str,
        deliver: bool = False,
        channel: str | None = None,
        to: str | None = None,
        delivery: CronDeliveryConfig | None = None,
        delete_after_run: bool = False,
        group_id: str | None = None,
        group_title: str | None = None,
    ) -> CronJob:
        """Add a new job."""
        store = self._load_store()
        now = _now_ms()

        if channel and to:
            if self.dedup_enabled and core_policies.has_duplicate_job(
                store.jobs,
                schedule=schedule,
                message=message,
                channel=channel,
                to=to,
                delete_after_run=delete_after_run,
            ):
                raise ValueError("duplicate schedule for destination")

            if self.max_jobs_per_destination > 0:
                destination_count = core_policies.count_jobs_for_destination(
                    store.jobs,
                    channel=channel,
                    to=to,
                )
                if destination_count >= self.max_jobs_per_destination:
                    raise ValueError("job limit reached for destination")

        job = CronJob(
            id=str(uuid.uuid4())[:8],
            name=name,
            enabled=True,
            schedule=schedule,
            payload=CronPayload(
                kind="agent_turn",
                message=message,
                deliver=deliver,
                channel=channel,
                to=to,
                group_id=group_id,
                group_title=group_title,
            ),
            delivery=delivery,
            state=CronJobState(next_run_at_ms=_compute_next_run(schedule, now)),
            created_at_ms=now,
            updated_at_ms=now,
            delete_after_run=delete_after_run,
        )
        
        store.jobs.append(job)
        self._save_store()
        self._arm_timer()
        
        logger.info(f"Cron: added job '{name}' ({job.id})")
        return job
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a job by ID."""
        store = self._load_store()
        before = len(store.jobs)
        store.jobs = [j for j in store.jobs if j.id != job_id]
        removed = len(store.jobs) < before
        
        if removed:
            self._save_store()
            self._arm_timer()
            logger.info(f"Cron: removed job {job_id}")
        
        return removed
    
    def enable_job(self, job_id: str, enabled: bool = True) -> CronJob | None:
        """Enable or disable a job."""
        store = self._load_store()
        for job in store.jobs:
            if job.id == job_id:
                job.enabled = enabled
                job.updated_at_ms = _now_ms()
                if enabled:
                    job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())
                else:
                    job.state.next_run_at_ms = None
                self._save_store()
                self._arm_timer()
                return job
        return None
    
    async def run_job(self, job_id: str, force: bool = False) -> bool:
        """Manually run a job."""
        store = self._load_store()
        for job in store.jobs:
            if job.id == job_id:
                if not force and not job.enabled:
                    return False
                await self._execute_job(job)
                self._save_store()
                self._arm_timer()
                return True
        return False
    
    def update_job(self, job_id: str, **kwargs) -> CronJob | None:
        """Update a job's properties."""
        store = self._load_store()
        for job in store.jobs:
            if job.id == job_id:
                if "message" in kwargs:
                    job.payload.message = kwargs["message"]
                    job.name = kwargs["message"][:30]
                if "enabled" in kwargs:
                    job.enabled = kwargs["enabled"]
                if "schedule" in kwargs:
                    job.schedule = kwargs["schedule"]
                    if job.enabled:
                        job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())
                if "deliver" in kwargs:
                    job.payload.deliver = kwargs["deliver"]
                if "delivery" in kwargs:
                    job.delivery = kwargs["delivery"]
                if "group_id" in kwargs:
                    job.payload.group_id = kwargs["group_id"]
                if "group_title" in kwargs:
                    job.payload.group_title = kwargs["group_title"]
                job.updated_at_ms = _now_ms()
                self._save_store()
                self._arm_timer()
                return job
        return None

    def get_run_history(self, job_id: str) -> list[dict]:
        """Get run history for a job."""
        store = self._load_store()
        for job in store.jobs:
            if job.id == job_id:
                if job.state.run_history:
                    return list(job.state.run_history)
                if job.state.last_run_at_ms:
                    # Backward-compatible fallback for old persisted state.
                    return [{
                        "run_at_ms": job.state.last_run_at_ms,
                        "status": job.state.last_status,
                        "error": job.state.last_error,
                    }]
                return []
        return []

    def status(self) -> dict:
        """Get service status."""
        store = self._load_store()
        return {
            "enabled": self._running,
            "jobs": len(store.jobs),
            "next_wake_at_ms": self._get_next_wake_ms(),
        }
