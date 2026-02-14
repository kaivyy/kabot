"""Cron tool for scheduling reminders and tasks."""

from typing import Any

from kabot.agent.tools.base import Tool
from kabot.cron.service import CronService
from kabot.cron.types import CronSchedule


class CronTool(Tool):
    """Tool to schedule reminders and recurring tasks."""
    
    def __init__(self, cron_service: CronService):
        self._cron = cron_service
        self._channel = ""
        self._chat_id = ""
    
    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the current session context for delivery."""
        self._channel = channel
        self._chat_id = chat_id
    
    @property
    def name(self) -> str:
        return "cron"
    
    @property
    def description(self) -> str:
        return "Schedule reminders and recurring tasks. Actions: add, list, remove."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "remove", "update", "run", "runs", "status"],
                    "description": "Action to perform"
                },
                "message": {
                    "type": "string",
                    "description": "Reminder message (for add)"
                },
                "at_time": {
                    "type": "string",
                    "description": "Specific time (ISO format or 'YYYY-MM-DD HH:MM')"
                },
                "every_seconds": {
                    "type": "integer",
                    "description": "Interval in seconds (for recurring tasks)"
                },
                "cron_expr": {
                    "type": "string",
                    "description": "Cron expression like '0 9 * * *' (for scheduled tasks)"
                },
                "job_id": {
                    "type": "string",
                    "description": "Job ID (for remove)"
                },
                "one_shot": {
                    "type": "boolean",
                    "description": "If true, the job will be deleted after running once (default: false for recurring, true for at_time)"
                }
            },
            "required": ["action"]
        }
    
    async def execute(
            self,
            action: str,
            message: str = "",
            at_time: str = "",
            every_seconds: int | None = None,
            cron_expr: str | None = None,
            job_id: str | None = None,
            one_shot: bool | None = None,
            **kwargs: Any
    ) -> str:
        match action:
            case "add":
                return self._add_job(message, at_time, every_seconds, cron_expr, one_shot)
            case "list":
                return self._list_jobs()
            case "remove":
                return self._remove_job(job_id)
            case "update":
                return self._update_job(job_id, **kwargs)
            case "run":
                return await self._run_job(job_id)
            case "runs":
                return self._get_runs(job_id)
            case "status":
                return self._get_status()
            case _:
                return f"Unknown action: {action}"
    
    def _add_job(self, message: str, at_time: str, every_seconds: int | None, cron_expr: str | None, one_shot: bool | None = None) -> str:
        if not message:
            return "Error: message is required for add"
        if not self._channel or not self._chat_id:
            return "Error: no session context (channel/chat_id)"

        # Default one_shot behavior
        delete_after_run = one_shot if one_shot is not None else (True if at_time else False)

        # Build schedule
        if at_time:
            # Parse at_time (expected format: "YYYY-MM-DD HH:MM" or ISO)
            from datetime import datetime
            try:
                if "T" in at_time:
                    dt = datetime.fromisoformat(at_time.replace("Z", "+00:00"))
                else:
                    dt = datetime.strptime(at_time, "%Y-%m-%d %H:%M")
                at_ms = int(dt.timestamp() * 1000)
                schedule = CronSchedule(kind="at", at_ms=at_ms)
            except ValueError:
                return f"Error: invalid at_time format. Use 'YYYY-MM-DD HH:MM' or ISO format"
        elif every_seconds:
            schedule = CronSchedule(kind="every", every_ms=every_seconds * 1000)
        elif cron_expr:
            schedule = CronSchedule(kind="cron", expr=cron_expr)
        else:
            return "Error: either at_time, every_seconds, or cron_expr is required"
        
        job = self._cron.add_job(
            name=message[:30],
            schedule=schedule,
            message=message,
            deliver=True,
            channel=self._channel,
            to=self._chat_id,
            delete_after_run=delete_after_run,
        )
        return f"Created job '{job.name}' (id: {job.id})"
    
    def _list_jobs(self) -> str:
        jobs = self._cron.list_jobs()
        if not jobs:
            return "No scheduled jobs."
        lines = [f"- {j.name} (id: {j.id}, {j.schedule.kind})" for j in jobs]
        return "Scheduled jobs:\n" + "\n".join(lines)
    
    def _remove_job(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for remove"
        if self._cron.remove_job(job_id):
            return f"Removed job {job_id}"
        return f"Job {job_id} not found"

    def _update_job(self, job_id: str | None, **kwargs) -> str:
        if not job_id:
            return "Error: job_id is required for update"
        job = self._cron.update_job(job_id, **kwargs)
        if job:
            return f"Updated job '{job.name}' ({job.id})"
        return f"Job {job_id} not found"

    async def _run_job(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for run"
        if await self._cron.run_job(job_id, force=True):
            return f"Executed job {job_id}"
        return f"Job {job_id} not found or disabled"

    def _get_runs(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for runs"
        history = self._cron.get_run_history(job_id)
        if not history:
            return f"No run history for job {job_id}"
        from datetime import datetime
        lines = []
        for run in history:
            dt = datetime.fromtimestamp(run["run_at_ms"] / 1000)
            lines.append(f"  {dt.isoformat()} — {run['status']}")
        return f"Run history for {job_id}:\n" + "\n".join(lines)

    def _get_status(self) -> str:
        status = self._cron.status()
        return (f"Cron Service: {'Running' if status['enabled'] else 'Stopped'}\n"
                f"Jobs: {status['jobs']}\n"
                f"Next wake: {status.get('next_wake_at_ms', 'None')}")
