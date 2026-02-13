"""Authentication manager with multi-method support."""

from typing import List, Optional, Dict, Any
import importlib
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from kabot.config.loader import load_config, save_config
from kabot.auth.menu import AUTH_PROVIDERS

console = Console()


class AuthManager:
    """Manages authentication for multiple providers with multiple methods."""

    def list_providers(self) -> List[str]:
        """Return a list of supported provider IDs."""
        return list(AUTH_PROVIDERS.keys())

    def login(self, provider_id: str, method_id: str = None, profile_id: str = "default") -> bool:
        """
        Execute login flow with method and profile selection.

        Args:
            provider_id: Provider (e.g., "openai")
            method_id: Optional method (e.g., "oauth"). If None, show menu.
            profile_id: Optional profile ID (e.g., "work"). Defaults to "default".

        Returns:
            True if authentication successful, False otherwise
        """
        # 1. Validate provider
        if provider_id not in AUTH_PROVIDERS:
            console.print(f"[bold red]Error:[/bold red] Provider '{provider_id}' not found.")
            return False

        provider = AUTH_PROVIDERS[provider_id]

        # 2. Method selection (if multiple methods available)
        if method_id is None:
            methods = provider["methods"]

            # If only 1 method, use it directly (no menu)
            if len(methods) == 1:
                method_id = list(methods.keys())[0]
                console.print(f"[dim]Using {methods[method_id]['label']}[/dim]")
            else:
                # Show method selection menu
                method_id = self._prompt_method_selection(provider_id, methods)
                if not method_id:
                    return False

        # 3. Validate method
        if method_id not in provider["methods"]:
            console.print(f"[bold red]Error:[/bold red] Method '{method_id}' not found for {provider_id}.")
            return False

        # 4. Load handler dynamically
        try:
            handler = self._load_handler(provider_id, method_id)
        except Exception as e:
            console.print(f"[bold red]Error loading handler:[/bold red] {e}")
            return False

        # 5. Execute authentication
        try:
            auth_data = handler.authenticate()
        except KeyboardInterrupt:
            console.print("\n[yellow]Authentication cancelled.[/yellow]")
            return False
        except TimeoutError:
            console.print("\n[red]Authentication timed out.[/red]")
            return False
        except Exception as e:
            console.print(f"\n[bold red]Authentication failed:[/bold red] {e}")
            return False

        if not auth_data:
            console.print("[yellow]No credentials provided.[/yellow]")
            return False

        # 6. Validate auth data
        if not self._validate_auth_data(auth_data):
            console.print("[bold red]Error:[/bold red] Invalid authentication data format.")
            return False

        # 7. Save credentials
        return self._save_credentials(auth_data, profile_id=profile_id)

    def _load_handler(self, provider_id: str, method_id: str):
        """Dynamically load handler class from string path."""
        provider = AUTH_PROVIDERS[provider_id]
        method = provider["methods"][method_id]
        handler_path = method["handler"]

        # Parse "kabot.auth.handlers.openai_key.OpenAIKeyHandler"
        module_path, class_name = handler_path.rsplit(".", 1)

        module = importlib.import_module(module_path)
        handler_class = getattr(module, class_name)
        return handler_class()

    def _prompt_method_selection(self, provider_id: str, methods: Dict) -> Optional[str]:
        """Show interactive method selection menu."""
        provider_name = AUTH_PROVIDERS[provider_id]["name"]

        # Build method selection table
        table = Table(title=f"{provider_name} Authentication")
        table.add_column("#", style="cyan", width=3)
        table.add_column("Method", style="green")
        table.add_column("Description", style="dim")

        method_list = list(methods.items())
        for idx, (method_id, method_info) in enumerate(method_list, 1):
            table.add_row(
                str(idx),
                method_info["label"],
                method_info["description"]
            )

        console.print("\n")
        console.print(table)
        console.print("\n")

        # Prompt for selection
        choices = [str(i) for i in range(1, len(method_list) + 1)]
        try:
            selection = Prompt.ask("Select authentication method", choices=choices)
            selected_method_id = method_list[int(selection) - 1][0]
            return selected_method_id
        except (KeyboardInterrupt, EOFError):
            return None

    def _validate_auth_data(self, auth_data: Dict[str, Any]) -> bool:
        """Validate auth data structure."""
        if not isinstance(auth_data, dict):
            return False

        if "providers" not in auth_data:
            return False

        # Check at least one provider has credentials
        for provider_data in auth_data["providers"].values():
            if any(key in provider_data for key in ["api_key", "oauth_token", "api_base"]):
                return True

        return False

        def _save_credentials(self, auth_data: Dict[str, Any], profile_id: str = "default") -> bool:
            """Save credentials to config using AuthProfiles."""
            from kabot.config.schema import AuthProfile
            try:
                current_config = load_config()
    
                if "providers" in auth_data:
                    for prov_name, prov_data in auth_data["providers"].items():
                        # Get or create provider config
                        provider_config_obj = getattr(current_config.providers, prov_name, None)   
    
                        if provider_config_obj is None:
                            console.print(f"[yellow]Warning: Provider '{prov_name}' not in config schema[/yellow]")
                            continue
    
                        # Multi-profile logic: update legacy fields AND profile list
                        # This ensures backward compatibility while adding multi-account power
                        
                        # 1. Update or create the profile
                        if profile_id not in provider_config_obj.profiles:
                            provider_config_obj.profiles[profile_id] = AuthProfile(name=profile_id)
                        
                        profile = provider_config_obj.profiles[profile_id]
                        
                        # 2. Update legacy top-level fields for safety
                        for key, value in prov_data.items():
                            if hasattr(provider_config_obj, key):
                                setattr(provider_config_obj, key, value)
                            
                            # 3. Update profile-specific fields
                            if hasattr(profile, key):
                                setattr(profile, key, value)
                        
                        # 4. Mark this profile as active
                        provider_config_obj.active_profile = profile_id
    
                save_config(current_config)
                return True
    
            except Exception as e:
                console.print(f"[bold red]Error saving config:[/bold red] {e}")
                return False

    def get_status(self):
        """Print the current status of configured providers and profiles."""
        config = load_config()

        table = Table(title="Auth Status")
        table.add_column("Provider", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Active Profile", style="yellow")
        table.add_column("Profiles", style="dim")

        # Provider ID to config field mapping
        config_mapping = {
            "openai": "openai",
            "anthropic": "anthropic",
            "google": "gemini",
            "ollama": "vllm",
            "kimi": "moonshot",
            "minimax": "minimax"
        }

        for pid, meta in AUTH_PROVIDERS.items():
            config_field = config_mapping.get(pid, pid)
            provider_cfg = getattr(config.providers, config_field, None)

            status = "[red]Not Configured[/red]"
            active_profile = "-"
            profile_list = "-"

            if provider_cfg:
                # Check for any valid credential (legacy or profiles)
                has_legacy = bool(provider_cfg.api_key)
                has_profiles = len(provider_cfg.profiles) > 0
                
                if has_legacy or has_profiles:
                    status = "[green]Configured[/green]"
                    active_profile = provider_cfg.active_profile
                    
                    if provider_cfg.profiles:
                        p_names = []
                        for name in provider_cfg.profiles.keys():
                            if name == provider_cfg.active_profile:
                                p_names.append(f"[bold yellow]{name}[/bold yellow]")
                            else:
                                p_names.append(name)
                        profile_list = ", ".join(p_names)
                    elif has_legacy:
                        profile_list = "legacy"

            table.add_row(meta["name"], status, active_profile, profile_list)

        console.print(table)
