"""Tests for agent scope resolution."""

def test_resolve_default_agent():
    from kabot.agent.agent_scope import resolve_default_agent_id
    from kabot.config.schema import Config, AgentsConfig, AgentConfig

    config = Config(agents=AgentsConfig(agents=[
        AgentConfig(id="work", default=True),
        AgentConfig(id="personal")
    ]))

    assert resolve_default_agent_id(config) == "work"


def test_resolve_default_agent_fallback():
    """Test that 'main' is returned when no agent has default=True."""
    from kabot.agent.agent_scope import resolve_default_agent_id
    from kabot.config.schema import Config, AgentsConfig, AgentConfig

    config = Config(agents=AgentsConfig(agents=[
        AgentConfig(id="work"),
        AgentConfig(id="personal")
    ]))

    assert resolve_default_agent_id(config) == "main"


def test_resolve_agent_workspace():
    from kabot.agent.agent_scope import resolve_agent_workspace
    from kabot.config.schema import Config, AgentsConfig, AgentConfig

    config = Config(agents=AgentsConfig(agents=[
        AgentConfig(id="work", workspace="~/.kabot/workspace-work")
    ]))

    workspace = resolve_agent_workspace(config, "work")
    assert "workspace-work" in str(workspace)


def test_resolve_agent_workspace_default():
    """Test that default workspace is provided when agent has no workspace configured."""
    from kabot.agent.agent_scope import resolve_agent_workspace
    from kabot.config.schema import Config, AgentsConfig, AgentConfig

    config = Config(agents=AgentsConfig(agents=[
        AgentConfig(id="work")
    ]))

    workspace = resolve_agent_workspace(config, "work")
    assert "workspace-work" in str(workspace)


def test_resolve_agent_model():
    from kabot.agent.agent_scope import resolve_agent_model
    from kabot.config.schema import Config, AgentsConfig, AgentConfig

    config = Config(agents=AgentsConfig(agents=[
        AgentConfig(id="work", model="anthropic/claude-opus-4-5")
    ]))

    model = resolve_agent_model(config, "work")
    assert model == "anthropic/claude-opus-4-5"


def test_resolve_agent_model_none():
    """Test that None is returned when agent has no model configured."""
    from kabot.agent.agent_scope import resolve_agent_model
    from kabot.config.schema import Config, AgentsConfig, AgentConfig

    config = Config(agents=AgentsConfig(agents=[
        AgentConfig(id="work")
    ]))

    model = resolve_agent_model(config, "work")
    assert model is None


def test_resolve_agent_config():
    """Test resolving agent config by ID."""
    from kabot.agent.agent_scope import resolve_agent_config
    from kabot.config.schema import Config, AgentsConfig, AgentConfig

    config = Config(agents=AgentsConfig(agents=[
        AgentConfig(id="work", name="Work Agent"),
        AgentConfig(id="personal", name="Personal Agent")
    ]))

    agent = resolve_agent_config(config, "work")
    assert agent is not None
    assert agent.id == "work"
    assert agent.name == "Work Agent"


def test_resolve_agent_config_not_found():
    """Test that None is returned when agent is not found."""
    from kabot.agent.agent_scope import resolve_agent_config
    from kabot.config.schema import Config, AgentsConfig, AgentConfig

    config = Config(agents=AgentsConfig(agents=[
        AgentConfig(id="work")
    ]))

    agent = resolve_agent_config(config, "nonexistent")
    assert agent is None
