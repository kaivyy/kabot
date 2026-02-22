
def test_registry_initialization(tmp_path):
    from kabot.agent.agent_registry import AgentRegistry

    registry_path = tmp_path / "agents" / "registry.json"
    registry = AgentRegistry(registry_path)

    assert registry_path.exists()
    agents = registry.list_agents()
    assert agents == []

def test_register_agent(tmp_path):
    from kabot.agent.agent_registry import AgentRegistry

    registry = AgentRegistry(tmp_path / "registry.json")
    registry.register("work", "Work Agent", "openai/gpt-4o", "~/.kabot/workspace-work")

    agent = registry.get("work")
    assert agent["id"] == "work"
    assert agent["model"] == "openai/gpt-4o"
