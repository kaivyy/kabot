from typing import List, Optional
from rich.console import Console
from rich.table import Table

from kabot.config.loader import load_config, save_config, get_config_path
from kabot.auth.menu import AUTH_PROVIDERS

console = Console()

class AuthManager:
    def list_providers(self) -> List[str]:
        """Return a list of supported provider IDs."""
        return list(AUTH_PROVIDERS.keys())

    def login(self, provider_id: str) -> bool:
        """
        Execute the login flow for a specific provider.
        """
        if provider_id not in AUTH_PROVIDERS:
            console.print(f"[bold red]Error:[/bold red] Provider '{provider_id}' not found.")
            return False

        handler_cls = AUTH_PROVIDERS[provider_id]["handler"]
        handler = handler_cls()

        # 1. Authenticate (Interactive)
        try:
            auth_data = handler.authenticate()
        except KeyboardInterrupt:
            console.print("\n[yellow]Setup cancelled.[/yellow]")
            return False

        if not auth_data:
            console.print("[yellow]No credentials provided.[/yellow]")
            return False

        # 2. Update Config
        try:
            current_config = load_config()

            # Deep merge the auth_data into current_config
            # Structure expected: {'providers': {'openai': {'api_key': '...'}}}
            if 'providers' in auth_data:
                for prov_name, prov_data in auth_data['providers'].items():
                    # Ensure provider section exists in config (it should if using Pydantic default_factory)
                    # But load_config returns a Pydantic model (Config object).

                    # We need to update the Pydantic model.
                    # Access: current_config.providers.openai

                    provider_config_obj = getattr(current_config.providers, prov_name)

                    if 'api_key' in prov_data:
                        provider_config_obj.api_key = prov_data['api_key']
                    if 'api_base' in prov_data:
                        provider_config_obj.api_base = prov_data['api_base']
                    if 'extra_headers' in prov_data:
                        provider_config_obj.extra_headers = prov_data['extra_headers']

            # 3. Save Config
            save_config(current_config)
            console.print(f"[green]Successfully configured {handler.name}![/green]")
            return True

        except Exception as e:
            console.print(f"[bold red]Error saving config:[/bold red] {e}")
            return False

    def get_status(self):
        """
        Print the current status of configured providers.
        """
        config = load_config()

        table = Table(title="Auth Status")
        table.add_column("Provider", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Key Preview", style="dim")

        # Iterate through known providers in our menu
        for pid, meta in AUTH_PROVIDERS.items():
            # Map pid to config field name (openai -> openai, google -> gemini)
            # We need a mapping if they differ.
            # In handlers we returned {'providers': {'gemini': ...}} for google.

            # Let's verify mapping:
            # openai -> openai
            # anthropic -> anthropic
            # google -> gemini
            # ollama -> vllm

            config_field = pid
            if pid == "google": config_field = "gemini"
            if pid == "ollama": config_field = "vllm"

            provider_cfg = getattr(config.providers, config_field, None)

            status = "[red]Not Configured[/red]"
            preview = ""

            if provider_cfg and provider_cfg.api_key:
                status = "[green]Configured[/green]"
                key = provider_cfg.api_key
                if len(key) > 8:
                    preview = f"{key[:4]}...{key[-4:]}"
                else:
                    preview = "***"

            table.add_row(meta["name"], status, preview)

        console.print(table)
