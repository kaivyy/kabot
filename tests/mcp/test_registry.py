from kabot.mcp.models import McpToolDescriptor
from kabot.mcp.registry import McpCapabilityRegistry


def test_registry_namespaces_mcp_tools():
    registry = McpCapabilityRegistry()
    registry.register_tool(
        McpToolDescriptor(
            server_name="github",
            tool_name="list_prs",
            description="List pull requests",
        )
    )

    names = registry.tool_names()
    assert names == ["mcp__github__list_prs"]
    tool = registry.get_tool("mcp__github__list_prs")
    assert tool.description == "List pull requests"
    assert tool.alias_name == "mcp.github.list_prs"


def test_registry_uses_api_safe_tool_names_and_preserves_alias():
    registry = McpCapabilityRegistry()
    registry.register_tool(
        McpToolDescriptor(
            server_name="local-echo",
            tool_name="echo.text",
            description="Echo text",
        )
    )

    names = registry.tool_names()
    assert names == ["mcp__local-echo__echo_text"]
    tool = registry.get_tool("mcp__local-echo__echo_text")
    assert tool.alias_name == "mcp.local-echo.echo.text"


def test_registry_preserves_descriptor_parameters():
    registry = McpCapabilityRegistry()
    registry.register_tool(
        McpToolDescriptor(
            server_name="local_echo",
            tool_name="echo",
            description="Echo text",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        )
    )

    tool = registry.get_tool("mcp__local_echo__echo")
    assert tool.parameters["properties"]["text"]["type"] == "string"
    assert tool.parameters["required"] == ["text"]
