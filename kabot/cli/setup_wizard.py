"""Interactive setup wizard for kabot."""

from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table

from kabot.config.schema import (
    Config, ProviderConfig, TelegramConfig, DiscordConfig, SlackConfig, EmailConfig
)

console = Console()

class SetupWizard:
    def __init__(self):
        self.config = Config()
    
    def run(self) -> Config:
        console.print("
[bold cyan]🚀 kabot Interactive Setup Wizard[/bold cyan]
")
        self._setup_provider()
        if Confirm.ask("
[bold]Configure chat channels?[/bold]", default=False):
            self._setup_channels()
        if Confirm.ask("
[bold]Configure advanced settings?[/bold]", default=False):
            self._setup_advanced()
        return self.config
    
    def _setup_provider(self):
        from kabot.auth.manager import AuthManager
        from kabot.auth.menu import get_auth_choices
        from kabot.config.loader import load_config

        console.print("\n[bold yellow]Step 1: Select AI Provider[/bold yellow]\n")

        manager = AuthManager()
        choices = get_auth_choices()

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="cyan", width=3)
        table.add_column("Provider", style="green")

        for idx, choice in enumerate(choices, 1):
            table.add_row(str(idx), choice['name'])

        table.add_row(str(len(choices)+1), "Skip (Manual config)")

        console.print(table)

        valid_choices = [str(i) for i in range(1, len(choices) + 2)]
        choice_idx = Prompt.ask("\n[bold]Select provider[/bold]", choices=valid_choices, default="1")

        if choice_idx == str(len(choices) + 1):
            console.print("[yellow]Skipped. Edit ~/.kabot/config.json manually[/yellow]")
            return

        provider_val = choices[int(choice_idx)-1]['value']

        if manager.login(provider_val):
            # Reload config to get the changes made by manager
            self.config = load_config()

            # Set default model suggestions
            models = {
                "openrouter": "openrouter/anthropic/claude-3.5-sonnet",
                "anthropic": "anthropic/claude-3-5-sonnet-20240620",
                "openai": "openai/gpt-4o",
                "google": "gemini/gemini-1.5-pro",
                "ollama": "vllm/llama3",
            }

            default_model = models.get(provider_val, "")
            model = Prompt.ask("Default model", default=default_model)
            if model:
                self.config.agents.defaults.model = model
    
    def _setup_channels(self):
        console.print("
[bold yellow]Configure Channels[/bold yellow]
")
        while True:
            choice = Prompt.ask("[1]Telegram [2]Discord [3]Slack [4]Email [5]Done", choices=["1","2","3","4","5"], default="5")
            if choice == "5": break
            if choice == "1": self._setup_telegram()
            elif choice == "2": self._setup_discord()
            elif choice == "3": self._setup_slack()
            elif choice == "4": self._setup_email()
            if not Confirm.ask("Configure another?", default=False): break
    
    def _setup_telegram(self):
        console.print("[dim]Get token from @BotFather, ID from @userinfobot[/dim]")
        token, user_id = Prompt.ask("Bot token"), Prompt.ask("User ID")
        if token and user_id:
            self.config.channels.telegram = TelegramConfig(enabled=True, token=token.strip(), allow_from=[user_id.strip()])
            console.print("[green]Telegram configured[/green]")
    
    def _setup_discord(self):
        console.print("[dim]Get from discord.com/developers/applications[/dim]")
        token, user_id = Prompt.ask("Bot token"), Prompt.ask("User ID")
        if token and user_id:
            self.config.channels.discord = DiscordConfig(enabled=True, token=token.strip(), allow_from=[user_id.strip()])
            console.print("[green]Discord configured[/green]")
    
    def _setup_slack(self):
        app_token, bot_token = Prompt.ask("App token (xapp-)"), Prompt.ask("Bot token (xoxb-)")
        if app_token and bot_token:
            self.config.channels.slack = SlackConfig(enabled=True, app_token=app_token.strip(), bot_token=bot_token.strip(), mode="socket")
            console.print("[green]Slack configured[/green]")
    
    def _setup_email(self):
        if not Confirm.ask("[yellow]Email requires mailbox access. Consent?[/yellow]", default=False): return
        imap_host = Prompt.ask("IMAP host", default="imap.gmail.com")
        imap_user = Prompt.ask("IMAP user")
        imap_pass = Prompt.ask("IMAP pass", password=True)
        smtp_host = Prompt.ask("SMTP host", default="smtp.gmail.com")
        if imap_host and imap_user:
            self.config.channels.email = EmailConfig(enabled=True, consent_granted=True, imap_host=imap_host, imap_username=imap_user, 
                                                       imap_password=imap_pass, smtp_host=smtp_host, smtp_username=imap_user, 
                                                       smtp_password=imap_pass, from_address=imap_user)
            console.print("[green]Email configured[/green]")
    
    def _setup_advanced(self):
        console.print("
[bold yellow]Advanced Settings[/bold yellow]
")
        self.config.agents.defaults.max_tokens = int(Prompt.ask("Max tokens", default="8192"))
        self.config.agents.defaults.temperature = float(Prompt.ask("Temperature", default="0.7"))
        self.config.tools.restrict_to_workspace = Confirm.ask("Restrict to workspace?", default=False)
        console.print("[green]Advanced configured[/green]")

def run_interactive_setup() -> Config:
    return SetupWizard().run()
