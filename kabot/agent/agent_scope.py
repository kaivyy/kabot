"""Agent scope resolution utilities.

This module provides functions to resolve agent-specific configuration
details from the Config object, including default agent, workspace paths,
and model assignments.
"""

from pathlib import Path
from kabot.config.schema import Config, AgentConfig


def resolve_default_agent_id(config: Config) -> str:
    """Resolve the default agent ID from configuration.

    Args:
        config: The application configuration

    Returns:
        The ID of the agent marked as default, or "main" if none is marked
    """
    for agent in config.agents.agents:
        if agent.default:
            return agent.id
    return "main"


def resolve_agent_config(config: Config, agent_id: str) -> AgentConfig | None:
    """Resolve agent configuration by ID.

    Args:
        config: The application configuration
        agent_id: The agent ID to look up

    Returns:
        The AgentConfig if found, None otherwise
    """
    for agent in config.agents.agents:
        if agent.id == agent_id:
            return agent
    return None


def resolve_agent_workspace(config: Config, agent_id: str) -> Path:
    """Resolve the workspace path for an agent.

    Args:
        config: The application configuration
        agent_id: The agent ID to resolve workspace for

    Returns:
        The expanded workspace path. If the agent has no workspace configured,
        returns a default path of ~/.kabot/workspace-{agent_id}
    """
    agent = resolve_agent_config(config, agent_id)
    if agent and agent.workspace:
        return Path(agent.workspace).expanduser()
    return Path.home() / ".kabot" / f"workspace-{agent_id}"


def resolve_agent_model(config: Config, agent_id: str) -> str | None:
    """Resolve the model for an agent.

    Args:
        config: The application configuration
        agent_id: The agent ID to resolve model for

    Returns:
        The model string if configured, None otherwise
    """
    agent = resolve_agent_config(config, agent_id)
    return agent.model if agent else None
