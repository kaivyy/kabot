import pytest
from pathlib import Path

@pytest.mark.asyncio
async def test_full_multi_agent_flow(tmp_path):
    """Test complete multi-agent flow from config to routing."""
    from kabot.config.schema import Config, AgentsConfig, AgentConfig, AgentBinding
    from kabot.routing.bindings import resolve_agent_route
    from kabot.session.session_key import build_agent_session_key
    from kabot.agent.agent_scope import resolve_agent_workspace, resolve_agent_model

    # Setup config
    config = Config(
        agents=AgentsConfig(
            agents=[
                AgentConfig(id="work", name="Work", model="openai/gpt-4o", workspace=str(tmp_path / "work")),
                AgentConfig(id="personal", name="Personal", model="anthropic/claude-sonnet-4-5", default=True)
            ],
            bindings=[
                AgentBinding(agent_id="work", channel="telegram"),
                AgentBinding(agent_id="personal", channel="whatsapp")
            ]
        )
    )

    # Test routing
    agent_id = resolve_agent_route(config, "telegram", "123")
    assert agent_id == "work"

    # Test session key
    session_key = build_agent_session_key(agent_id, "telegram", "123")
    assert session_key == "agent:work:telegram:123"

    # Test workspace resolution
    workspace = resolve_agent_workspace(config, agent_id)
    assert "work" in str(workspace)

    # Test model resolution
    model = resolve_agent_model(config, agent_id)
    assert model == "openai/gpt-4o"
