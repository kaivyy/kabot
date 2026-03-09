"""Tail/system execution helpers extracted from message_runtime."""

from __future__ import annotations

import time
from typing import Any

from loguru import logger

from kabot.bus.events import InboundMessage, OutboundMessage


async def process_pending_exec_approval(
    loop: Any,
    msg: InboundMessage,
    action: str,
    approval_id: str | None = None,
) -> OutboundMessage:
    """Handle explicit approval commands for pending exec actions."""
    session = await loop._init_session(msg)
    exec_tool = loop.tools.get("exec")
    if not exec_tool or not hasattr(exec_tool, "consume_pending_approval"):
        return await loop._finalize_session(
            msg,
            session,
            "No executable approval flow is available in this session.",
        )

    if action == "deny":
        cleared = exec_tool.clear_pending_approval(msg.session_key, approval_id)
        if cleared:
            return await loop._finalize_session(
                msg,
                session,
                "Pending command approval denied.",
            )
        return await loop._finalize_session(
            msg,
            session,
            "No matching pending command approval found.",
        )

    pending = exec_tool.consume_pending_approval(msg.session_key, approval_id)
    if not pending:
        return await loop._finalize_session(
            msg,
            session,
            "No matching pending command approval found.",
        )

    command = pending.get("command")
    if not isinstance(command, str) or not command.strip():
        return await loop._finalize_session(
            msg,
            session,
            "Pending approval entry is invalid.",
        )

    working_dir = pending.get("working_dir")
    result = await exec_tool.execute(
        command=command,
        working_dir=working_dir if isinstance(working_dir, str) else None,
        _session_key=msg.session_key,
        _approved_by_user=True,
    )
    return await loop._finalize_session(msg, session, result)

async def process_system_message(loop: Any, msg: InboundMessage) -> OutboundMessage | None:
    """Process synthetic/system messages (e.g., cron callbacks)."""
    logger.info(f"Processing system message from {msg.sender_id}")
    if ":" in msg.chat_id:
        parts = msg.chat_id.split(":", 1)
        origin_channel, origin_chat_id = parts[0], parts[1]
    else:
        origin_channel, origin_chat_id = "cli", msg.chat_id

    session_key = f"{origin_channel}:{origin_chat_id}"
    session = loop.sessions.get_or_create(session_key)

    for tool_name in ["message", "spawn", "cron"]:
        tool = loop.tools.get(tool_name)
        if hasattr(tool, "set_context"):
            tool.set_context(origin_channel, origin_chat_id)

    context_builder = loop.context
    resolve_context = getattr(loop, "_resolve_context_for_channel_chat", None)
    if callable(resolve_context):
        try:
            resolved_context = resolve_context(origin_channel, origin_chat_id)
            if resolved_context is not None:
                context_builder = resolved_context
        except Exception as exc:
            logger.warning(f"Failed to resolve system routed context builder: {exc}")

    messages = context_builder.build_messages(
        history=session.get_history(),
        current_message=msg.content,
        channel=origin_channel,
        chat_id=origin_chat_id,
    )

    final_content = await loop._run_agent_loop(msg, messages, session)
    session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
    if final_content:
        session.add_message("assistant", final_content)
    try:
        loop.sessions.save(session)
    except Exception as exc:
        logger.warning(f"Session save failed for {session_key}: {exc}")
    return OutboundMessage(
        channel=origin_channel,
        chat_id=origin_chat_id,
        content=final_content or "",
    )

async def process_isolated(
    loop: Any,
    content: str,
    channel: str = "cli",
    chat_id: str = "direct",
    job_id: str = "",
) -> str:
    """Process a message in a fully isolated session."""
    session_key = f"isolated:cron:{job_id}" if job_id else f"isolated:{int(time.time())}"
    msg = InboundMessage(
        channel=channel,
        sender_id="system",
        chat_id=chat_id,
        content=content,
        _session_key=session_key,
    )

    # Set context for tools without loading history
    for tool_name in ["message", "spawn", "cron"]:
        tool = loop.tools.get(tool_name)
        if hasattr(tool, "set_context"):
            tool.set_context(channel, chat_id)

    # Build messages without history: fresh context
    context_builder = loop.context
    resolve_context = getattr(loop, "_resolve_context_for_channel_chat", None)
    if callable(resolve_context):
        try:
            resolved_context = resolve_context(channel, chat_id)
            if resolved_context is not None:
                context_builder = resolved_context
        except Exception as exc:
            logger.warning(f"Failed to resolve isolated routed context builder: {exc}")

    messages = context_builder.build_messages(
        history=[],
        current_message=content,
        channel=channel,
        chat_id=chat_id,
        profile="GENERAL",
        tool_names=loop.tools.tool_names,
    )

    # Create a minimal session for isolated execution
    session = loop.sessions.get_or_create(session_key)

    # Run the full loop for isolated jobs.
    final_content = await loop._run_agent_loop(msg, messages, session)
    return final_content or ""
