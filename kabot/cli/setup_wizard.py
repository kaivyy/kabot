"""Modular, interactive setup wizard for kabot (v2.1)."""

import sys
import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box

from kabot import __version__, __logo__
from kabot.config.schema import Config, AuthProfile
from kabot.config.loader import load_config, save_config
from kabot.utils.network import probe_gateway
from kabot.providers.registry import ModelRegistry

console = Console()

class ClackUI:
    """Helper to draw Kabot/Clack style UI components."""
    
    @staticmethod
    def header():
        logo = r"""
    _  __    _    ____   ____  _______ 
   | |/ /   / \  | __ ) / __ \|__   __|
   | ' /   / _ \ |  _ \| |  | |  | |   
   |  <   / ___ \| |_) | |__| |  | |   
   | . \ / /   \ \____/ \____/   |_|   
   |_|\_/_/     \_\                    
"""
        console.print(f"[bold cyan]{logo}[/bold cyan]")
        console.print(f"  🐈 [bold]kabot {__version__}[/bold] — Light footprint, heavy punch.")
        console.print()

    @staticmethod
    def section_start(title: str):
        console.print(f"┌  [bold cyan]{title}[/bold cyan]")

    @staticmethod
    def section_end():
        console.print("└")

    @staticmethod
    def summary_box(config: Config):
        c = config
        lines = []
        
        # Model
        lines.append(f"model: {c.agents.defaults.model}")
        
        # Gateway
        mode = "local" # Default/Placeholder until we have remote support
        lines.append(f"gateway.mode: {mode}")
        lines.append(f"gateway.port: {c.gateway.port}")
        
        # Gateway Bind
        bind = c.gateway.host or "loopback"
        if bind == "127.0.0.1" or bind == "localhost": bind = "loopback"
        elif bind == "0.0.0.0": bind = "all interfaces"
        lines.append(f"gateway.bind: {bind}")

        # Auth
        auth_status = "configured" if c.gateway.auth_token else "none"
        lines.append(f"gateway.auth: {auth_status}")

        # Channels
        active_channels = []
        if c.channels.telegram.enabled: active_channels.append("telegram")
        if c.channels.whatsapp.enabled: active_channels.append("whatsapp")
        if c.channels.discord.enabled: active_channels.append("discord")
        if c.channels.slack.enabled: active_channels.append("slack")
        if c.channels.email.enabled: active_channels.append("email")
        if c.channels.dingtalk.enabled: active_channels.append("dingtalk")
        if c.channels.qq.enabled: active_channels.append("qq")
        if c.channels.feishu.enabled: active_channels.append("feishu")
        
        if active_channels:
            lines.append(f"channels: {', '.join(active_channels)}")

        # Tools
        tools = []
        if c.tools.web.search.api_key: tools.append("web_search")
        if c.tools.exec.docker.enabled: tools.append("docker_sandbox")
        if tools:
            lines.append(f"tools: {', '.join(tools)}")

        # Workspace (Shorten user home?)
        ws_path = str(c.workspace_path)
        home = os.path.expanduser("~")
        if ws_path.startswith(home):
            ws_path = "~" + ws_path[len(home):]
        lines.append(f"workspace: {ws_path}")

        content = "\n".join(lines)
        
        panel = Panel(
            content,
            title="Existing config detected",
            title_align="left",
            border_style="dim",
            box=box.ROUNDED,
            padding=(1, 2)
        )
        
        console.print("│")
        # Use a grid to put the diamond and panel side-by-side
        grid = Table.grid(padding=(0, 1))
        grid.add_row(Text("◇ "), panel)
        console.print(grid)
        console.print("│")

    @staticmethod
    def clack_select(message: str, choices: List[Any], default: Any = None) -> str:
        """A questionary select styled with Clack vertical lines."""
        console.print("│")
        result = questionary.select(
            f"◇  {message}",
            choices=choices,
            default=default,
            style=questionary.Style([
                ('qmark', 'fg:cyan bold'),
                ('question', 'bold'),
                ('pointer', 'fg:cyan bold'),
                ('highlighted', 'fg:cyan bold'),
                ('selected', 'fg:green'),
            ])
        ).ask()
        if result is None:
            console.print("│  [yellow]Cancelled[/yellow]")
            return None
        return result

class SetupWizard:
    def __init__(self):
        self.config = load_config()
        self.registry = ModelRegistry()
        self.ran_section = False

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

    def _save_setup_state(self, section: str, completed: bool = False, **data):
        """Save setup state to file."""
        state_file = Path.home() / ".kabot" / "setup-state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)

        state = self._load_setup_state()

        if not state["started_at"]:
            state["started_at"] = datetime.now().isoformat()

        state["last_updated"] = datetime.now().isoformat()
        state["sections"][section] = {
            "completed": completed,
            "timestamp": datetime.now().isoformat(),
            **data
        }

        try:
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)
        except IOError as e:
            console.print(f"│  [yellow]Warning: Could not save setup state: {e}[/yellow]")

    def _clear_setup_state(self):
        """Clear setup state file on successful completion."""
        state_file = Path.home() / ".kabot" / "setup-state.json"
        if state_file.exists():
            try:
                state_file.unlink()
            except IOError as e:
                console.print(f"│  [yellow]Warning: Could not clear setup state: {e}[/yellow]")

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
        console.print("│")
        console.print("◇  [yellow]Interrupted setup detected[/yellow]")
        console.print(f"│  Started: {state['started_at']}")
        console.print(f"│  Last updated: {state.get('last_updated', 'Unknown')}")
        console.print("│")
        console.print("│  [bold]Incomplete sections:[/bold]")
        for section in incomplete_sections:
            console.print(f"│    - {section}")
        console.print("│")

        resume = Confirm.ask("◇  Resume from where you left off?", default=True)

        if resume:
            # Restore user selections
            selections = state.get("user_selections", {})
            if selections.get("workspace_path"):
                self.config.agents.defaults.workspace = selections["workspace_path"]
            console.print("│  [green]✓ Resuming setup...[/green]")
            console.print("│")
            return True
        else:
            # Start fresh
            if Confirm.ask("│  Start fresh setup? (This will clear saved progress)", default=True):
                self._clear_setup_state()
                console.print("│  [cyan]Starting fresh setup...[/cyan]")
                console.print("│")
                return False
            else:
                console.print("│  [yellow]Setup cancelled[/yellow]")
                return None

    def run(self) -> Config:
        ClackUI.header()

        # Check for interrupted setup and offer to resume
        resume_result = self._check_resume_setup()
        if resume_result is None:  # User cancelled
            return self.config

        ClackUI.summary_box(self.config)

        # Create backup before making any changes
        try:
            console.print("│")
            console.print("◇  [cyan]Creating configuration backup...[/cyan]")
            backup_path = self._create_backup()
            console.print(f"│  [green]✓ Backup created at: {backup_path}[/green]")
            console.print("│")
        except Exception as e:
            console.print(f"│  [yellow]⚠ Backup creation failed: {e}[/yellow]")
            console.print("│  [dim]Continuing without backup...[/dim]")
            console.print("│")

        # Initialize setup state if not resuming
        if not resume_result:
            self._save_setup_state("setup", completed=False, mode="local")

        ClackUI.section_start("Environment")

        mode = ClackUI.clack_select(
            "Where will the Gateway run?",
            choices=[
                questionary.Choice("Local (this machine)", value="local"),
                questionary.Choice("Remote (info-only)", value="remote"),
            ],
            default="local"
        )
        ClackUI.section_end()

        if mode is None: return self.config

        # Save environment selection
        self._save_setup_state("environment", completed=True, mode=mode)

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
            elif choice == "gateway":
                self._configure_gateway()
            elif choice == "channels":
                self._configure_channels()
            elif choice == "skills":
                self._configure_skills()
            elif choice == "logging":
                self._configure_logging()
            elif choice == "doctor":
                self._run_doctor()

            self.ran_section = True

        # Clear setup state on successful completion
        if self.ran_section:
            self._clear_setup_state()
            console.print("│")
            console.print("◇  [green]Setup completed successfully![/green]")
            console.print("│")

        return self.config



    def _main_menu(self) -> str:
        ClackUI.summary_box(self.config)
        
        ClackUI.section_start("Configuration Menu")
        
        options = [
            questionary.Choice("Workspace (Set path + sessions)", value="workspace"),
            questionary.Choice("Model / Auth (Providers, Keys, OAuth)", value="model"),
            questionary.Choice("Tools & Sandbox (Search, Docker, Shell)", value="tools"),
            questionary.Choice("Gateway (Port, Host, Bindings)", value="gateway"),
            questionary.Choice("Skills (Install & Configure)", value="skills"),
            questionary.Choice("Channels (Telegram, WhatsApp, Slack)", value="channels"),
            questionary.Choice("Logging & Debugging", value="logging"),
            questionary.Choice("Health Check (Run system diagnostic)", value="doctor"),
            questionary.Choice("Continue & Finish", value="finish")
        ]
        
        choice = ClackUI.clack_select("Select section to configure", choices=options)
        ClackUI.section_end()
        return choice

    def _configure_workspace(self):
        ClackUI.section_start("Workspace")

        # Mark section as in progress
        self._save_setup_state("workspace", completed=False, in_progress=True)

        path = Prompt.ask("│  Workspace directory", default=self.config.agents.defaults.workspace)
        self.config.agents.defaults.workspace = path
        os.makedirs(os.path.expanduser(path), exist_ok=True)

        # Save user selection and mark as completed
        self._save_setup_state("workspace", completed=True, workspace_path=path)

        # Update user selections for resume capability
        state = self._load_setup_state()
        state["user_selections"]["workspace_path"] = path
        with open(Path.home() / ".kabot" / "setup-state.json", "w") as f:
            json.dump(state, f, indent=2)

        console.print(f"│  [green]✓ Workspace path set.[/green]")
        ClackUI.section_end()

    def _configure_model(self):
        ClackUI.section_start("Model & Auth")

        # Mark section as in progress
        self._save_setup_state("auth", completed=False, in_progress=True)

        from kabot.auth.menu import get_auth_choices
        from kabot.auth.manager import AuthManager

        manager = AuthManager()
        auth_choices = get_auth_choices()
        configured_providers = []

        while True:
            choice = ClackUI.clack_select(
                "Select an option:",
                choices=[
                    questionary.Choice("Provider Login (Setup API Keys/OAuth)", value="login"),
                    questionary.Choice("Select Default Model (Browse Registry)", value="picker"),
                    questionary.Choice("Back", value="back"),
                ]
            )

            if choice == "back" or choice is None:
                break

            if choice == "login":
                p_options = [questionary.Choice(c['name'], value=c['value']) for c in auth_choices]
                provider_val = ClackUI.clack_select("Select provider to login", choices=p_options)

                if provider_val and manager.login(provider_val):
                    configured_providers.append(provider_val)
                    # Validate the API key after successful login
                    self._validate_provider_credentials(provider_val)
                    self._model_picker(provider_val)

            elif choice == "picker":
                self._model_picker()

        # Save configured providers and mark as completed
        self._save_setup_state("auth", completed=True,
                             configured_providers=configured_providers,
                             default_model=self.config.agents.defaults.model)

        # Update user selections
        state = self._load_setup_state()
        state["user_selections"]["selected_providers"] = configured_providers
        state["user_selections"]["default_model"] = self.config.agents.defaults.model
        with open(Path.home() / ".kabot" / "setup-state.json", "w") as f:
            json.dump(state, f, indent=2)

        ClackUI.section_end()

    def _model_picker(self, provider_id: Optional[str] = None):
        from kabot.cli.model_validator import resolve_alias
        from kabot.providers.model_status import get_model_status, get_status_indicator

        # Popular aliases section
        popular_aliases = [
            ("codex", "OpenAI GPT-5.1 Codex (Advanced Coding)"),
            ("sonnet", "Claude 3.5 Sonnet (Latest, 200K context)"),
            ("gemini", "Google Gemini 1.5 Pro (2M context)"),
            ("gpt4o", "OpenAI GPT-4o (Multi-modal)"),
        ]

        m_choices = [
            questionary.Choice(f"Keep current ({self.config.agents.defaults.model})", value="keep"),
        ]

        # Add popular aliases
        for alias, description in popular_aliases:
            model_id = resolve_alias(alias)
            if model_id:
                status = get_model_status(model_id)
                indicator = get_status_indicator(status)
                m_choices.append(
                    questionary.Choice(f"{alias:10} - {description} {indicator}", value=f"alias:{alias}")
                )

        # Add browse and manual options
        m_choices.extend([
            questionary.Choice("Browse All Models (by provider)", value="browse"),
            questionary.Choice("Enter Model ID or Alias Manually", value="manual"),
        ])

        selected = ClackUI.clack_select("Select default model (or use alias)", choices=m_choices)

        if selected == "keep" or selected is None:
            return
        elif selected == "browse":
            self._model_browser(provider_id)
        elif selected == "manual":
            self._manual_model_entry()
        elif selected.startswith("alias:"):
            alias = selected.split(":")[1]
            model_id = resolve_alias(alias)
            if model_id:
                self._confirm_and_set_model(model_id)

    def _model_browser(self, provider_id: Optional[str] = None):
        """Browse models by provider with status indicators."""
        from kabot.providers.model_status import get_model_status, get_status_indicator

        providers = self.registry.get_providers()
        sorted_providers = sorted(providers.items())

        p_choices = [questionary.Choice(f"All providers ({len(self.registry.list_models())} models)", value="all")]
        for p_name, count in sorted_providers:
            p_choices.append(questionary.Choice(f"{p_name} ({count} models)", value=p_name))

        if provider_id is None:
            p_val = ClackUI.clack_select("Filter models by provider", choices=p_choices)
            if p_val == "all":
                provider_id = None
            else:
                provider_id = p_val

        all_models = self.registry.list_models()
        if provider_id:
            models = [m for m in all_models if m.provider == provider_id]
        else:
            models = all_models
        models.sort(key=lambda x: (not x.is_premium, x.id))

        m_choices = [
            questionary.Choice(f"Keep current ({self.config.agents.defaults.model})", value="keep"),
            questionary.Choice("Enter model ID or Alias Manually", value="manual"),
        ]
        for m in models:
            status = get_model_status(m.id)
            indicator = get_status_indicator(status)
            label = f"{indicator} {m.id} ({m.name})"
            if m.is_premium:
                label += " ★"
            m_choices.append(questionary.Choice(label, value=m.id))

        selected_model = ClackUI.clack_select("Select default model", choices=m_choices)

        if selected_model == "keep" or selected_model is None:
            return
        elif selected_model == "manual":
            self._manual_model_entry()
        else:
            self._confirm_and_set_model(selected_model)

    def _manual_model_entry(self):
        """Manual model entry with format hints and validation."""
        from kabot.cli.model_validator import validate_format, resolve_alias, suggest_alternatives
        from kabot.providers.model_status import get_model_status, get_status_indicator

        console.print("│")
        console.print("│  [bold]Enter Model ID or Alias[/bold]")
        console.print("│")
        console.print("│  Format: [cyan]provider/model-name[/cyan]  OR  [cyan]alias[/cyan]")
        console.print("│  Examples:")
        console.print("│    • openai/gpt-4o")
        console.print("│    • anthropic/claude-3-5-sonnet-20241022")
        console.print("│    • codex (alias for openai/gpt-5.1-codex)")
        console.print("│")
        console.print("│  Available aliases: codex, sonnet, gemini, gpt4o, o1, kimi")
        console.print("│  Type 'help' to see all aliases")
        console.print("│")

        while True:
            user_input = Prompt.ask("│  Your input").strip()

            if user_input == "help":
                self._show_alias_help()
                continue

            if not user_input:
                console.print("│  [yellow]Cancelled[/yellow]")
                return

            # Try alias resolution first
            model_id = resolve_alias(user_input)
            if model_id:
                console.print(f"│  [green]✓ Resolved alias '{user_input}' to: {model_id}[/green]")
                self._confirm_and_set_model(model_id)
                return

            # Validate format
            if not validate_format(user_input):
                console.print(f"│  [red]❌ Invalid format: \"{user_input}\"[/red]")
                console.print("│  [dim]Expected: provider/model-name[/dim]")
                console.print("│")

                suggestions = suggest_alternatives(user_input)
                if suggestions:
                    console.print("│  [yellow]Did you mean one of these?[/yellow]")
                    for suggestion in suggestions:
                        console.print(f"│    • {suggestion}")
                    console.print("│")
                continue

            # Valid format, check status and confirm
            self._confirm_and_set_model(user_input)
            return

    def _confirm_and_set_model(self, model_id: str):
        """Confirm model selection and set if approved."""
        from kabot.providers.model_status import get_model_status, get_status_indicator

        status = get_model_status(model_id)
        indicator = get_status_indicator(status)

        console.print(f"│  {indicator} Model: {model_id}")
        console.print(f"│  Status: {status}")

        if status == "unsupported":
            console.print("│  [red]⚠️  This provider is not supported by LiteLLM[/red]")
            console.print("│  [dim]The model may not work correctly[/dim]")
            if not Confirm.ask("│  Continue anyway?", default=False):
                return
        elif status == "catalog":
            console.print("│  [yellow]⚠️  This model is in catalog but not verified[/yellow]")
            console.print("│  [dim]If you encounter issues, try a working model[/dim]")

        self.config.agents.defaults.model = model_id
        console.print(f"│  [green]✓ Model set to {model_id}[/green]")

    def _show_alias_help(self):
        """Show all available aliases."""
        from kabot.providers.registry import ModelRegistry

        registry = ModelRegistry()
        aliases = registry.get_all_aliases()

        # Group by provider
        grouped = {}
        for alias, model_id in aliases.items():
            provider = model_id.split("/")[0]
            if provider not in grouped:
                grouped[provider] = []
            grouped[provider].append((alias, model_id))

        console.print("│")
        console.print("│  [bold cyan]Available Model Aliases[/bold cyan]")
        console.print("│")

        for provider, items in sorted(grouped.items()):
            console.print(f"│  [bold]{provider.title()}:[/bold]")
            for alias, model_id in sorted(items):
                console.print(f"│    {alias:12} → {model_id}")
            console.print("│")

        console.print("│  [dim]Press Enter to continue...[/dim]")
        input()

    def _configure_tools(self):
        ClackUI.section_start("Tools & Sandbox")

        # Mark section as in progress
        self._save_setup_state("tools", completed=False, in_progress=True)

        # Web Search
        console.print("│  [bold]Web Search[/bold]")
        self.config.tools.web.search.api_key = Prompt.ask("│  Brave Search API Key", default=self.config.tools.web.search.api_key)
        self.config.tools.web.search.max_results = int(Prompt.ask("│  Max Search Results", default=str(self.config.tools.web.search.max_results)))

        # Execution
        console.print("│  [bold]Execution Policy[/bold]")
        self.config.tools.restrict_to_workspace = Confirm.ask("│  Restrict FS usage to workspace?", default=self.config.tools.restrict_to_workspace)
        self.config.tools.exec.timeout = int(Prompt.ask("│  Command Timeout (s)", default=str(self.config.tools.exec.timeout)))

        # Docker Sandbox
        console.print("│  [bold]Docker Sandbox[/bold]")
        docker_enabled = False
        if Confirm.ask("│  Enable Docker Sandbox?", default=self.config.tools.exec.docker.enabled):
            self.config.tools.exec.docker.enabled = True
            docker_enabled = True
            self.config.tools.exec.docker.image = Prompt.ask("│  Docker Image", default=self.config.tools.exec.docker.image)
            self.config.tools.exec.docker.memory_limit = Prompt.ask("│  Memory Limit", default=self.config.tools.exec.docker.memory_limit)
            self.config.tools.exec.docker.cpu_limit = float(Prompt.ask("│  CPU Limit", default=str(self.config.tools.exec.docker.cpu_limit)))
            self.config.tools.exec.docker.network_disabled = Confirm.ask("│  Disable Network in Sandbox?", default=self.config.tools.exec.docker.network_disabled)
        else:
            self.config.tools.exec.docker.enabled = False

        # Mark as completed and save configuration
        self._save_setup_state("tools", completed=True,
                             web_search_enabled=bool(self.config.tools.web.search.api_key),
                             docker_enabled=docker_enabled,
                             restrict_to_workspace=self.config.tools.restrict_to_workspace)

        ClackUI.section_end()

    def _configure_gateway(self):
        ClackUI.section_start("Gateway")

        # Mark section as in progress
        self._save_setup_state("gateway", completed=False, in_progress=True)

        # Bind Mode
        modes = [
            questionary.Choice("Loopback (Localhost only) [Secure]", value="loopback"),
            questionary.Choice("Local Network (LAN)", value="local"),
            questionary.Choice("Public (0.0.0.0) [Unsafe without Auth]", value="public"),
            questionary.Choice("Tailscale (Private VPN)", value="tailscale"),
        ]
        bind_val = ClackUI.clack_select("Bind Mode", choices=modes, default=self.config.gateway.bind_mode)
        if bind_val:
            self.config.gateway.bind_mode = bind_val
            if bind_val == "loopback": self.config.gateway.host = "127.0.0.1"
            elif bind_val == "local": self.config.gateway.host = "0.0.0.0" # Simplification, or prompt for specific IP? usually 0.0.0.0 is fine for LAN
            elif bind_val == "public": self.config.gateway.host = "0.0.0.0"
            elif bind_val == "tailscale":
                self.config.gateway.host = "127.0.0.1"
                self.config.gateway.tailscale = True

        self.config.gateway.port = int(Prompt.ask("│  Port", default=str(self.config.gateway.port)))

        # Auth Config
        auth_mode = ClackUI.clack_select("Authentication", choices=[
            questionary.Choice("Token (Bearer)", value="token"),
            questionary.Choice("None (Testing only)", value="none"),
        ], default="token" if self.config.gateway.auth_token else "none")

        auth_configured = False
        if auth_mode == "token":
            import secrets
            current = self.config.gateway.auth_token
            default_token = current if current else secrets.token_hex(16)
            token = Prompt.ask("│  Auth Token", default=default_token)
            self.config.gateway.auth_token = token
            auth_configured = bool(token)
        else:
            self.config.gateway.auth_token = ""

        # Tailscale explicit toggle if not selected in bind mode
        if bind_val != "tailscale":
             self.config.gateway.tailscale = Confirm.ask("│  Enable Tailscale Funnel?", default=self.config.gateway.tailscale)

        # Mark as completed and save configuration
        self._save_setup_state("gateway", completed=True,
                             bind_mode=bind_val,
                             port=self.config.gateway.port,
                             auth_configured=auth_configured,
                             tailscale_enabled=self.config.gateway.tailscale)

        ClackUI.section_end()

    def _configure_skills(self):
        ClackUI.section_start("Skills")

        # Mark section as in progress
        self._save_setup_state("skills", completed=False, in_progress=True)

        from kabot.agent.skills import SkillsLoader
        loader = SkillsLoader(self.config.workspace_path)

        # 1. Load all skills with detailed status
        all_skills = loader.list_skills(filter_unavailable=False)

        eligible = [s for s in all_skills if s['eligible']]
        missing_reqs = [s for s in all_skills if not s['eligible'] and not s['missing']['os']]
        unsupported = [s for s in all_skills if s['missing']['os']]
        blocked = [] # Future feature

        # 2. Status Board
        console.print("│")
        console.print("◇  Skills status ─────────────╮")
        console.print("│                             │")
        console.print(f"│  Eligible: {len(eligible):<17}│")
        console.print(f"│  Missing requirements: {len(missing_reqs):<5}│")
        console.print(f"│  Unsupported on this OS: {len(unsupported):<3}│")
        console.print(f"│  Blocked by allowlist: {len(blocked):<5}│")
        console.print("│                             │")
        console.print("├─────────────────────────────╯")
        console.print("│")

        configured_skills = []
        installed_skills = []

        # 3. Configure/Install Prompt
        if not Confirm.ask("◇  Configure skills now? (recommended)", default=True):
            # Mark as completed even if skipped
            self._save_setup_state("skills", completed=True,
                                 configured_skills=configured_skills,
                                 installed_skills=installed_skills,
                                 skipped=True)
            ClackUI.section_end()
            return

        # 4. Installation Flow (Missing Binaries/Deps)
        installable = [s for s in missing_reqs if s['missing']['bins'] or s['install']]

        if installable:
            choices = [questionary.Choice("Skip for now", value="skip")]
            for s in installable:
                missing_str = ", ".join(s['missing']['bins'])
                label = f"{s['name']}"
                if missing_str:
                    label += f" (missing: {missing_str})"
                choices.append(questionary.Choice(label, value=s['name']))

            console.print("│")
            console.print("◆  Install missing skill dependencies")
            selected_names = questionary.checkbox(
                "Select skills to install dependencies for",
                choices=choices,
                style=questionary.Style([
                    ('qmark', 'fg:cyan bold'),
                    ('question', 'bold'),
                    ('pointer', 'fg:cyan bold'),
                    ('highlighted', 'fg:cyan bold'),
                    ('selected', 'fg:green'),
                ])
            ).ask()

            if selected_names and "skip" not in selected_names:
                for name in selected_names:
                    skill = next((s for s in installable if s['name'] == name), None)
                    if not skill: continue

                    console.print(f"│  [cyan]Installing dependencies for {name}...[/cyan]")

                    # Check for install metadata
                    install_meta = skill.get("install", {})

                    if install_meta and "cmd" in install_meta:
                        import subprocess
                        cmd = install_meta["cmd"]
                        console.print(f"│  Running: [dim]{cmd}[/dim]")
                        try:
                            # Run the command
                            result = subprocess.run(
                                cmd,
                                shell=True,
                                capture_output=True,
                                text=True,
                                cwd=self.config.workspace_path
                            )
                            if result.returncode == 0:
                                console.print(f"│  [green]✓ Installed successfully[/green]")
                                installed_skills.append(name)
                            else:
                                console.print(f"│  [red]✗ Install failed (exit {result.returncode})[/red]")
                                console.print(f"│    {result.stderr.strip()[:200]}") # Show partial error
                        except Exception as e:
                            console.print(f"│  [red]✗ Error executing command: {e}[/red]")

                    # Show manual instructions if we can't auto-install (or if checks still fail after install)
                    if skill['missing']['bins'] and (not install_meta or not install_meta.get("cmd")):
                        console.print(f"│  [yellow]Please install the following binaries manually:[/yellow]")
                        for b in skill['missing']['bins']:
                            console.print(f"│    - {b}")

                    console.print(f"│  [dim]Finished processing {name}[/dim]")

        # 5. Environment Variable Configuration (for Eligible + Newly Installed)
        console.print("│")

        # Filter for skills that need keys (iterate ALL skills again to catch those fixed by install)
        # We focus on `primaryEnv` or missing envs
        needs_env = []
        for s in all_skills:
            # Refresh status if needed, but for now use existing.
            # If we just installed deps, 'missing.bins' might be stale in this list unless we reload.
            # But 'missing.env' is what we care about here.
            if s['missing']['env']:
                needs_env.append(s)

        if needs_env:
            # console.print("◆  Configure Environment Variables") # OpenClaw doesn't have this header, it just asks

            for s in needs_env:
                primary_env = s.get('primaryEnv')
                if not primary_env: continue # Should not happen if missing['env'] is set due to our logic

                # Ask if user wants to configure this skill
                if not Confirm.ask(f"◇  Set {primary_env} for [cyan]{s['name']}[/cyan]?", default=True):
                    console.print("│")
                    continue

                current_val = os.environ.get(primary_env)
                val = Prompt.ask(f"│  Enter {primary_env}", default=current_val or "", password=True)

                if val:
                    if s['name'] not in self.config.skills:
                        self.config.skills[s['name']] = {"env": {}}
                    if "env" not in self.config.skills[s['name']]:
                        self.config.skills[s['name']]["env"] = {}

                    self.config.skills[s['name']]["env"][primary_env] = val
                    os.environ[primary_env] = val
                    console.print(f"│  [green]✓ Saved[/green]")
                    configured_skills.append(s['name'])
                console.print("│")

        # Install built-in skills after configuration
        console.print("│")
        builtin_installed = self._install_builtin_skills_with_progress()

        # Mark as completed and save configuration
        self._save_setup_state("skills", completed=True,
                             configured_skills=configured_skills,
                             installed_skills=installed_skills,
                             builtin_skills_installed=builtin_installed,
                             eligible_count=len(eligible),
                             missing_reqs_count=len(missing_reqs))

        ClackUI.section_end()

    def _configure_channels(self):
        # Mark section as in progress
        self._save_setup_state("channels", completed=False, in_progress=True)

        configured_channels = []

        while True:
            ClackUI.section_start("Channels")

            # Build choices based on current config status
            c = self.config.channels

            def status(enabled: bool):
                return "[green]ON[/green]" if enabled else "[dim]OFF[/dim]"

            # Show instance count if any exist
            instance_label = "Manage Channel Instances"
            if c.instances:
                instance_label = f"Manage Channel Instances ({len(c.instances)} configured)"

            options = [
                questionary.Choice(instance_label, value="instances"),
                questionary.Choice(f"Telegram  [{status(c.telegram.enabled)}]", value="telegram"),
                questionary.Choice(f"WhatsApp  [{status(c.whatsapp.enabled)}]", value="whatsapp"),
                questionary.Choice(f"Discord   [{status(c.discord.enabled)}]", value="discord"),
                questionary.Choice(f"Slack     [{status(c.slack.enabled)}]", value="slack"),
                questionary.Choice(f"Feishu    [{status(c.feishu.enabled)}]", value="feishu"),
                questionary.Choice(f"DingTalk  [{status(c.dingtalk.enabled)}]", value="dingtalk"),
                questionary.Choice(f"QQ        [{status(c.qq.enabled)}]", value="qq"),
                questionary.Choice(f"Email     [{status(c.email.enabled)}]", value="email"),
                questionary.Choice("Back", value="back"),
            ]

            choice = ClackUI.clack_select("Select channel to configure", choices=options)

            if choice == "back" or choice is None:
                ClackUI.section_end()
                break

            if choice == "instances":
                self._configure_channel_instances()

            elif choice == "telegram":
                if Confirm.ask("│  Enable Telegram?", default=c.telegram.enabled):
                    token = Prompt.ask("│  Bot Token", default=c.telegram.token)
                    if token:
                        c.telegram.token = token
                        c.telegram.enabled = True
                        configured_channels.append("telegram")
                        console.print("│  [green]✓ Telegram configured[/green]")
                else:
                    c.telegram.enabled = False

            elif choice == "whatsapp":
                self._configure_whatsapp()
                if c.whatsapp.enabled:
                    configured_channels.append("whatsapp")

            elif choice == "discord":
                if Confirm.ask("│  Enable Discord?", default=c.discord.enabled):
                    token = Prompt.ask("│  Bot Token", default=c.discord.token)
                    if token:
                        c.discord.token = token
                        c.discord.enabled = True
                        configured_channels.append("discord")

                    # Optional advanced fields
                    if Confirm.ask("│  Configure Gateway/Intents (Advanced)?"):
                        c.discord.gateway_url = Prompt.ask("│  Gateway URL", default=c.discord.gateway_url)
                        intents_str = Prompt.ask("│  Intents (comma separated)", default=",".join([str(i) for i in c.discord.intents or []]))
                        if intents_str:
                            try:
                                c.discord.intents = [int(i.strip()) for i in intents_str.split(",") if i.strip()]
                            except ValueError:
                                console.print("│  [red]Invalid intents format[/red]")
                else:
                    c.discord.enabled = False

            elif choice == "slack":
                if Confirm.ask("│  Enable Slack?", default=c.slack.enabled):
                    bot_token = Prompt.ask("│  Bot Token (xoxb-...)", default=c.slack.bot_token)
                    app_token = Prompt.ask("│  App Token (xapp-...)", default=c.slack.app_token)
                    if bot_token and app_token:
                        c.slack.bot_token = bot_token
                        c.slack.app_token = app_token
                        c.slack.enabled = True
                        configured_channels.append("slack")
                else:
                    c.slack.enabled = False

            elif choice == "feishu":
                if Confirm.ask("│  Enable Feishu?", default=c.feishu.enabled):
                    app_id = Prompt.ask("│  App ID", default=c.feishu.app_id)
                    app_secret = Prompt.ask("│  App Secret", default=c.feishu.app_secret)
                    if app_id and app_secret:
                        c.feishu.app_id = app_id
                        c.feishu.app_secret = app_secret
                        c.feishu.enabled = True
                        configured_channels.append("feishu")
                else:
                    c.feishu.enabled = False

            elif choice == "dingtalk":
                if Confirm.ask("│  Enable DingTalk?", default=c.dingtalk.enabled):
                    c.dingtalk.client_id = Prompt.ask("│  Client ID (AppKey)", default=c.dingtalk.client_id)
                    c.dingtalk.client_secret = Prompt.ask("│  Client Secret (AppSecret)", default=c.dingtalk.client_secret)
                    c.dingtalk.enabled = True
                    configured_channels.append("dingtalk")
                else:
                    c.dingtalk.enabled = False

            elif choice == "qq":
                if Confirm.ask("│  Enable QQ?", default=c.qq.enabled):
                    c.qq.app_id = Prompt.ask("│  App ID", default=c.qq.app_id)
                    c.qq.secret = Prompt.ask("│  App Secret", default=c.qq.secret)
                    c.qq.enabled = True
                    configured_channels.append("qq")
                else:
                    c.qq.enabled = False

            elif choice == "email":
                if Confirm.ask("│  Enable Email Channel?", default=c.email.enabled):
                    console.print("│  [bold]IMAP (Incoming)[/bold]")
                    c.email.imap_host = Prompt.ask("│  IMAP Host", default=c.email.imap_host)
                    c.email.imap_username = Prompt.ask("│  IMAP User", default=c.email.imap_username)
                    if Confirm.ask("│  Update IMAP Password?"):
                        c.email.imap_password = Prompt.ask("│  IMAP Password", password=True)

                    console.print("│  [bold]SMTP (Outgoing)[/bold]")
                    c.email.smtp_host = Prompt.ask("│  SMTP Host", default=c.email.smtp_host)
                    c.email.smtp_username = Prompt.ask("│  SMTP User", default=c.email.smtp_username)
                    if Confirm.ask("│  Update SMTP Password?"):
                        c.email.smtp_password = Prompt.ask("│  SMTP Password", password=True)

                    c.email.from_address = Prompt.ask("│  Sender Address (From)", default=c.email.from_address)
                    c.email.enabled = True
                    configured_channels.append("email")
                else:
                    c.email.enabled = False

            ClackUI.section_end()

        # Mark as completed and save configuration
        self._save_setup_state("channels", completed=True,
                             configured_channels=configured_channels,
                             instance_count=len(c.instances) if c.instances else 0)

    def _validate_api_key(self, provider: str, api_key: str) -> bool:
        """Validate API key by making a test call."""
        if not api_key or api_key.strip() == "":
            return True  # Skip validation for empty keys

        try:
            if provider == "openai":
                import openai
                client = openai.OpenAI(api_key=api_key)
                client.models.list()
                return True
            elif provider == "anthropic":
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=1,
                    messages=[{"role": "user", "content": "test"}]
                )
                return True
            elif provider == "groq":
                import groq
                client = groq.Groq(api_key=api_key)
                client.models.list()
                return True
        except Exception as e:
            console.print(f"│  [red]Validation failed: {str(e)}[/red]")
            return False

        return True  # Default to valid for unknown providers

    def _validate_provider_credentials(self, provider_id: str):
        """Validate provider credentials with user feedback and retry options."""
        from kabot.config.loader import load_config
        from rich.prompt import Confirm
        import signal
        import time

        # Load current config to get the API key
        config = load_config()

        # Map provider IDs to config fields and extract API key
        provider_mapping = {
            "openai": ("openai", "api_key"),
            "anthropic": ("anthropic", "api_key"),
            "google": ("gemini", "api_key"),
            "groq": ("groq", "api_key"),
            "kimi": ("moonshot", "api_key"),
            "minimax": ("minimax", "api_key")
        }

        if provider_id not in provider_mapping:
            console.print(f"│  [yellow]Validation not supported for {provider_id}[/yellow]")
            return

        config_field, key_field = provider_mapping[provider_id]
        provider_config = getattr(config.providers, config_field, None)

        if not provider_config:
            console.print(f"│  [yellow]No configuration found for {provider_id}[/yellow]")
            return

        # Get API key from active profile or legacy field
        api_key = None
        if provider_config.active_profile and provider_config.profiles:
            active_profile = provider_config.profiles.get(provider_config.active_profile)
            if active_profile:
                api_key = getattr(active_profile, key_field, None)

        if not api_key:
            api_key = getattr(provider_config, key_field, None)

        if not api_key:
            console.print(f"│  [yellow]No API key found for {provider_id}[/yellow]")
            return

        console.print("│")
        console.print(f"│  [cyan]Validating {provider_id} API key...[/cyan]")

        # Validation with timeout and retry logic
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                # Set up timeout handler
                def timeout_handler(signum, frame):
                    raise TimeoutError("Validation timed out")

                # Set timeout for validation (10 seconds)
                if hasattr(signal, 'SIGALRM'):  # Unix systems
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(10)

                # Perform validation
                is_valid = self._validate_api_key(provider_id, api_key)

                # Clear timeout
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)

                if is_valid:
                    console.print(f"│  [green]✓ {provider_id} API key is valid[/green]")
                    return
                else:
                    console.print(f"│  [red]✗ {provider_id} API key validation failed[/red]")
                    break

            except TimeoutError:
                console.print(f"│  [yellow]⚠ Validation timed out (attempt {attempt + 1}/{max_retries + 1})[/yellow]")
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)

            except ImportError as e:
                console.print(f"│  [yellow]⚠ Cannot validate {provider_id}: Missing dependency ({str(e)})[/yellow]")
                console.print(f"│  [dim]Install with: pip install {provider_id}[/dim]")
                return

            except Exception as e:
                console.print(f"│  [red]✗ Validation error: {str(e)}[/red]")
                break

            # Ask if user wants to retry on timeout
            if attempt < max_retries:
                if not Confirm.ask("│  Retry validation?", default=True):
                    break
                console.print("│  [cyan]Retrying...[/cyan]")
                time.sleep(1)

        # Handle validation failure
        console.print("│")
        if Confirm.ask("│  Continue anyway? (You can fix this later)", default=True):
            console.print("│  [yellow]⚠ Continuing with potentially invalid key[/yellow]")
        else:
            console.print("│  [dim]You can reconfigure this provider later from the main menu[/dim]")

    def _configure_channel_instances(self):
        """Configure multiple channel instances (e.g., 4 Telegram bots, 4 Discord bots)."""
        from kabot.config.schema import ChannelInstance

        while True:
            ClackUI.section_start("Channel Instances")

            # Show current instances
            if self.config.channels.instances:
                console.print("│  [bold]Current Instances:[/bold]")
                for idx, inst in enumerate(self.config.channels.instances, 1):
                    status = "[green]✓[/green]" if inst.enabled else "[dim]✗[/dim]"
                    binding = f" → {inst.agent_binding}" if inst.agent_binding else ""
                    console.print(f"│    {idx}. [{inst.type}] {inst.id} {status}{binding}")
                console.print("│")

            options = [
                questionary.Choice("Add Instance", value="add"),
                questionary.Choice("Edit Instance", value="edit"),
                questionary.Choice("Delete Instance", value="delete"),
                questionary.Choice("Back", value="back"),
            ]

            choice = ClackUI.clack_select("Manage Instances", choices=options)

            if choice == "back" or choice is None:
                ClackUI.section_end()
                break
            elif choice == "add":
                self._add_channel_instance()
            elif choice == "edit":
                self._edit_channel_instance()
            elif choice == "delete":
                self._delete_channel_instance()

    def _add_channel_instance(self):
        """Add a new channel instance."""
        from kabot.config.schema import ChannelInstance

        instance_id = Prompt.ask("│  Instance ID (e.g., work_bot, personal_bot)")
        if not instance_id:
            console.print("│  [yellow]Cancelled[/yellow]")
            return

        channel_type = ClackUI.clack_select("Channel Type", choices=[
            questionary.Choice("Telegram", value="telegram"),
            questionary.Choice("Discord", value="discord"),
            questionary.Choice("WhatsApp", value="whatsapp"),
            questionary.Choice("Slack", value="slack"),
        ])

        # Get type-specific configuration
        config_dict = {}

        if channel_type == "telegram":
            token = Prompt.ask("│  Bot Token")
            if not token:
                console.print("│  [yellow]Cancelled[/yellow]")
                return
            config_dict = {"token": token, "allow_from": []}

        elif channel_type == "discord":
            token = Prompt.ask("│  Bot Token")
            if not token:
                console.print("│  [yellow]Cancelled[/yellow]")
                return
            config_dict = {"token": token, "allow_from": []}

        elif channel_type == "whatsapp":
            bridge_url = Prompt.ask("│  Bridge URL", default="ws://localhost:3001")
            config_dict = {"bridge_url": bridge_url, "allow_from": []}

        elif channel_type == "slack":
            bot_token = Prompt.ask("│  Bot Token (xoxb-...)")
            app_token = Prompt.ask("│  App Token (xapp-...)")
            if not bot_token or not app_token:
                console.print("│  [yellow]Cancelled[/yellow]")
                return
            config_dict = {"bot_token": bot_token, "app_token": app_token}

        # Optional agent binding
        agent_binding = None
        if self.config.agents.agents:
            if Confirm.ask("│  Bind to specific agent?", default=False):
                agent_ids = [a.id for a in self.config.agents.agents]
                agent_binding = ClackUI.clack_select("Agent ID", choices=[
                    questionary.Choice(aid, value=aid) for aid in agent_ids
                ])

        # Create instance
        instance = ChannelInstance(
            id=instance_id,
            type=channel_type,
            enabled=True,
            config=config_dict,
            agent_binding=agent_binding
        )

        self.config.channels.instances.append(instance)
        console.print(f"│  [green]✓ Added {channel_type} instance '{instance_id}'[/green]")

    def _edit_channel_instance(self):
        """Edit an existing channel instance."""
        if not self.config.channels.instances:
            console.print("│  [yellow]No instances configured[/yellow]")
            return

        # Show instances with numbers
        choices = []
        for idx, inst in enumerate(self.config.channels.instances, 1):
            label = f"{idx}. [{inst.type}] {inst.id}"
            choices.append(questionary.Choice(label, value=idx - 1))

        idx = ClackUI.clack_select("Select instance to edit", choices=choices)
        if idx is None:
            return

        instance = self.config.channels.instances[idx]

        # Edit enabled status
        instance.enabled = Confirm.ask(
            f"│  Enable {instance.id}?",
            default=instance.enabled
        )

        # Edit agent binding
        if self.config.agents.agents:
            if Confirm.ask("│  Change agent binding?", default=False):
                agent_ids = ["none"] + [a.id for a in self.config.agents.agents]
                choices = [questionary.Choice(aid, value=aid) for aid in agent_ids]
                binding = ClackUI.clack_select("Agent ID", choices=choices)
                instance.agent_binding = None if binding == "none" else binding

        console.print(f"│  [green]✓ Updated {instance.id}[/green]")

    def _delete_channel_instance(self):
        """Delete a channel instance."""
        if not self.config.channels.instances:
            console.print("│  [yellow]No instances configured[/yellow]")
            return

        # Show instances with numbers
        choices = []
        for idx, inst in enumerate(self.config.channels.instances, 1):
            label = f"{idx}. [{inst.type}] {inst.id}"
            choices.append(questionary.Choice(label, value=idx - 1))

        idx = ClackUI.clack_select("Select instance to delete", choices=choices)
        if idx is None:
            return

        instance = self.config.channels.instances[idx]
        if Confirm.ask(f"│  Delete {instance.id}?", default=False):
            self.config.channels.instances.pop(idx)
            console.print(f"│  [green]✓ Deleted {instance.id}[/green]")

    def _configure_whatsapp(self):
        """Special flow for WhatsApp Bridge."""
         # Check if we should enable/disable first
        if not Confirm.ask("│  Enable WhatsApp?", default=self.config.channels.whatsapp.enabled):
            self.config.channels.whatsapp.enabled = False
            return

        self.config.channels.whatsapp.enabled = True
        
        # Bridge setup logic
        try:
            from kabot.cli.bridge_utils import get_bridge_dir, run_bridge_login
            import shutil
            
            # Check/Install Bridge
            with console.status("│  Checking WhatsApp Bridge..."):
                bridge_dir = get_bridge_dir()
            
            console.print("│  [green]✓ Bridge installed[/green]")
            
            if Confirm.ask("│  Connect now? (Show QR Code)"):
                console.print("│")
                console.print("│  [yellow]starting bridge... Press Ctrl+C to stop/return after scanning.[/yellow]")
                console.print("│")
                try:
                    run_bridge_login()
                except KeyboardInterrupt:
                    console.print("\n│  [yellow]Returned to wizard.[/yellow]")
                except Exception as e:
                     console.print(f"│  [red]Error running bridge: {e}[/red]")
        except ImportError:
             console.print("│  [red]Could not load CLI commands. Please install dependencies.[/red]")
        except Exception as e:
             console.print(f"│  [red]Bridge setup failed: {e}[/red]")

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
        retention = Prompt.ask("│  File Retention (e.g. '7 days', '1 week')", default=self.config.logging.retention)
        self.config.logging.retention = retention

        # DB Retention
        db_days = Prompt.ask("│  Database Retention (days)", default=str(self.config.logging.db_retention_days))
        try:
            self.config.logging.db_retention_days = int(db_days)
        except ValueError:
            console.print("│  [red]Invalid number, keeping default.[/red]")

        console.print("│  [green]✓ Logging configured[/green]")

        # Mark as completed and save configuration
        self._save_setup_state("logging", completed=True,
                             log_level=level,
                             file_retention=retention,
                             db_retention_days=self.config.logging.db_retention_days)

        ClackUI.section_end()

    def _run_doctor(self):
        from kabot.utils.doctor import KabotDoctor
        doc = KabotDoctor()
        doc.render_report()
        Prompt.ask("│\n◆  Press Enter to return to menu")

    def _install_builtin_skills(self):
        """Copy built-in skills to workspace if not present."""
        skills_src = Path(__file__).parent.parent / "skills"
        skills_dst = Path(self.config.agents.defaults.workspace) / "skills"

        if not skills_src.exists():
            console.print(f"│  [yellow]Warning: Built-in skills not found at {skills_src}[/yellow]")
            return

        # Ensure destination exists
        if not skills_dst.exists():
            os.makedirs(skills_dst, exist_ok=True)
            console.print(f"│  [cyan]Initializing skills directory at {skills_dst}...[/cyan]")

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
                         console.print(f"│  [red]Failed to copy skill {item.name}: {e}[/red]")

        if count > 0:
            console.print(f"│  [green]✓ Installed {count} built-in skills to workspace[/green]")

    def _install_builtin_skills_with_progress(self) -> bool:
        """Install built-in skills with progress indicators and error handling."""
        console.print("◇  [cyan]Installing built-in skills...[/cyan]")

        skills_src = Path(__file__).parent.parent / "skills"
        skills_dst = Path(self.config.agents.defaults.workspace) / "skills"

        # Check if source skills exist
        if not skills_src.exists():
            console.print(f"│  [yellow]⚠ Built-in skills not found at {skills_src}[/yellow]")
            console.print("│  [dim]Continuing without built-in skills installation[/dim]")
            return False

        # Ensure destination exists
        try:
            if not skills_dst.exists():
                os.makedirs(skills_dst, exist_ok=True)
                console.print(f"│  [cyan]Created skills directory: {skills_dst}[/cyan]")
        except Exception as e:
            console.print(f"│  [red]✗ Failed to create skills directory: {e}[/red]")
            console.print("│  [dim]Continuing without built-in skills installation[/dim]")
            return False

        # Discover available skills
        available_skills = []
        for item in skills_src.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                available_skills.append(item)

        if not available_skills:
            console.print("│  [yellow]⚠ No built-in skills found to install[/yellow]")
            return False

        console.print(f"│  Found {len(available_skills)} built-in skills to install")

        # Install skills with progress feedback
        import shutil
        installed_count = 0
        failed_count = 0
        skipped_count = 0

        for skill_src in available_skills:
            skill_name = skill_src.name
            skill_dst = skills_dst / skill_name

            if skill_dst.exists():
                console.print(f"│  [dim]- {skill_name} (already exists)[/dim]")
                skipped_count += 1
                continue

            try:
                console.print(f"│  [cyan]Installing {skill_name}...[/cyan]")
                shutil.copytree(skill_src, skill_dst)
                console.print(f"│  [green]✓ {skill_name}[/green]")
                installed_count += 1
            except Exception as e:
                console.print(f"│  [red]✗ {skill_name}: {str(e)[:60]}...[/red]")
                failed_count += 1

        # Summary
        console.print("│")
        if installed_count > 0:
            console.print(f"│  [green]✓ Successfully installed {installed_count} built-in skills[/green]")

        if skipped_count > 0:
            console.print(f"│  [dim]- Skipped {skipped_count} existing skills[/dim]")

        if failed_count > 0:
            console.print(f"│  [yellow]⚠ Failed to install {failed_count} skills[/yellow]")
            console.print("│  [dim]Setup will continue - you can manually install these later[/dim]")

        return installed_count > 0

def run_interactive_setup() -> Config:
    wizard = SetupWizard()
    # Ensure workspace exists and install skills before running wizard
    os.makedirs(os.path.expanduser(wizard.config.agents.defaults.workspace), exist_ok=True)
    wizard._install_builtin_skills()
    return wizard.run()
