"""SetupWizard section methods: core."""

from __future__ import annotations

import os
from pathlib import Path

import questionary
from rich.console import Console
from rich.prompt import Prompt

from kabot.cli.wizard.ui import ClackUI
from kabot.utils.workspace_templates import ensure_workspace_templates

console = Console()

def _configure_google(self):
    ClackUI.section_start("Google Suite Configuration")
    console.print("|  [dim]Setup native Google Suite integration (Gmail & Calendar)[/dim]")
    console.print("|  [dim]No npm, Node.js skill install, or gog setup is required here.[/dim]")
    console.print("|  [dim]Use this menu for Kabot's built-in Google auth flow.[/dim]")

    action = ClackUI.clack_select(
        "Google Suite action",
        choices=[
            questionary.Choice("Authenticate / Re-authenticate", value="auth"),
            questionary.Choice("Back", value="back"),
        ],
        default="auth",
    )
    if action in {None, "back"}:
        ClackUI.section_end()
        return

    from kabot.auth.google_auth import GoogleAuthManager
    auth_manager = GoogleAuthManager()

    # Check if already authenticated
    if auth_manager.token_path.exists():
        console.print("|")
        console.print("|  [green]OK Google Suite is already authenticated[/green]")
        reset_action = ClackUI.clack_select(
            "Google credentials already exist",
            choices=[
                questionary.Choice("Keep current credentials (Back)", value="keep"),
                questionary.Choice("Re-authenticate and replace", value="reset"),
                questionary.Choice("Back", value="back"),
            ],
            default="keep",
        )
        if reset_action in {None, "keep", "back"}:
            ClackUI.section_end()
            return

    console.print("|")
    console.print("|  To proceed, you need a 'credentials.json' from Google Cloud Console.")
    path_action = ClackUI.clack_select(
        "Credentials file",
        choices=[
            questionary.Choice("Enter path to google_credentials.json", value="path"),
            questionary.Choice("Back", value="back"),
        ],
        default="path",
    )
    if path_action in {None, "back"}:
        ClackUI.section_end()
        return

    path = questionary.path("Path to your google_credentials.json file:").unsafe_ask()
    if not path or str(path).strip().lower() == "back":
        console.print("|  [yellow]Cancelled[/yellow]")
        ClackUI.section_end()
        return

    import shutil
    from pathlib import Path
    cred_file = Path(path)

    if not cred_file.exists():
        console.print(f"|  [red]Error: Credentials file not found at {cred_file}[/red]")
        ClackUI.section_end()
        return

    try:
        shutil.copy(cred_file, auth_manager.credentials_path)
        console.print(f"|  [green]OK Copied credentials to {auth_manager.credentials_path}[/green]")
        console.print("|  [cyan]Initiating Google OAuth login flow in your browser...[/cyan]")
        auth_manager.get_credentials()
        console.print("|  [green]OK Successfully authenticated with Google Suite![/green]")
    except Exception as e:
        console.print(f"|  [red]Authentication failed: {e}[/red]")

    ClackUI.section_end()

def _configure_workspace(self):
    ClackUI.section_start("Workspace")

    # Mark section as in progress
    self._save_setup_state("workspace", completed=False, in_progress=True)

    action = ClackUI.clack_select(
        "Workspace action",
        choices=[
            questionary.Choice("Set workspace path", value="set"),
            questionary.Choice("Back", value="back"),
        ],
        default="set",
    )
    if action in {None, "back"}:
        ClackUI.section_end()
        return

    path = Prompt.ask("|  Workspace directory", default=self.config.agents.defaults.workspace).strip()
    if path.lower() == "back":
        console.print("|  [yellow]Cancelled[/yellow]")
        ClackUI.section_end()
        return

    self.config.agents.defaults.workspace = path
    workspace_path = Path(os.path.expanduser(path))
    created = ensure_workspace_templates(workspace_path)

    # Save user selection and mark as completed
    self._save_setup_state("workspace", completed=True, workspace_path=path)

    # Update user selections for resume capability
    state = self._load_setup_state()
    state["user_selections"]["workspace_path"] = path
    self._write_setup_state(state)

    if created:
        console.print(f"|  [green]OK Workspace path set and initialized ({len(created)} files).[/green]")
    else:
        console.print("|  [green]OK Workspace path set (already initialized).[/green]")
    ClackUI.section_end()

def bind_core_sections(cls):
    cls._configure_google = _configure_google
    cls._configure_workspace = _configure_workspace
    return cls
