"""Helpers for resolving MCP configuration into runtime definitions."""

from __future__ import annotations

from kabot.config.schema import Config
from kabot.mcp.models import McpServerDefinition


def resolve_mcp_server_definitions(cfg: Config) -> list[McpServerDefinition]:
    """Resolve enabled MCP server config into immutable runtime definitions."""

    resolved: list[McpServerDefinition] = []
    for name, server in (cfg.mcp.servers or {}).items():
        if not server.enabled:
            continue
        resolved.append(
            McpServerDefinition(
                name=name,
                transport=server.transport,
                command=server.command or None,
                args=list(server.args),
                env=dict(server.env),
                url=server.url or None,
                headers=dict(server.headers),
                enabled=server.enabled,
            )
        )
    return resolved
