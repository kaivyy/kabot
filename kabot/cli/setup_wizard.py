"""Modular, interactive setup wizard for kabot (v2.1)."""

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import questionary
from rich.console import Console
from rich.prompt import Confirm, Prompt

from kabot.cli.wizard import ClackUI
from kabot.config.loader import load_config
from kabot.config.schema import Config
from kabot.providers.registry import ModelRegistry
from kabot.utils.environment import detect_runtime_environment, recommended_gateway_mode

if hasattr(sys.stdout, 'encoding') and sys.stdout.encoding:
    if sys.stdout.encoding.lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

console = Console()
__all__ = ["SetupWizard", "run_interactive_setup", "ClackUI", "Confirm", "Prompt"]

class SetupWizard:
    def __init__(self):
        self.config = load_config()
        self.registry = ModelRegistry()
        self.ran_section = False
        self.setup_mode = "simple"

    def _suggest_gateway_mode(self) -> str:
        """Suggest gateway mode based on detected runtime environment."""
        return recommended_gateway_mode(detect_runtime_environment())

    def _detected_environment_payload(self) -> dict:
        """Return detected environment flags for setup state snapshot."""
        runtime = detect_runtime_environment()
        return {
            "platform": runtime.platform,
            "is_windows": runtime.is_windows,
            "is_macos": runtime.is_macos,
            "is_linux": runtime.is_linux,
            "is_wsl": runtime.is_wsl,
            "is_termux": runtime.is_termux,
            "is_vps": runtime.is_vps,
            "is_headless": runtime.is_headless,
            "is_ci": runtime.is_ci,
            "has_display": runtime.has_display,
        }

    def _create_backup(self) -> str:
        """Create configuration backup before changes."""
        import hashlib

        backup_dir = Path.home() / ".kabot" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        backup_path = backup_dir / f"{timestamp}_pre-setup"
        backup_path.mkdir(exist_ok=True)

        config_file = Path.home() / ".kabot" / "config.json"
        if config_file.exists():
            shutil.copy2(config_file, backup_path / "config.json")

            # Create metadata
            metadata = {
                "created_at": timestamp,
                "type": "pre-setup",
                "original_path": str(config_file)
            }

            with open(backup_path / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)

            # Create checksum
            with open(backup_path / "config.json", "rb") as f:
                checksum = hashlib.sha256(f.read()).hexdigest()

            with open(backup_path / "checksum.sha256", "w") as f:
                f.write(f"{checksum}  config.json\n")

        return str(backup_path)

    def _load_setup_state(self) -> dict:
        """Load setup state from file."""
        state_file = Path.home() / ".kabot" / "setup-state.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                # Handle corrupted state file gracefully
                return self._get_default_state()
        return self._get_default_state()

    def _get_default_state(self) -> dict:
        """Get default setup state structure."""
        return {
            "version": "1.0",
            "started_at": None,
            "sections": {},
            "user_selections": {}
        }

    def _to_json_compatible(self, value):
        """Convert setup-state payloads to JSON-compatible structures."""
        if hasattr(value, "model_dump"):
            return self._to_json_compatible(value.model_dump())
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {k: self._to_json_compatible(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._to_json_compatible(v) for v in value]
        if isinstance(value, tuple):
            return [self._to_json_compatible(v) for v in value]
        if isinstance(value, set):
            return [self._to_json_compatible(v) for v in sorted(value)]
        return value

    def _write_setup_state(self, state: dict) -> None:
        """Write setup state with safe JSON serialization."""
        state_file = Path.home() / ".kabot" / "setup-state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        serializable_state = self._to_json_compatible(state)
        try:
            with open(state_file, "w") as f:
                json.dump(serializable_state, f, indent=2)
        except (IOError, TypeError, ValueError) as e:
            console.print(f"|  [yellow]Warning: Could not save setup state: {e}[/yellow]")

    def _save_setup_state(self, section: str, completed: bool = False, **data):
        """Save setup state to file."""
        state = self._load_setup_state()

        if not state["started_at"]:
            state["started_at"] = datetime.now().isoformat()

        state["last_updated"] = datetime.now().isoformat()
        state["sections"][section] = {
            "completed": completed,
            "timestamp": datetime.now().isoformat(),
            **data
        }

        self._write_setup_state(state)

    def _clear_setup_state(self):
        """Clear setup state file on successful completion."""
        state_file = Path.home() / ".kabot" / "setup-state.json"
        if state_file.exists():
            try:
                state_file.unlink()
            except IOError as e:
                console.print(f"|  [yellow]Warning: Could not clear setup state: {e}[/yellow]")

    def _check_resume_setup(self) -> bool:
        """Check if there's an interrupted setup and offer to resume."""
        state = self._load_setup_state()

        if not state.get("started_at"):
            return False

        # Check if any sections are incomplete
        incomplete_sections = []
        for section, info in state.get("sections", {}).items():
            if not info.get("completed", False):
                incomplete_sections.append(section)

        if not incomplete_sections:
            # All sections completed, clear state
            self._clear_setup_state()
            return False

        # Show resume prompt
        console.print("|")
        console.print("*  [yellow]Interrupted setup detected[/yellow]")
        console.print(f"|  Started: {state['started_at']}")
        console.print(f"|  Last updated: {state.get('last_updated', 'Unknown')}")
        console.print("|")
        console.print("|  [bold]Incomplete sections:[/bold]")
        for section in incomplete_sections:
            console.print(f"|    - {section}")
        console.print("|")

        resume = Confirm.ask("*  Resume from where you left off", default=True)

        if resume:
            # Restore user selections
            selections = state.get("user_selections", {})
            if selections.get("workspace_path"):
                self.config.agents.defaults.workspace = selections["workspace_path"]
            console.print("|  [green]OK Resuming setup...[/green]")
            console.print("|")
            return True
        else:
            # Start fresh
            if Confirm.ask("|  Start fresh setup (This will clear saved progress)", default=True):
                self._clear_setup_state()
                console.print("|  [cyan]Starting fresh setup...[/cyan]")
                console.print("|")
                return False
            else:
                console.print("|  [yellow]Setup cancelled[/yellow]")
                return None

    def run(self) -> Config:
        ClackUI.header()

        # Check for interrupted setup and offer to resume
        resume_result = self._check_resume_setup()
        if resume_result is None:  # User cancelled
            return self.config

        ClackUI.summary_box(self.config)

        setup_mode = ClackUI.clack_select(
            "Setup mode",
            choices=[
                questionary.Choice("Simple (Recommended)", value="simple"),
                questionary.Choice("Advanced", value="advanced"),
            ],
            default="simple",
        )
        if setup_mode is None:
            return self.config
        self._set_setup_mode(setup_mode)

        # Create backup before making any changes
        try:
            console.print("|")
            console.print("*  [cyan]Creating configuration backup...[/cyan]")
            backup_path = self._create_backup()
            console.print(f"|  [green]OK Backup created at: {backup_path}[/green]")
            console.print("|")
        except Exception as e:
            console.print(f"|  [yellow]! Backup creation failed: {e}[/yellow]")
            console.print("|  [dim]Continuing without backup...[/dim]")
            console.print("|")

        # Initialize setup state if not resuming
        if not resume_result:
            self._save_setup_state("setup", completed=False, mode="local")

        ClackUI.section_start("Environment")
        detected_env = self._detected_environment_payload()
        detected_tags = []
        if detected_env["is_termux"]:
            detected_tags.append("termux")
        if detected_env["is_wsl"]:
            detected_tags.append("wsl")
        if detected_env["is_vps"]:
            detected_tags.append("vps")
        if detected_env["is_headless"]:
            detected_tags.append("headless")
        if detected_env["is_ci"]:
            detected_tags.append("ci")
        if detected_tags:
            console.print(f"|  [dim]Detected: {detected_env['platform']} ({', '.join(detected_tags)})[/dim]")
        else:
            console.print(f"|  [dim]Detected: {detected_env['platform']}[/dim]")
        suggested_mode = self._suggest_gateway_mode()

        mode = ClackUI.clack_select(
            "Where will the Gateway run",
            choices=[
                questionary.Choice("Local (this machine)", value="local"),
                questionary.Choice("Remote (info-only)", value="remote"),
            ],
            default=suggested_mode
        )
        ClackUI.section_end()

        if mode is None:
            return self.config

        # Save environment selection
        self._save_setup_state(
            "environment",
            completed=True,
            mode=mode,
            detected=detected_env,
            suggested_mode=suggested_mode,
        )

        while True:
            choice = self._main_menu()
            if choice == "finish" or choice is None:
                break

            if choice == "workspace":
                self._configure_workspace()
            elif choice == "model":
                self._configure_model()
            elif choice == "tools":
                self._configure_tools()
            elif choice == "memory":
                self._configure_memory()
            elif choice == "gateway":
                self._configure_gateway()
            elif choice == "channels":
                self._configure_channels()
            elif choice == "autostart":
                self._configure_autostart()
            elif choice == "skills":
                self._configure_skills()
            elif choice == "logging":
                self._configure_logging()
            elif choice == "doctor":
                self._run_doctor()
            elif choice == "google":
                self._configure_google()

            self.ran_section = True

        # Clear setup state on successful completion
        if self.ran_section:
            self._clear_setup_state()
            console.print("|")
            console.print("*  [green]Setup completed successfully![/green]")
            console.print("|")

        return self.config



    def _main_menu(self) -> str:
        ClackUI.summary_box(self.config)

        ClackUI.section_start("Configuration Menu")
        options = self._main_menu_choices()

        choice = ClackUI.clack_select("Select section to configure", choices=options)
        ClackUI.section_end()
        return choice

    def _set_setup_mode(self, mode: str) -> None:
        self.setup_mode = "advanced" if mode == "advanced" else "simple"

    def _main_menu_option_values(self) -> list[str]:
        if self.setup_mode == "advanced":
            return [
                "workspace",
                "model",
                "memory",
                "tools",
                "gateway",
                "skills",
                "google",
                "channels",
                "autostart",
                "logging",
                "doctor",
                "finish",
            ]
        return [
            "workspace",
            "model",
            "memory",
            "tools",     # <-- Added advanced tools to simple mode
            "skills",
            "google",
            "channels",
            "autostart",
            "finish",
        ]

    def _main_menu_choices(self) -> list:
        labels = {
            "workspace": "Workspace (Set path + sessions)",
            "model": "Model / Auth (Providers, Keys, OAuth)",
            "memory": "Memory (Backend, Embeddings, Database)",
            "tools": "Tools & Sandbox (Search, Docker, Shell)",
            "gateway": "Gateway (Port, Host, Bindings)",
            "skills": "Skills (Configure & Install Plans)",
            "google": "Google Suite (Native Auth, no npm)",
            "channels": "Channels (Telegram, WhatsApp, Slack)",
            "autostart": "Auto-start (Enable boot-up service)",
            "logging": "Logging & Debugging",
            "doctor": "Health Check (Run system diagnostic)",
            "finish": "Continue & Finish",
        }
        return [questionary.Choice(labels[value], value=value) for value in self._main_menu_option_values()]

    # Section methods extracted to kabot.cli.wizard.setup_sections.


def _bind_setup_wizard_sections() -> None:
    from kabot.cli.wizard.setup_sections import bind_setup_wizard_sections

    bind_setup_wizard_sections(SetupWizard)


_bind_setup_wizard_sections()


def run_interactive_setup() -> Config:
    wizard = SetupWizard()
    # Ensure workspace exists and install skills before running wizard
    os.makedirs(os.path.expanduser(wizard.config.agents.defaults.workspace), exist_ok=True)
    wizard._install_builtin_skills()
    return wizard.run()





