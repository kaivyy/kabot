import pytest

from kabot.mcp.models import McpServerDefinition
from kabot.mcp.runtime import McpSessionRuntime


def test_session_runtime_tracks_attached_servers():
    runtime = McpSessionRuntime(session_id="s1")
    runtime.attach(
        McpServerDefinition(
            name="github",
            transport="streamable_http",
            url="https://example.com/mcp",
        )
    )

    assert runtime.attached_server_names() == ["github"]
    assert runtime.has_server("github") is True


@pytest.mark.asyncio
async def test_session_runtime_connects_and_lists_tools(monkeypatch):
    from kabot.mcp.models import McpToolDescriptor

    class _FakeTransport:
        def __init__(self, definition):
            self.definition = definition

        async def list_tools(self):
            return [
                McpToolDescriptor(
                    server_name=self.definition.name,
                    tool_name="list_prs",
                    description="List pull requests",
                )
            ]

        async def call_tool(self, tool_name, arguments=None):
            return {"is_error": False, "text": f"{tool_name}:{arguments or {}}", "structured_content": None}

        async def close(self):
            return None

    monkeypatch.setattr("kabot.mcp.runtime.build_transport_for_server", lambda definition: _FakeTransport(definition))

    runtime = McpSessionRuntime(session_id="s1")
    runtime.attach(
        McpServerDefinition(
            name="github",
            transport="streamable_http",
            url="https://example.com/mcp",
        )
    )

    tools = await runtime.list_tools("github")
    result = await runtime.call_tool("github", "list_prs", {"state": "open"})
    await runtime.close()

    assert [tool.tool_name for tool in tools] == ["list_prs"]
    assert "list_prs" in result["text"]


@pytest.mark.asyncio
async def test_session_runtime_lists_resources_and_prompts(monkeypatch):
    class _FakeTransport:
        def __init__(self, definition):
            self.definition = definition

        async def list_tools(self):
            return []

        async def list_resources(self):
            return [
                {
                    "name": "Field Guide",
                    "uri": "memory://field-guide",
                    "description": "Field guide notes",
                    "mimeType": "text/markdown",
                }
            ]

        async def read_resource(self, uri):
            return {
                "text": "# Field Guide\n\nMove carefully.",
                "contents": [{"uri": str(uri), "text": "# Field Guide\n\nMove carefully."}],
            }

        async def list_prompts(self):
            return [
                {
                    "name": "briefing",
                    "description": "Create a mission briefing",
                    "arguments": [{"name": "goal", "required": True}],
                }
            ]

        async def get_prompt(self, name, arguments=None):
            return {
                "description": "Mission briefing template",
                "messages": [
                    {
                        "role": "user",
                        "text": f"Briefing for {arguments['goal']}",
                    }
                ],
                "text": f"Briefing for {arguments['goal']}",
            }

        async def call_tool(self, tool_name, arguments=None):
            return {"is_error": False, "text": "", "structured_content": None}

        async def close(self):
            return None

    monkeypatch.setattr("kabot.mcp.runtime.build_transport_for_server", lambda definition: _FakeTransport(definition))

    runtime = McpSessionRuntime(session_id="s1")
    runtime.attach(
        McpServerDefinition(
            name="ops",
            transport="streamable_http",
            url="https://example.com/mcp",
        )
    )

    resources = await runtime.list_resources("ops")
    resource = await runtime.read_resource("ops", "memory://field-guide")
    prompts = await runtime.list_prompts("ops")
    prompt = await runtime.get_prompt("ops", "briefing", {"goal": "evacuation"})
    await runtime.close()

    assert resources[0].uri == "memory://field-guide"
    assert resources[0].mime_type == "text/markdown"
    assert "Field Guide" in resource["text"]
    assert prompts[0].prompt_name == "briefing"
    assert prompts[0].arguments[0]["name"] == "goal"
    assert "evacuation" in prompt["text"]


@pytest.mark.asyncio
async def test_session_runtime_caches_capability_snapshots_and_payloads(monkeypatch):
    call_counts = {
        "list_tools": 0,
        "list_resources": 0,
        "read_resource": 0,
        "list_prompts": 0,
        "get_prompt": 0,
    }

    class _FakeTransport:
        def __init__(self, definition):
            self.definition = definition

        async def list_tools(self):
            call_counts["list_tools"] += 1
            return []

        async def list_resources(self):
            call_counts["list_resources"] += 1
            return [{"name": "Field Guide", "uri": "memory://field-guide"}]

        async def read_resource(self, uri):
            call_counts["read_resource"] += 1
            return {"text": f"resource:{uri}"}

        async def list_prompts(self):
            call_counts["list_prompts"] += 1
            return [{"name": "briefing", "arguments": []}]

        async def get_prompt(self, name, arguments=None):
            call_counts["get_prompt"] += 1
            return {"text": f"{name}:{arguments or {}}"}

        async def call_tool(self, tool_name, arguments=None):
            return {"is_error": False, "text": "", "structured_content": None}

        async def close(self):
            return None

    monkeypatch.setattr("kabot.mcp.runtime.build_transport_for_server", lambda definition: _FakeTransport(definition))

    runtime = McpSessionRuntime(session_id="s1")
    runtime.attach(
        McpServerDefinition(
            name="ops",
            transport="streamable_http",
            url="https://example.com/mcp",
        )
    )

    await runtime.list_tools("ops")
    await runtime.list_tools("ops")
    await runtime.list_resources("ops")
    await runtime.list_resources("ops")
    await runtime.read_resource("ops", "memory://field-guide")
    await runtime.read_resource("ops", "memory://field-guide")
    await runtime.list_prompts("ops")
    await runtime.list_prompts("ops")
    await runtime.get_prompt("ops", "briefing", {"goal": "evacuation"})
    await runtime.get_prompt("ops", "briefing", {"goal": "evacuation"})
    await runtime.close()

    assert call_counts == {
        "list_tools": 1,
        "list_resources": 1,
        "read_resource": 1,
        "list_prompts": 1,
        "get_prompt": 1,
    }
