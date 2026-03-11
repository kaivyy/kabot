from typer.testing import CliRunner


def test_mcp_status_renders_configured_servers(monkeypatch):
    from kabot.cli.commands import app
    from kabot.config.schema import Config

    cfg = Config.model_validate(
        {
            "mcp": {
                "enabled": True,
                "servers": {
                    "local_echo": {
                        "transport": "stdio",
                        "command": "python",
                        "args": ["-m", "kabot.mcp.dev.echo_server"],
                    },
                    "remote_docs": {
                        "transport": "streamable_http",
                        "url": "https://example.test/mcp",
                    },
                },
            }
        }
    )

    monkeypatch.setattr("kabot.cli.commands_mcp.load_config", lambda: cfg)

    result = CliRunner().invoke(app, ["mcp", "status"])

    assert result.exit_code == 0
    assert "local_echo" in result.output
    assert "remote_docs" in result.output
    assert "stdio" in result.output
    assert "streamable_http" in result.output


def test_mcp_example_config_prints_json_snippet():
    from kabot.cli.commands import app

    result = CliRunner().invoke(app, ["mcp", "example-config"])

    assert result.exit_code == 0
    assert "\"mcp\"" in result.output
    assert "\"transport\": \"stdio\"" in result.output
    assert "\"transport\": \"streamable_http\"" in result.output


def test_mcp_inspect_renders_capabilities(monkeypatch):
    from kabot.cli.commands import app
    from kabot.config.schema import Config

    cfg = Config.model_validate(
        {
            "mcp": {
                "enabled": True,
                "servers": {
                    "local_echo": {
                        "transport": "stdio",
                        "command": "python",
                        "args": ["-m", "kabot.mcp.dev.echo_server"],
                    }
                },
            }
        }
    )

    monkeypatch.setattr("kabot.cli.commands_mcp.load_config", lambda: cfg)
    monkeypatch.setattr(
        "kabot.cli.commands_mcp.inspect_mcp_server_snapshot",
        lambda _cfg, _name: {
            "server_name": "local_echo",
            "tools": [{"name": "echo", "description": "Echo text"}],
            "resources": [{"name": "Field Guide", "uri": "memory://field-guide"}],
            "prompts": [{"name": "briefing", "description": "Mission briefing"}],
        },
    )

    result = CliRunner().invoke(app, ["mcp", "inspect", "local_echo"])

    assert result.exit_code == 0
    assert "local_echo" in result.output
    assert "echo" in result.output
    assert "memory://field-guide" in result.output
    assert "briefing" in result.output
