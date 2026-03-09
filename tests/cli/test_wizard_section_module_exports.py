from kabot.cli.wizard.sections import (
    channels,
    channels_helpers,
    model_auth,
    model_auth_helpers,
    tools_gateway_skills,
    tools_gateway_skills_helpers,
)


def test_channels_section_reexports_helper_functions():
    assert channels._prompt_secret_value is channels_helpers._prompt_secret_value
    assert channels._ensure_agent_exists is channels_helpers._ensure_agent_exists


def test_model_auth_section_reexports_helper_functions():
    assert model_auth._sync_provider_credentials_from_disk is model_auth_helpers._sync_provider_credentials_from_disk
    assert model_auth._apply_auto_default_model_chain is model_auth_helpers._apply_auto_default_model_chain


def test_tools_gateway_skills_section_reexports_helper_functions():
    assert tools_gateway_skills._detect_skill_auth_hint is tools_gateway_skills_helpers._detect_skill_auth_hint
    assert tools_gateway_skills._inject_skill_persona is tools_gateway_skills_helpers._inject_skill_persona
