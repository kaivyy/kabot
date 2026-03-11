"""Session-scoped MCP state."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field

from kabot.mcp.models import McpServerDefinition

_ACTIVE_MCP_RUNTIME: ContextVar[object | None] = ContextVar(
    "kabot_active_mcp_runtime",
    default=None,
)


@dataclass(slots=True)
class McpSessionState:
    """Mutable attached-MCP state for a single Kabot session."""

    session_id: str
    servers: dict[str, McpServerDefinition] = field(default_factory=dict)


def get_active_mcp_runtime() -> object | None:
    """Return the MCP runtime bound to the current async context."""

    return _ACTIVE_MCP_RUNTIME.get()


def set_active_mcp_runtime(runtime: object | None) -> Token:
    """Bind an MCP runtime to the current async context."""

    return _ACTIVE_MCP_RUNTIME.set(runtime)


def reset_active_mcp_runtime(token: Token) -> None:
    """Reset the active MCP runtime binding for the current async context."""

    _ACTIVE_MCP_RUNTIME.reset(token)


@contextmanager
def activate_mcp_runtime(runtime: object | None):
    """Temporarily bind an MCP runtime to the current async context."""

    token = set_active_mcp_runtime(runtime)
    try:
        yield runtime
    finally:
        reset_active_mcp_runtime(token)
