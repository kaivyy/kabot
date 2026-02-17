"""Tests for agent configuration schema."""

import pytest


def test_agent_config_schema():
    """Test AgentConfig schema with all fields."""
    from kabot.config.schema import AgentConfig

    config = AgentConfig(
        id="work",
        name="Work Agent",
        model="openai/gpt-4o",
        workspace="~/.kabot/workspace-work"
    )
    assert config.id == "work"
    assert config.name == "Work Agent"
    assert config.model == "openai/gpt-4o"
    assert config.workspace == "~/.kabot/workspace-work"
    assert config.default is False


def test_agent_config_minimal():
    """Test AgentConfig with minimal required fields."""
    from kabot.config.schema import AgentConfig

    config = AgentConfig(id="personal")
    assert config.id == "personal"
    assert config.name == ""
    assert config.model is None
    assert config.workspace is None
    assert config.default is False


def test_agent_config_default_flag():
    """Test AgentConfig with default flag set."""
    from kabot.config.schema import AgentConfig

    config = AgentConfig(id="main", default=True)
    assert config.id == "main"
    assert config.default is True


def test_agents_config_with_list():
    """Test AgentsConfig with list of agents."""
    from kabot.config.schema import AgentsConfig, AgentConfig

    agents = AgentsConfig(
        agents=[
            AgentConfig(id="work", name="Work", model="openai/gpt-4o"),
            AgentConfig(id="personal", name="Personal", model="anthropic/claude-sonnet-4-5")
        ]
    )
    assert len(agents.agents) == 2
    assert agents.agents[0].id == "work"
    assert agents.agents[1].id == "personal"


def test_agents_config_empty_list():
    """Test AgentsConfig with empty list (default)."""
    from kabot.config.schema import AgentsConfig

    agents = AgentsConfig()
    assert len(agents.agents) == 0
    assert isinstance(agents.agents, list)
