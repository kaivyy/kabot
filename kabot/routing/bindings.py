"""Agent binding resolution for message routing.

This module provides functions to route incoming messages to the correct agent
based on channel and chat_id bindings configured in the system.
"""

from kabot.config.schema import Config
from kabot.agent.agent_scope import resolve_default_agent_id


def resolve_agent_route(config: Config, channel: str, chat_id: str) -> str:
    """Resolve which agent should handle a message based on bindings.

    Priority order:
    1. Exact match: channel + chat_id
    2. Channel-only match: channel (chat_id is None)
    3. Default agent

    Args:
        config: The application configuration
        channel: The channel name (e.g., "telegram", "whatsapp")
        chat_id: The chat/conversation identifier

    Returns:
        The agent ID that should handle this message
    """
    # Priority 1: Exact channel + chat_id match
    for binding in config.agents.bindings:
        if binding.channel == channel and binding.chat_id == chat_id:
            return binding.agent_id

    # Priority 2: Channel-only match
    for binding in config.agents.bindings:
        if binding.channel == channel and binding.chat_id is None:
            return binding.agent_id

    # Priority 3: Default agent
    return resolve_default_agent_id(config)
