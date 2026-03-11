"""Real Streamable HTTP MCP transport wrapper using the official Python MCP SDK."""

from __future__ import annotations

from contextlib import AsyncExitStack
from importlib import import_module
from typing import Any

from kabot.mcp.models import McpServerDefinition
from kabot.mcp.transports.stdio import (
    _flatten_call_result,
    _flatten_get_prompt_result,
    _flatten_read_resource_result,
    _object_or_dict_value,
)


def _load_streamable_http_sdk() -> dict[str, Any]:
    mcp_module = import_module("mcp")
    streamable_http_module = import_module("mcp.client.streamable_http")
    httpx_module = import_module("httpx")
    return {
        "ClientSession": getattr(mcp_module, "ClientSession"),
        "AsyncClient": getattr(httpx_module, "AsyncClient"),
        "streamable_http_client": getattr(streamable_http_module, "streamable_http_client"),
    }


class StreamableHttpMcpTransport:
    """Connect to a Streamable HTTP MCP server and expose core operations."""

    def __init__(self, definition: McpServerDefinition):
        self.definition = definition
        self._stack: AsyncExitStack | None = None
        self._session: Any = None

    async def connect(self) -> None:
        if self._session is not None:
            return
        sdk = _load_streamable_http_sdk()
        stack = AsyncExitStack()
        http_client = sdk["AsyncClient"](headers=self.definition.headers or None)
        read_stream, write_stream, _session_id = await stack.enter_async_context(
            sdk["streamable_http_client"](self.definition.url, http_client=http_client)
        )
        session = await stack.enter_async_context(sdk["ClientSession"](read_stream, write_stream))
        await session.initialize()
        self._stack = stack
        self._session = session

    async def close(self) -> None:
        if self._stack is None:
            return
        await self._stack.aclose()
        self._stack = None
        self._session = None

    async def list_tools(self) -> list[Any]:
        await self.connect()
        result = await self._session.list_tools()
        return list(getattr(result, "tools", []) or [])

    async def list_resources(self) -> list[dict[str, Any]]:
        await self.connect()
        result = await self._session.list_resources()
        resources = []
        for item in getattr(result, "resources", []) or []:
            resources.append(
                {
                    "name": str(_object_or_dict_value(item, "name", "") or ""),
                    "title": str(_object_or_dict_value(item, "title", "") or ""),
                    "uri": str(_object_or_dict_value(item, "uri", "") or ""),
                    "description": str(_object_or_dict_value(item, "description", "") or ""),
                    "mimeType": str(_object_or_dict_value(item, "mimeType", "") or ""),
                    "size": _object_or_dict_value(item, "size"),
                }
            )
        return resources

    async def read_resource(self, uri: str) -> dict[str, Any]:
        await self.connect()
        result = await self._session.read_resource(uri)
        return _flatten_read_resource_result(result)

    async def list_prompts(self) -> list[dict[str, Any]]:
        await self.connect()
        result = await self._session.list_prompts()
        prompts = []
        for item in getattr(result, "prompts", []) or []:
            raw_arguments = _object_or_dict_value(item, "arguments", []) or []
            arguments = []
            for argument in raw_arguments:
                arguments.append(
                    {
                        "name": str(_object_or_dict_value(argument, "name", "") or ""),
                        "description": str(_object_or_dict_value(argument, "description", "") or ""),
                        "required": bool(_object_or_dict_value(argument, "required", False)),
                    }
                )
            prompts.append(
                {
                    "name": str(_object_or_dict_value(item, "name", "") or ""),
                    "title": str(_object_or_dict_value(item, "title", "") or ""),
                    "description": str(_object_or_dict_value(item, "description", "") or ""),
                    "arguments": arguments,
                }
            )
        return prompts

    async def get_prompt(self, name: str, arguments: dict[str, str] | None = None) -> dict[str, Any]:
        await self.connect()
        result = await self._session.get_prompt(name, arguments)
        return _flatten_get_prompt_result(result)

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        await self.connect()
        result = await self._session.call_tool(tool_name, arguments)
        return _flatten_call_result(result)
