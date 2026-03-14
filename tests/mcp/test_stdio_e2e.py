from __future__ import annotations

import sys
from textwrap import dedent

import pytest

from kabot.mcp.models import McpServerDefinition
from kabot.mcp.runtime import McpSessionRuntime


@pytest.mark.asyncio
async def test_stdio_runtime_talks_to_real_python_mcp_server(tmp_path):
    pytest.importorskip("mcp.server.fastmcp")
    pytest.importorskip("mcp.client.stdio")

    server_script = tmp_path / "mini_mcp_server.py"
    server_script.write_text(
        dedent(
            """
            from mcp.server.fastmcp import FastMCP

            app = FastMCP("Mini MCP")


            @app.tool()
            def echo(text: str) -> dict:
                return {"echo": text}


            @app.resource("memory://field-guide")
            def field_guide() -> str:
                return "# Field Guide\\n\\nStay on route."


            @app.prompt()
            def briefing(goal: str):
                return f"Mission goal: {goal}"


            if __name__ == "__main__":
                app.run("stdio")
            """
        ),
        encoding="utf-8",
    )

    runtime = McpSessionRuntime(session_id="s1")
    runtime.attach(
        McpServerDefinition(
            name="local",
            transport="stdio",
            command=sys.executable,
            args=[str(server_script)],
        )
    )

    tools = await runtime.list_tools("local")
    resources = await runtime.list_resources("local")
    resource = await runtime.read_resource("local", "memory://field-guide")
    prompts = await runtime.list_prompts("local")
    prompt = await runtime.get_prompt("local", "briefing", {"goal": "evacuation"})
    result = await runtime.call_tool("local", "echo", {"text": "halo"})
    await runtime.close()

    assert [tool.tool_name for tool in tools] == ["echo"]
    assert resources[0].uri == "memory://field-guide"
    assert "Stay on route." in resource["text"]
    assert prompts[0].prompt_name == "briefing"
    assert "evacuation" in prompt["text"]
    assert result["is_error"] is False
    assert "halo" in result["text"]
