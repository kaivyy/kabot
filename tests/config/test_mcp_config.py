from pydantic import ValidationError

from kabot.config.schema import Config


def test_mcp_defaults_are_disabled():
    cfg = Config()
    assert cfg.mcp.enabled is False
    assert cfg.mcp.servers == {}


def test_stdio_mcp_server_requires_command():
    try:
        Config.model_validate(
            {
                "mcp": {
                    "enabled": True,
                    "servers": {
                        "local": {
                            "transport": "stdio",
                        }
                    },
                }
            }
        )
    except ValidationError as exc:
        assert "command" in str(exc)
    else:
        raise AssertionError("Expected ValidationError")


def test_streamable_http_mcp_server_requires_url():
    try:
        Config.model_validate(
            {
                "mcp": {
                    "enabled": True,
                    "servers": {
                        "remote": {
                            "transport": "streamable_http",
                        }
                    },
                }
            }
        )
    except ValidationError as exc:
        assert "url" in str(exc)
    else:
        raise AssertionError("Expected ValidationError")
