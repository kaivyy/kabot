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
from kabot.config.schema import Config, AuthProfile, AgentConfig, ChannelInstance
from kabot.config.loader import load_config, save_config
from kabot.cli.fleet_templates import FLEET_TEMPLATES, get_template_roles
from kabot.utils.network import probe_gateway
from kabot.utils.environment import detect_runtime_environment, recommended_gateway_mode
from kabot.providers.registry import ModelRegistry

import sys
if hasattr(sys.stdout, 'encoding') and sys.stdout.encoding:
    if sys.stdout.encoding.lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

console = Console()

class ClackUI:
    """Helper to draw Kabot/Clack style UI components."""
    
    @staticmethod
    def header():
        logo = r"""
 ██╗  ██╗ █████╗ ██████╗  ██████╗ ████████╗
 ██║ ██╔╝██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝
 █████╔╝ ███████║██████╔╝██║   ██║   ██║   
 ██╔═██╗ ██╔══██║██╔══██╗██║   ██║   ██║   
 ██║  ██╗██║  ██║██████╔╝╚██████╔╝   ██║   
 ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝  ╚═════╝    ╚═╝   
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
        model = c.agents.defaults.model
        if hasattr(model, "primary"):
            fallbacks = ", ".join(getattr(model, "fallbacks", []) or [])
            lines.append(f"model: {model.primary} (fallbacks: {fallbacks})")
        else:
            lines.append(f"model: {model}")
        
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

        # Advanced tools
        adv = []
        if c.tools.web.fetch.firecrawl_api_key: adv.append("firecrawl")
        if c.tools.web.search.perplexity_api_key: adv.append("perplexity")
        if c.tools.web.search.xai_api_key: adv.append("grok")
        if adv:
            lines.append(f"advanced: {', '.join(adv)}")

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
            console.print(f"│  [yellow]Warning: Could not save setup state: {e}[/yellow]")

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
            console.print(f"â”‚  [dim]Detected: {detected_env['platform']} ({', '.join(detected_tags)})[/dim]")
        else:
            console.print(f"â”‚  [dim]Detected: {detected_env['platform']}[/dim]")
        suggested_mode = self._suggest_gateway_mode()

        mode = ClackUI.clack_select(
            "Where will the Gateway run?",
            choices=[
                questionary.Choice("Local (this machine)", value="local"),
                questionary.Choice("Remote (info-only)", value="remote"),
            ],
            default=suggested_mode
        )
        ClackUI.section_end()

        if mode is None: return self.config

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
            elif choice == "gateway":
                self._configure_gateway()
            elif choice == "channels",
            "autostart":
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
                "tools",
                "gateway",
                "skills",
                "channels",
            "autostart",
                "autostart",
                "logging",
                "doctor",
                "finish",
            ]
        return [
            "workspace",
            "model",
            "tools",     # <-- Added advanced tools to simple mode
            "skills",
            "channels",
            "autostart",
                "autostart",
            "finish",
        ]

    def _main_menu_choices(self) -> list:
        labels = {
            "workspace": "Workspace (Set path + sessions)",
            "model": "Model / Auth (Providers, Keys, OAuth)",
            "tools": "Tools & Sandbox (Search, Docker, Shell)",
            "gateway": "Gateway (Port, Host, Bindings)",
            "skills": "Skills (Install & Configure)",
            "channels",
            "autostart": "Channels (Telegram, WhatsApp, Slack)",
            "logging": "Logging & Debugging",
            "doctor": "Health Check (Run system diagnostic)",
            "finish": "Continue & Finish",
        }
        return [questionary.Choice(labels[value], value=value) for value in self._main_menu_option_values()]

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
        self._write_setup_state(state)

        console.print(f"│  [green]✓ Workspace path set.[/green]")
        ClackUI.section_end()

    def _sync_provider_credentials_from_disk(self) -> None:
        """Merge provider credentials saved by AuthManager into in-memory wizard config."""
        try:
            disk_config = load_config()
            self.config.providers = disk_config.providers.model_copy(deep=True)
        except Exception as e:
            console.print(f"│  [yellow]Warning: Could not sync provider credentials: {e}[/yellow]")

    def _provider_has_credentials(self, provider_config) -> bool:
        """Check whether a provider config has any API key/OAuth credentials."""
        if not provider_config:
            return False
        if provider_config.api_key or getattr(provider_config, "setup_token", None):
            return True
        if provider_config.active_profile in provider_config.profiles:
            active = provider_config.profiles[provider_config.active_profile]
            if active.api_key or active.oauth_token or active.setup_token:
                return True
        for profile in provider_config.profiles.values():
            if profile.api_key or profile.oauth_token or profile.setup_token:
                return True
        return False

    def _apply_post_login_defaults(self, provider_id: str) -> bool:
        """Apply provider-specific default model behavior after successful login."""
        from kabot.config.schema import AgentModelConfig

        if provider_id != "openai":
            return False

        openai_codex_cfg = self.config.providers.openai_codex
        if not self._provider_has_credentials(openai_codex_cfg):
            return False

        current_model = self.config.agents.defaults.model
        current_primary = current_model.primary if isinstance(current_model, AgentModelConfig) else current_model
        if not isinstance(current_primary, str):
            return False

        if not (current_primary.startswith("openai/") or current_primary.startswith("openai-codex/")):
            return False

        target_primary = "openai-codex/gpt-5.3-codex"
        target_fallbacks = [
            "openai/gpt-5.2-codex",
            "openai/gpt-4o-mini",
        ]

        if isinstance(current_model, AgentModelConfig):
            if current_model.primary == target_primary and current_model.fallbacks == target_fallbacks:
                return False

        self.config.agents.defaults.model = AgentModelConfig(
            primary=target_primary,
            fallbacks=target_fallbacks,
        )
        return True

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
                    self._sync_provider_credentials_from_disk()
                    configured_providers.append(provider_val)
                    self._apply_post_login_defaults(provider_val)
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
        self._write_setup_state(state)

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
        freedom_mode = Confirm.ask(
            "│  Enable OpenClaw-style freedom mode? [Trusted environment only]",
            default=bool(self.config.tools.exec.auto_approve),
        )
        self._set_openclaw_freedom_mode(freedom_mode)

        self.config.tools.restrict_to_workspace = Confirm.ask(
            "│  Restrict FS usage to workspace?",
            default=self.config.tools.restrict_to_workspace,
        )
        self.config.tools.exec.timeout = int(Prompt.ask("│  Command Timeout (s)", default=str(self.config.tools.exec.timeout)))
        self.config.tools.exec.auto_approve = freedom_mode

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

        # Advanced Tools (Optional)
        console.print("│")
        console.print("│  [bold]Advanced Tools (Optional)[/bold]")
        console.print("│  [dim]Premium API keys for enhanced capabilities. Press Enter to skip.[/dim]")
        console.print("│")

        # FireCrawl
        firecrawl_key = Prompt.ask(
            "│  FireCrawl API Key (JS rendering)",
            default=self.config.tools.web.fetch.firecrawl_api_key or "",
        )
        if firecrawl_key.strip():
            self.config.tools.web.fetch.firecrawl_api_key = firecrawl_key.strip()
            console.print("│  [green]✓ FireCrawl configured[/green]")
        else:
            console.print("│  [dim]  Skipped (BeautifulSoup only)[/dim]")

        # Perplexity
        perplexity_key = Prompt.ask(
            "│  Perplexity API Key (AI search)",
            default=self.config.tools.web.search.perplexity_api_key or "",
        )
        if perplexity_key.strip():
            self.config.tools.web.search.perplexity_api_key = perplexity_key.strip()
            self.config.tools.web.search.provider = "perplexity"
            console.print("│  [green]✓ Perplexity configured (set as default search)[/green]")
        else:
            console.print("│  [dim]  Skipped (Brave Search only)[/dim]")

        # xAI / Grok
        xai_key = Prompt.ask(
            "│  xAI API Key (Grok search)",
            default=self.config.tools.web.search.xai_api_key or "",
        )
        if xai_key.strip():
            self.config.tools.web.search.xai_api_key = xai_key.strip()
            if not perplexity_key.strip():
                self.config.tools.web.search.provider = "grok"
                console.print("│  [green]✓ Grok configured (set as default search)[/green]")
            else:
                console.print("│  [green]✓ Grok configured (available as fallback)[/green]")
        else:
            console.print("│  [dim]  Skipped[/dim]")

        # Summary
        console.print("│")
        adv_tools = []
        if self.config.tools.web.fetch.firecrawl_api_key:
            adv_tools.append("FireCrawl")
        if self.config.tools.web.search.perplexity_api_key:
            adv_tools.append("Perplexity")
        if self.config.tools.web.search.xai_api_key:
            adv_tools.append("Grok")
        if adv_tools:
            console.print(f"│  [bold green]Military-grade tools active: {', '.join(adv_tools)}[/bold green]")
        else:
            console.print("│  [dim]Standard mode (all tools work with defaults)[/dim]")

        # Mark as completed and save configuration
        self._save_setup_state("tools", completed=True,
                             web_search_enabled=bool(self.config.tools.web.search.api_key),
                             docker_enabled=docker_enabled,
                             restrict_to_workspace=self.config.tools.restrict_to_workspace,
                             freedom_mode=freedom_mode)

        ClackUI.section_end()

    def _set_openclaw_freedom_mode(self, enabled: bool) -> None:
        """Apply trusted-mode defaults for maximum tool flexibility."""
        if enabled:
            self.config.tools.exec.auto_approve = True
            self.config.tools.restrict_to_workspace = False
            self.config.integrations.http_guard.enabled = False
            self.config.integrations.http_guard.block_private_networks = False
            self.config.integrations.http_guard.allow_hosts = []
            self.config.integrations.http_guard.deny_hosts = []
            return

        self.config.tools.exec.auto_approve = False
        self.config.integrations.http_guard.enabled = True
        self.config.integrations.http_guard.block_private_networks = True
        self.config.integrations.http_guard.allow_hosts = []
        self.config.integrations.http_guard.deny_hosts = [
            "localhost",
            "127.0.0.1",
            "169.254.169.254",
            "metadata.google.internal",
        ]

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

        port_input = Prompt.ask("│  Port", default=str(self.config.gateway.port))
        try:
            self.config.gateway.port = int(port_input)
        except (TypeError, ValueError):
            console.print("│  [yellow]Invalid port, keeping previous value[/yellow]")

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

        injected_env_count = self._inject_configured_skill_env()
        if injected_env_count > 0:
            console.print(f"│  [dim]Loaded {injected_env_count} configured skill env var(s)[/dim]")

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

            selected_names = selected_names or []
            selected_install_names = [name for name in selected_names if name != "skip"]
            if selected_install_names:
                for name in selected_install_names:
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
        self._save_setup_state("channels",
            "autostart",
                "autostart", completed=False, in_progress=True)

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
                        intents_str = Prompt.ask(
                            "│  Intents (bitmask or comma separated)",
                            default=self._discord_intents_default_value(c.discord.intents),
                        )
                        if intents_str:
                            parsed_intents = self._parse_discord_intents(intents_str)
                            if parsed_intents is None:
                                console.print("│  [red]Invalid intents format[/red]")
                            else:
                                c.discord.intents = parsed_intents
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
        self._save_setup_state("channels",
            "autostart",
                "autostart", completed=True,
                             configured_channels=configured_channels,
                             instance_count=len(c.instances) if c.instances else 0)

    def _inject_configured_skill_env(self) -> int:
        configured_skills = getattr(self.config, "skills", {}) or {}
        if not isinstance(configured_skills, dict):
            return 0

        injected = 0
        for skill_cfg in configured_skills.values():
            if not isinstance(skill_cfg, dict):
                continue
            env_vars = skill_cfg.get("env", {})
            if not isinstance(env_vars, dict):
                continue
            for key, value in env_vars.items():
                if not key or value in (None, ""):
                    continue
                if key not in os.environ:
                    os.environ[key] = str(value)
                    injected += 1
        return injected

    def _discord_intents_default_value(self, current: Any) -> str:
        if isinstance(current, int):
            return str(current)
        if isinstance(current, list):
            values = [str(item) for item in current if isinstance(item, int)]
            return ",".join(values) if values else "37377"
        return "37377"

    def _parse_discord_intents(self, raw_value: str) -> int | None:
        cleaned = (raw_value or "").strip()
        if not cleaned:
            return None
        try:
            if "," not in cleaned:
                return int(cleaned, 0)
            value = 0
            for segment in cleaned.split(","):
                bit = segment.strip()
                if not bit:
                    continue
                value |= int(bit, 0)
            return value
        except ValueError:
            return None

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

        # Map provider IDs to config fields for credential lookup
        provider_mapping = {
            "openai": "openai",
            "anthropic": "anthropic",
            "google": "gemini",
            "groq": "groq",
            "kimi": "moonshot",
            "minimax": "minimax"
        }

        if provider_id not in provider_mapping:
            console.print(f"│  [yellow]Validation not supported for {provider_id}[/yellow]")
            return

        config_field = provider_mapping[provider_id]
        provider_config = getattr(config.providers, config_field, None)

        if not provider_config:
            console.print(f"│  [yellow]No configuration found for {provider_id}[/yellow]")
            return

        # Get credential from active profile or legacy field.
        credential_fields = ("api_key", "oauth_token", "setup_token")
        api_key = None
        if provider_config.active_profile and provider_config.profiles:
            active_profile = provider_config.profiles.get(provider_config.active_profile)
            if active_profile:
                for field in credential_fields:
                    value = getattr(active_profile, field, None)
                    if value:
                        api_key = value
                        break

        if not api_key:
            for field in credential_fields:
                value = getattr(provider_config, field, None)
                if value:
                    api_key = value
                    break

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

    def _instance_id_exists(self, instance_id: str) -> bool:
        return any(inst.id == instance_id for inst in self.config.channels.instances)

    def _next_available_instance_id(self, preferred_id: str) -> str:
        base = (preferred_id or "").strip().replace(" ", "_")
        if not base:
            base = "bot"
        if not self._instance_id_exists(base):
            return base
        i = 2
        while True:
            candidate = f"{base}_{i}"
            if not self._instance_id_exists(candidate):
                return candidate
            i += 1

    def _ensure_agent_exists(self, agent_id: str, model_override: str | None = None) -> str:
        clean_id = (agent_id or "").strip().replace(" ", "_") or "main"
        existing = next((a for a in self.config.agents.agents if a.id == clean_id), None)
        if existing:
            if model_override:
                existing.model = model_override
            return clean_id

        workspace_path = Path.home() / ".kabot" / f"workspace-{clean_id}"
        workspace_path.mkdir(parents=True, exist_ok=True)
        self.config.agents.agents.append(
            AgentConfig(
                id=clean_id,
                name=clean_id.replace("_", " ").title(),
                model=model_override or None,
                workspace=str(workspace_path),
                default=(len(self.config.agents.agents) == 0),
            )
        )
        return clean_id

    def _add_channel_instance_record(
        self,
        *,
        instance_id: str,
        channel_type: str,
        config_dict: dict[str, Any],
        agent_binding: str | None = None,
        auto_create_agent: bool = False,
        model_override: str | None = None,
    ) -> ChannelInstance:
        final_id = self._next_available_instance_id(instance_id)
        final_binding = agent_binding
        if auto_create_agent:
            final_binding = self._ensure_agent_exists(final_binding or final_id, model_override=model_override)

        instance = ChannelInstance(
            id=final_id,
            type=channel_type,
            enabled=True,
            config=config_dict,
            agent_binding=final_binding,
        )
        self.config.channels.instances.append(instance)
        return instance

    def _prompt_instance_config(self, channel_type: str) -> dict[str, Any] | None:
        if channel_type == "telegram":
            token = Prompt.ask("|  Bot Token")
            if not token:
                return None
            return {"token": token, "allow_from": []}

        if channel_type == "discord":
            token = Prompt.ask("|  Bot Token")
            if not token:
                return None
            return {"token": token, "allow_from": []}

        if channel_type == "whatsapp":
            bridge_url = Prompt.ask("|  Bridge URL", default="ws://localhost:3001")
            return {"bridge_url": bridge_url, "allow_from": []}

        if channel_type == "slack":
            bot_token = Prompt.ask("|  Bot Token (xoxb-...)")
            app_token = Prompt.ask("|  App Token (xapp-...)")
            if not bot_token or not app_token:
                return None
            return {"bot_token": bot_token, "app_token": app_token}

        return None

    def _prompt_agent_binding(self, default_agent_id: str) -> tuple[str | None, bool, str | None]:
        if not self.config.agents.agents:
            if Confirm.ask("|  Auto-create dedicated agent for this bot?", default=True):
                use_custom_model = Confirm.ask("|  Set custom model for this new agent?", default=False)
                model_override = Prompt.ask("|  Agent Model", default="").strip() if use_custom_model else None
                return default_agent_id, True, model_override or None
            return None, False, None

        if not Confirm.ask("|  Bind this bot to a specific agent?", default=False):
            return None, False, None

        choices = [
            questionary.Choice("No binding (shared default)", value="__none__"),
            questionary.Choice("Create new agent", value="__create__"),
        ]
        choices.extend(questionary.Choice(agent.id, value=agent.id) for agent in self.config.agents.agents)
        selection = ClackUI.clack_select("Agent Binding", choices=choices)

        if selection == "__none__":
            return None, False, None
        if selection == "__create__":
            new_agent_id = Prompt.ask("|  New Agent ID", default=default_agent_id)
            use_custom_model = Confirm.ask("|  Set custom model for this new agent?", default=False)
            model_override = Prompt.ask("|  Agent Model", default="").strip() if use_custom_model else None
            return new_agent_id, True, model_override or None
        return selection, False, None

    def _configure_channel_instances(self):
        """Configure multiple channel instances (e.g., 4 Telegram bots, 4 Discord bots)."""
        while True:
            ClackUI.section_start("Channel Instances")

            if self.config.channels.instances:
                console.print("|  [bold]Current Instances:[/bold]")
                for idx, inst in enumerate(self.config.channels.instances, 1):
                    status = "[green]ON[/green]" if inst.enabled else "[dim]OFF[/dim]"
                    binding = f" -> {inst.agent_binding}" if inst.agent_binding else ""
                    console.print(f"|    {idx}. [{inst.type}] {inst.id} {status}{binding}")
                console.print("|")

            options = [
                questionary.Choice("Add Instance", value="add"),
                questionary.Choice("Quick Add Multiple", value="bulk"),
                questionary.Choice("Apply Fleet Template", value="template"),
                questionary.Choice("Edit Instance", value="edit"),
                questionary.Choice("Delete Instance", value="delete"),
                questionary.Choice("Back", value="back"),
            ]
            choice = ClackUI.clack_select("Manage Instances", choices=options)

            if choice == "back" or choice is None:
                ClackUI.section_end()
                break
            if choice == "add":
                self._add_channel_instance()
            elif choice == "bulk":
                self._bulk_add_channel_instances()
            elif choice == "template":
                self._apply_fleet_template_interactive()
            elif choice == "edit":
                self._edit_channel_instance()
            elif choice == "delete":
                self._delete_channel_instance()

    def _add_channel_instance(self):
        """Add a single channel instance with optional dedicated agent creation."""
        instance_id = Prompt.ask("|  Instance ID (e.g., work_bot, personal_bot)").strip()
        if not instance_id:
            console.print("|  [yellow]Cancelled[/yellow]")
            return

        channel_type = ClackUI.clack_select(
            "Channel Type",
            choices=[
                questionary.Choice("Telegram", value="telegram"),
                questionary.Choice("Discord", value="discord"),
                questionary.Choice("WhatsApp", value="whatsapp"),
                questionary.Choice("Slack", value="slack"),
            ],
        )
        if not channel_type:
            return

        config_dict = self._prompt_instance_config(channel_type)
        if not config_dict:
            console.print("|  [yellow]Cancelled[/yellow]")
            return

        agent_binding, auto_create_agent, model_override = self._prompt_agent_binding(instance_id)
        instance = self._add_channel_instance_record(
            instance_id=instance_id,
            channel_type=channel_type,
            config_dict=config_dict,
            agent_binding=agent_binding,
            auto_create_agent=auto_create_agent,
            model_override=model_override,
        )
        console.print(f"|  [green]OK[/green] Added {channel_type} instance '{instance.id}'")

    def _bulk_add_channel_instances(self):
        """Quick flow for adding many instances at once."""
        channel_type = ClackUI.clack_select(
            "Bulk Channel Type",
            choices=[
                questionary.Choice("Telegram", value="telegram"),
                questionary.Choice("Discord", value="discord"),
                questionary.Choice("WhatsApp", value="whatsapp"),
                questionary.Choice("Slack", value="slack"),
            ],
        )
        if not channel_type:
            return

        count_raw = Prompt.ask("|  Number of bots to add", default="2").strip()
        try:
            count = int(count_raw)
        except ValueError:
            console.print("|  [red]Invalid count[/red]")
            return
        if count < 1 or count > 20:
            console.print("|  [red]Count must be 1-20[/red]")
            return

        prefix = Prompt.ask("|  Instance ID prefix", default=f"{channel_type}_bot").strip() or f"{channel_type}_bot"
        auto_bind = Confirm.ask("|  Auto-create dedicated agent for each bot?", default=True)
        shared_model_override = None
        if auto_bind and Confirm.ask("|  Set one model for all new agents?", default=False):
            shared_model_override = Prompt.ask("|  Agent Model", default="").strip() or None

        for index in range(1, count + 1):
            console.print(f"|  [bold]Bot #{index}[/bold]")
            default_instance_id = f"{prefix}_{index}"
            instance_id = Prompt.ask(f"|  Instance ID #{index}", default=default_instance_id).strip() or default_instance_id

            config_dict = self._prompt_instance_config(channel_type)
            if not config_dict:
                console.print("|  [yellow]Skipped (missing config)[/yellow]")
                continue

            agent_binding = None
            auto_create_agent = False
            model_override = shared_model_override
            if auto_bind:
                agent_binding = instance_id
                auto_create_agent = True
            else:
                agent_binding, auto_create_agent, model_override = self._prompt_agent_binding(instance_id)

            instance = self._add_channel_instance_record(
                instance_id=instance_id,
                channel_type=channel_type,
                config_dict=config_dict,
                agent_binding=agent_binding,
                auto_create_agent=auto_create_agent,
                model_override=model_override,
            )
            console.print(f"|  [green]OK[/green] Added {channel_type} instance '{instance.id}'")

    def _build_template_channel_config(self, channel_type: str, token: str) -> dict[str, Any]:
        """Build channel config from one credential token for fleet templates."""
        clean = (token or "").strip()
        if channel_type == "telegram":
            return {"token": clean, "allow_from": []}
        if channel_type == "discord":
            return {"token": clean, "allow_from": []}
        if channel_type == "whatsapp":
            return {"bridge_url": clean or "ws://localhost:3001", "allow_from": []}
        if channel_type == "slack":
            if "|" in clean:
                bot_token, app_token = [part.strip() for part in clean.split("|", 1)]
            else:
                bot_token, app_token = clean, ""
            return {"bot_token": bot_token, "app_token": app_token}
        raise ValueError(f"Unsupported channel type for fleet template: {channel_type}")

    def _apply_fleet_template(
        self,
        *,
        template_id: str,
        channel_type: str,
        base_id: str,
        bot_tokens: list[str],
    ) -> int:
        """Apply fleet template by creating bound agents + channel instances."""
        template = FLEET_TEMPLATES.get(template_id)
        if not template:
            raise ValueError(f"Unknown fleet template: {template_id}")
        if not bot_tokens:
            raise ValueError("bot_tokens cannot be empty")

        roles = get_template_roles(template_id)
        if not roles:
            raise ValueError(f"Template '{template_id}' has no role definitions")

        created = 0
        clean_base = (base_id or "fleet").strip().replace(" ", "_") or "fleet"
        max_items = min(len(roles), len(bot_tokens))

        for index in range(max_items):
            role_cfg = roles[index]
            role = str(role_cfg.get("role", f"role_{index + 1}")).strip().replace(" ", "_")
            model = role_cfg.get("default_model")

            agent_id = f"{clean_base}_{role}"
            bound_agent = self._ensure_agent_exists(agent_id, model_override=model)
            config_dict = self._build_template_channel_config(channel_type, bot_tokens[index])

            self._add_channel_instance_record(
                instance_id=agent_id,
                channel_type=channel_type,
                config_dict=config_dict,
                agent_binding=bound_agent,
                auto_create_agent=False,
            )
            created += 1

        return created

    def _apply_fleet_template_interactive(self) -> None:
        """Interactive flow to apply predefined fleet templates."""
        template_choices = [
            questionary.Choice(f"{meta.get('label', key)}", value=key)
            for key, meta in FLEET_TEMPLATES.items()
        ]
        template_id = ClackUI.clack_select("Fleet Template", choices=template_choices)
        if not template_id:
            return

        channel_type = ClackUI.clack_select(
            "Channel Type",
            choices=[
                questionary.Choice("Telegram", value="telegram"),
                questionary.Choice("Discord", value="discord"),
                questionary.Choice("WhatsApp", value="whatsapp"),
                questionary.Choice("Slack", value="slack"),
            ],
        )
        if not channel_type:
            return

        roles = get_template_roles(template_id)
        base_id = Prompt.ask("|  Fleet base id", default="team").strip() or "team"

        token_hint = "Bot Token"
        if channel_type == "slack":
            token_hint = "Bot token|App token"
        elif channel_type == "whatsapp":
            token_hint = "Bridge URL"

        bot_tokens: list[str] = []
        for idx, role_cfg in enumerate(roles, 1):
            role = role_cfg.get("role", f"role_{idx}")
            value = Prompt.ask(f"|  {token_hint} for {role}").strip()
            if not value:
                console.print("|  [yellow]Skipped empty credential[/yellow]")
                continue
            bot_tokens.append(value)

        if not bot_tokens:
            console.print("|  [yellow]Cancelled (no credentials provided)[/yellow]")
            return

        created = self._apply_fleet_template(
            template_id=template_id,
            channel_type=channel_type,
            base_id=base_id,
            bot_tokens=bot_tokens,
        )
        console.print(f"|  [green]OK[/green] Applied template '{template_id}' with {created} bot(s)")

    def _edit_channel_instance(self):
        """Edit an existing channel instance."""
        if not self.config.channels.instances:
            console.print("|  [yellow]No instances configured[/yellow]")
            return

        choices = []
        for idx, inst in enumerate(self.config.channels.instances, 1):
            label = f"{idx}. [{inst.type}] {inst.id}"
            choices.append(questionary.Choice(label, value=idx - 1))

        idx = ClackUI.clack_select("Select instance to edit", choices=choices)
        if idx is None:
            return

        instance = self.config.channels.instances[idx]
        instance.enabled = Confirm.ask(f"|  Enable {instance.id}?", default=instance.enabled)

        if Confirm.ask("|  Change agent binding?", default=False):
            binding, auto_create, model_override = self._prompt_agent_binding(instance.id)
            if auto_create and binding:
                instance.agent_binding = self._ensure_agent_exists(binding, model_override=model_override)
            else:
                instance.agent_binding = binding

        console.print(f"|  [green]OK[/green] Updated {instance.id}")

    def _delete_channel_instance(self):
        """Delete a channel instance."""
        if not self.config.channels.instances:
            console.print("|  [yellow]No instances configured[/yellow]")
            return

        choices = []
        for idx, inst in enumerate(self.config.channels.instances, 1):
            label = f"{idx}. [{inst.type}] {inst.id}"
            choices.append(questionary.Choice(label, value=idx - 1))

        idx = ClackUI.clack_select("Select instance to delete", choices=choices)
        if idx is None:
            return

        instance = self.config.channels.instances[idx]
        if Confirm.ask(f"|  Delete {instance.id}?", default=False):
            self.config.channels.instances.pop(idx)
            console.print(f"|  [green]OK[/green] Deleted {instance.id}")

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

    
    def _configure_autostart(self):
        ClackUI.section_start("Auto-start Configuration")
        
        from kabot.core.daemon import get_service_status, install_systemd_service, install_launchd_service, install_windows_task_service, install_termux_service
        
        status = get_service_status()
        installed = status.get("installed", False)
        service_type = status.get("service_type", "unknown")

        if installed:
            console.print(f"|  [green]✓ Auto-start is already INSTALLED ({service_type})[/green]")
            if not Confirm.ask("|  Reinstall/Update service?", default=False):
                ClackUI.section_end()
                return
        else:
            console.print(f"|  [yellow]! Auto-start is NOT installed[/yellow]")
        
        if not Confirm.ask(f"|  Enable Kabot to start automatically on boot ({service_type})?", default=True):
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
            console.print(f"|  [green]✓ {msg}[/green]")
        else:
            console.print(f"|  [red]✗ {msg}[/red]")
        
        self._save_setup_state("autostart", completed=ok, service_type=service_type)
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

