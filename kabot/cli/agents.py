"""CLI commands for managing multi-agent configuration."""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Manage multi-agent configuration")
console = Console()


@app.command("list")
def list_agents():
    """List all configured agents."""
    from kabot.config.loader import load_config

    config = load_config()

    if not config.agents.agents:
        console.print("[yellow]No agents configured[/yellow]")
        return

    table = Table(title="Configured Agents")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Model", style="blue")
    table.add_column("Default", style="magenta")

    for agent in config.agents.agents:
        table.add_row(
            agent.id,
            agent.name or "-",
            agent.model or "-",
            "✓" if agent.default else ""
        )

    console.print(table)


@app.command("add")
def add_agent(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    name: str = typer.Option("", help="Agent name"),
    model: str = typer.Option("", help="Model to use"),
    workspace: str = typer.Option("", help="Workspace directory"),
    default: bool = typer.Option(False, help="Set as default agent"),
):
    """Add a new agent."""
    from kabot.config.loader import load_config, save_config
    from kabot.config.schema import AgentConfig

    config = load_config()

    # Check if agent already exists
    if any(a.id == agent_id for a in config.agents.agents):
        console.print(f"[red]Agent '{agent_id}' already exists[/red]")
        raise typer.Exit(1)

    # Create workspace directory
    workspace_path = Path(workspace).expanduser() if workspace else Path.home() / ".kabot" / f"workspace-{agent_id}"
    workspace_path.mkdir(parents=True, exist_ok=True)

    # Add agent
    new_agent = AgentConfig(
        id=agent_id,
        name=name or agent_id.title(),
        model=model or None,
        workspace=str(workspace_path),
        default=default
    )
    config.agents.agents.append(new_agent)

    save_config(config)
    console.print(f"[green]OK[/green] Agent '{agent_id}' added")


@app.command("delete")
def delete_agent(
    agent_id: str = typer.Argument(..., help="Agent ID to delete"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
):
    """Delete an agent."""
    from kabot.config.loader import load_config, save_config

    config = load_config()

    # Find agent
    agent = next((a for a in config.agents.agents if a.id == agent_id), None)
    if not agent:
        console.print(f"[red]Agent '{agent_id}' not found[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Delete agent '{agent_id}'?")
        if not confirm:
            raise typer.Abort()

    # Remove agent
    config.agents.agents = [a for a in config.agents.agents if a.id != agent_id]
    save_config(config)

    console.print(f"[green]OK[/green] Agent '{agent_id}' deleted")
