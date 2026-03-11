import pytest

from kabot.agent.tools.registry import ToolRegistry
from kabot.mcp.models import McpRegisteredTool
from kabot.mcp.runtime import register_mcp_tools
from kabot.mcp.session_state import activate_mcp_runtime


class _FakeRuntime:
    async def call_tool(self, server_name: str, tool_name: str, arguments: dict | None = None):
        return {
            "is_error": False,
            "text": f"{server_name}.{tool_name}:{arguments or {}}",
            "structured_content": None,
        }


def test_register_mcp_tools_adds_namespaced_tools_to_registry():
    registry = ToolRegistry()
    register_mcp_tools(
        registry,
        runtime_resolver=lambda: _FakeRuntime(),
        registered_tools=[
            McpRegisteredTool(
                qualified_name="mcp__github__list_prs",
                alias_name="mcp.github.list_prs",
                server_name="github",
                tool_name="list_prs",
                description="List pull requests",
            )
        ],
    )

    assert registry.has("mcp__github__list_prs") is True


@pytest.mark.asyncio
async def test_registered_mcp_tool_executes_using_active_runtime():
    registry = ToolRegistry()
    register_mcp_tools(
        registry,
        runtime_resolver=lambda: _FakeRuntime(),
        registered_tools=[
            McpRegisteredTool(
                qualified_name="mcp__github__list_prs",
                alias_name="mcp.github.list_prs",
                server_name="github",
                tool_name="list_prs",
                description="List pull requests",
                parameters={"type": "object", "properties": {}},
            )
        ],
    )

    with activate_mcp_runtime(_FakeRuntime()):
        result = await registry.execute("mcp__github__list_prs", {})

    assert "github.list_prs" in result
