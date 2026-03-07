"""SetupWizard section methods: operations."""

from __future__ import annotations

import os
from pathlib import Path

import questionary
from rich.console import Console
from rich.prompt import Confirm, Prompt

from kabot.cli.wizard.ui import ClackUI

console = Console()


def _builtin_skills_source_path(self) -> Path:
    """Resolve built-in skills source directory from package layout."""
    candidates = [
        # .../kabot/cli/wizard/sections/operations.py -> .../kabot/skills
        Path(__file__).resolve().parents[3] / "skills",
        # Fallback for alternative packaging/layout.
        Path(__file__).resolve().parents[2] / "skills",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]

def _configure_logging(self):
    ClackUI.section_start("Logging & Debugging")

    # Mark section as in progress
    self._save_setup_state("logging", completed=False, in_progress=True)

    # Log Level
    level = ClackUI.clack_select("Log Level", choices=[
        questionary.Choice("DEBUG (Verbose)", value="DEBUG"),
        questionary.Choice("INFO (Standard)", value="INFO"),
        questionary.Choice("WARNING (Issues only)", value="WARNING"),
        questionary.Choice("ERROR (Critical only)", value="ERROR"),
    ], default=self.config.logging.level)
    self.config.logging.level = level

    # File Retention
    retention = Prompt.ask("|  File Retention (e.g. '7 days', '1 week')", default=self.config.logging.retention)
    self.config.logging.retention = retention

    # DB Retention
    db_days = Prompt.ask("|  Database Retention (days)", default=str(self.config.logging.db_retention_days))
    try:
        self.config.logging.db_retention_days = int(db_days)
    except ValueError:
        console.print("|  [red]Invalid number, keeping default.[/red]")

    console.print("|  [green]OK Logging configured[/green]")

    # Mark as completed and save configuration
    self._save_setup_state("logging", completed=True,
                         log_level=level,
                         file_retention=retention,
                         db_retention_days=self.config.logging.db_retention_days)

    ClackUI.section_end()

def _configure_autostart(self):
    ClackUI.section_start("Auto-start Configuration")

    from kabot.core.daemon import (
        get_service_status,
        install_launchd_service,
        install_systemd_service,
        install_termux_service,
        install_windows_task_service,
    )

    status = get_service_status()
    installed = status.get("installed", False)
    service_type = status.get("service_type", "unknown")

    if installed:
        console.print(f"|  [green]OK Auto-start is already INSTALLED ({service_type})[/green]")
        if not Confirm.ask("|  Reinstall/Update service", default=False):
            ClackUI.section_end()
            return
    else:
        console.print("|  [yellow]! Auto-start is NOT installed[/yellow]")

    if not Confirm.ask(f"|  Enable Kabot to start automatically on boot ({service_type})", default=True):
        ClackUI.section_end()
        return

    with console.status("|  Installing service..."):
        if service_type == "systemd":
            ok, msg = install_systemd_service()
        elif service_type == "launchd":
            ok, msg = install_launchd_service()
        elif service_type == "task_scheduler":
            ok, msg = install_windows_task_service()
        elif service_type == "termux":
            ok, msg = install_termux_service()
        else:
            ok, msg = False, f"Unsupported service type: {service_type}"

    if ok:
        console.print(f"|  [green]OK {msg}[/green]")
    else:
        console.print(f"|  [red]X {msg}[/red]")

    self._save_setup_state("autostart", completed=ok, service_type=service_type)
    ClackUI.section_end()

def _run_doctor(self):
    from kabot.utils.doctor import KabotDoctor
    doc = KabotDoctor()
    doc.render_report()
    Prompt.ask("|\n*  Press Enter to return to menu")

def _install_builtin_skills(self):
    """Copy built-in skill definitions to workspace if not present."""
    skills_src = self._builtin_skills_source_path()
    skills_dst = Path(self.config.agents.defaults.workspace) / "skills"

    if not skills_src.exists():
        console.print(f"|  [yellow]Warning: Built-in skills not found at {skills_src}[/yellow]")
        return

    # Ensure destination exists
    if not skills_dst.exists():
        os.makedirs(skills_dst, exist_ok=True)
        console.print(f"|  [cyan]Initializing workspace skill definitions at {skills_dst}...[/cyan]")

    # Copy skills
    import shutil
    count = 0
    for item in skills_src.iterdir():
        if item.is_dir() and (item / "SKILL.md").exists():
            dst_path = skills_dst / item.name
            if not dst_path.exists():
                try:
                    shutil.copytree(item, dst_path)
                    count += 1
                except Exception as e:
                     console.print(f"|  [red]Failed to copy skill {item.name}: {e}[/red]")

    if count > 0:
        console.print(f"|  [green]OK Synced {count} built-in skill definitions to workspace[/green]")

def _install_builtin_skills_with_progress(self) -> bool:
    """Sync built-in skill definitions with progress indicators and error handling."""
    console.print("*  [cyan]Syncing built-in skill definitions...[/cyan]")

    skills_src = self._builtin_skills_source_path()
    skills_dst = Path(self.config.agents.defaults.workspace) / "skills"

    # Check if source skills exist
    if not skills_src.exists():
        console.print(f"|  [yellow]! Built-in skills not found at {skills_src}[/yellow]")
        console.print("|  [dim]Continuing without built-in skills installation[/dim]")
        return False

    # Ensure destination exists
    try:
        if not skills_dst.exists():
            os.makedirs(skills_dst, exist_ok=True)
        console.print(f"|  [cyan]Created workspace skills directory: {skills_dst}[/cyan]")
    except Exception as e:
        console.print(f"|  [red]X Failed to create skills directory: {e}[/red]")
        console.print("|  [dim]Continuing without built-in skills installation[/dim]")
        return False

    # Discover available skills
    available_skills = []
    for item in skills_src.iterdir():
        if item.is_dir() and (item / "SKILL.md").exists():
            available_skills.append(item)

    if not available_skills:
        console.print("|  [yellow]! No built-in skill definitions found to sync[/yellow]")
        return False

    console.print(f"|  Found {len(available_skills)} built-in skill definitions to sync")

    # Install skills with progress feedback
    import shutil
    installed_count = 0
    failed_count = 0
    skipped_count = 0

    for skill_src in available_skills:
        skill_name = skill_src.name
        skill_dst = skills_dst / skill_name

        if skill_dst.exists():
            console.print(f"|  [dim]- {skill_name} (already exists)[/dim]")
            skipped_count += 1
            continue

        try:
            console.print(f"|  [cyan]Syncing {skill_name}...[/cyan]")
            shutil.copytree(skill_src, skill_dst)
            console.print(f"|  [green]OK {skill_name}[/green]")
            installed_count += 1
        except Exception as e:
            console.print(f"|  [red]X {skill_name}: {str(e)[:60]}...[/red]")
            failed_count += 1

    # Summary
    console.print("|")
    if installed_count > 0:
        console.print(f"|  [green]OK Successfully synced {installed_count} built-in skill definitions[/green]")

    if skipped_count > 0:
        console.print(f"|  [dim]- Skipped {skipped_count} existing skill definitions[/dim]")

    if failed_count > 0:
        console.print(f"|  [yellow]! Failed to sync {failed_count} skill definitions[/yellow]")
        console.print("|  [dim]Setup will continue - you can sync or reinstall these definitions later[/dim]")

    return installed_count > 0

def bind_operations_sections(cls):
    cls._configure_logging = _configure_logging
    cls._configure_autostart = _configure_autostart
    cls._run_doctor = _run_doctor
    cls._builtin_skills_source_path = _builtin_skills_source_path
    cls._install_builtin_skills = _install_builtin_skills
    cls._install_builtin_skills_with_progress = _install_builtin_skills_with_progress
    return cls
