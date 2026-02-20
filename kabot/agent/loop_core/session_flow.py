"""Session lifecycle helpers extracted from AgentLoop."""

from __future__ import annotations

from typing import Any

from loguru import logger

from kabot.bus.events import InboundMessage, OutboundMessage


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
    loop.memory.create_session(session_key, msg.channel, msg.chat_id, msg.sender_id)
    await loop.memory.add_message(session_key, "user", msg.content)

    for tool_name in ["message", "spawn", "cron"]:
        tool = loop.tools.get(tool_name)
        if hasattr(tool, "set_context"):
            logger.debug(f"Setting context for {tool_name}: {msg.channel}:{msg.chat_id}")
            tool.set_context(msg.channel, msg.chat_id)

    for tool_name in ["save_memory", "get_memory", "list_reminders"]:
        tool = loop.tools.get(tool_name)
        if hasattr(tool, "set_context"):
            tool.set_context(session_key)

    spawn_tool = loop.tools.get("spawn")
    if spawn_tool and hasattr(spawn_tool, "set_session_context"):
        spawn_tool.set_session_context(session_key)

    return session


async def finalize_session(
    loop: Any,
    msg: InboundMessage,
    session: Any,
    final_content: str | None,
) -> OutboundMessage:
    """Persist final session state and produce outbound response."""
    if final_content and not final_content.startswith("I've completed"):
        await loop.memory.add_message(msg.session_key, "assistant", final_content)

    if not msg.session_key.startswith("background:"):
        session.add_message("user", msg.content)
        if final_content:
            session.add_message("assistant", final_content)
        try:
            loop.sessions.save(session)
        except Exception as exc:
            logger.warning(f"Session save failed for {msg.session_key}: {exc}")

    return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=final_content or "")
