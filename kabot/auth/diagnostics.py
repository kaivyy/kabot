import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

@dataclass
class DependencyStatus:
    """Status of an external dependency."""
    name: str
    found: bool
    version: Optional[str] = None
    path: Optional[str] = None
    error_message: Optional[str] = None

def render_help_panel(tool_name: str, install_cmd: str, docs_url: Optional[str] = None):
    """Render an OpenClaw-style help panel for a missing dependency."""
    help_text = Text.from_markup(
        f"\n[bold red]Failed to find {tool_name}.[/bold red]\n\n"
        f"Kabot requires this tool to extract authentication secrets automatically.\n\n"
        f" [bold cyan]Install it first:[/bold cyan]\n"
        f" [yellow]{install_cmd}[/yellow]\n"
    )

    if docs_url:
        help_text.append(f"\n [bold cyan]Documentation:[/bold cyan]\n {docs_url}\n")

    panel = Panel(
        help_text,
        title=f" Dependency Missing: {tool_name} ",
        border_style="red",
        padding=(1, 2)
    )
    console.print(panel)

class GuidedInstaller:
    """OS-aware utility to help users install missing dependencies."""

    @staticmethod
    def get_install_command(tool_id: str) -> str:
        """Get the appropriate install command for the current OS."""
        if tool_id == "gemini-cli":
            if sys.platform == "win32":
                return "npm install -g @google/gemini-cli"
            elif sys.platform == "darwin": # macOS
                return "brew install gemini-cli"
            else: # Linux
                return "npm install -g @google/gemini-cli"
        return "Not available"

    @staticmethod
    def try_install(command: str) -> bool:
        """Attempt to run an install command after user confirmation."""
        try:
            # Use shell=True for npm/brew commands which might be scripts/aliases
            process = subprocess.run(command, shell=True, check=True)
            return process.returncode == 0
        except Exception as e:
            console.print(f"[bold red]Installation failed:[/bold red] {e}")
            return False
