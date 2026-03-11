"""Public surface for Kabot's Python-native MCP foundation."""

from kabot.mcp.config import resolve_mcp_server_definitions
from kabot.mcp.models import (
    McpRegisteredTool,
    McpServerDefinition,
    McpToolDescriptor,
)
from kabot.mcp.registry import McpCapabilityRegistry, qualify_mcp_tool_name
from kabot.mcp.runtime import (
    McpSessionRuntime,
    build_transport_for_server,
    register_mcp_tools,
    safe_list_server_tools,
)
from kabot.mcp.session_state import activate_mcp_runtime, get_active_mcp_runtime
from kabot.mcp.tool_adapter import McpRuntimeTool
from kabot.mcp.transcript import make_mcp_missing_tool_result
from kabot.mcp.transports import StdioMcpTransport, StreamableHttpMcpTransport

__all__ = [
    "activate_mcp_runtime",
    "get_active_mcp_runtime",
    "McpCapabilityRegistry",
    "McpRegisteredTool",
    "McpRuntimeTool",
    "McpServerDefinition",
    "McpSessionRuntime",
    "McpToolDescriptor",
    "StdioMcpTransport",
    "StreamableHttpMcpTransport",
    "build_transport_for_server",
    "make_mcp_missing_tool_result",
    "qualify_mcp_tool_name",
    "register_mcp_tools",
    "resolve_mcp_server_definitions",
    "safe_list_server_tools",
]
