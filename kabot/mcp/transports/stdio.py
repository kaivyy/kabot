"""Real stdio MCP transport wrapper using the official Python MCP SDK."""

from __future__ import annotations

from contextlib import AsyncExitStack
from importlib import import_module
from typing import Any

from kabot.mcp.models import McpServerDefinition


def _load_stdio_sdk() -> dict[str, Any]:
    mcp_module = import_module("mcp")
    stdio_module = import_module("mcp.client.stdio")
    return {
        "ClientSession": getattr(mcp_module, "ClientSession"),
        "StdioServerParameters": getattr(stdio_module, "StdioServerParameters"),
        "stdio_client": getattr(stdio_module, "stdio_client"),
    }


def _flatten_call_result(result: Any) -> dict[str, Any]:
    text_parts: list[str] = []
    for block in getattr(result, "content", []) or []:
        if isinstance(block, dict):
            if block.get("type") == "text":
                text_parts.append(str(block.get("text", "")))
            else:
                text_parts.append(str(block))
            continue
        block_type = getattr(block, "type", None)
        if block_type == "text":
            text_parts.append(str(getattr(block, "text", "")))
        else:
            text_parts.append(str(block))
    return {
        "is_error": bool(getattr(result, "isError", False)),
        "text": "\n".join(part for part in text_parts if part).strip(),
        "structured_content": getattr(result, "structuredContent", None),
    }


def _object_or_dict_value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _flatten_resource_content_item(item: Any) -> dict[str, Any]:
    return {
        "uri": str(_object_or_dict_value(item, "uri", "") or ""),
        "mime_type": str(_object_or_dict_value(item, "mimeType", "") or ""),
        "text": str(_object_or_dict_value(item, "text", "") or ""),
        "blob": _object_or_dict_value(item, "blob"),
    }


def _flatten_read_resource_result(result: Any) -> dict[str, Any]:
    contents = [_flatten_resource_content_item(item) for item in getattr(result, "contents", []) or []]
    text = "\n".join(item["text"] for item in contents if item["text"]).strip()
    return {
        "contents": contents,
        "text": text,
    }


def _flatten_prompt_content(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        content_type = str(content.get("type", "") or "")
        payload = dict(content)
    else:
        content_type = str(getattr(content, "type", "") or "")
        payload = {
            "type": content_type,
            "text": getattr(content, "text", None),
            "data": getattr(content, "data", None),
            "mime_type": getattr(content, "mimeType", None),
            "resource": getattr(content, "resource", None),
        }
    resource = payload.get("resource")
    if resource is not None and not isinstance(resource, dict):
        resource = _flatten_resource_content_item(resource)
    payload["type"] = content_type
    payload["resource"] = resource
    return payload


def _flatten_prompt_message(message: Any) -> dict[str, Any]:
    role = str(_object_or_dict_value(message, "role", "") or "")
    content = _object_or_dict_value(message, "content")
    flattened_content = _flatten_prompt_content(content)
    text = ""
    if flattened_content.get("type") == "text":
        text = str(flattened_content.get("text", "") or "")
    elif flattened_content.get("type") == "resource":
        resource = flattened_content.get("resource") or {}
        text = str(resource.get("text", "") or "")
    return {
        "role": role,
        "content": flattened_content,
        "text": text,
    }


def _flatten_get_prompt_result(result: Any) -> dict[str, Any]:
    messages = [_flatten_prompt_message(item) for item in getattr(result, "messages", []) or []]
    text = "\n".join(item["text"] for item in messages if item["text"]).strip()
    return {
        "description": str(getattr(result, "description", "") or ""),
        "messages": messages,
        "text": text,
    }


class StdioMcpTransport:
    """Connect to a stdio MCP server and expose core operations."""

    def __init__(self, definition: McpServerDefinition):
        self.definition = definition
        self._stack: AsyncExitStack | None = None
        self._session: Any = None

    async def connect(self) -> None:
        if self._session is not None:
            return
        sdk = _load_stdio_sdk()
        stack = AsyncExitStack()
        server_params = sdk["StdioServerParameters"](
            command=self.definition.command,
            args=self.definition.args,
            env=self.definition.env or None,
        )
        read_stream, write_stream = await stack.enter_async_context(sdk["stdio_client"](server_params))
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
