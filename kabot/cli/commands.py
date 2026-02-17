"""CLI commands for kabot."""

import asyncio
import atexit
import os
import signal
from pathlib import Path
import select
import sys

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from kabot import __version__, __logo__

app = typer.Typer(
    name="kabot",
    help=f"{__logo__} kabot - Personal AI Assistant",
    no_args_is_help=True,
)

console = Console()
EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit", ":q"}

# ---------------------------------------------------------------------------
# Lightweight CLI input: readline for arrow keys / history, termios for flush
# ---------------------------------------------------------------------------

_READLINE = None
_HISTORY_FILE: Path | None = None
_HISTORY_HOOK_REGISTERED = False
_USING_LIBEDIT = False
_SAVED_TERM_ATTRS = None  # original termios settings, restored on exit


def _flush_pending_tty_input() -> None:
    """Drop unread keypresses typed while the model was generating output."""
    try:
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return
    except Exception:
        return

    try:
        import termios
        termios.tcflush(fd, termios.TCIFLUSH)
        return
    except Exception:
        pass

    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break
            if not os.read(fd, 4096):
                break
    except Exception:
        return


def _save_history() -> None:
    if _READLINE is None or _HISTORY_FILE is None:
        return
    try:
        _READLINE.write_history_file(str(_HISTORY_FILE))
    except Exception:
        return


def _restore_terminal() -> None:
    """Restore terminal to its original state (echo, line buffering, etc.)."""
    if _SAVED_TERM_ATTRS is None:
        return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _SAVED_TERM_ATTRS)
    except Exception:
        pass


def _enable_line_editing() -> None:
    """Enable readline for arrow keys, line editing, and persistent history."""
    global _READLINE, _HISTORY_FILE, _HISTORY_HOOK_REGISTERED, _USING_LIBEDIT, _SAVED_TERM_ATTRS

    # Save terminal state before readline touches it
    try:
        import termios
        _SAVED_TERM_ATTRS = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

    history_file = Path.home() / ".kabot" / "history" / "cli_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    _HISTORY_FILE = history_file

    try:
        import readline
    except ImportError:
        return

    _READLINE = readline
    _USING_LIBEDIT = "libedit" in (readline.__doc__ or "").lower()

    try:
        if _USING_LIBEDIT:
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")
        readline.parse_and_bind("set editing-mode emacs")
    except Exception:
        pass

    try:
        readline.read_history_file(str(history_file))
    except Exception:
        pass

    if not _HISTORY_HOOK_REGISTERED:
        atexit.register(_save_history)
        _HISTORY_HOOK_REGISTERED = True


def _prompt_text() -> str:
    """Build a readline-friendly colored prompt."""
    if _READLINE is None:
        return "You: "
    # libedit on macOS does not honor GNU readline non-printing markers.
    if _USING_LIBEDIT:
        return "\033[1;34mYou:\033[0m "
    return "\001\033[1;34m\002You:\001\033[0m\002 "


def _print_agent_response(response: str, render_markdown: bool) -> None:
    """Render assistant response with consistent terminal styling."""
    content = response or ""
    body = Markdown(content) if render_markdown else Text(content)
    console.print()
    console.print(
        Panel(
            body,
            title=f"{__logo__} kabot",
            title_align="left",
            border_style="cyan",
            padding=(0, 1),
        )
    )
    console.print()


def _is_exit_command(command: str) -> bool:
    """Return True when input should end interactive chat."""
    return command.lower() in EXIT_COMMANDS


async def _read_interactive_input_async() -> str:
    """Read user input with arrow keys and history (runs input() in a thread)."""
    try:
        return await asyncio.to_thread(input, _prompt_text())
    except EOFError as exc:
        raise KeyboardInterrupt from exc


def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} kabot v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """kabot - Personal AI Assistant."""
    pass


# ============================================================================
# Onboard / Setup
# ============================================================================


@app.command()
def onboard():
    """Initialize kabot configuration and workspace."""
    from kabot.config.loader import get_config_path, save_config
    from kabot.config.schema import Config
    from kabot.utils.helpers import get_workspace_path

    config_path = get_config_path()

    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit()

    # Create default config
    config = Config()
    save_config(config)
    console.print(f"[green]✓[/green] Created config at {config_path}")

    # Create workspace
    workspace = get_workspace_path()
    console.print(f"[green]✓[/green] Created workspace at {workspace}")

    # Create default bootstrap files
    _create_workspace_templates(workspace)

    console.print(f"\n{__logo__} kabot is ready!")
    console.print("\nNext steps:")
    console.print("  1. Add your API key to [cyan]~/.kabot/config.json[/cyan]")
    console.print("     Get one at: https://openrouter.ai/keys")
    console.print("  2. Chat: [cyan]kabot agent -m \"Hello!\"[/cyan]")
    console.print("\n[dim]Want Telegram/WhatsApp? See: https://github.com/kaivyy/kabot#-chat-apps[/dim]")


@app.command()
def setup(
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Run interactive setup wizard"),
):
    """Interactive setup wizard for configuring kabot."""
    from kabot.config.loader import get_config_path, save_config
    from kabot.utils.helpers import get_workspace_path

    config_path = get_config_path()

    if interactive:
        from kabot.cli.setup_wizard import run_interactive_setup

        console.print(f"\n{__logo__} [bold cyan]Welcome to Kabot Setup![/bold cyan]\n")        

        if config_path.exists():
            console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
            if not typer.confirm("Run setup wizard to reconfigure?"):
                raise typer.Exit()

        # Run interactive wizard
        config = run_interactive_setup()

        # Save configuration
        save_config(config)
        console.print(f"\n[green]✓ Configuration saved to {config_path}[/green]")

        # Create workspace and templates
        workspace = get_workspace_path()
        _create_workspace_templates(workspace)
        console.print(f"[green]✓ Workspace ready at {workspace}[/green]")

        # Show next steps
        console.print(f"\n{__logo__} Kabot is configured!\n")
        console.print("[bold]Next steps:[/bold]")
        console.print("  1. Start gateway: [cyan]kabot gateway[/cyan]")
        console.print("  2. Test agent: [cyan]kabot agent -m 'Hello!'[/cyan]")
        console.print("  3. Auto-start: [cyan]See deployment/README.md[/cyan]\n")
    else:
        # Fallback to old onboard behavior
        onboard()


@app.command()
def config(
    edit: bool = typer.Option(False, "--edit", "-e", help="Open configuration file in default editor"),
):
    """Configure kabot settings."""
    from kabot.config.loader import get_config_path
    
    if edit:
        config_path = get_config_path()
        if not config_path.exists():
            console.print(f"[yellow]Config not found at {config_path}. Running setup first...[/yellow]")
            setup(interactive=True)
            return
            
        console.print(f"Opening {config_path}...")
        typer.launch(str(config_path))
    else:
        setup(interactive=True)


def _create_workspace_templates(workspace: Path):
    """Create default workspace template files."""
    templates = {
        "AGENTS.md": """# Agent Instructions

You are a helpful AI assistant. Be concise, accurate, and friendly.

## Guidelines

- Always explain what you're doing before taking actions
- Ask for clarification when the request is ambiguous
- Use tools to help accomplish tasks
- Remember important information in your memory files
""",
        "SOUL.md": """# Soul

I am kabot, a lightweight AI assistant.

## Personality

- Helpful and friendly
- Concise and to the point
- Curious and eager to learn

## Values

- Accuracy over speed
- User privacy and safety
- Transparency in actions
""",
        "USER.md": """# User

Information about the user goes here.

## Preferences

- Communication style: (casual/formal)
- Timezone: (your timezone)
- Language: (your preferred language)
""",
    }

    for filename, content in templates.items():
        file_path = workspace / filename
        if not file_path.exists():
            file_path.write_text(content)
            console.print(f"  [dim]Created {filename}[/dim]")

    # Create memory directory and MEMORY.md
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("""# Long-term Memory

This file stores important information that should persist across sessions.

## User Information

(Important facts about the user)

## Preferences

(User preferences learned over time)

## Important Notes

(Things to remember)
""")
        console.print("  [dim]Created memory/MEMORY.md[/dim]")


def _make_provider(config):
    """Create LLMProvider from config. Exits if no API key found."""
    from kabot.providers.litellm_provider import LiteLLMProvider

    p = config.get_provider()
    provider_name = config.get_provider_name()
    model = config.agents.defaults.model

    # Special handling for Letta provider
    if provider_name == "letta":
        from kabot.providers.letta_provider import LettaProvider
        return LettaProvider(
            api_key=p.api_key if p else None,
            api_base=config.get_api_base(),
            workspace_path=config.agents.defaults.workspace,
            default_model=model,
        )

    if not (p and p.api_key) and not model.startswith("bedrock/"):
        console.print("[red]Error: No API key configured.[/red]")
        console.print("Set one in ~/.kabot/config.json under providers section")
        raise typer.Exit(1)

    return LiteLLMProvider(
        api_key=p.api_key if p else None,
        api_base=config.get_api_base(),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=provider_name,
        fallbacks=p.fallbacks if p else None,
    )


def _inject_skill_env(config):
    """Inject skill environment variables from config into os.environ."""
    if not hasattr(config, "skills"):
        return
    
    count = 0
    for skill_name, skill_cfg in config.skills.items():
        env_vars = skill_cfg.get("env", {})
        for key, value in env_vars.items():
            if key and value and key not in os.environ:
                os.environ[key] = value
                count += 1
    if count > 0:
        console.print(f"[dim]Injected {count} skill environment variables[/dim]")


# ============================================================================
# Gateway / Server
# ============================================================================


@app.command()
def gateway(
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Start the kabot gateway."""
    from kabot.config.loader import load_config, get_data_dir
    from kabot.bus.queue import MessageBus
    from kabot.agent.loop import AgentLoop
    from kabot.channels.manager import ChannelManager
    from kabot.session.manager import SessionManager
    from kabot.cron.service import CronService
    from kabot.cron.types import CronJob
    from kabot.heartbeat.service import HeartbeatService
    from kabot.gateway.webhook_server import WebhookServer

    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    console.print(f"{__logo__} Starting kabot gateway on port {port}...")

    config = load_config()
    _inject_skill_env(config)
    
    # Configure logger
    from kabot.core.logger import configure_logger
    from kabot.memory.sqlite_store import SQLiteMetadataStore
    
    db_path = get_data_dir() / "metadata.db"
    store = SQLiteMetadataStore(db_path)
    configure_logger(config, store)

    bus = MessageBus()
    provider = _make_provider(config)
    session_manager = SessionManager(config.workspace_path)

    # Create cron service first (callback set after agent creation)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    p = config.get_provider()

    # Create agent with cron service
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        fallbacks=p.fallbacks if p else None,
        max_iterations=config.agents.defaults.max_tool_iterations,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        session_manager=session_manager,
        enable_hybrid_memory=config.agents.enable_hybrid_memory,
    )

    # Set cron callback (needs agent)
    async def on_cron_job(job: CronJob) -> str | None:
        """Execute a cron job through the agent."""
        response = await agent.process_direct(
            job.payload.message,
            session_key=f"background:cron:{job.id}",
            channel=job.payload.channel or "cli",
            chat_id=job.payload.to or "direct",
        )
        if job.payload.deliver and job.payload.to:
            from kabot.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to,
                content=response or ""
            ))
        return response
    cron.on_job = on_cron_job

    # Create heartbeat service
    async def on_heartbeat(prompt: str) -> str:
        """Execute heartbeat through the agent."""
        return await agent.process_direct(prompt, session_key="heartbeat")

    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        on_heartbeat=on_heartbeat,
        interval_s=30 * 60,  # 30 minutes
        enabled=True
    )

    # Create webhook server
    webhook_server = WebhookServer(bus)

    # Create channel manager
    channels = ChannelManager(config, bus, session_manager=session_manager)

    # Check for restart recovery
    from kabot.utils.restart import RestartManager
    restart_mgr = RestartManager(config.workspace_path / "RESTART_PENDING.json")
    recovery_data = restart_mgr.check_and_recover()

    if channels.enabled_channels:
        console.print(f"[green]*[/green] Channels enabled: {', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]Warning: No channels enabled[/yellow]")

    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]*[/green] Cron: {cron_status['jobs']} scheduled jobs")

    console.print(f"[green]*[/green] Heartbeat: every 30m")
    console.print(f"[green]*[/green] Webhooks: listening on port {port}")

    async def run():
        try:
            await cron.start()
            await heartbeat.start()

            # Start webhook server (using same port as gateway for simplicity in this phase)   
            # In a real production setup, we might want separate ports or a reverse proxy      
            # But here we are integrating into the main event loop
            webhook_runner = await webhook_server.start(port=port)

            tasks = [
                agent.run(),
                channels.start_all(),
                bus.dispatch_system_events(),
            ]

            if recovery_data:
                async def _recover():
                    await asyncio.sleep(5)
                    from kabot.bus.events import OutboundMessage
                    await bus.publish_outbound(OutboundMessage(
                        chat_id=recovery_data["chat_id"],
                        channel=recovery_data["channel"],
                        content=recovery_data["message"]
                    ))
                    console.print("[green]✓[/green] Restored pending conversation")
                tasks.append(_recover())

            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            console.print("\nShutting down...")
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()
            if 'webhook_runner' in locals():
                await webhook_runner.cleanup()

    asyncio.run(run())




# ============================================================================
# Agent Commands
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"), 
    session_id: str = typer.Option("cli:default", "--session", "-s", help="Session ID"),       
    markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render assistant output as Markdown"),
    logs: bool = typer.Option(False, "--logs/--no-logs", help="Show kabot runtime logs during chat"),
):
    """Interact with the agent directly."""
    from kabot.config.loader import load_config
    from kabot.bus.queue import MessageBus
    from kabot.agent.loop import AgentLoop
    from kabot.cron.service import CronService
    from kabot.cron.types import CronJob
    from kabot.config.loader import get_data_dir
    from loguru import logger

    config = load_config()
    _inject_skill_env(config)

    # Configure logger
    from kabot.core.logger import configure_logger
    from kabot.memory.sqlite_store import SQLiteMetadataStore
    
    db_path = get_data_dir() / "metadata.db"
    store = SQLiteMetadataStore(db_path)
    configure_logger(config, store)

    bus = MessageBus()
    provider = _make_provider(config)

    if logs:
        logger.enable("kabot")
    else:
        logger.disable("kabot")

    p = config.get_provider()

    # Initialize CronService (required for reminder tools)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        fallbacks=p.fallbacks if p else None,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        enable_hybrid_memory=config.agents.enable_hybrid_memory,
        cron_service=cron,  # Pass cron service to enable tools
    )

    # Setup cron callback for CLI
    async def on_cron_job(job: CronJob) -> str | None:
        """Execute a cron job and print to CLI."""
        # Check if this is a CLI-originated job or generic
        target = job.payload.channel
        if target and target != "cli":
            return None  # Ignore jobs for other channels? Or execute anyway?

        response = await agent_loop.process_direct(
            job.payload.message,
            session_key=f"background:cron:{job.id}"
        )
        
        # Verify if we should print it (if in interactive mode)
        if response and job.payload.deliver:
            _print_agent_response(f"[Reminder] {response}", render_markdown=markdown)
        return response

    cron.on_job = on_cron_job

    # Show spinner when logs are off (no output to miss); skip when logs are on
    def _thinking_ctx():
        if logs:
            from contextlib import nullcontext
            return nullcontext()
        return console.status("[dim]kabot is thinking...[/dim]", spinner="dots")

    if message:
        # Single message mode
        async def run_once():
            # Start cron briefly to allow scheduling (though async jobs won't fire)
            await cron.start()
            try:
                with _thinking_ctx():
                    response = await agent_loop.process_direct(message, session_id)
                _print_agent_response(response, render_markdown=markdown)
            finally:
                cron.stop()

        asyncio.run(run_once())
    else:
        # Interactive mode
        _enable_line_editing()
        console.print(f"{__logo__} Interactive mode (type [bold]exit[/bold] or [bold]Ctrl+C[/bold] to quit)\n")

        # input() runs in a worker thread that can't be cancelled.
        # Without this handler, asyncio.run() would hang waiting for it.
        def _exit_on_sigint(signum, frame):
            _save_history()
            _restore_terminal()
            console.print("\nGoodbye!")
            os._exit(0)

        signal.signal(signal.SIGINT, _exit_on_sigint)

        async def run_interactive():
            await cron.start()
            try:
                while True:
                    try:
                        _flush_pending_tty_input()
                        user_input = await _read_interactive_input_async()
                        command = user_input.strip()
                        if not command:
                            continue

                        if _is_exit_command(command):
                            _save_history()
                            _restore_terminal()
                            console.print("\nGoodbye!")
                            break

                        with _thinking_ctx():
                            response = await agent_loop.process_direct(user_input, session_id)     
                        _print_agent_response(response, render_markdown=markdown)
                    except KeyboardInterrupt:
                        _save_history()
                        _restore_terminal()
                        console.print("\nGoodbye!")
                        break
                    except EOFError:
                        _save_history()
                        _restore_terminal()
                        console.print("\nGoodbye!")
                        break
            finally:
                cron.stop()

        asyncio.run(run_interactive())


# ============================================================================
# Agent Commands
# ============================================================================

from kabot.cli import agents

app.add_typer(agents.app, name="agents")


# ============================================================================
# Mode Commands
# ============================================================================

from kabot.cli import mode

app.add_typer(mode.app, name="mode")


# ============================================================================
# Model Commands
# ============================================================================

models_app = typer.Typer(help="Manage AI models and metadata")
app.add_typer(models_app, name="models")


@models_app.command("list")
def models_list(
    provider: str = typer.Option(None, "--provider", "-p", help="Filter by provider"),
    premium: bool = typer.Option(False, "--premium", help="Show only premium models"),
):
    """List all available models with pricing and capabilities."""
    from kabot.providers.registry import ModelRegistry
    from kabot.memory.sqlite_store import SQLiteMetadataStore
    from kabot.config.loader import get_data_dir

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

@models_app.command("scan")
def models_scan():
    """Scan provider APIs to discover available models."""
    from kabot.providers.registry import ModelRegistry
    from kabot.providers.scanner import ModelScanner
    from kabot.memory.sqlite_store import SQLiteMetadataStore
    from kabot.config.loader import load_config, get_data_dir

    config = load_config()
    db_path = get_data_dir() / "metadata.db"
    db = SQLiteMetadataStore(db_path)
    registry = ModelRegistry(db=db)
    scanner = ModelScanner(registry, db=db)

    with console.status("[bold cyan]Scanning providers for models..."):
        count = scanner.scan_all(config.providers)

    console.print(f"\n[green]✓[/green] Scan complete! Found and registered [bold]{count}[/bold] models.")
    console.print("[dim]Use `kabot models list` to see them.[/dim]")


@models_app.command("info")
def models_info(
    model_id: str = typer.Argument(..., help="Model ID or short name"),
):
    """Show detailed metadata for a specific model."""
    from kabot.providers.registry import ModelRegistry
    from kabot.memory.sqlite_store import SQLiteMetadataStore
    from kabot.config.loader import get_data_dir

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


@models_app.command("set")
def models_set(
    model_name: str = typer.Argument(..., help="Model ID or Alias"),
):
    """Set the primary model for the agent."""
    from kabot.providers.registry import ModelRegistry
    from kabot.config.loader import load_config, save_config, get_data_dir
    from kabot.memory.sqlite_store import SQLiteMetadataStore

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

# ============================================================================
# Channel Commands
# ============================================================================


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
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





@channels_app.command("login")
def channels_login():
    """Link device via QR code."""
    import subprocess

    from kabot.cli.bridge_utils import get_bridge_dir
    bridge_dir = get_bridge_dir()

    console.print(f"{__logo__} Starting bridge...")
    console.print("Scan the QR code to connect.\n")

    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Bridge failed: {e}[/red]")
    except FileNotFoundError:
        console.print("[red]npm not found. Please install Node.js.[/red]")


# ============================================================================
# Auth Commands
# ============================================================================

auth_app = typer.Typer(help="Manage authentication")
app.add_typer(auth_app, name="auth")


@auth_app.command("list")
def auth_list():
    """List supported authentication providers."""
    from kabot.auth.manager import AuthManager
    from kabot.auth.menu import AUTH_PROVIDERS
    from rich.table import Table

    table = Table(title="Supported Providers")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Methods", style="yellow")

    for pid, meta in AUTH_PROVIDERS.items():
        methods = ", ".join(meta["methods"].keys())
        table.add_row(pid, meta["name"], methods)

    console.print(table)


@auth_app.command("login")
def auth_login(
    provider: str = typer.Argument(None, help="Provider ID (e.g., openai, anthropic)"),        
    method: str = typer.Option(None, "--method", "-m", help="Auth method (e.g., oauth, api_key)"),
    profile: str = typer.Option("default", "--profile", "-p", help="Profile name (e.g., work, personal)"),
):
    """Login to a provider with optional method and profile selection."""
    from kabot.auth.manager import AuthManager
    from kabot.auth.menu import get_auth_choices, AUTH_PROVIDERS
    from rich.prompt import Prompt

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
        from kabot.providers.registry import ModelRegistry
        from kabot.config.loader import load_config, save_config, get_data_dir
        from kabot.memory.sqlite_store import SQLiteMetadataStore

        db_path = get_data_dir() / "metadata.db"
        db = SQLiteMetadataStore(db_path)
        registry = ModelRegistry(db=db)

        # Find premium models for this provider
        available_models = [m for m in registry.list_models() if m.provider == provider and m.is_premium]

        if available_models:
            console.print(f"\n[bold]Suggested premium models for {provider}:[/bold]\n")        
            for idx, m in enumerate(available_models, 1):
                console.print(f"  [{idx}] {m.name} ({m.short_id}) - Context: {m.context_window:,}")

            console.print(f"  [0] Skip (Keep current default)")

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
        console.print(f"\n[red]✗ Authentication failed[/red]")
        raise typer.Exit(1)


@auth_app.command("methods")
def auth_methods(
    provider: str = typer.Argument(..., help="Provider ID"),
):
    """List available authentication methods for a provider."""
    from kabot.auth.menu import AUTH_PROVIDERS
    from rich.table import Table

    if provider not in AUTH_PROVIDERS:
        console.print(f"[red]Provider '{provider}' not found[/red]")
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
    console.print(f"[dim]Usage: kabot auth login {provider} --method <method_id>[/dim]")       


@auth_app.command("status")
def auth_status():
    """Show authentication status."""
    from kabot.auth.manager import AuthManager
    manager = AuthManager()
    manager.get_status()


# ============================================================================
# Cron Commands
# ============================================================================

cron_app = typer.Typer(help="Manage scheduled tasks")
app.add_typer(cron_app, name="cron")


@cron_app.command("list")
def cron_list(
    all: bool = typer.Option(False, "--all", "-a", help="Include disabled jobs"),
):
    """List scheduled jobs."""
    from kabot.config.loader import get_data_dir
    from kabot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    jobs = service.list_jobs(include_disabled=all)

    if not jobs:
        console.print("No scheduled jobs.")
        return

    table = Table(title="Scheduled Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Schedule")
    table.add_column("Status")
    table.add_column("Next Run")

    import time
    for job in jobs:
        # Format schedule
        if job.schedule.kind == "every":
            sched = f"every {(job.schedule.every_ms or 0) // 1000}s"
        elif job.schedule.kind == "cron":
            sched = job.schedule.expr or ""
        else:
            sched = "one-time"

        # Format next run
        next_run = ""
        if job.state.next_run_at_ms:
            next_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(job.state.next_run_at_ms / 1000))
            next_run = next_time

        status = "[green]enabled[/green]" if job.enabled else "[dim]disabled[/dim]"

        table.add_row(job.id, job.name, sched, status, next_run)

    console.print(table)


@cron_app.command("add")
def cron_add(
    name: str = typer.Option(..., "--name", "-n", help="Job name"),
    message: str = typer.Option(..., "--message", "-m", help="Message for agent"),
    every: int = typer.Option(None, "--every", "-e", help="Run every N seconds"),
    cron_expr: str = typer.Option(None, "--cron", "-c", help="Cron expression (e.g. '0 9 * * *')"),
    at: str = typer.Option(None, "--at", help="Run once at time (ISO format)"),
    deliver: bool = typer.Option(False, "--deliver", "-d", help="Deliver response to channel"),
    to: str = typer.Option(None, "--to", help="Recipient for delivery"),
    channel: str = typer.Option(None, "--channel", help="Channel for delivery (e.g. 'telegram', 'whatsapp')"),
):
    """Add a scheduled job."""
    from kabot.config.loader import get_data_dir
    from kabot.cron.service import CronService
    from kabot.cron.types import CronSchedule

    # Determine schedule type
    if every:
        schedule = CronSchedule(kind="every", every_ms=every * 1000)
    elif cron_expr:
        schedule = CronSchedule(kind="cron", expr=cron_expr)
    elif at:
        import datetime
        dt = datetime.datetime.fromisoformat(at)
        schedule = CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))
    else:
        console.print("[red]Error: Must specify --every, --cron, or --at[/red]")
        raise typer.Exit(1)

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    job = service.add_job(
        name=name,
        schedule=schedule,
        message=message,
        deliver=deliver,
        to=to,
        channel=channel,
    )

    console.print(f"[green]✓[/green] Added job '{job.name}' ({job.id})")


@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="Job ID to remove"),
):
    """Remove a scheduled job."""
    from kabot.config.loader import get_data_dir
    from kabot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    if service.remove_job(job_id):
        console.print(f"[green]✓[/green] Removed job {job_id}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("enable")
def cron_enable(
    job_id: str = typer.Argument(..., help="Job ID"),
    disable: bool = typer.Option(False, "--disable", help="Disable instead of enable"),        
):
    """Enable or disable a job."""
    from kabot.config.loader import get_data_dir
    from kabot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    job = service.enable_job(job_id, enabled=not disable)
    if job:
        status = "disabled" if disable else "enabled"
        console.print(f"[green]✓[/green] Job '{job.name}' {status}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("run")
def cron_run(
    job_id: str = typer.Argument(..., help="Job ID to run"),
    force: bool = typer.Option(False, "--force", "-f", help="Run even if disabled"),
):
    """Manually run a job."""
    from kabot.config.loader import get_data_dir
    from kabot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    async def run():
        return await service.run_job(job_id, force=force)

    if asyncio.run(run()):
        console.print(f"[green]✓[/green] Job executed")
    else:
        console.print(f"[red]Failed to run job {job_id}[/red]")


# ============================================================================
# Status Commands
# ============================================================================


@app.command()
def status():
    """Show kabot status."""
    from kabot.config.loader import load_config, get_config_path

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} kabot Status\n")

    console.print(f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")

    if config_path.exists():
        from kabot.providers.registry import PROVIDERS

        console.print(f"Model: {config.agents.defaults.model}")

        # Check API keys from registry
        from kabot.providers.registry import PROVIDERS
        for spec in PROVIDERS:
            # Map registry name to config field if different
            config_field = spec.name
            p = getattr(config.providers, config_field, None)

            if p is None:
                continue

            if spec.is_local:
                # Local deployments show api_base instead of api_key
                if p.api_base:
                    console.print(f"{spec.label}: [green]✓ {p.api_base}[/green]")
                else:
                    console.print(f"{spec.label}: [dim]not set[/dim]")
            else:
                has_key = bool(p.api_key)
                status_icon = "[green]✓[/green]" if has_key else "[dim]not set[/dim]"
                console.print(f"{spec.label}: {status_icon}")


@app.command("security-audit")
def security_audit():
    """Run a security audit on the workspace."""
    from kabot.config.loader import load_config
    from kabot.utils.security_audit import SecurityAuditor
    from rich.table import Table

    config = load_config()
    auditor = SecurityAuditor(config.workspace_path)

    with console.status("[bold cyan]Running security audit..."):
        findings = auditor.run_audit()

    if not findings:
        console.print("\n[bold green]✓ No security issues found![/bold green]")
        return

    table = Table(title=f"Security Audit Results ({len(findings)} findings)")
    table.add_column("Type", style="bold red")
    table.add_column("Severity", style="magenta")
    table.add_column("File", style="cyan")
    table.add_column("Detail", style="white")

    for f in findings:
        table.add_row(f["type"], f["severity"], f["file"], f["detail"])

    console.print("\n")
    console.print(table)
    console.print("\n[yellow]⚠️ Please review the findings above and secure your workspace.[/yellow]")


@app.command("doctor")
def doctor(
    agent: str = typer.Option("main", "--agent", "-a", help="Agent ID to check"),
    fix: bool = typer.Option(False, "--fix", help="Automatically fix critical integrity issues"),
):
    """Run system health and integrity checks."""
    from kabot.utils.doctor import KabotDoctor
    doc = KabotDoctor(agent_id=agent)
    doc.render_report(fix=fix)


@app.command("plugins")
def plugins_cmd(
    action: str = typer.Argument("list", help="Action to perform (list)"),
):
    """Manage plugins."""
    from kabot.plugins.registry import PluginRegistry
    from kabot.plugins.loader import load_plugins
    from kabot.config.loader import load_config

    config = load_config()
    registry = PluginRegistry()
    plugins_dir = config.workspace_path / "plugins"
    load_plugins(plugins_dir, registry)

    if action == "list":
        plugins_list = registry.list_all()

        if not plugins_list:
            console.print("[yellow]No plugins found.[/yellow]")
            console.print(f"[dim]Add plugins to: {plugins_dir}[/dim]")
            return

        table = Table(title="Installed Plugins")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        table.add_column("Status")

        for p in plugins_list:
            status = "[green]Enabled[/green]" if p.enabled else "[red]Disabled[/red]"
            table.add_row(p.name, p.description, status)

        console.print(table)
        console.print(f"\n[dim]Total: {len(plugins_list)} plugin(s)[/dim]")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("[dim]Available actions: list[/dim]")


if __name__ == "__main__":
    app()
