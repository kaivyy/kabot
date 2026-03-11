"""Session-scoped MCP runtime skeleton."""

from __future__ import annotations

import json
from collections.abc import Callable

from loguru import logger

from kabot.agent.tools.registry import ToolRegistry
from kabot.mcp.models import (
    McpPromptDescriptor,
    McpResourceDescriptor,
    McpServerDefinition,
)
from kabot.mcp.registry import McpCapabilityRegistry
from kabot.mcp.session_state import McpSessionState
from kabot.mcp.tool_adapter import McpRuntimeTool
from kabot.mcp.transports.stdio import StdioMcpTransport
from kabot.mcp.transports.streamable_http import StreamableHttpMcpTransport


def build_transport_for_server(definition: McpServerDefinition):
    """Build the correct transport wrapper for an MCP server definition."""

    if definition.transport == "stdio":
        return StdioMcpTransport(definition)
    if definition.transport == "streamable_http":
        return StreamableHttpMcpTransport(definition)
    raise ValueError(f"Unsupported MCP transport: {definition.transport}")


def register_mcp_tools(
    registry: ToolRegistry,
    *,
    runtime: object | None = None,
    runtime_resolver: Callable[[], object | None] | None = None,
    registered_tools: list,
) -> None:
    """Register MCP-backed tools into a Kabot ToolRegistry."""

    for registered_tool in registered_tools:
        if registry.has(registered_tool.qualified_name):
            continue
        registry.register(
            McpRuntimeTool(
                runtime=runtime,
                runtime_resolver=runtime_resolver,
                registered_tool=registered_tool,
            )
        )


class McpSessionRuntime:
    """Track attached MCP servers for a session without opening transports yet."""

    def __init__(self, session_id: str) -> None:
        self.state = McpSessionState(session_id=session_id)
        self.registry = McpCapabilityRegistry()
        self._transports: dict[str, object] = {}
        self._tool_cache: dict[str, list] = {}
        self._resource_cache: dict[str, list[McpResourceDescriptor]] = {}
        self._prompt_cache: dict[str, list[McpPromptDescriptor]] = {}
        self._resource_read_cache: dict[tuple[str, str], dict] = {}
        self._prompt_render_cache: dict[tuple[str, str, str], dict] = {}

    def attach(self, definition: McpServerDefinition) -> None:
        self.state.servers[definition.name] = definition

    def has_server(self, server_name: str) -> bool:
        return server_name in self.state.servers

    def attached_server_names(self) -> list[str]:
        return sorted(self.state.servers.keys())

    async def get_transport(self, server_name: str):
        transport = self._transports.get(server_name)
        if transport is not None:
            return transport
        definition = self.state.servers[server_name]
        transport = build_transport_for_server(definition)
        self._transports[server_name] = transport
        return transport

    async def list_tools(self, server_name: str) -> list:
        cached = self._tool_cache.get(server_name)
        if cached is not None:
            return list(cached)
        transport = await self.get_transport(server_name)
        tools = await transport.list_tools()
        normalized = []
        for item in tools:
            if hasattr(item, "server_name") and hasattr(item, "tool_name"):
                descriptor = self.registry.register_tool(item)
            else:
                descriptor = self.registry.register_tool_descriptor_like(server_name, item)
            normalized.append(descriptor)
        self._tool_cache[server_name] = list(normalized)
        return normalized

    async def list_resources(self, server_name: str) -> list[McpResourceDescriptor]:
        cached = self._resource_cache.get(server_name)
        if cached is not None:
            return list(cached)
        transport = await self.get_transport(server_name)
        resources = await transport.list_resources()
        normalized: list[McpResourceDescriptor] = []
        for item in resources:
            normalized.append(
                McpResourceDescriptor(
                    server_name=server_name,
                    uri=str(getattr(item, "uri", None) if not isinstance(item, dict) else item.get("uri", "") or ""),
                    name=str(getattr(item, "name", None) if not isinstance(item, dict) else item.get("name", "") or ""),
                    title=str(getattr(item, "title", None) if not isinstance(item, dict) else item.get("title", "") or ""),
                    description=str(
                        getattr(item, "description", None)
                        if not isinstance(item, dict)
                        else item.get("description", "")
                        or ""
                    ),
                    mime_type=str(
                        getattr(item, "mimeType", None)
                        if not isinstance(item, dict)
                        else item.get("mimeType", "")
                        or ""
                    ),
                    size=(getattr(item, "size", None) if not isinstance(item, dict) else item.get("size")),
                )
            )
        self._resource_cache[server_name] = list(normalized)
        return normalized

    async def read_resource(self, server_name: str, uri: str) -> dict:
        cache_key = (server_name, str(uri))
        cached = self._resource_read_cache.get(cache_key)
        if cached is not None:
            return dict(cached)
        transport = await self.get_transport(server_name)
        payload = await transport.read_resource(uri)
        self._resource_read_cache[cache_key] = dict(payload)
        return payload

    async def list_prompts(self, server_name: str) -> list[McpPromptDescriptor]:
        cached = self._prompt_cache.get(server_name)
        if cached is not None:
            return list(cached)
        transport = await self.get_transport(server_name)
        prompts = await transport.list_prompts()
        normalized: list[McpPromptDescriptor] = []
        for item in prompts:
            normalized.append(
                McpPromptDescriptor(
                    server_name=server_name,
                    prompt_name=str(
                        getattr(item, "name", None) if not isinstance(item, dict) else item.get("name", "") or ""
                    ),
                    title=str(getattr(item, "title", None) if not isinstance(item, dict) else item.get("title", "") or ""),
                    description=str(
                        getattr(item, "description", None)
                        if not isinstance(item, dict)
                        else item.get("description", "")
                        or ""
                    ),
                    arguments=list(
                        getattr(item, "arguments", None) if not isinstance(item, dict) else item.get("arguments", [])
                        or []
                    ),
                )
            )
        self._prompt_cache[server_name] = list(normalized)
        return normalized

    async def get_prompt(
        self, server_name: str, prompt_name: str, arguments: dict[str, str] | None = None
    ) -> dict:
        serialized_args = json.dumps(arguments or {}, ensure_ascii=False, sort_keys=True)
        cache_key = (server_name, prompt_name, serialized_args)
        cached = self._prompt_render_cache.get(cache_key)
        if cached is not None:
            return dict(cached)
        transport = await self.get_transport(server_name)
        payload = await transport.get_prompt(prompt_name, arguments)
        self._prompt_render_cache[cache_key] = dict(payload)
        return payload

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict | None = None):
        transport = await self.get_transport(server_name)
        return await transport.call_tool(tool_name, arguments)

    async def close(self) -> None:
        for transport in self._transports.values():
            close = getattr(transport, "close", None)
            if close is not None:
                await close()
        self._transports.clear()
        self._tool_cache.clear()
        self._resource_cache.clear()
        self._prompt_cache.clear()
        self._resource_read_cache.clear()
        self._prompt_render_cache.clear()


async def safe_list_server_tools(runtime: McpSessionRuntime, server_name: str) -> list:
    """Best-effort tool listing for a single MCP server."""

    try:
        return await runtime.list_tools(server_name)
    except Exception as exc:
        logger.warning(f"MCP tool discovery skipped for server '{server_name}': {exc}")
        return []
