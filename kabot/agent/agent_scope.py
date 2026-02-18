"""Agent scope resolution utilities.

This module provides functions to resolve agent-specific configuration
details from the Config object, including default agent, workspace paths,
model assignments, and OpenClaw-compatible per-agent configs.
"""

from pathlib import Path
from kabot.config.schema import (
    Config,
    AgentConfig,
    AgentModelConfig,
    AgentSandboxConfig,
    AgentToolsConfig,
)


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
        returns a default path based on whether it's the default agent or not.
    """
    agent = resolve_agent_config(config, agent_id)

    # Agent-specific workspace
    if agent and agent.workspace:
        return Path(agent.workspace).expanduser()

    # Default agent uses global default workspace
    default_agent_id = resolve_default_agent_id(config)
    if agent_id == default_agent_id:
        return Path(config.agents.defaults.workspace).expanduser()

    # Non-default agents get isolated workspace
    return Path.home() / ".kabot" / f"workspace-{agent_id}"


def resolve_agent_dir(config: Config, agent_id: str) -> Path:
    """Resolve the agent directory for an agent (separate from workspace).

    This is where agent-specific state, config, and metadata are stored.

    Args:
        config: The application configuration
        agent_id: The agent ID to resolve agent dir for

    Returns:
        The expanded agent directory path
    """
    agent = resolve_agent_config(config, agent_id)

    # Agent-specific agent_dir
    if agent and agent.agent_dir:
        return Path(agent.agent_dir).expanduser()

    # Default: ~/.kabot/agents/{agent_id}/agent
    return Path.home() / ".kabot" / "agents" / agent_id / "agent"


def resolve_agent_model(config: Config, agent_id: str) -> str | None:
    """Resolve the primary model for an agent.

    Args:
        config: The application configuration
        agent_id: The agent ID to resolve model for

    Returns:
        The model string if configured, None otherwise
    """
    agent = resolve_agent_config(config, agent_id)
    if not agent or not agent.model:
        return None

    # Handle both string and AgentModelConfig
    if isinstance(agent.model, str):
        return agent.model
    elif isinstance(agent.model, AgentModelConfig):
        return agent.model.primary

    return None


def resolve_agent_model_fallbacks(config: Config, agent_id: str) -> list[str] | None:
    """Resolve model fallbacks for an agent.

    Args:
        config: The application configuration
        agent_id: The agent ID to resolve fallbacks for

    Returns:
        List of fallback models if configured, None otherwise
    """
    agent = resolve_agent_config(config, agent_id)
    if not agent or not agent.model:
        return None

    # Only AgentModelConfig has fallbacks
    if isinstance(agent.model, AgentModelConfig):
        return agent.model.fallbacks if agent.model.fallbacks else None

    return None


def resolve_agent_skills_filter(config: Config, agent_id: str) -> list[str] | None:
    """Resolve skills filter/allowlist for an agent.

    Args:
        config: The application configuration
        agent_id: The agent ID to resolve skills for

    Returns:
        List of allowed skill names if configured, None for no filtering
    """
    agent = resolve_agent_config(config, agent_id)
    if not agent or not agent.skills:
        return None

    return agent.skills


def resolve_agent_sandbox_config(config: Config, agent_id: str) -> AgentSandboxConfig | None:
    """Resolve sandbox configuration for an agent.

    Args:
        config: The application configuration
        agent_id: The agent ID to resolve sandbox config for

    Returns:
        AgentSandboxConfig if configured, None otherwise
    """
    agent = resolve_agent_config(config, agent_id)
    if not agent:
        return None

    return agent.sandbox


def resolve_agent_tools_config(config: Config, agent_id: str) -> AgentToolsConfig | None:
    """Resolve tools configuration for an agent.

    Args:
        config: The application configuration
        agent_id: The agent ID to resolve tools config for

    Returns:
        AgentToolsConfig if configured, None otherwise
    """
    agent = resolve_agent_config(config, agent_id)
    if not agent:
        return None

    return agent.tools


def resolve_agent_memory_search(config: Config, agent_id: str) -> bool | None:
    """Resolve memory search setting for an agent.

    Args:
        config: The application configuration
        agent_id: The agent ID to resolve setting for

    Returns:
        Memory search enabled flag if configured, None for default
    """
    agent = resolve_agent_config(config, agent_id)
    if not agent:
        return None

    return agent.memory_search


def resolve_agent_human_delay(config: Config, agent_id: str) -> int | None:
    """Resolve human delay setting for an agent.

    Args:
        config: The application configuration
        agent_id: The agent ID to resolve setting for

    Returns:
        Human delay in seconds if configured, None for default
    """
    agent = resolve_agent_config(config, agent_id)
    if not agent:
        return None

    return agent.human_delay


def resolve_agent_heartbeat(config: Config, agent_id: str) -> int | None:
    """Resolve heartbeat interval for an agent.

    Args:
        config: The application configuration
        agent_id: The agent ID to resolve setting for

    Returns:
        Heartbeat interval in seconds if configured, None for default
    """
    agent = resolve_agent_config(config, agent_id)
    if not agent:
        return None

    return agent.heartbeat
