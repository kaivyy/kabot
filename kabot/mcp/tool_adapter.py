"""Tool adapter that exposes MCP tools through Kabot's Tool interface."""

from __future__ import annotations

import json
from typing import Any, Callable

from kabot.agent.tools.base import Tool
from kabot.mcp.models import McpRegisteredTool


class McpRuntimeTool(Tool):
    """Adapt a registered MCP tool into a Kabot runtime tool."""

    def __init__(
        self,
        *,
        registered_tool: McpRegisteredTool,
        runtime: Any | None = None,
        runtime_resolver: Callable[[], Any | None] | None = None,
    ):
        if runtime is None and runtime_resolver is None:
            raise ValueError("runtime or runtime_resolver is required for McpRuntimeTool")
        self._runtime = runtime
        self._runtime_resolver = runtime_resolver
        self._registered_tool = registered_tool

    @property
    def name(self) -> str:
        return self._registered_tool.qualified_name

    @property
    def description(self) -> str:
        alias = str(self._registered_tool.alias_name or "").strip()
        description = str(self._registered_tool.description or "").strip()
        if alias and description:
            return f"{description}\nUser-facing alias: {alias}"
        if alias:
            return f"User-facing alias: {alias}"
        return description

    @property
    def parameters(self) -> dict[str, Any]:
        return dict(self._registered_tool.parameters or {"type": "object", "properties": {}})

    async def execute(self, **kwargs: Any) -> str:
        runtime = self._runtime
        if runtime is None and self._runtime_resolver is not None:
            runtime = self._runtime_resolver()
        if runtime is None:
            raise RuntimeError(
                f"No active MCP runtime is bound for tool '{self._registered_tool.qualified_name}'"
            )
        result = await runtime.call_tool(
            self._registered_tool.server_name,
            self._registered_tool.tool_name,
            kwargs,
        )
        text = str(result.get("text", ""))
        structured = result.get("structured_content")
        if structured is None:
            return text
        return f"{text}\nStructured: {json.dumps(structured, ensure_ascii=False)}"
