"""Cron tool for scheduling reminders and tasks."""

from typing import Any

from kabot.agent.tools.base import Tool
from kabot.agent.tools.cron_ops import actions as cron_actions
from kabot.agent.tools.cron_ops import schedule as cron_schedule
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
        self._context_text = ""

    def set_context(self, channel: str, chat_id: str, history: list[dict] | None = None) -> None:
        """Set the current session context for delivery."""
        self._channel = channel
        self._chat_id = chat_id
        self._context_text = ""
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
            context_text: str | None = None,
            **kwargs: Any
    ) -> str:
        self._context_text = (context_text or message or "").strip()
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
        return cron_actions.handle_add_job(
            self,
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
    
    def _list_jobs(self) -> str:
        return cron_actions.handle_list_jobs(self)

    def _list_groups(self) -> str:
        return cron_actions.handle_list_groups(self)
    
    def _remove_job(self, job_id: str | None) -> str:
        return cron_actions.handle_remove_job(self, job_id)

    def _find_group_jobs(self, group_id: str | None = None, title: str | None = None):
        return cron_actions._find_group_jobs(self, group_id=group_id, title=title)

    def _remove_group(self, group_id: str | None = None, title: str | None = None) -> str:
        return cron_actions.handle_remove_group(self, group_id=group_id, title=title)

    def _update_job(self, job_id: str | None, **kwargs) -> str:
        return cron_actions.handle_update_job(self, job_id, **kwargs)

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
        return cron_actions.handle_update_group(
            self,
            group_id=group_id,
            title=title,
            new_title=new_title,
            message=message,
            at_time=at_time,
            every_seconds=every_seconds,
            start_at=start_at,
            cron_expr=cron_expr,
        )

    async def _run_job(self, job_id: str | None) -> str:
        return await cron_actions.handle_run_job(self, job_id)

    def _get_runs(self, job_id: str | None) -> str:
        return cron_actions.handle_get_runs(self, job_id)

    def _get_status(self) -> str:
        return cron_actions.handle_get_status(self)

    def _generate_group_id(self, title: str) -> str:
        return cron_schedule.generate_group_id(title)

    def _build_schedule(
        self,
        at_time: str = "",
        every_seconds: int | None = None,
        start_at: str | None = None,
        cron_expr: str | None = None,
        allow_empty: bool = False,
    ) -> tuple[CronSchedule | None, str | None]:
        return cron_schedule.build_schedule(
            at_time=at_time,
            every_seconds=every_seconds,
            start_at=start_at,
            cron_expr=cron_expr,
            allow_empty=allow_empty,
        )

    def _format_timestamp(self, ts_ms: int) -> str:
        return cron_schedule.format_timestamp(ts_ms)

