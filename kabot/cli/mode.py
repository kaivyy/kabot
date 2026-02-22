# kabot/cli/mode.py
import typer
from rich.console import Console

app = typer.Typer(help="Manage agent execution mode")
console = Console()

@app.command("set")
def set_mode(
    mode: str = typer.Argument(..., help="Mode: single or multi"),
    user_id: str = typer.Option("", help="User ID (default: current user)"),
):
    """Set agent execution mode."""
    from pathlib import Path

    from kabot.agent.mode_manager import ModeManager

    if mode not in ["single", "multi"]:
        console.print(f"[red]Invalid mode: {mode}. Use 'single' or 'multi'[/red]")
        raise typer.Exit(1)

    manager = ModeManager(Path.home() / ".kabot" / "mode_config.json")
    user_id = user_id or "default"
    manager.set_mode(user_id, mode)

    console.print(f"[green]OK[/green] Mode set to '{mode}' for {user_id}")

@app.command("status")
def show_status(
    user_id: str = typer.Option("", help="User ID (default: current user)"),
):
    """Show current mode."""
    from pathlib import Path

    from kabot.agent.mode_manager import ModeManager

    manager = ModeManager(Path.home() / ".kabot" / "mode_config.json")
    user_id = user_id or "default"
    mode = manager.get_mode(user_id)

    console.print(f"Current mode for {user_id}: [cyan]{mode}[/cyan]")
