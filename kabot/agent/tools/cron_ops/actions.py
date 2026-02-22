"""Action handlers for CronTool."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from kabot.agent.tools.cron_ops.schedule import build_schedule, format_timestamp, generate_group_id
from kabot.i18n.catalog import tr as i18n_t

REMINDER_CONTEXT_MARKER = "\n\nRecent context:\n"
MAX_CONTEXT_PER_MESSAGE = 220
MAX_CONTEXT_TOTAL = 700


def _resolve_text_context(tool: Any, fallback: str = "") -> str:
    raw = getattr(tool, "_context_text", "") or fallback
    return raw if isinstance(raw, str) else ""


def _t(tool: Any, key: str, *, fallback_text: str = "", **kwargs: Any) -> str:
    return i18n_t(key, text=_resolve_text_context(tool, fallback=fallback_text), **kwargs)


def _build_reminder_context(
    history: list[dict],
    max_messages: int = 10,
    max_per_message: int = MAX_CONTEXT_PER_MESSAGE,
    max_total: int = MAX_CONTEXT_TOTAL,
) -> str:
    recent = [m for m in history[-max_messages:] if m.get("role") in ("user", "assistant")]
    if not recent:
        return ""

    lines: list[str] = []
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


def handle_add_job(
    tool: Any,
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
        return _t(tool, "cron.add.error_message_required")

    if not tool._channel or not tool._chat_id:
        return _t(tool, "cron.add.error_no_session_context")

    if context_messages > 0 and tool._history:
        context = _build_reminder_context(tool._history, max_messages=context_messages)
        if context:
            message = message + context

    group_title = (title or "").strip() or None
    resolved_group_id = (group_id or "").strip() or None
    if group_title and not resolved_group_id:
        resolved_group_id = generate_group_id(group_title)
    elif resolved_group_id and not group_title:
        group_title = resolved_group_id

    delete_after_run = one_shot if one_shot is not None else (True if at_time else False)

    schedule, error = build_schedule(
        at_time=at_time,
        every_seconds=every_seconds,
        start_at=start_at,
        cron_expr=cron_expr,
    )
    if error:
        return _t(tool, "cron.add.error_schedule_invalid", fallback_text=message, error=error)
    if not schedule:
        return _t(tool, "cron.add.error_schedule_required", fallback_text=message)

    try:
        job = tool._cron.add_job(
            name=(group_title or message)[:30],
            schedule=schedule,
            message=message,
            deliver=True,
            channel=tool._channel,
            to=tool._chat_id,
            delete_after_run=delete_after_run,
            group_id=resolved_group_id,
            group_title=group_title,
        )
    except ValueError as exc:
        return _t(tool, "cron.add.error_policy_violation", fallback_text=message, error=str(exc))
    if resolved_group_id:
        return _t(
            tool,
            "cron.add.created_group",
            fallback_text=message,
            name=job.name,
            job_id=job.id,
            group_id=resolved_group_id,
            title=group_title or resolved_group_id,
        )
    return _t(tool, "cron.add.created", fallback_text=message, name=job.name, job_id=job.id)


def handle_list_jobs(tool: Any) -> str:
    jobs = tool._cron.list_jobs()
    if not jobs:
        return _t(tool, "cron.list.empty")
    lines: list[str] = []
    for job in jobs:
        group_suffix = ""
        if job.payload.group_id:
            title = job.payload.group_title or job.payload.group_id
            group_suffix = f", group={title} ({job.payload.group_id})"
        lines.append(f"- {job.name} (id: {job.id}, {job.schedule.kind}{group_suffix})")
    return _t(tool, "cron.list.header") + "\n" + "\n".join(lines)


def handle_list_groups(tool: Any) -> str:
    jobs = tool._cron.list_jobs(include_disabled=False)
    if not jobs:
        return _t(tool, "cron.list_groups.empty")

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
        next_run_str = format_timestamp(next_run) if next_run else "none"
        lines.append(
            f"- {info['title']} (group_id: {gid}, jobs: {len(group_jobs)}, next: {next_run_str})"
        )
    return _t(tool, "cron.list_groups.header") + "\n" + "\n".join(lines)


def _find_group_jobs(tool: Any, group_id: str | None = None, title: str | None = None):
    jobs = tool._cron.list_jobs(include_disabled=True)
    if group_id:
        target = group_id.strip()
        return [job for job in jobs if job.payload.group_id == target]
    if title:
        target_title = title.strip().casefold()
        return [job for job in jobs if (job.payload.group_title or "").casefold() == target_title]
    return []


def handle_remove_job(tool: Any, job_id: str | None) -> str:
    if not job_id:
        return _t(tool, "cron.remove.error_job_id_required")
    if tool._cron.remove_job(job_id):
        return _t(tool, "cron.remove.ok", job_id=job_id)
    return _t(tool, "cron.remove.not_found", job_id=job_id)


def handle_remove_group(tool: Any, group_id: str | None = None, title: str | None = None) -> str:
    group_jobs = _find_group_jobs(tool, group_id=group_id, title=title)
    if not group_jobs:
        return _t(tool, "cron.remove_group.error_not_found")

    removed = 0
    for job in group_jobs:
        if tool._cron.remove_job(job.id):
            removed += 1

    gid = group_jobs[0].payload.group_id or f"single:{group_jobs[0].id}"
    gtitle = group_jobs[0].payload.group_title or group_jobs[0].name
    return _t(tool, "cron.remove_group.ok", title=gtitle, group_id=gid, removed=removed)


def handle_update_job(tool: Any, job_id: str | None, **kwargs) -> str:
    if not job_id:
        return _t(tool, "cron.update.error_job_id_required")
    job = tool._cron.update_job(job_id, **kwargs)
    if job:
        return _t(tool, "cron.update.ok", name=job.name, job_id=job.id)
    return _t(tool, "cron.update.not_found", job_id=job_id)


def handle_update_group(
    tool: Any,
    group_id: str | None = None,
    title: str | None = None,
    new_title: str | None = None,
    message: str = "",
    at_time: str = "",
    every_seconds: int | None = None,
    start_at: str | None = None,
    cron_expr: str | None = None,
) -> str:
    group_jobs = _find_group_jobs(tool, group_id=group_id, title=title)
    if not group_jobs:
        return _t(tool, "cron.update_group.error_not_found")

    schedule, error = build_schedule(
        at_time=at_time,
        every_seconds=every_seconds,
        start_at=start_at,
        cron_expr=cron_expr,
        allow_empty=True,
    )
    if error:
        return _t(tool, "cron.update_group.error_schedule_invalid", error=error)

    updates: dict[str, Any] = {}
    if message:
        updates["message"] = message
    if schedule:
        updates["schedule"] = schedule
    if new_title:
        updates["group_title"] = new_title.strip()

    if not updates:
        return _t(tool, "cron.update_group.error_nothing_to_update")

    updated = 0
    for job in group_jobs:
        if tool._cron.update_job(job.id, **updates):
            updated += 1

    gid = group_jobs[0].payload.group_id or f"single:{group_jobs[0].id}"
    effective_title = (new_title or group_jobs[0].payload.group_title or group_jobs[0].name).strip()
    return _t(tool, "cron.update_group.ok", title=effective_title, group_id=gid, updated=updated)


async def handle_run_job(tool: Any, job_id: str | None) -> str:
    if not job_id:
        return _t(tool, "cron.run.error_job_id_required")
    if await tool._cron.run_job(job_id, force=True):
        return _t(tool, "cron.run.ok", job_id=job_id)
    return _t(tool, "cron.run.not_found", job_id=job_id)


def handle_get_runs(tool: Any, job_id: str | None) -> str:
    if not job_id:
        return _t(tool, "cron.runs.error_job_id_required")
    history = tool._cron.get_run_history(job_id)
    if not history:
        return _t(tool, "cron.runs.empty", job_id=job_id)
    lines: list[str] = []
    for run in history:
        dt = datetime.fromtimestamp(run["run_at_ms"] / 1000)
        lines.append(f"  {dt.isoformat()} - {run['status']}")
    return _t(tool, "cron.runs.header", job_id=job_id) + "\n" + "\n".join(lines)


def handle_get_status(tool: Any) -> str:
    status = tool._cron.status()
    service_state = _t(tool, "cron.status.running") if status["enabled"] else _t(tool, "cron.status.stopped")
    return _t(
        tool,
        "cron.status.summary",
        service_state=service_state,
        jobs=status["jobs"],
        next_wake=status.get("next_wake_at_ms", "None"),
    )
