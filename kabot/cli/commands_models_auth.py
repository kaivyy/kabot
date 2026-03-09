"""Extracted CLI command helpers from kabot.cli.commands."""


import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def _resolve_commands_override(name: str, fallback):
    try:
        from kabot.cli import commands as commands_module
    except Exception:
        return fallback
    return getattr(commands_module, name, fallback)

def models_list(
    provider: str = typer.Option(None, "--provider", "-p", help="Filter by provider"),
    premium: bool = typer.Option(False, "--premium", help="Show only premium models"),
):
    """List all available models with pricing and capabilities."""
    from kabot.config.loader import get_data_dir
    from kabot.memory.sqlite_store import SQLiteMetadataStore
    from kabot.providers.registry import ModelRegistry

    db_path = get_data_dir() / "metadata.db"
    db = SQLiteMetadataStore(db_path)
    registry = ModelRegistry(db=db)

    models = registry.list_models()

    if provider:
        models = [m for m in models if m.provider == provider]
    if premium:
        models = [m for m in models if m.is_premium]

    if not models:
        console.print("No models found. Try running [cyan]kabot models scan[/cyan].")
        return

    table = Table(title="Available AI Models")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Provider", style="magenta")
    table.add_column("Pricing (In/Out)", style="yellow")
    table.add_column("Context", style="blue")
    table.add_column("Capabilities", style="dim")

    # Sort models: premium first, then by ID
    models.sort(key=lambda x: (not x.is_premium, x.id))

    for m in models:
        pricing = f"${m.pricing.input_1m}/${m.pricing.output_1m}"
        caps = ", ".join(m.capabilities) if m.capabilities else "-"
        ctx = f"{m.context_window:,}" if m.context_window else "Unknown"

        # Highlighting logic
        name = m.name
        row_id = m.id

        # Resolve current config for highlighting
        from kabot.config.loader import load_config
        cfg = load_config()
        current_primary = cfg.agents.defaults.model
        p_cfg = cfg.get_provider()
        current_fallbacks = p_cfg.fallbacks if p_cfg else []

        if m.id == current_primary:
            name = f"[bold green]{name}[/bold green] [bold cyan](Primary)[/bold cyan]"
            row_id = f"[bold green]{row_id}[/bold green]"
        elif m.id in current_fallbacks:
            name = f"[green]{name}[/green] [dim](Fallback)[/dim]"
            row_id = f"[green]{row_id}[/green]"

        if m.is_premium:
            name = f"{name} [yellow]★[/yellow]"

        table.add_row(row_id, name, m.provider, pricing, ctx, caps)

    console.print(table)
    console.print("\n[dim]Legend: [yellow]★[/yellow] Premium model, [bold green]Primary[/bold green] Active model, [green]Fallback[/green] Backup model[/dim]")

def models_scan():
    """Scan provider APIs to discover available models."""
    from kabot.config.loader import get_data_dir, load_config
    from kabot.memory.sqlite_store import SQLiteMetadataStore
    from kabot.providers.registry import ModelRegistry
    from kabot.providers.scanner import ModelScanner

    config = load_config()
    db_path = get_data_dir() / "metadata.db"
    db = SQLiteMetadataStore(db_path)
    registry = ModelRegistry(db=db)
    scanner = ModelScanner(registry, db=db)

    with console.status("[bold cyan]Scanning providers for models..."):
        count = scanner.scan_all(config.providers)

    console.print(f"\n[green]✓[/green] Scan complete! Found and registered [bold]{count}[/bold] models.")
    console.print("[dim]Use `kabot models list` to see them.[/dim]")

def models_info(
    model_id: str = typer.Argument(..., help="Model ID or short name"),
):
    """Show detailed metadata for a specific model."""
    from kabot.config.loader import get_data_dir
    from kabot.memory.sqlite_store import SQLiteMetadataStore
    from kabot.providers.registry import ModelRegistry

    db_path = get_data_dir() / "metadata.db"
    db = SQLiteMetadataStore(db_path)
    registry = ModelRegistry(db=db)

    m = registry.get_model(model_id)
    if not m:
        console.print(f"[red]Error: Model '{model_id}' not found.[/red]")
        raise typer.Exit(1)

    console.print(Panel(
        f"[bold]ID:[/bold] {m.id}\n"
        f"[bold]Name:[/bold] {m.name}\n"
        f"[bold]Provider:[/bold] {m.provider}\n"
        f"[bold]Context Window:[/bold] {m.context_window:,} tokens\n"
        f"[bold]Pricing (1M tokens):[/bold] Input: ${m.pricing.input_1m}, Output: ${m.pricing.output_1m}\n"
        f"[bold]Capabilities:[/bold] {', '.join(m.capabilities) if m.capabilities else 'None'}\n"
        f"[bold]Status:[/bold] {'Premium [yellow]★[/yellow]' if m.is_premium else 'Standard'}",
        title=f"Model Info: {m.short_id}",
        border_style="cyan"
    ))

def models_set(
    model_name: str = typer.Argument(..., help="Model ID or Alias"),
):
    """Set the primary model for the agent."""
    from kabot.config.loader import get_data_dir, load_config, save_config
    from kabot.memory.sqlite_store import SQLiteMetadataStore
    from kabot.providers.registry import ModelRegistry

    db_path = get_data_dir() / "metadata.db"
    db = SQLiteMetadataStore(db_path)
    registry = ModelRegistry(db=db)

    # Resolve alias/short-id
    resolved_id = registry.resolve(model_name)

    # Check if the resolved ID is known
    if not registry.get_model(resolved_id):
        console.print(f"[yellow]Warning: '{resolved_id}' is not in the model registry.[/yellow]")
        if not typer.confirm("Set it anyway?"):
            raise typer.Exit()

    config = load_config()
    config.agents.defaults.model = resolved_id
    save_config(config)

    console.print(f"\n[green]✓ Primary model set to: [bold]{resolved_id}[/bold][/green]")
    if resolved_id != model_name:
        console.print(f"[dim](Resolved from '{model_name}')[/dim]")

def channels_status():
    """Show channel status."""
    from kabot.config.loader import load_config

    config = load_config()

    table = Table(title="Channel Status")
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    table.add_column("Configuration", style="yellow")

    # WhatsApp
    wa = config.channels.whatsapp
    table.add_row(
        "WhatsApp",
        "✓" if wa.enabled else "✗",
        wa.bridge_url
    )

    dc = config.channels.discord
    table.add_row(
        "Discord",
        "✓" if dc.enabled else "✗",
        dc.gateway_url
    )

    # Telegram
    tg = config.channels.telegram
    tg_config = f"token: {tg.token[:10]}..." if tg.token else "[dim]not configured[/dim]"
    table.add_row(
        "Telegram",
        "✓" if tg.enabled else "✗",
        tg_config
    )

    # Slack
    slack = config.channels.slack
    slack_config = "socket" if slack.app_token and slack.bot_token else "[dim]not configured[/dim]"
    table.add_row(
        "Slack",
        "✓" if slack.enabled else "✗",
        slack_config
    )

    console.print(table)

def channels_login():
    """Link device via QR code."""
    from kabot.cli.bridge_utils import run_bridge_login
    from kabot.config.loader import load_config

    config = load_config()
    bridge_url = config.channels.whatsapp.bridge_url
    run_bridge_login(stop_when_connected=False, bridge_url=bridge_url)

def auth_list():
    """List supported authentication providers."""
    from rich.table import Table

    from kabot.auth.menu import AUTH_PROVIDERS

    table = Table(title="Supported Providers")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Methods", style="yellow")

    for pid, meta in AUTH_PROVIDERS.items():
        methods = ", ".join(meta["methods"].keys())
        table.add_row(pid, meta["name"], methods)

    console.print(table)

def auth_login(
    provider: str = typer.Argument(None, help="Provider ID (e.g., openai, anthropic)"),
    method: str = typer.Option(None, "--method", "-m", help="Auth method (e.g., oauth, api_key)"),
    profile: str = typer.Option("default", "--profile", "-p", help="Profile name (e.g., work, personal)"),
):
    """Login to a provider with optional method and profile selection."""
    from rich.prompt import Prompt

    from kabot.auth.manager import AuthManager
    from kabot.auth.menu import get_auth_choices

    manager = AuthManager()
    # If no provider, show provider selection
    if not provider:
        choices = get_auth_choices()
        console.print("\n[bold]Select a provider to configure:[/bold]\n")

        for idx, choice in enumerate(choices, 1):
            console.print(f"  [{idx}] {choice['name']}")

        console.print()
        try:
            choice_idx = Prompt.ask(
                "Select option",
                choices=[str(i) for i in range(1, len(choices)+1)]
            )
            provider = choices[int(choice_idx)-1]['value']
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    # Execute login with optional method and profile
    success = manager.login(provider, method_id=method, profile_id=profile)

    if success:
        console.print(f"\n[green]✓ Successfully configured {provider}![/green]")

        # --- Task 5: Semi-Auto Model Configuration ---
        from kabot.config.loader import get_data_dir, load_config, save_config
        from kabot.memory.sqlite_store import SQLiteMetadataStore
        from kabot.providers.registry import ModelRegistry

        db_path = get_data_dir() / "metadata.db"
        db = SQLiteMetadataStore(db_path)
        registry = ModelRegistry(db=db)

        # Find premium models for this provider
        available_models = [m for m in registry.list_models() if m.provider == provider and m.is_premium]

        if available_models:
            console.print(f"\n[bold]Suggested premium models for {provider}:[/bold]\n")
            for idx, m in enumerate(available_models, 1):
                console.print(f"  [{idx}] {m.name} ({m.short_id}) - Context: {m.context_window:,}")

            console.print("  [0] Skip (Keep current default)")

            try:
                choice = Prompt.ask(
                    "\nSelect a model to set as default",
                    choices=[str(i) for i in range(len(available_models) + 1)],
                    default="0"
                )

                if choice != "0":
                    selected = available_models[int(choice)-1]
                    config = load_config()
                    config.agents.defaults.model = selected.id
                    save_config(config)
                    console.print(f"\n[green]✓ Default model set to: [bold]{selected.id}[/bold][/green]")
            except (KeyboardInterrupt, EOFError):
                pass
    else:
        console.print("\n[red]✗ Authentication failed[/red]")
        raise typer.Exit(1)

def auth_methods(
    provider: str = typer.Argument(..., help="Provider ID"),
):
    """List available authentication methods for a provider."""
    from rich.table import Table

    from kabot.auth.manager import _PROVIDER_ALIASES
    from kabot.auth.menu import AUTH_PROVIDERS

    original_provider = provider
    provider = _PROVIDER_ALIASES.get(provider, provider)

    if provider not in AUTH_PROVIDERS:
        console.print(f"[red]Provider '{original_provider}' not found[/red]")
        console.print("\nAvailable providers:")
        for pid in AUTH_PROVIDERS.keys():
            console.print(f"  - {pid}")
        raise typer.Exit(1)

    provider_info = AUTH_PROVIDERS[provider]
    methods = provider_info["methods"]

    table = Table(title=f"{provider_info['name']} - Authentication Methods")
    table.add_column("Method ID", style="cyan")
    table.add_column("Label", style="green")
    table.add_column("Description", style="dim")

    for method_id, method_info in methods.items():
        table.add_row(
            method_id,
            method_info["label"],
            method_info["description"]
        )

    console.print("\n")
    console.print(table)
    console.print("\n")
    console.print(f"[dim]Usage: kabot auth login {original_provider} --method <method_id>[/dim]")

def auth_status():
    """Show authentication status."""
    from kabot.auth.manager import AuthManager
    manager = AuthManager()
    manager.get_status()

def auth_parity():
    """Run OAuth/auth handler parity diagnostics across providers."""
    from kabot.auth.manager import AuthManager

    manager = AuthManager()
    report = manager.parity_report()

    summary = Table(title="Auth Parity Summary")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="green")
    summary.add_row("Providers", str(report.get("provider_count", 0)))
    summary.add_row("Methods", str(report.get("method_count", 0)))
    summary.add_row("OAuth Methods", str(report.get("oauth_method_count", 0)))
    summary.add_row("Status", "OK" if report.get("ok") else "Issues Found")
    console.print(summary)

    issues = report.get("issues", [])
    if issues:
        issue_table = Table(title="Auth Parity Issues")
        issue_table.add_column("Issue", style="yellow")
        for issue in issues:
            issue_table.add_row(str(issue))
        console.print(issue_table)
    else:
        console.print("[green]No parity issues detected.[/green]")
