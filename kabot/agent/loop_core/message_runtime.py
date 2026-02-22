"""Message/session runtime helpers extracted from AgentLoop."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from loguru import logger

from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.core.command_router import CommandContext


async def process_message(loop: Any, msg: InboundMessage) -> OutboundMessage | None:
    """Process a regular inbound message."""
    if msg.channel == "system":
        return await process_system_message(loop, msg)

    approval_action = loop._parse_approval_command(msg.content)
    if approval_action:
        action, approval_id = approval_action
        return await process_pending_exec_approval(
            loop,
            msg,
            action=action,
            approval_id=approval_id,
        )

    # Phase 8: Intercept slash commands BEFORE routing to LLM
    if loop.command_router.is_command(msg.content):
        ctx = CommandContext(
            message=msg.content,
            args=[],
            sender_id=msg.sender_id,
            channel=msg.channel,
            chat_id=msg.chat_id,
            session_key=msg.session_key,
            agent_loop=loop,
        )
        result = await loop.command_router.route(msg.content, ctx)
        if result:
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=result,
            )

    session = await loop._init_session(msg)

    # Phase 9: Parse directives from message body
    clean_body, directives = loop.directive_parser.parse(msg.content)
    effective_content = clean_body or msg.content

    # Store directives in session metadata
    if directives.raw_directives:
        active = loop.directive_parser.format_active_directives(directives)
        logger.info(f"Directives active: {active}")

        session.metadata["directives"] = {
            "think": directives.think,
            "verbose": directives.verbose,
            "elevated": directives.elevated,
        }
        # Ensure metadata persists
        loop.sessions.save(session)

    # Phase 9: Model override via directive
    if directives.model:
        logger.info(f"Directive override: model -> {directives.model}")

    # Phase 13: Detect document uploads and inject hint for KnowledgeLearnTool
    if hasattr(msg, "media") and msg.media:
        document_paths = []
        for path in msg.media:
            ext = Path(path).suffix.lower()
            if ext in [".pdf", ".txt", ".md", ".csv"]:
                document_paths.append(path)

        if document_paths:
            hint = "\n\n[System Note: Document(s) detected: " + ", ".join(document_paths) + ". If the user wants you to 'learn' or 'memorize' these permanently, use the 'knowledge_learn' tool.]"
            effective_content += hint
            logger.info(f"Document hint injected: {len(document_paths)} files")

    conversation_history = loop.memory.get_conversation_context(msg.session_key, max_messages=30)
    if conversation_history:
        conversation_history = [m for m in conversation_history if isinstance(m, dict)]

    # Router triase: SIMPLE vs COMPLEX
    decision = await loop.router.route(effective_content)
    logger.info(f"Route: profile={decision.profile}, complex={decision.is_complex}")

    messages = loop.context.build_messages(
        history=conversation_history,
        current_message=effective_content,
        media=msg.media if hasattr(msg, "media") else None,
        channel=msg.channel,
        chat_id=msg.chat_id,
        profile=decision.profile,
        tool_names=loop.tools.tool_names,
    )

    # Check if this query REQUIRES a specific tool (cleanup, sysinfo, weather, cron)
    required_tool = loop._required_tool_for_query(effective_content)

    # CRITICAL FIX: If user gives a short confirmation, elevate to complex
    # if the AI was offering an action in the previous turn. (Multilingual)
    if not decision.is_complex and not required_tool:
        short_confirmations = (
            "ya", "yes", "y", "iya", "ok", "oke", "boleh", "silakan", "lanjut", "sip", "yep", "yup", "sure",
            "si", "sí", "oui", "ja", "da", "net",
            "はい", "네", "是", "对", "好的", "baik"
        )
        offer_keywords = (
            "reminder", "ingatkan", "set", "jadwal", "cleanup", "bersihkan", "download", "unduh",
            "schedule", "alarm", "timer", "jadual", "peringatan", "เตือน", "ตาราง", "提醒", "日程",
            "clean", "optimasi", "hapus", "delete", "remove"
        )
        if effective_content.strip().lower() in short_confirmations:
            last_asst = next((m.get("content", "") for m in reversed(conversation_history) if m.get("role") == "assistant"), "")
            if any(k in str(last_asst).lower() for k in offer_keywords):
                logger.info("Elevating short confirmation to complex route based on recent AI offer")
                decision.is_complex = True

    if decision.is_complex or required_tool:
        if required_tool and not decision.is_complex:
            logger.info(f"Route override: simple -> complex (required_tool={required_tool})")
        final_content = await loop._run_agent_loop(msg, messages, session)
    else:
        final_content = await loop._run_simple_response(msg, messages)

    return await loop._finalize_session(msg, session, final_content)


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

    messages = loop.context.build_messages(
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
    messages = loop.context.build_messages(
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
