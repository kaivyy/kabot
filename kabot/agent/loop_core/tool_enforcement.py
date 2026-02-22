"""Tool-enforcement and deterministic fallback logic for AgentLoop."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from kabot.agent.cron_fallback_nlp import (
    CRON_MANAGEMENT_OPS,
    CRON_MANAGEMENT_TERMS,
    extract_cycle_schedule,
    extract_explicit_schedule_title,
    extract_new_schedule_title,
    extract_recurring_schedule,
    extract_reminder_message,
    extract_weather_location,
    required_tool_for_query,
)
from kabot.agent.cron_fallback_nlp import (
    build_cycle_title as nlp_build_cycle_title,
)
from kabot.agent.cron_fallback_nlp import (
    build_group_id as nlp_build_group_id,
)
from kabot.agent.cron_fallback_nlp import (
    make_unique_schedule_title as nlp_make_unique_schedule_title,
)
from kabot.agent.fallback_i18n import t as i18n_t
from kabot.bus.events import InboundMessage


def existing_schedule_titles(loop: Any) -> list[str]:
    """Collect existing grouped schedule titles from cron service."""
    if not getattr(loop, "cron_service", None):
        return []
    titles: list[str] = []
    try:
        for job in loop.cron_service.list_jobs(include_disabled=True):
            title = (job.payload.group_title or "").strip()
            if title:
                titles.append(title)
    except Exception:
        return []
    return titles


def required_tool_for_query_for_loop(loop: Any, question: str) -> str | None:
    """Resolve required tool for immediate-action query types."""
    return required_tool_for_query(
        question=question,
        has_weather_tool=loop.tools.has("weather"),
        has_cron_tool=loop.tools.has("cron"),
        has_system_info_tool=loop.tools.has("get_system_info"),
        has_cleanup_tool=loop.tools.has("cleanup_system"),
        has_process_memory_tool=loop.tools.has("get_process_memory"),
    )


def make_unique_schedule_title_for_loop(loop: Any, base_title: str) -> str:
    return nlp_make_unique_schedule_title(base_title, existing_schedule_titles(loop))


def build_group_id_for_loop(loop: Any, title: str) -> str:
    stamp = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    return nlp_build_group_id(title, now_ms=stamp)


async def execute_required_tool_fallback(loop: Any, required_tool: str, msg: InboundMessage) -> str | None:
    """Deterministic fallback when model skips required tools repeatedly."""
    if required_tool == "weather":
        location = extract_weather_location(msg.content)
        if not location:
            return i18n_t("weather.need_location", msg.content)
        result = await loop.tools.execute(
            "weather",
            {"location": location, "context_text": msg.content},
        )
        return str(result)

    if required_tool == "get_system_info":
        result = await loop.tools.execute("get_system_info", {})
        return str(result)

    if required_tool == "get_process_memory":
        q_lower = (msg.content or "").lower()
        limit = 15
        match = re.search(r"\b(\d{1,3})\b", q_lower)
        if match:
            try:
                limit = int(match.group(1))
            except Exception:
                limit = 15
        if limit < 1:
            limit = 1
        if limit > 200:
            limit = 200
        result = await loop.tools.execute("get_process_memory", {"limit": limit})
        return str(result)

    if required_tool == "cleanup_system":
        # Detect cleanup level from user message
        q_lower = (msg.content or "").lower()
        level = "standard"
        if any(k in q_lower for k in ("deep", "dalam", "mendalam", "full", "lengkap")):
            level = "deep"
        elif any(k in q_lower for k in ("quick", "cepat", "ringan", "light")):
            level = "quick"
        result = await loop.tools.execute("cleanup_system", {"level": level})
        return str(result)

    if required_tool != "cron":
        return None

    from kabot.cron.parse import parse_absolute_time_ms, parse_relative_time_ms

    async def _exec_cron(payload: dict[str, Any]) -> Any:
        enriched = dict(payload)
        enriched.setdefault("context_text", msg.content)
        return await loop.tools.execute("cron", enriched)

    q_lower = (msg.content or "").lower()
    is_management = any(op in q_lower for op in CRON_MANAGEMENT_OPS) and any(
        term in q_lower for term in CRON_MANAGEMENT_TERMS
    )

    if is_management and any(k in q_lower for k in ("list", "lihat", "show")):
        result = await _exec_cron({"action": "list_groups"})
        return str(result)

    if is_management and any(k in q_lower for k in ("hapus", "delete", "remove")):
        group_id_match = re.search(r"\bgrp_[a-z0-9_-]+\b", q_lower)
        if group_id_match:
            result = await _exec_cron({"action": "remove_group", "group_id": group_id_match.group(0)})
            return str(result)

        title = extract_explicit_schedule_title(msg.content)
        if title:
            result = await _exec_cron({"action": "remove_group", "title": title})
            return str(result)

        job_id_match = re.search(r"\b[a-f0-9]{8}\b", q_lower)
        if job_id_match:
            result = await _exec_cron({"action": "remove", "job_id": job_id_match.group(0)})
            return str(result)

        return i18n_t("cron.remove.need_selector", msg.content)

    if is_management and any(k in q_lower for k in ("edit", "ubah", "update")):
        selector_payload: dict[str, Any] = {}
        group_id_match = re.search(r"\bgrp_[a-z0-9_-]+\b", q_lower)
        if group_id_match:
            selector_payload["group_id"] = group_id_match.group(0)
        else:
            title = extract_explicit_schedule_title(msg.content)
            if title:
                selector_payload["title"] = title

        if not selector_payload:
            return i18n_t("cron.update.need_selector", msg.content)

        update_payload: dict[str, Any] = {"action": "update_group", **selector_payload}
        recurring_update = extract_recurring_schedule(msg.content)
        if recurring_update:
            update_payload.update(recurring_update)

        new_title = extract_new_schedule_title(msg.content)
        if new_title:
            update_payload["new_title"] = make_unique_schedule_title_for_loop(loop, new_title)

        if len(update_payload) <= 2:
            return i18n_t("cron.update.incomplete", msg.content)

        result = await _exec_cron(update_payload)
        return str(result)

    cycle_schedule = extract_cycle_schedule(msg.content)
    if cycle_schedule:
        every_seconds = int(cycle_schedule["period_days"]) * 86400
        group_title = nlp_build_cycle_title(
            msg.content,
            int(cycle_schedule["period_days"]),
            existing_schedule_titles(loop),
        )
        group_id = build_group_id_for_loop(loop, group_title)
        created_jobs = 0
        for event in cycle_schedule["events"]:
            payload = {
                "action": "add",
                "message": event["message"],
                "title": group_title,
                "group_id": group_id,
                "every_seconds": every_seconds,
                "start_at": event["start_at"],
                "one_shot": False,
            }
            await _exec_cron(payload)
            created_jobs += 1
        return i18n_t(
            "cron.cycle_created",
            msg.content,
            title=group_title,
            group_id=group_id,
            job_count=created_jobs,
            period_days=int(cycle_schedule["period_days"]),
        )

    reminder_text = extract_reminder_message(msg.content)
    recurring_schedule = extract_recurring_schedule(msg.content)
    if recurring_schedule:
        default_title = f"Recurring: {reminder_text[:40]}".strip()
        group_title = make_unique_schedule_title_for_loop(loop, default_title)
        recurring_payload = {
            "action": "add",
            "message": reminder_text,
            "title": group_title,
            "group_id": build_group_id_for_loop(loop, group_title),
            **recurring_schedule,
        }
        result = await _exec_cron(recurring_payload)
        return str(result)

    target_ms: int | None = None
    relative_ms = parse_relative_time_ms(msg.content)
    if relative_ms is not None:
        now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        target_ms = now_ms + relative_ms
    else:
        absolute_match = re.search(
            r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)",
            msg.content or "",
        )
        if absolute_match:
            target_ms = parse_absolute_time_ms(absolute_match.group(1))

    if target_ms is None:
        return i18n_t("cron.time_unclear", msg.content)

    at_time = datetime.fromtimestamp(target_ms / 1000, tz=timezone.utc).astimezone().isoformat(timespec="seconds")
    result = await _exec_cron(
        {
            "action": "add",
            "message": reminder_text,
            "at_time": at_time,
            "one_shot": True,
        }
    )
    return str(result)
