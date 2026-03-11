"""User-facing MCP CLI commands."""

from __future__ import annotations

import asyncio
import inspect
import json

import typer
from rich.console import Console
from rich.table import Table

from kabot.config.loader import get_config_path, load_config
from kabot.mcp.config import resolve_mcp_server_definitions
from kabot.mcp.runtime import McpSessionRuntime

console = Console()


def _render_target(server) -> str:
    if server.transport == "stdio":
        parts = [str(server.command or "").strip(), *[str(arg).strip() for arg in server.args or []]]
        return " ".join(part for part in parts if part).strip() or "-"
    return str(server.url or "").strip() or "-"


def mcp_status() -> None:
    """Show configured MCP servers."""

    config = load_config()
    console.print(f"[bold]MCP enabled:[/bold] {'yes' if config.mcp.enabled else 'no'}")
    console.print(f"[dim]Config:[/dim] {get_config_path()}")

    if not config.mcp.servers:
        console.print("[yellow]No MCP servers configured.[/yellow]")
        return

    table = Table(title="Configured MCP Servers")
    table.add_column("Name", style="cyan")
    table.add_column("Transport")
    table.add_column("Target")
    table.add_column("Enabled")

    for name, server in sorted(config.mcp.servers.items()):
        table.add_row(
            name,
            server.transport,
            _render_target(server),
            "yes" if server.enabled else "no",
        )

    console.print(table)


def mcp_example_config() -> None:
    """Print a minimal MCP config example."""

    snippet = {
        "mcp": {
            "enabled": True,
            "servers": {
                "local_echo": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["-m", "kabot.mcp.dev.echo_server"],
                },
                "remote_docs": {
                    "transport": "streamable_http",
                    "url": "https://example.test/mcp",
                },
            },
        }
    }
    typer.echo(json.dumps(snippet, ensure_ascii=False, indent=2))


async def inspect_mcp_server_snapshot(config, server_name: str) -> dict[str, object]:
    """Collect a live MCP capability snapshot for one configured server."""

    resolved = {item.name: item for item in resolve_mcp_server_definitions(config)}
    if server_name not in resolved:
        raise typer.BadParameter(f"Unknown MCP server: {server_name}")

    runtime = McpSessionRuntime(session_id=f"cli:mcp-inspect:{server_name}")
    runtime.attach(resolved[server_name])
    try:
        tools = await runtime.list_tools(server_name)
        resources = await runtime.list_resources(server_name)
        prompts = await runtime.list_prompts(server_name)
        return {
            "server_name": server_name,
            "tools": [
                {"name": item.tool_name, "qualified_name": item.qualified_name, "description": item.description}
                for item in tools
            ],
            "resources": [
                {"name": item.name, "uri": item.uri, "description": item.description}
                for item in resources
            ],
            "prompts": [
                {"name": item.prompt_name, "description": item.description}
                for item in prompts
            ],
        }
    finally:
        await runtime.close()


def mcp_inspect(server_name: str) -> None:
    """Inspect one configured MCP server and list its live capabilities."""

    config = load_config()
    snapshot_result = inspect_mcp_server_snapshot(config, server_name)
    snapshot = asyncio.run(snapshot_result) if inspect.isawaitable(snapshot_result) else snapshot_result

    console.print(f"[bold]MCP server:[/bold] {snapshot['server_name']}")

    tools = snapshot["tools"]
    resources = snapshot["resources"]
    prompts = snapshot["prompts"]

    console.print(
        f"[dim]Capabilities:[/dim] tools={len(tools)} resources={len(resources)} prompts={len(prompts)}"
    )

    if tools:
        tool_table = Table(title="Tools")
        tool_table.add_column("Name", style="cyan")
        tool_table.add_column("Qualified")
        tool_table.add_column("Description")
        for item in tools:
            tool_table.add_row(item["name"], item.get("qualified_name", "-"), item.get("description", ""))
        console.print(tool_table)

    if resources:
        resource_table = Table(title="Resources")
        resource_table.add_column("Name", style="cyan")
        resource_table.add_column("URI")
        resource_table.add_column("Description")
        for item in resources:
            resource_table.add_row(item["name"], item["uri"], item.get("description", ""))
        console.print(resource_table)

    if prompts:
        prompt_table = Table(title="Prompts")
        prompt_table.add_column("Name", style="cyan")
        prompt_table.add_column("Description")
        for item in prompts:
            prompt_table.add_row(item["name"], item.get("description", ""))
        console.print(prompt_table)
