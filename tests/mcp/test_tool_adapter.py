from __future__ import annotations

import pytest

from kabot.mcp.models import McpRegisteredTool


class _FakeRuntime:
    async def call_tool(self, server_name: str, tool_name: str, arguments: dict | None = None):
        return {
            "is_error": False,
            "text": f"{server_name}.{tool_name}:{arguments or {}}",
            "structured_content": {"ok": True},
        }


@pytest.mark.asyncio
async def test_mcp_runtime_tool_exposes_schema_and_executes():
    from kabot.mcp.tool_adapter import McpRuntimeTool

    tool = McpRuntimeTool(
        runtime=_FakeRuntime(),
        registered_tool=McpRegisteredTool(
            qualified_name="mcp__github__list_prs",
            alias_name="mcp.github.list_prs",
            server_name="github",
            tool_name="list_prs",
            description="List pull requests",
            parameters={
                "type": "object",
                "properties": {
                    "state": {"type": "string"},
                },
            },
        ),
    )

    assert tool.name == "mcp__github__list_prs"
    assert "List pull requests" in tool.description
    assert "mcp.github.list_prs" in tool.description
    assert tool.parameters["type"] == "object"

    result = await tool.execute(state="open")
    assert "github.list_prs" in result
    assert "open" in result
