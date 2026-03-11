from kabot.config.schema import Config
from kabot.mcp import McpSessionRuntime, resolve_mcp_server_definitions


def test_resolve_stdio_mcp_server_definition():
    cfg = Config.model_validate(
        {
            "mcp": {
                "enabled": True,
                "servers": {
                    "local_tools": {
                        "transport": "stdio",
                        "command": "python",
                        "args": ["-m", "example_server"],
                        "env": {"FOO": "bar"},
                    }
                },
            }
        }
    )

    resolved = resolve_mcp_server_definitions(cfg)
    assert [item.name for item in resolved] == ["local_tools"]
    assert resolved[0].transport == "stdio"
    assert resolved[0].command == "python"
    assert resolved[0].args == ["-m", "example_server"]
    assert resolved[0].env == {"FOO": "bar"}


def test_mcp_package_exports_stable_surface():
    assert McpSessionRuntime is not None
    assert callable(resolve_mcp_server_definitions)
