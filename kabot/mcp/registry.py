"""Namespaced MCP capability registry."""

from __future__ import annotations

import re

from kabot.mcp.models import McpRegisteredTool, McpToolDescriptor


def mcp_tool_alias_name(server_name: str, tool_name: str) -> str:
    return f"mcp.{server_name}.{tool_name}"


def _sanitize_mcp_name_part(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "").strip())
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "tool"


def qualify_mcp_tool_name(server_name: str, tool_name: str) -> str:
    return f"mcp__{_sanitize_mcp_name_part(server_name)}__{_sanitize_mcp_name_part(tool_name)}"


class McpCapabilityRegistry:
    """Track MCP tools exposed to a Kabot session/runtime."""

    def __init__(self) -> None:
        self._tools: dict[str, McpRegisteredTool] = {}

    def register_tool(self, descriptor: McpToolDescriptor) -> McpRegisteredTool:
        qualified_name = qualify_mcp_tool_name(descriptor.server_name, descriptor.tool_name)
        if qualified_name in self._tools:
            return self._tools[qualified_name]
        registered = McpRegisteredTool(
            qualified_name=qualified_name,
            alias_name=mcp_tool_alias_name(descriptor.server_name, descriptor.tool_name),
            server_name=descriptor.server_name,
            tool_name=descriptor.tool_name,
            description=descriptor.description,
            parameters=getattr(descriptor, "parameters", None)
            or getattr(descriptor, "inputSchema", None)
            or {"type": "object", "properties": {}},
        )
        self._tools[qualified_name] = registered
        return registered

    def register_tool_descriptor_like(self, server_name: str, item: object) -> McpRegisteredTool:
        descriptor = McpToolDescriptor(
            server_name=server_name,
            tool_name=str(getattr(item, "tool_name", None) or getattr(item, "name")),
            description=str(getattr(item, "description", "") or ""),
            parameters=getattr(item, "parameters", None)
            or getattr(item, "inputSchema", None)
            or {"type": "object", "properties": {}},
        )
        return self.register_tool(descriptor)

    def tool_names(self) -> list[str]:
        return sorted(self._tools.keys())

    def get_tool(self, qualified_name: str) -> McpRegisteredTool:
        return self._tools[qualified_name]
