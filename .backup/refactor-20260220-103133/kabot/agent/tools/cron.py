"""Cron tool for scheduling reminders and tasks."""

import re
import time
from typing import Any

from kabot.agent.tools.base import Tool
from kabot.cron.service import CronService
from kabot.cron.types import CronSchedule


REMINDER_CONTEXT_MARKER = "\n\nRecent context:\n"
MAX_CONTEXT_PER_MESSAGE = 220
MAX_CONTEXT_TOTAL = 700


def build_reminder_context(
    history: list[dict],
    max_messages: int = 10,
    max_per_message: int = MAX_CONTEXT_PER_MESSAGE,
    max_total: int = MAX_CONTEXT_TOTAL
) -> str:
    """Build context summary from recent messages to attach to reminder."""
    recent = [m for m in history[-max_messages:] if m.get("role") in ("user", "assistant")]
    if not recent:
        return ""

    lines = []
    total = 0
    for msg in recent:
        label = "User" if msg["role"] == "user" else "Assistant"
        text = msg.get("content", "")[:max_per_message]
        if len(msg.get("content", "")) > max_per_message:
            text += "..."
        line = f"- {label}: {text}"
        total += len(line)
        if total > max_total:
            break
        lines.append(line)

    return REMINDER_CONTEXT_MARKER + "\n".join(lines) if lines else ""


class CronTool(Tool):
    """Tool to schedule reminders and recurring tasks."""
    
    def __init__(self, cron_service: CronService):
        self._cron = cron_service
        self._channel = ""
        self._chat_id = ""
        self._history: list[dict] = []  # For context messages

    def set_context(self, channel: str, chat_id: str, history: list[dict] | None = None) -> None:
        """Set the current session context for delivery."""
        self._channel = channel
        self._chat_id = chat_id
        if history is not None:
            self._history = history
    
    @property
    def name(self) -> str:
        return "cron"
    
    @property
    def description(self) -> str:
        return """Manage scheduled cron jobs (reminders, recurring tasks, timed events).

ACTIONS:
- status: Check cron scheduler status
- list: List all scheduled jobs
- list_groups: List grouped schedules/cycles with titles
- add: Create a new scheduled job (requires message + schedule)
- update: Modify an existing job (requires job_id)
- update_group: Modify all jobs in a group (requires group_id or title)
- remove: Delete a job (requires job_id)
- remove_group: Delete all jobs in a group (requires group_id or title)
- run: Execute a job immediately (requires job_id)
- runs: Get job run history (requires job_id)

SCHEDULE TYPES (use ONE of these):
- at_time: One-shot at specific time (ISO-8601: "2026-02-15T10:00:00+07:00")
- every_seconds: Recurring interval (e.g. 3600 for every hour)
- start_at: Optional first-run anchor for every_seconds (ISO-8601 or "YYYY-MM-DD HH:MM")
- cron_expr: Cron expression (e.g. "0 9 * * *" for daily 9am)

IMPORTANT RULES:
- For reminders, ALWAYS set action="add" with a message and at_time
- Use context_messages (0-10) to attach recent chat context to the reminder
- one_shot defaults to true for at_time, false for recurring
- Times without timezone are treated as LOCAL TIME

EXAMPLES:
- Reminder: action="add", message="Waktunya meeting!", at_time="2026-02-15T10:00:00+07:00"
- Daily task: action="add", message="Backup database", cron_expr="0 2 * * *"
- Every hour: action="add", message="Check inbox", every_seconds=3600"""
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "add",
                        "list",
                        "list_groups",
                        "remove",
                        "remove_group",
                        "update",
                        "update_group",
                        "run",
                        "runs",
                        "status",
                    ],
                    "description": "Action to perform"
                },
                "message": {
                    "type": "string",
                    "description": "Reminder message (for add)"
                },
                "title": {
                    "type": "string",
                    "description": "Optional group title for grouped schedules/cycles"
                },
                "new_title": {
                    "type": "string",
                    "description": "New title for group update/rename"
                },
                "group_id": {
                    "type": "string",
                    "description": "Group ID for grouped schedule actions"
                },
                "at_time": {
                    "type": "string",
                    "description": "Specific time (ISO format or 'YYYY-MM-DD HH:MM')"
                },
                "every_seconds": {
                    "type": "integer",
                    "description": "Interval in seconds (for recurring tasks)"
                },
                "start_at": {
                    "type": "string",
                    "description": "Optional start anchor time for every_seconds (ISO or 'YYYY-MM-DD HH:MM')"
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
                },
                "context_messages": {
                    "type": "integer",
                    "description": "Number of recent messages (0-10) to attach as context to the reminder",
                    "minimum": 0,
                    "maximum": 10
                }
            },
            "required": ["action"]
        }
    
    async def execute(
            self,
            action: str,
            message: str = "",
            title: str | None = None,
            new_title: str | None = None,
            group_id: str | None = None,
            at_time: str = "",
            every_seconds: int | None = None,
            start_at: str | None = None,
            cron_expr: str | None = None,
            job_id: str | None = None,
            one_shot: bool | None = None,
            context_messages: int = 0,
            **kwargs: Any
    ) -> str:
        match action:
            case "add":
                return self._add_job(
                    message=message,
                    title=title,
                    group_id=group_id,
                    at_time=at_time,
                    every_seconds=every_seconds,
                    start_at=start_at,
                    cron_expr=cron_expr,
                    one_shot=one_shot,
                    context_messages=context_messages,
                )
            case "list":
                return self._list_jobs()
            case "list_groups":
                return self._list_groups()
            case "remove":
                return self._remove_job(job_id)
            case "remove_group":
                return self._remove_group(group_id=group_id, title=title)
            case "update":
                return self._update_job(job_id, **kwargs)
            case "update_group":
                return self._update_group(
                    group_id=group_id,
                    title=title,
                    new_title=new_title,
                    message=message,
                    at_time=at_time,
                    every_seconds=every_seconds,
                    start_at=start_at,
                    cron_expr=cron_expr,
                )
            case "run":
                return await self._run_job(job_id)
            case "runs":
                return self._get_runs(job_id)
            case "status":
                return self._get_status()
            case _:
                return f"Unknown action: {action}"
    
    def _add_job(
        self,
        message: str,
        title: str | None,
        group_id: str | None,
        at_time: str,
        every_seconds: int | None,
        start_at: str | None,
        cron_expr: str | None,
        one_shot: bool | None = None,
        context_messages: int = 0,
    ) -> str:
        if not message:
            return "Error: message is required for add"
        
        # logger.debug(f"Adding job: msg='{message}', channel='{self._channel}', chat_id='{self._chat_id}'")
        if not self._channel or not self._chat_id:
            return "Error: no session context (channel/chat_id)"

        # Attach context if requested
        if context_messages > 0 and self._history:
            context = build_reminder_context(self._history, max_messages=context_messages)
            if context:
                message = message + context

        group_title = (title or "").strip() or None
        resolved_group_id = (group_id or "").strip() or None
        if group_title and not resolved_group_id:
            resolved_group_id = self._generate_group_id(group_title)
        elif resolved_group_id and not group_title:
            group_title = resolved_group_id

        # Default one_shot behavior
        delete_after_run = one_shot if one_shot is not None else (True if at_time else False)

        schedule, error = self._build_schedule(
            at_time=at_time,
            every_seconds=every_seconds,
            start_at=start_at,
            cron_expr=cron_expr,
        )
        if error:
            return error
        if not schedule:
            return "Error: either at_time, every_seconds, or cron_expr is required"
        
        job = self._cron.add_job(
            name=(group_title or message)[:30],
            schedule=schedule,
            message=message,
            deliver=True,
            channel=self._channel,
            to=self._chat_id,
            delete_after_run=delete_after_run,
            group_id=resolved_group_id,
            group_title=group_title,
        )
        if resolved_group_id:
            return f"Created job '{job.name}' (id: {job.id}, group: {resolved_group_id}, title: {group_title})"
        return f"Created job '{job.name}' (id: {job.id})"
    
    def _list_jobs(self) -> str:
        jobs = self._cron.list_jobs()
        if not jobs:
            return "No scheduled jobs."
        lines: list[str] = []
        for j in jobs:
            group_suffix = ""
            if j.payload.group_id:
                title = j.payload.group_title or j.payload.group_id
                group_suffix = f", group={title} ({j.payload.group_id})"
            lines.append(f"- {j.name} (id: {j.id}, {j.schedule.kind}{group_suffix})")
        return "Scheduled jobs:\n" + "\n".join(lines)

    def _list_groups(self) -> str:
        jobs = self._cron.list_jobs(include_disabled=False)
        if not jobs:
            return "No grouped schedules."

        grouped: dict[str, dict[str, Any]] = {}
        for job in jobs:
            gid = job.payload.group_id or f"single:{job.id}"
            if gid not in grouped:
                grouped[gid] = {
                    "title": job.payload.group_title or job.name,
                    "jobs": [],
                }
            grouped[gid]["jobs"].append(job)

        lines: list[str] = []
        for gid, info in grouped.items():
            group_jobs = info["jobs"]
            next_runs = [j.state.next_run_at_ms for j in group_jobs if j.state.next_run_at_ms]
            next_run = min(next_runs) if next_runs else None
            next_run_str = self._format_timestamp(next_run) if next_run else "none"
            lines.append(
                f"- {info['title']} (group_id: {gid}, jobs: {len(group_jobs)}, next: {next_run_str})"
            )
        return "Schedule groups:\n" + "\n".join(lines)
    
    def _remove_job(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for remove"
        if self._cron.remove_job(job_id):
            return f"Removed job {job_id}"
        return f"Job {job_id} not found"

    def _find_group_jobs(self, group_id: str | None = None, title: str | None = None):
        jobs = self._cron.list_jobs(include_disabled=True)
        if group_id:
            target = group_id.strip()
            return [j for j in jobs if j.payload.group_id == target]
        if title:
            target_title = title.strip().casefold()
            return [j for j in jobs if (j.payload.group_title or "").casefold() == target_title]
        return []

    def _remove_group(self, group_id: str | None = None, title: str | None = None) -> str:
        group_jobs = self._find_group_jobs(group_id=group_id, title=title)
        if not group_jobs:
            return "Error: group not found. Provide valid group_id or title."

        removed = 0
        for job in group_jobs:
            if self._cron.remove_job(job.id):
                removed += 1

        gid = group_jobs[0].payload.group_id or f"single:{group_jobs[0].id}"
        gtitle = group_jobs[0].payload.group_title or group_jobs[0].name
        return f"Removed group '{gtitle}' ({gid}) with {removed} jobs"

    def _update_job(self, job_id: str | None, **kwargs) -> str:
        if not job_id:
            return "Error: job_id is required for update"
        job = self._cron.update_job(job_id, **kwargs)
        if job:
            return f"Updated job '{job.name}' ({job.id})"
        return f"Job {job_id} not found"

    def _update_group(
        self,
        group_id: str | None = None,
        title: str | None = None,
        new_title: str | None = None,
        message: str = "",
        at_time: str = "",
        every_seconds: int | None = None,
        start_at: str | None = None,
        cron_expr: str | None = None,
    ) -> str:
        group_jobs = self._find_group_jobs(group_id=group_id, title=title)
        if not group_jobs:
            return "Error: group not found. Provide valid group_id or title."

        schedule, error = self._build_schedule(
            at_time=at_time,
            every_seconds=every_seconds,
            start_at=start_at,
            cron_expr=cron_expr,
            allow_empty=True,
        )
        if error:
            return error

        updates: dict[str, Any] = {}
        if message:
            updates["message"] = message
        if schedule:
            updates["schedule"] = schedule
        if new_title:
            updates["group_title"] = new_title.strip()

        if not updates:
            return "Error: nothing to update. Provide message, schedule, or new_title."

        updated = 0
        for job in group_jobs:
            if self._cron.update_job(job.id, **updates):
                updated += 1

        gid = group_jobs[0].payload.group_id or f"single:{group_jobs[0].id}"
        effective_title = (new_title or group_jobs[0].payload.group_title or group_jobs[0].name).strip()
        return f"Updated group '{effective_title}' ({gid}) with {updated} jobs"

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

    def _generate_group_id(self, title: str) -> str:
        """Generate stable-ish unique group id from title + timestamp."""
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        if not slug:
            slug = "schedule"
        slug = slug[:24]
        return f"grp_{slug}_{int(time.time() * 1000) % 1_000_000:06d}"

    def _build_schedule(
        self,
        at_time: str = "",
        every_seconds: int | None = None,
        start_at: str | None = None,
        cron_expr: str | None = None,
        allow_empty: bool = False,
    ) -> tuple[CronSchedule | None, str | None]:
        """Build schedule object from user params."""
        if at_time:
            from datetime import datetime
            try:
                if "T" in at_time:
                    dt = datetime.fromisoformat(at_time.replace("Z", "+00:00"))
                else:
                    dt = datetime.strptime(at_time, "%Y-%m-%d %H:%M")
                at_ms = int(dt.timestamp() * 1000)
                return CronSchedule(kind="at", at_ms=at_ms), None
            except ValueError:
                return None, "Error: invalid at_time format. Use 'YYYY-MM-DD HH:MM' or ISO format"

        if every_seconds:
            start_at_ms: int | None = None
            if start_at:
                from datetime import datetime
                try:
                    if "T" in start_at:
                        start_dt = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
                    else:
                        start_dt = datetime.strptime(start_at, "%Y-%m-%d %H:%M")
                    start_at_ms = int(start_dt.timestamp() * 1000)
                except ValueError:
                    return None, "Error: invalid start_at format. Use 'YYYY-MM-DD HH:MM' or ISO format"
            return CronSchedule(kind="every", every_ms=every_seconds * 1000, start_at_ms=start_at_ms), None

        if cron_expr:
            return CronSchedule(kind="cron", expr=cron_expr), None

        if allow_empty:
            return None, None
        return None, "Error: either at_time, every_seconds, or cron_expr is required"

    def _format_timestamp(self, ts_ms: int) -> str:
        from datetime import datetime
        return datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d %H:%M")
