from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from kabot.mcp.models import McpServerDefinition


class _FakeSession:
    def __init__(self) -> None:
        self.initialized = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def initialize(self):
        self.initialized = True

    async def list_tools(self):
        class _Result:
            def __init__(self) -> None:
                self.tools = []

        return _Result()

    async def list_resources(self):
        class _Result:
            def __init__(self) -> None:
                self.resources = [
                    {
                        "name": "Field Guide",
                        "uri": "memory://field-guide",
                        "mimeType": "text/markdown",
                    }
                ]

        return _Result()

    async def read_resource(self, uri):
        class _Result:
            def __init__(self, resource_uri: str) -> None:
                self.contents = [{"uri": resource_uri, "text": "Field guide body"}]

        return _Result(str(uri))

    async def list_prompts(self):
        class _Result:
            def __init__(self) -> None:
                self.prompts = [
                    {
                        "name": "briefing",
                        "description": "Mission briefing",
                        "arguments": [{"name": "goal", "required": True}],
                    }
                ]

        return _Result()

    async def get_prompt(self, name: str, arguments: dict | None = None):
        class _Result:
            def __init__(self, prompt_name: str, payload: dict | None) -> None:
                goal = (payload or {}).get("goal", "unknown")
                self.description = f"{prompt_name} template"
                self.messages = [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": f"Prompt for {goal}",
                        },
                    }
                ]

        return _Result(name, arguments)

    async def call_tool(self, name: str, arguments: dict | None = None):
        class _Result:
            def __init__(self, tool_name: str, payload: dict | None) -> None:
                self.content = [{"type": "text", "text": f"{tool_name}:{payload or {}}"}]
                self.structuredContent = None
                self.isError = False

        return _Result(name, arguments)


@pytest.mark.asyncio
async def test_stdio_transport_initializes_session(monkeypatch):
    from kabot.mcp.transports.stdio import StdioMcpTransport

    captured: dict[str, object] = {}

    class _FakeServerParams:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    @asynccontextmanager
    async def _fake_stdio_client(server_params):
        captured["server_params"] = server_params
        yield ("read", "write")

    sdk = {
        "ClientSession": lambda read, write: _FakeSession(),
        "StdioServerParameters": _FakeServerParams,
        "stdio_client": _fake_stdio_client,
    }

    monkeypatch.setattr("kabot.mcp.transports.stdio._load_stdio_sdk", lambda: sdk)

    transport = StdioMcpTransport(
        McpServerDefinition(
            name="local_tools",
            transport="stdio",
            command="python",
            args=["-m", "server"],
            env={"FOO": "bar"},
        )
    )

    await transport.connect()
    result = await transport.call_tool("ping", {"ok": True})
    await transport.close()

    assert captured["command"] == "python"
    assert captured["args"] == ["-m", "server"]
    assert captured["env"] == {"FOO": "bar"}
    assert result["is_error"] is False
    assert "ping" in result["text"]

    resources = await transport.list_resources()
    resource = await transport.read_resource("memory://field-guide")
    prompts = await transport.list_prompts()
    prompt = await transport.get_prompt("briefing", {"goal": "evacuation"})

    assert resources[0]["uri"] == "memory://field-guide"
    assert resource["contents"][0]["text"] == "Field guide body"
    assert prompts[0]["name"] == "briefing"
    assert "evacuation" in prompt["text"]


@pytest.mark.asyncio
async def test_streamable_http_transport_initializes_session(monkeypatch):
    from kabot.mcp.transports.streamable_http import StreamableHttpMcpTransport

    captured: dict[str, object] = {}

    @asynccontextmanager
    async def _fake_streamable_http_client(url: str, http_client=None):
        captured["url"] = url
        captured["headers"] = dict(http_client.headers)
        yield ("read", "write", lambda: "session-1")

    class _FakeAsyncClient:
        def __init__(self, headers=None):
            self.headers = headers or {}

    sdk = {
        "ClientSession": lambda read, write: _FakeSession(),
        "AsyncClient": _FakeAsyncClient,
        "streamable_http_client": _fake_streamable_http_client,
    }

    monkeypatch.setattr("kabot.mcp.transports.streamable_http._load_streamable_http_sdk", lambda: sdk)

    transport = StreamableHttpMcpTransport(
        McpServerDefinition(
            name="remote_tools",
            transport="streamable_http",
            url="https://example.com/mcp",
            headers={"Authorization": "Bearer test"},
        )
    )

    await transport.connect()
    result = await transport.call_tool("echo", {"hello": "world"})
    await transport.close()

    assert captured["url"] == "https://example.com/mcp"
    assert captured["headers"] == {"Authorization": "Bearer test"}
    assert result["is_error"] is False
    assert "echo" in result["text"]

    resources = await transport.list_resources()
    resource = await transport.read_resource("memory://field-guide")
    prompts = await transport.list_prompts()
    prompt = await transport.get_prompt("briefing", {"goal": "survey"})

    assert resources[0]["uri"] == "memory://field-guide"
    assert resource["contents"][0]["text"] == "Field guide body"
    assert prompts[0]["name"] == "briefing"
    assert "survey" in prompt["text"]
