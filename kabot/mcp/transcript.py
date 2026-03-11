"""Transcript-safe helpers for MCP tool events."""

from __future__ import annotations

from kabot.mcp.registry import qualify_mcp_tool_name


def make_mcp_missing_tool_result(*, call_id: str, server_name: str, tool_name: str) -> dict[str, object]:
    """Create a synthetic MCP tool error result for transcript repair."""

    return {
        "role": "tool",
        "tool_call_id": call_id,
        "tool_name": qualify_mcp_tool_name(server_name, tool_name),
        "is_error": True,
        "content": (
            "Synthetic MCP tool error result inserted during transcript repair because "
            "the original MCP tool result was missing."
        ),
    }
