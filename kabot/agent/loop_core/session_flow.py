"""Session lifecycle helpers extracted from AgentLoop."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from loguru import logger

from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.session.delivery_route import (
    delivery_route_from_message,
    merge_delivery_route,
    normalize_delivery_route,
)


def _defer_memory_writes(loop: Any) -> bool:
    perf_cfg = getattr(loop, "runtime_performance", None)
    if not perf_cfg:
        return False
    return bool(getattr(perf_cfg, "fast_first_response", True))


def _is_probe_mode_message(msg: InboundMessage) -> bool:
    metadata = getattr(msg, "metadata", None)
    return bool(isinstance(metadata, dict) and metadata.get("probe_mode"))


def _should_persist_probe_history(msg: InboundMessage) -> bool:
    metadata = getattr(msg, "metadata", None)
    return bool(isinstance(metadata, dict) and metadata.get("persist_history"))


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
            # Expected during one-shot CLI shutdown when background writes are cancelled.
            return
        except Exception as exc:
            logger.warning(f"Background memory write failed ({label}): {exc}")

    task.add_done_callback(_done_callback)


async def drain_pending_memory_writes(loop: Any, *, max_wait_ms: int = 250) -> int:
    """Wait briefly for already-scheduled memory writes so history stays fresh."""
    pending = getattr(loop, "_pending_memory_tasks", None)
    if not isinstance(pending, set) or not pending:
        return 0

    live_tasks = [
        task for task in list(pending)
        if isinstance(task, asyncio.Task) and not task.done()
    ]
    if not live_tasks:
        return 0

    timeout = None
    if isinstance(max_wait_ms, (int, float)) and max_wait_ms > 0:
        timeout = float(max_wait_ms) / 1000.0

    done, _pending = await asyncio.wait(live_tasks, timeout=timeout)
    drained = 0
    for task in done:
        pending.discard(task)
        drained += 1
        try:
            task.result()
        except asyncio.CancelledError:
            continue
        except Exception as exc:
            logger.warning(f"Background memory write failed during drain: {exc}")
    return drained


def get_session_key(loop: Any, msg: InboundMessage) -> str:
    """Resolve session key using existing route resolver."""
    route = loop._resolve_route_for_message(msg)
    return route["session_key"]


async def init_session(loop: Any, msg: InboundMessage) -> Any:
    """Prepare session and tool context before processing message."""
    logger.info(f"Processing message from {msg.channel}:{msg.sender_id}: {msg.content[:80]}...")

    if not msg._session_key:
        session_key = get_session_key(loop, msg)
        msg._session_key = session_key
    else:
        session_key = msg._session_key

    run_id = f"msg-{session_key}-{msg.timestamp.timestamp()}"
    loop.tools._run_id = run_id

    message_id = f"{msg.channel}:{msg.chat_id}:{msg.sender_id}"
    loop.sentinel.mark_session_active(
        session_id=session_key,
        message_id=message_id,
        user_message=msg.content,
    )

    session = loop.sessions.get_or_create(session_key)

    inbound_meta = msg.metadata if isinstance(msg.metadata, dict) else {}
    session_meta = getattr(session, "metadata", None)
    current_delivery_route = delivery_route_from_message(msg)
    if isinstance(session_meta, dict):
        session_last_nav = str(session_meta.get("last_navigated_path") or "").strip()
        session_last_delivery = str(session_meta.get("last_delivery_path") or "").strip()
        session_working_directory = str(session_meta.get("working_directory") or "").strip()
        session_delivery_route = normalize_delivery_route(session_meta.get("delivery_route"))
        if session_last_nav or session_last_delivery or session_working_directory:
            if not isinstance(msg.metadata, dict):
                msg.metadata = {}
                inbound_meta = msg.metadata
        if session_delivery_route and not inbound_meta.get("delivery_route"):
            inbound_meta["delivery_route"] = dict(session_delivery_route)
        if session_working_directory:
            if not str(inbound_meta.get("working_directory") or "").strip():
                inbound_meta["working_directory"] = session_working_directory
            if not isinstance(inbound_meta.get("last_tool_context"), dict):
                inbound_meta["last_tool_context"] = {
                    "tool": "list_dir",
                    "path": session_working_directory,
                }
        if session_last_nav and not session_working_directory:
            if not str(inbound_meta.get("working_directory") or "").strip():
                inbound_meta["working_directory"] = session_last_nav
            if not isinstance(inbound_meta.get("last_tool_context"), dict):
                inbound_meta["last_tool_context"] = {
                    "tool": "list_dir",
                    "path": session_last_nav,
                }
    effective_delivery_route = merge_delivery_route(inbound_meta.get("delivery_route"), current_delivery_route)
    if effective_delivery_route:
        if not isinstance(msg.metadata, dict):
            msg.metadata = {}
            inbound_meta = msg.metadata
        inbound_meta["delivery_route"] = dict(effective_delivery_route)

    persist_probe_history = _should_persist_probe_history(msg)
    if not _is_probe_mode_message(msg) or persist_probe_history:
        loop.memory.create_session(session_key, msg.channel, msg.chat_id, msg.sender_id)
        if _defer_memory_writes(loop) and not persist_probe_history:
            _schedule_memory_write(
                loop,
                loop.memory.add_message(session_key, "user", msg.content),
                label="user-message",
            )
        else:
            await loop.memory.add_message(session_key, "user", msg.content)

    for tool_name in ["message", "spawn", "cron"]:
        tool = loop.tools.get(tool_name)
        if hasattr(tool, "set_context"):
            logger.debug(f"Setting context for {tool_name}: {msg.channel}:{msg.chat_id}")
            if tool_name == "message":
                tool.set_context(msg.channel, msg.chat_id, delivery_route=effective_delivery_route)
            else:
                tool.set_context(msg.channel, msg.chat_id)

    for tool_name in ["save_memory", "get_memory", "graph_memory", "list_reminders"]:
        tool = loop.tools.get(tool_name)
        if hasattr(tool, "set_context"):
            tool.set_context(session_key)

    spawn_tool = loop.tools.get("spawn")
    if spawn_tool and hasattr(spawn_tool, "set_session_context"):
        spawn_tool.set_session_context(session_key)

    return session


def _append_daily_notes_summary(loop: Any, msg: InboundMessage, final_content: str | None) -> None:
    """Best-effort periodic memory dump for each completed conversation turn."""
    context = None
    resolve_context = getattr(loop, "_resolve_context_for_message", None)
    if callable(resolve_context):
        try:
            context = resolve_context(msg)
        except Exception as exc:
            logger.warning(f"Failed to resolve routed context for daily notes: {exc}")
    if context is None:
        context = getattr(loop, "context", None)
    daily_memory = getattr(context, "memory", None) if context else None
    append_today = getattr(daily_memory, "append_today", None)
    if not callable(append_today):
        return

    user_text = (msg.content or "").strip()
    assistant_text = (final_content or "").strip()
    if not user_text and not assistant_text:
        return

    lines = [f"- [{msg.session_key}]"]
    if user_text:
        lines.append(f"  U: {user_text}")
    if assistant_text:
        lines.append(f"  A: {assistant_text}")

    try:
        append_today("\n".join(lines))
    except Exception as exc:
        logger.warning(f"Daily notes append failed for {msg.session_key}: {exc}")


def _coerce_json_response(content: str | None) -> str:
    raw = str(content or "")
    stripped = raw.strip()
    if not stripped:
        return raw
    try:
        parsed = json.loads(stripped)
    except Exception:
        parsed = {"response": raw}
    else:
        if not isinstance(parsed, (dict, list)):
            parsed = {"response": parsed}
    return json.dumps(parsed, ensure_ascii=False, indent=2)


def _apply_outbound_response_directives(
    loop: Any,
    msg: InboundMessage,
    final_content: str | None,
) -> tuple[str | None, dict[str, Any]]:
    inbound_meta = msg.metadata if isinstance(msg.metadata, dict) else {}
    outbound_meta: dict[str, Any] = {}
    content = final_content

    if bool(inbound_meta.get("directive_json_output")) and content is not None:
        content = _coerce_json_response(content)
        outbound_meta["response_format"] = "json"

    if bool(inbound_meta.get("directive_raw")):
        outbound_meta["render_markdown"] = False
        outbound_meta.setdefault("response_format", "raw")

    setattr(loop, "_last_outbound_metadata", dict(outbound_meta))
    return content, outbound_meta


async def finalize_session(
    loop: Any,
    msg: InboundMessage,
    session: Any,
    final_content: str | None,
) -> OutboundMessage:
    """Persist final session state and produce outbound response."""
    final_content, outbound_metadata = _apply_outbound_response_directives(loop, msg, final_content)

    if (
        final_content
        and not final_content.startswith("I've completed")
        and (not _is_probe_mode_message(msg) or _should_persist_probe_history(msg))
    ):
        if _defer_memory_writes(loop) and not _should_persist_probe_history(msg):
            _schedule_memory_write(
                loop,
                loop.memory.add_message(msg.session_key, "assistant", final_content),
                label="assistant-message",
            )
        else:
            await loop.memory.add_message(msg.session_key, "assistant", final_content)

    if not msg.session_key.startswith("background:"):
        session.add_message("user", msg.content)
        if final_content:
            # Capture usage from loop if available
            usage_metadata = getattr(loop, "last_usage", None)
            if isinstance(usage_metadata, dict):
                session.add_message(
                    "assistant",
                    final_content,
                    usage=usage_metadata,
                    model=usage_metadata.get("model")
                )
                # Clear for next turn
                setattr(loop, "last_usage", None)
            else:
                session.add_message("assistant", final_content)

        inbound_meta = msg.metadata if isinstance(msg.metadata, dict) else {}
        session_meta = getattr(session, "metadata", None)
        if isinstance(session_meta, dict):
            working_directory = str(inbound_meta.get("working_directory") or "").strip()
            if working_directory:
                session_meta["working_directory"] = working_directory
            last_navigated_path = str(inbound_meta.get("last_navigated_path") or "").strip()
            if last_navigated_path and last_navigated_path != working_directory:
                session_meta["last_navigated_path"] = last_navigated_path
            elif working_directory:
                session_meta.pop("last_navigated_path", None)
            last_delivery_path = str(inbound_meta.get("last_delivery_path") or "").strip()
            if last_delivery_path:
                session_meta["last_delivery_path"] = last_delivery_path
            delivery_route = merge_delivery_route(
                inbound_meta.get("delivery_route"),
                delivery_route_from_message(msg),
            )
            if delivery_route:
                session_meta["delivery_route"] = dict(delivery_route)

        refresh_snapshot = getattr(session, "refresh_durable_history_snapshot", None)
        if callable(refresh_snapshot):
            try:
                refresh_snapshot()
            except Exception as exc:
                logger.warning(f"Session snapshot refresh failed for {msg.session_key}: {exc}")
        try:
            loop.sessions.save(session)
        except Exception as exc:
            logger.warning(f"Session save failed for {msg.session_key}: {exc}")

    _append_daily_notes_summary(loop, msg, final_content)

    return OutboundMessage(
        channel=msg.channel,
        chat_id=msg.chat_id,
        content=final_content or "",
        metadata=outbound_metadata,
    )
