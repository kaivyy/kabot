"""Modular, interactive setup wizard for kabot (v2.1)."""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

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
███            █████  █████      █████████      ██████████      █████████    ███████████ 
░░░███         ░░███  ░░███     ░░███░░░███    ░░███░░░░░███   ░░███░░░░░███ ░░░░███░░░░ 
  ░░░███        ░███ ░███      ░███   ░███    ░███    ░███   ░███    ░███    ░███     
    ░░░███      ░██████        ░███████████   ░██████████    ░███    ░███    ░███     
     ███░       ░███░░███      ░███░░░░░███   ░███░░░░░███   ░███    ░███    ░███     
   ███░         ░███  ░░███    ░███    ░███   ░███    ░███   ░███    ░███    ░███     
 ███░          █████  █████   █████   █████  ███████████    ███████████     █████    
░░░            ░░░░░   ░░░░░   ░░░░░   ░░░░░  ░░░░░░░░░░░    ░░░░░░░░░░░     ░░░░░    
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
        current_model = config.agents.defaults.model
        gateway_host = config.gateway.host
        gateway_port = config.gateway.port
        
        reachable = probe_gateway(gateway_host, gateway_port)
        status_text = "[green]reachable[/green]" if reachable else "[red]not detected[/red]"
        
        content = Text()
        content.append(f" model: {current_model}\n", style="dim")
        content.append(f" gateway: http://{gateway_host}:{gateway_port} ({status_text})", style="dim")
        
        panel = Panel(
            content,
            title=" Existing config detected ",
            title_align="left",
            border_style="dim",
            box=box.ROUNDED,
            padding=(1, 2)
        )
        
        console.print("│")
        console.print(f"◇  {panel}")
        console.print("│")

class SetupWizard:
    def __init__(self):
        self.config = load_config()
        self.registry = ModelRegistry()
        self.ran_section = False

    def run(self) -> Config:
        ClackUI.header()
        ClackUI.summary_box(self.config)
        
        ClackUI.section_start("Environment")
        console.print("│")
        
        reachable = probe_gateway(self.config.gateway.host, self.config.gateway.port)
        local_hint = "(Gateway reachable)" if reachable else "(No gateway detected)"
        
        console.print(f"│  ● Local (this machine) [dim]{local_hint}[/dim]")
        console.print("│  ○ Remote (info-only)")
        console.print("│")
        
        mode_raw = Prompt.ask(
            "◇  Where will the Gateway run?",
            choices=["local", "remote"],
            default="local"
        )
        ClackUI.section_end()
        
        while True:
            choice = self._main_menu()
            if choice == "finish":
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
            elif choice == "doctor":
                self._run_doctor()
            
            self.ran_section = True
            
        return self.config

    def _main_menu(self) -> str:
        ClackUI.section_start("Sections")
        console.print("│")
        
        options = [
            ("workspace", "Workspace (Set path + sessions)"),
            ("model", "Model / Auth (Providers, Keys, OAuth)"),
            ("tools", "Web tools (Search, Browser, Shell)"),
            ("gateway", "Gateway (Port, Host, Bindings)"),
            ("channels", "Channels (Telegram, WhatsApp, Slack)"),
            ("doctor", "Health Check (Run system diagnostic)"),
            ("finish", "Continue & Finish")
        ]
        
        for idx, (val, label) in enumerate(options, 1):
            prefix = "●" if idx == 1 and not self.ran_section else "○"
            console.print(f"│  {prefix} {label}")
            
        console.print("│")
        choice_idx_raw = Prompt.ask(
            "◆  Select section to configure",
            choices=[str(i) for i in range(1, len(options) + 1)],
            default=str(len(options))
        )
        choice_idx = int(str(choice_idx_raw))
        ClackUI.section_end()
        return options[choice_idx-1][0]

    def _configure_workspace(self):
        ClackUI.section_start("Workspace")
        path = Prompt.ask("│  Workspace directory", default=self.config.agents.defaults.workspace)
        self.config.agents.defaults.workspace = path
        # Ensure directory exists
        os.makedirs(os.path.expanduser(path), exist_ok=True)
        console.print(f"│  [green]✓ Workspace path set.[/green]")
        ClackUI.section_end()

    def _configure_model(self):
        ClackUI.section_start("Model & Auth")
        from kabot.auth.menu import get_auth_choices
        from kabot.auth.manager import AuthManager
        
        manager = AuthManager()
        choices = get_auth_choices()
        
        while True:
            console.print("│")
            console.print("│  Select an option:")
            console.print("│  ● [1] Provider Login (Setup API Keys/OAuth)")
            console.print("│  ○ [2] Select Default Model (Browse Registry)")
            console.print("│  ○ [3] Back")
            
            choice_raw = Prompt.ask("│\n◆  Choice", choices=["1", "2", "3"], default="1")
            choice = str(choice_raw)
            
            if choice == "3":
                break
            
            if choice == "1":
                console.print("│")
                for idx, c in enumerate(choices, 1):
                    console.print(f"│  ○ {idx}. {c['name']}")
                
                valid = [str(i) for i in range(1, len(choices) + 1)]
                idx_raw = Prompt.ask("│\n◆  Select provider to login", choices=valid)
                idx = int(str(idx_raw))
                provider_val = choices[idx-1]['value']
                if manager.login(provider_val):
                    self._model_picker(provider_val)
            
            elif choice == "2":
                self._model_picker()
        
        ClackUI.section_end()

    def _model_picker(self, provider_id: Optional[str] = None):
        if not provider_id:
            providers = self.registry.get_providers()
            sorted_providers = sorted(providers.items())
            console.print("│")
            console.print("│  Filter models by provider:")
            console.print(f"│  ○ 0. All providers ({len(self.registry.list_models())} models)")
            for idx, (p_name, count) in enumerate(sorted_providers, 1):
                console.print(f"│  ○ {idx}. {p_name} ({count} models)")
            p_choices = [str(i) for i in range(len(sorted_providers) + 1)]
            p_idx_raw = Prompt.ask("│\n◆  Select provider", choices=p_choices, default="0")
            p_idx = int(str(p_idx_raw))
            if p_idx > 0:
                provider_id = sorted_providers[p_idx-1][0]

        all_models = self.registry.list_models()
        if provider_id:
            models = [m for m in all_models if m.provider == provider_id]
        else:
            models = all_models
        models.sort(key=lambda x: (not x.is_premium, x.id))

        console.print("│")
        console.print(f"│  Default model (Current: {self.config.agents.defaults.model})")
        console.print("│  ● 0. Keep current")
        console.print("│  ○ 1. Enter model manually")
        for idx, m in enumerate(models, 2):
            name = m.name
            if m.is_premium: name = f"{name} [yellow]★[/yellow]"
            console.print(f"│  ○ {idx}. {m.id} ({name})")
        
        m_choices = [str(i) for i in range(len(models) + 2)]
        m_idx_raw = Prompt.ask("│\n◆  Select model", choices=m_choices, default="0")
        m_idx = int(str(m_idx_raw))
        if m_idx == 0: return
        elif m_idx == 1:
            manual = Prompt.ask("│  Enter Model ID")
            if manual: self.config.agents.defaults.model = manual
        else:
            selected = models[m_idx-2]
            self.config.agents.defaults.model = selected.id
            console.print(f"│  [green]✓ Set to {selected.id}[/green]")

    def _configure_tools(self):
        ClackUI.section_start("Web Tools")
        self.config.tools.web.search.api_key = Prompt.ask("│  Brave Search API Key", default=self.config.tools.web.search.api_key)
        self.config.tools.restrict_to_workspace = Confirm.ask("│  Restrict to workspace?", default=self.config.tools.restrict_to_workspace)
        ClackUI.section_end()

    def _configure_gateway(self):
        ClackUI.section_start("Gateway")
        self.config.gateway.host = Prompt.ask("│  Bind Host", default=self.config.gateway.host)
        self.config.gateway.port = int(Prompt.ask("│  Port", default=str(self.config.gateway.port)))
        ClackUI.section_end()

    def _configure_channels(self):
        ClackUI.section_start("Channels")
        console.print("│  [dim]Configure external chat platforms[/dim]")
        if Confirm.ask("│  Configure Telegram?", default=False):
            token = Prompt.ask("│  Bot Token")
            if token:
                self.config.channels.telegram.token = token
                self.config.channels.telegram.enabled = True
        ClackUI.section_end()

    def _run_doctor(self):
        from kabot.utils.doctor import KabotDoctor
        doc = KabotDoctor()
        doc.render_report()
        Prompt.ask("│\n◆  Press Enter to return to menu")

def run_interactive_setup() -> Config:
    return SetupWizard().run()
