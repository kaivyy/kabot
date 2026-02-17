def test_role_definitions():
    from kabot.agent.role_manager import AGENT_ROLES

    assert "master" in AGENT_ROLES
    assert "brainstorming" in AGENT_ROLES
    assert "executor" in AGENT_ROLES
    assert "verifier" in AGENT_ROLES

def test_get_role_config():
    from kabot.agent.role_manager import get_role_config

    config = get_role_config("master")
    assert config["default_model"] == "openai/gpt-4o"
    assert "planning" in config["capabilities"]
