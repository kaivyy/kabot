"""Typed models for Kabot's Python-native MCP runtime."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class McpServerDefinition:
    """Resolved MCP server definition ready for runtime attachment."""

    name: str
    transport: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class McpToolDescriptor:
    """A single tool exposed by an MCP server."""

    server_name: str
    tool_name: str
    description: str = ""
    parameters: dict[str, object] = field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )


@dataclass(frozen=True, slots=True)
class McpRegisteredTool:
    """Namespaced MCP tool entry stored in the registry."""

    qualified_name: str
    server_name: str
    tool_name: str
    alias_name: str = ""
    description: str = ""
    parameters: dict[str, object] = field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )


@dataclass(frozen=True, slots=True)
class McpResourceDescriptor:
    """A single resource exposed by an MCP server."""

    server_name: str
    uri: str
    name: str
    title: str = ""
    description: str = ""
    mime_type: str = ""
    size: int | None = None


@dataclass(frozen=True, slots=True)
class McpPromptDescriptor:
    """A single prompt exposed by an MCP server."""

    server_name: str
    prompt_name: str
    title: str = ""
    description: str = ""
    arguments: list[dict[str, object]] = field(default_factory=list)
