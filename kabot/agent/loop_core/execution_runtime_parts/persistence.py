"""Persistence and interruption helpers for execution runtime."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any

from loguru import logger

from kabot.bus.events import InboundMessage


def _prune_expiring_cache(cache: dict[str, tuple[float, str]]) -> None:
    now = time.time()
    expired = [key for key, (expires_at, _) in cache.items() if expires_at <= now]
    for key in expired:
        cache.pop(key, None)


def _stable_tool_payload_hash(
    session_key: str,
    turn_id: str,
    tool_name: str,
    tool_args: dict[str, Any],
) -> str:
    normalized_args = json.dumps(tool_args, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    raw = f"{session_key}|{turn_id}|{tool_name}|{normalized_args}"
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def _should_defer_memory_write(loop: Any) -> bool:
    perf_cfg = getattr(loop, "runtime_performance", None)
    if not perf_cfg:
        return False
    return bool(getattr(perf_cfg, "fast_first_response", True))


def _schedule_memory_write(loop: Any, coro: Any, *, label: str) -> None:
    task = asyncio.create_task(coro)
    pending = getattr(loop, "_pending_memory_tasks", None)
    if not isinstance(pending, set):
        pending = set()
        setattr(loop, "_pending_memory_tasks", pending)
    pending.add(task)

    def _done_callback(done_task: asyncio.Task) -> None:
        pending.discard(done_task)
        try:
            done_task.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning(f"Background memory write failed ({label}): {exc}")

    task.add_done_callback(_done_callback)


def _interrupt_preview_text(content: str, *, max_chars: int = 120) -> str:
    text = " ".join(str(content or "").split())
    if len(text) > max_chars:
        return text[: max_chars - 3].rstrip() + "..."
    return text


async def _take_pending_interrupt_messages(
    loop: Any,
    msg: InboundMessage,
    *,
    limit: int = 3,
) -> list[InboundMessage]:
    bus = getattr(loop, "bus", None)
    taker = getattr(bus, "take_pending_inbound_for_session", None)
    if not callable(taker):
        return []
    try:
        result = taker(msg.session_key, limit=limit)
        if asyncio.iscoroutine(result):
            result = await result
    except Exception as exc:
        logger.debug(f"pending interrupt drain skipped: {exc}")
        return []
    if not isinstance(result, list):
        return []
    pending: list[InboundMessage] = []
    for item in result:
        if isinstance(item, InboundMessage) and item.session_key == msg.session_key:
            pending.append(item)
    return pending[: max(1, int(limit or 3))]


def _build_pending_interrupt_note(pending_messages: list[InboundMessage]) -> str:
    previews = [
        _interrupt_preview_text(item.content)
        for item in pending_messages
        if isinstance(item, InboundMessage) and str(item.content or "").strip()
    ]
    if not previews:
        return ""
    lines = ["[Pending User Messages]"]
    lines.extend(f"- {preview}" for preview in previews[:3])
    lines.extend(
        [
            "",
            "[Pending User Message Note]",
            "The user sent new messages while you were still working. Acknowledge that briefly, "
            "then incorporate the new requests into the active task without pretending they never arrived.",
        ]
    )
    return "\n".join(lines).strip()
