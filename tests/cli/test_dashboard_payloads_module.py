from kabot.cli import commands


def test_commands_reexports_dashboard_payload_helpers_from_dedicated_module():
    from kabot.cli import dashboard_payloads

    assert commands._build_dashboard_command_surface is dashboard_payloads._build_dashboard_command_surface
    assert commands._build_dashboard_config_summary is dashboard_payloads._build_dashboard_config_summary
    assert commands._build_dashboard_status_payload is dashboard_payloads._build_dashboard_status_payload
    assert commands._compose_model_override is dashboard_payloads._compose_model_override
    assert commands._parse_model_fallbacks is dashboard_payloads._parse_model_fallbacks
