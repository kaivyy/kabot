"""Session lifecycle helpers extracted from AgentLoop."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from kabot.bus.events import InboundMessage, OutboundMessage


def _defer_memory_writes(loop: Any) -> bool:
    perf_cfg = getattr(loop, "runtime_performance", None)
    if not perf_cfg:
        return False
    return bool(getattr(perf_cfg, "fast_first_response", True))


def _is_probe_mode_message(msg: InboundMessage) -> bool:
    metadata = getattr(msg, "metadata", None)
    return bool(isinstance(metadata, dict) and metadata.get("probe_mode"))


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
    if not _is_probe_mode_message(msg):
        loop.memory.create_session(session_key, msg.channel, msg.chat_id, msg.sender_id)
        if _defer_memory_writes(loop):
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


async def finalize_session(
    loop: Any,
    msg: InboundMessage,
    session: Any,
    final_content: str | None,
) -> OutboundMessage:
    """Persist final session state and produce outbound response."""
    if (
        final_content
        and not final_content.startswith("I've completed")
        and not _is_probe_mode_message(msg)
    ):
        if _defer_memory_writes(loop):
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
        try:
            loop.sessions.save(session)
        except Exception as exc:
            logger.warning(f"Session save failed for {msg.session_key}: {exc}")

    _append_daily_notes_summary(loop, msg, final_content)

    return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=final_content or "")
