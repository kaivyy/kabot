"""CLI commands for kabot."""

import asyncio
import atexit
import inspect
import json
import os
import select
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

import typer
from loguru import logger
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from kabot import __logo__, __version__
from kabot.cli import agents, mode
from kabot.cron.callbacks import (
    build_bus_cron_callback,
    build_cli_cron_callback,
)
from kabot.cron.callbacks import (
    render_cron_delivery_with_ai as _render_cron_delivery_with_ai_impl,
)
from kabot.cron.callbacks import (
    resolve_cron_delivery_content as _resolve_cron_delivery_content_impl,
)
from kabot.cron.callbacks import (
    should_use_reminder_fallback as _should_use_reminder_fallback_impl,
)
from kabot.cron.callbacks import (
    strip_reminder_context as _strip_reminder_context_impl,
)
from kabot.utils.workspace_templates import ensure_workspace_templates

app = typer.Typer(
    name="kabot",
    help=f"{__logo__} kabot - Personal AI Assistant",
    no_args_is_help=True,
)

console = Console()
EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit", ":q"}


def _ensure_utf8_stdio() -> None:
    """Best-effort UTF-8 stdio for Windows terminals (avoid cp1252 crashes)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            continue


_ensure_utf8_stdio()

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


def _terminal_safe(text: str, encoding: str | None = None) -> str:
    """Best-effort conversion for terminals that cannot print Unicode content."""
    value = text or ""
    enc = encoding or getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        value.encode(enc)
        return value
    except (LookupError, UnicodeEncodeError):
        return value.encode(enc, errors="replace").decode(enc, errors="replace")


def _print_agent_response(response: str, render_markdown: bool) -> None:
    """Render assistant response with consistent terminal styling."""
    content = _terminal_safe(response or "")
    body = Markdown(content) if render_markdown else Text(content)
    title = _terminal_safe(f"{__logo__} kabot")
    console.print()
    console.print(
        Panel(
            body,
            title=title,
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

@app.command("google-auth")
def google_auth(
    credentials_path: str = typer.Argument(
        ..., help="Path to the downloaded google_credentials.json file."
    )
):
    """Setup Google Suite OAuth credentials interactively."""
    import shutil
    from pathlib import Path

    from kabot.auth.google_auth import GoogleAuthManager

    cred_file = Path(credentials_path)
    if not cred_file.exists():
        console.print(f"[red]Error: Credentials file not found at {cred_file}[/red]")
        raise typer.Exit(1)

    auth_manager = GoogleAuthManager()

    # Copy credentials to the workspace
    target_path = auth_manager.credentials_path
    try:
        shutil.copy(cred_file, target_path)
        console.print(f"[green]✓[/green] Copied credentials to {target_path}")
    except Exception as e:
        console.print(f"[red]Failed to copy credentials: {e}[/red]")
        raise typer.Exit(1)

    # Trigger auth flow
    console.print("[cyan]Initiating Google OAuth login flow in your browser...[/cyan]")
    try:
        auth_manager.get_credentials()
        console.print("[green]✓[/green] Successfully authenticated with Google Suite!")
    except Exception as e:
        console.print(f"[red]Authentication failed: {e}[/red]")
        raise typer.Exit(1)


@app.command("train")
def train(
    file_path: str = typer.Argument(
        ..., help="Path to the .pdf, .txt, or .md file to train the agent on."
    ),
    workspace: str = typer.Option(
        "cli", "--workspace", "-w", help="Workspace to inject the memory into (e.g. Aizawa, Hawk)."
    )
):
    """Auto-Onboard an agent by uploading a document directly into its memory."""
    from pathlib import Path

    from kabot.memory.chroma_memory import ChromaMemoryManager
    from kabot.utils.document_parser import DocumentParser
    from kabot.utils.helpers import get_workspace_path

    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]Error: File not found at {path}[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Reading document: {path.name}...[/cyan]")
    try:
        text = DocumentParser.extract_text(path)
        chunks = DocumentParser.chunk_text(text, chunk_size=1500, overlap=300)
    except Exception as e:
        console.print(f"[red]Failed to extract text: {e}[/red]")
        raise typer.Exit(1)

    if not chunks:
        console.print("[yellow]No text could be extracted from the file.[/yellow]")
        raise typer.Exit(1)

    console.print(f"[cyan]Extracted {len(chunks)} chunks. Injecting into workspace '{workspace}'...[/cyan]")

    # Initialize chroma DB for the specific workspace
    base_dir = get_workspace_path()
    chroma_dir = base_dir / "sessions" / workspace / "chroma"
    chroma_manager = ChromaMemoryManager(persist_directory=str(chroma_dir))

    try:
        # Save each chunk as a memory
        for i, chunk in enumerate(chunks):
            # Prefix it to signify it's training data, not conversation history
            doc_content = f"Training Reference ({path.name} part {i+1}): {chunk}"
            # Inject it
            chroma_manager.add_messages([
                {"role": "system", "content": doc_content}
            ])

        console.print(f"[green]✓[/green] Successfully trained '{workspace}' with {len(chunks)} chunks from {path.name}!")
    except Exception as e:
        console.print(f"[red]Memory injection failed: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def setup(
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Run interactive setup wizard"),
):
    """Interactive setup wizard for configuring kabot."""
    from kabot.config.loader import get_config_path, save_config

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
        workspace = Path(config.agents.defaults.workspace).expanduser()
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
    token_mode: str = typer.Option(
        "",
        "--token-mode",
        help="Set runtime token mode directly: boros or hemat",
    ),
    token_saver: bool | None = typer.Option(
        None,
        "--token-saver/--no-token-saver",
        help="Shortcut toggle: enabled=hemat, disabled=boros",
    ),
):
    """Configure kabot settings."""
    from kabot.config.loader import get_config_path, load_config, save_config

    if str(token_mode or "").strip() or token_saver is not None:
        raw_mode = str(token_mode or "").strip().lower()
        if raw_mode:
            if raw_mode not in {"boros", "hemat"}:
                raise typer.BadParameter("Token mode must be boros or hemat.", param_hint="--token-mode")
            resolved_mode = raw_mode
        else:
            resolved_mode = "hemat" if bool(token_saver) else "boros"

        cfg = load_config()
        cfg.runtime.performance.token_mode = resolved_mode
        save_config(cfg)
        console.print(f"[green]Runtime token mode set to {resolved_mode.upper()}[/green]")
        return

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


def _is_secret_env_name(env_key: str) -> bool:
    upper = str(env_key or "").upper()
    return any(token in upper for token in ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH"))


def _collect_skill_env_requirements(config, skill_key: str) -> list[str]:
    """Collect required env keys for a specific installed skill."""
    from kabot.agent.skills import SkillsLoader

    key = str(skill_key or "").strip()
    if not key:
        return []
    try:
        loader = SkillsLoader(config.workspace_path, skills_config=config.skills)
        statuses = loader.list_skills(filter_unavailable=False)
    except Exception:
        return []

    status = next(
        (
            s
            for s in statuses
            if str(s.get("skill_key") or "").strip() == key
            or str(s.get("name") or "").strip() == key
        ),
        None,
    )
    if not isinstance(status, dict):
        return []

    env_keys: list[str] = []
    missing = status.get("missing", {})
    if isinstance(missing, dict):
        missing_env = missing.get("env", [])
        if isinstance(missing_env, list):
            for raw in missing_env:
                env = str(raw).strip()
                if env and env not in env_keys:
                    env_keys.append(env)

    primary = str(status.get("primaryEnv") or "").strip()
    if primary and primary not in env_keys:
        env_keys.append(primary)

    return env_keys


def _load_skill_persona_snippet(installed_dir: Path, skill_name: str, skill_key: str) -> str:
    """Load optional skill persona snippet, fallback to generic snippet."""
    candidates = [
        installed_dir / "soul-injection.md",
        installed_dir / "templates" / "soul-injection.md",
        installed_dir / "SOUL.md",
        installed_dir / "templates" / "SOUL.md",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if text:
            return text

    display_name = (skill_name or skill_key or "Skill").strip()
    return (
        f"## {display_name} Capability\n\n"
        f"When user requests tasks related to this capability, use `{skill_key}` skill."
    )


def _inject_skill_persona(workspace: Path, snippet: str) -> bool:
    """Append persona snippet to SOUL.md once."""
    ensure_workspace_templates(workspace)
    soul_path = workspace / "SOUL.md"
    if not soul_path.exists():
        soul_path.write_text("", encoding="utf-8")
    current = soul_path.read_text(encoding="utf-8")
    normalized_snippet = snippet.strip()
    if not normalized_snippet:
        return False
    if normalized_snippet in current:
        return False
    new_content = current.rstrip() + ("\n\n" if current.strip() else "") + normalized_snippet + "\n"
    soul_path.write_text(new_content, encoding="utf-8")
    return True


def _handle_skill_onboarding(config, installed) -> dict[str, Any]:
    """Apply one-shot onboarding: auto-enable, env prompts, and persona injection."""
    from kabot.config.skills_settings import (
        resolve_onboarding_settings,
        set_skill_entry_enabled,
        set_skill_entry_env,
    )

    onboarding = resolve_onboarding_settings(config.skills)
    auto_enable = bool(onboarding.get("auto_enable_after_install", True))
    auto_prompt_env = bool(onboarding.get("auto_prompt_env", True))
    soul_mode = str(onboarding.get("soul_injection_mode", "prompt") or "prompt").strip().lower()
    if soul_mode not in {"disabled", "prompt", "auto"}:
        soul_mode = "prompt"

    if auto_enable:
        config.skills = set_skill_entry_enabled(
            config.skills,
            installed.skill_key,
            True,
            persist_true=True,
        )

    saved_env_keys: list[str] = []
    if auto_prompt_env:
        env_keys = _collect_skill_env_requirements(config, installed.skill_key)
        for env_key in env_keys:
            current_val = os.environ.get(env_key) or ""
            prompt_text = f"Enter {env_key}"
            value = typer.prompt(
                prompt_text,
                default=current_val,
                hide_input=_is_secret_env_name(env_key),
            )
            val = str(value or "").strip()
            if not val:
                continue
            config.skills = set_skill_entry_env(config.skills, installed.skill_key, env_key, val)
            if env_key not in saved_env_keys:
                saved_env_keys.append(env_key)
            if env_key not in os.environ:
                os.environ[env_key] = val

    persona_injected = False
    if soul_mode != "disabled":
        should_inject = soul_mode == "auto"
        if soul_mode == "prompt":
            if sys.stdin.isatty() and sys.stdout.isatty():
                should_inject = typer.confirm(
                    f"Inject persona snippet into SOUL.md for '{installed.skill_name}'?",
                    default=True,
                )
            else:
                should_inject = False
        if should_inject:
            snippet = _load_skill_persona_snippet(
                installed.installed_dir,
                installed.skill_name,
                installed.skill_key,
            )
            persona_injected = _inject_skill_persona(config.workspace_path, snippet)

    return {
        "auto_enabled": auto_enable,
        "saved_env_keys": saved_env_keys,
        "persona_injected": persona_injected,
    }


skills_app = typer.Typer(help="Manage external skills")
app.add_typer(skills_app, name="skills")


@skills_app.command("install")
def skills_install(
    git: str = typer.Option(..., "--git", help="Git repository URL/path that contains SKILL.md"),
    ref: str = typer.Option("", "--ref", help="Optional git ref (tag/branch/commit)"),
    subdir: str = typer.Option(
        "",
        "--subdir",
        help="Relative folder in repo containing SKILL.md (required when repo has multiple skills)",
    ),
    name: str = typer.Option("", "--name", help="Override installed skill name/slug"),
    target: str = typer.Option("managed", "--target", help="Install target: managed or workspace"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing destination"),
):
    """Install skill from git repository into Kabot skills directory."""
    from kabot.cli.skill_repo_installer import install_skill_from_git
    from kabot.config.loader import load_config, save_config
    from kabot.config.skills_settings import (
        normalize_skills_settings,
        resolve_load_settings,
        resolve_onboarding_settings,
    )
    from kabot.utils.skill_validator import validate_skill_trust

    cfg = load_config()
    target_value = target.strip().lower()
    if target_value not in {"managed", "workspace"}:
        console.print("[red]Invalid --target. Use: managed or workspace[/red]")
        raise typer.Exit(1)

    if target_value == "workspace":
        target_dir = cfg.workspace_path / "skills"
    else:
        load_settings = resolve_load_settings(cfg.skills)
        managed_dir = str(load_settings.get("managed_dir") or "").strip()
        if managed_dir:
            target_dir = Path(managed_dir).expanduser()
        else:
            target_dir = Path("~/.kabot/skills").expanduser()

    try:
        installed = install_skill_from_git(
            repo_url=git,
            target_dir=target_dir,
            ref=ref.strip() or None,
            subdir=subdir.strip() or None,
            skill_name=name.strip() or None,
            overwrite=force,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    trust_mode = getattr(getattr(cfg, "security", None), "trust_mode", None)
    trust_enabled = bool(getattr(trust_mode, "enabled", False))
    if trust_enabled:
        trust_ok, trust_detail = validate_skill_trust(
            installed.installed_dir,
            verify_skill_manifest=bool(getattr(trust_mode, "verify_skill_manifest", False)),
            allowed_signers=list(getattr(trust_mode, "allowed_signers", []) or []),
        )
        if not trust_ok:
            try:
                import shutil
                shutil.rmtree(installed.installed_dir, ignore_errors=True)
            except Exception:
                pass
            console.print(f"[red]Trust mode blocked skill install: {trust_detail}[/red]")
            raise typer.Exit(1)
        console.print(f"[green]Trust mode verified[/green]: {trust_detail}")

    onboarding = resolve_onboarding_settings(cfg.skills)
    auto_enable = bool(onboarding.get("auto_enable_after_install", True))
    onboarding_result = _handle_skill_onboarding(cfg, installed)
    cfg.skills = normalize_skills_settings(cfg.skills)
    save_config(cfg)

    console.print(f"[green]✓[/green] Installed skill: [cyan]{installed.skill_name}[/cyan]")
    console.print(f"  Source repo: {installed.repo_url}")
    console.print(f"  Source dir: {installed.selected_dir}")
    console.print(f"  Installed to: {installed.installed_dir}")
    if auto_enable:
        console.print("  Enabled in config: skills.entries.{0}.enabled=true".format(installed.skill_key))
    else:
        console.print("  Auto-enable after install is OFF (skills.onboarding.autoEnableAfterInstall=false).")
    saved_env_keys = onboarding_result.get("saved_env_keys", [])
    if saved_env_keys:
        console.print(f"  Saved env keys: {', '.join(saved_env_keys)}")
    if onboarding_result.get("persona_injected"):
        console.print("  Persona snippet injected into SOUL.md")
    console.print("\nNext:")
    console.print("  1. Run [cyan]kabot config[/cyan] -> Skills to configure env keys/dependency plan")
    console.print("  2. Run [cyan]kabot doctor[/cyan] to verify runtime requirements")


def _create_workspace_templates(workspace: Path):
    """Create default workspace template files."""
    created = ensure_workspace_templates(workspace)
    for file_path in created:
        relative = file_path.relative_to(workspace)
        console.print(f"  [dim]Created {relative}[/dim]")


def _merge_fallbacks(primary: str, *groups: list[str]) -> list[str]:
    """Merge fallback lists while preserving order and removing duplicates."""
    merged: list[str] = []
    for group in groups:
        for model in group:
            if not model or model == primary:
                continue
            if model not in merged:
                merged.append(model)
    return merged


def _provider_has_credentials(provider_config) -> bool:
    """Check if provider has any usable credentials configured."""
    if not provider_config:
        return False

    if provider_config.api_key or provider_config.setup_token:
        return True

    active_id = getattr(provider_config, "active_profile", "default")
    profiles = getattr(provider_config, "profiles", {}) or {}
    active = profiles.get(active_id)
    if active and (active.api_key or active.oauth_token or active.setup_token):
        return True

    for profile in profiles.values():
        if profile.api_key or profile.oauth_token or profile.setup_token:
            return True

    return False


def _implicit_runtime_fallbacks(config, primary: str, explicit_chain: list[str]) -> list[str]:
    """
    Build implicit runtime fallback chain when user did not configure one explicitly.

    Rule:
    - Only when the user has no explicit fallback chain.
    - Only for OpenAI/OpenAI-Codex primaries.
    - If Groq credentials exist, inject Groq Llama-4 Scout as emergency failover.
    """
    if explicit_chain:
        return []

    primary_l = str(primary or "").lower()
    if not (primary_l.startswith("openai/") or primary_l.startswith("openai-codex/")):
        return []

    groq_cfg = getattr(getattr(config, "providers", None), "groq", None)
    if not _provider_has_credentials(groq_cfg):
        return []

    return ["groq/meta-llama/llama-4-scout-17b-16e-instruct"]


def _resolve_runtime_fallbacks(
    config,
    primary: str,
    model_fallbacks: list[str],
    provider_fallbacks: list[str],
) -> list[str]:
    """Resolve effective runtime fallback chain (explicit + implicit)."""
    explicit_chain = _merge_fallbacks(primary, model_fallbacks, provider_fallbacks)
    implicit_chain = _implicit_runtime_fallbacks(config, primary, explicit_chain)
    return _merge_fallbacks(primary, explicit_chain, implicit_chain)


def _resolve_model_runtime(config) -> tuple[str, list[str]]:
    """Resolve default model + fallback chain from config defaults."""
    from kabot.config.schema import AgentModelConfig

    model_config = config.agents.defaults.model
    if isinstance(model_config, AgentModelConfig):
        return model_config.primary, list(model_config.fallbacks or [])
    return str(model_config), []


def _resolve_gateway_runtime_port(config, cli_port: int | None) -> int:
    """Resolve gateway port: CLI override > config.gateway.port > default."""
    if isinstance(cli_port, int) and 0 < cli_port < 65536:
        return cli_port

    configured = getattr(getattr(config, "gateway", None), "port", None)
    try:
        configured_port = int(configured)
    except (TypeError, ValueError):
        configured_port = 0

    if 0 < configured_port < 65536:
        return configured_port
    return 18790


def _resolve_tailscale_mode(config) -> str:
    """Map Kabot gateway config into runtime tailscale mode."""
    gateway_cfg = getattr(config, "gateway", None)
    bind_mode = str(getattr(gateway_cfg, "bind_mode", "") or "").strip().lower()
    funnel_enabled = bool(getattr(gateway_cfg, "tailscale", False))

    # Keep backward compatibility with existing wizard fields:
    # - bind_mode=tailscale means private tailnet exposure (serve)
    # - tailscale=true means funnel exposure (public) when not in tailscale bind mode
    if bind_mode == "tailscale":
        return "serve"
    if funnel_enabled:
        return "funnel"
    return "off"


def _is_port_in_use_error(exc: BaseException) -> bool:
    """Return True when exception indicates gateway port bind conflict."""
    if not isinstance(exc, OSError):
        return False
    errno_value = getattr(exc, "errno", None)
    winerror_value = getattr(exc, "winerror", None)
    if errno_value in {48, 98, 10048, 10013}:
        return True
    if winerror_value in {48, 10048, 10013}:
        return True
    message = str(exc).lower()
    if "address already in use" in message:
        return True
    if "forbidden by its access permissions" in message:
        return True
    if "attempting to bind on address" in message and "10048" in message:
        return True
    return False


def _preflight_gateway_port(host: str, port: int) -> None:
    """
    Fail fast if gateway bind target is already occupied.

    This runs before heavy runtime initialization so watchdog startup feedback
    is immediate when another instance already holds the port.
    """
    import socket

    bind_host = str(host or "0.0.0.0").strip() or "0.0.0.0"

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((bind_host, int(port)))
        except OSError as exc:
            if _is_port_in_use_error(exc):
                console.print(
                    f"[yellow]Gateway port {port} is already in use.[/yellow]"
                )
                console.print(
                    "[yellow]Another Kabot instance may already be running. "
                    "Stop existing process first or change `gateway.port` in config.[/yellow]"
                )
                raise typer.Exit(code=78)
            raise


def _run_tailscale_cli(args: list[str], timeout_s: int = 10) -> tuple[int, str, str]:
    """Run tailscale CLI command and return (code, stdout, stderr)."""
    tailscale_bin = shutil.which("tailscale") or "tailscale"
    try:
        result = subprocess.run(
            [tailscale_bin, *args],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return result.returncode, (result.stdout or "").strip(), (result.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", "tailscale binary not found in PATH"
    except subprocess.TimeoutExpired:
        return 124, "", f"tailscale command timed out: {' '.join(args)}"
    except Exception as exc:  # pragma: no cover - defensive fallback
        return 1, "", str(exc)


def _parse_tailscale_status(stdout: str) -> dict[str, Any]:
    """Parse tailscale status JSON, tolerating noisy prefixes/suffixes."""
    text = (stdout or "").strip()
    if not text:
        return {}
    start = text.find("{")
    end = text.rfind("}")
    candidate = text[start : end + 1] if start >= 0 and end > start else text
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_tailnet_host(status_payload: dict[str, Any]) -> str:
    """Extract DNSName (preferred) or first Tailscale IP from status JSON."""
    self_payload = status_payload.get("Self")
    if isinstance(self_payload, dict):
        dns_name = self_payload.get("DNSName")
        if isinstance(dns_name, str) and dns_name.strip():
            return dns_name.strip().rstrip(".")
        ips = self_payload.get("TailscaleIPs")
        if isinstance(ips, list):
            for value in ips:
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return ""


def _configure_tailscale_runtime(
    mode: str,
    port: int,
    runner: Callable[[list[str], int], tuple[int, str, str]] | None = None,
) -> dict[str, Any]:
    """Enable tailscale serve/funnel for gateway runtime and report status."""
    normalized = str(mode or "").strip().lower()
    if normalized not in {"serve", "funnel"}:
        return {"enabled": False, "ok": True, "mode": "off", "error": "", "https_url": ""}

    execute = runner or _run_tailscale_cli
    status_code, status_stdout, status_stderr = execute(["status", "--json"], 8)
    if status_code != 0:
        detail = status_stderr or status_stdout or "tailscale status command failed"
        return {
            "enabled": True,
            "ok": False,
            "mode": normalized,
            "error": detail,
            "https_url": "",
        }

    status_payload = _parse_tailscale_status(status_stdout)
    backend_state = str(status_payload.get("BackendState", "") or "").strip().lower()
    if backend_state and backend_state != "running":
        return {
            "enabled": True,
            "ok": False,
            "mode": normalized,
            "error": f"tailscale backend is '{backend_state}', expected 'running'",
            "https_url": "",
        }

    action_args = [normalized, "--bg", "--yes", str(port)]
    action_code, action_stdout, action_stderr = execute(action_args, 15)
    if action_code != 0:
        detail = action_stderr or action_stdout or f"tailscale {normalized} failed"
        return {
            "enabled": True,
            "ok": False,
            "mode": normalized,
            "error": detail,
            "https_url": "",
        }

    host = _extract_tailnet_host(status_payload)
    https_url = f"https://{host}/" if host else ""
    return {
        "enabled": True,
        "ok": True,
        "mode": normalized,
        "error": "",
        "https_url": https_url,
    }


def _resolve_api_key_with_refresh(config, model: str) -> str | None:
    """Resolve API/OAuth token with async refresh when no loop is running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        try:
            return asyncio.run(config.get_api_key_async(model))
        except Exception:
            return config.get_api_key(model)
    return config.get_api_key(model)


def _make_provider(config):
    """Create LLMProvider from config. Exits if no API key found."""
    from kabot.providers.litellm_provider import LiteLLMProvider

    model, model_fallbacks = _resolve_model_runtime(config)
    p = config.get_provider(model)
    provider_name = config.get_provider_name(model)
    provider_fallbacks = list(p.fallbacks) if p else []
    runtime_fallbacks = _resolve_runtime_fallbacks(
        config=config,
        primary=model,
        model_fallbacks=model_fallbacks,
        provider_fallbacks=provider_fallbacks,
    )
    runtime_models = [model, *runtime_fallbacks]

    provider_api_keys: dict[str, str] = {}
    provider_api_bases: dict[str, str] = {}
    provider_extra_headers: dict[str, dict[str, str]] = {}
    for runtime_model in runtime_models:
        provider_name_for_model = config.get_provider_name(runtime_model)
        if not provider_name_for_model:
            continue

        runtime_key = _resolve_api_key_with_refresh(config, runtime_model)
        if runtime_key:
            provider_api_keys[provider_name_for_model] = runtime_key

        runtime_api_base = config.get_api_base(runtime_model)
        if runtime_api_base:
            provider_api_bases[provider_name_for_model] = runtime_api_base

        runtime_provider_cfg = config.get_provider(runtime_model)
        runtime_headers = getattr(runtime_provider_cfg, "extra_headers", None)
        if runtime_headers:
            provider_extra_headers[provider_name_for_model] = dict(runtime_headers)

    # Special handling for Letta provider
    if provider_name == "letta":
        from kabot.providers.letta_provider import LettaProvider
        return LettaProvider(
            api_key=p.api_key if p else None,
            api_base=config.get_api_base(model),
            workspace_path=config.agents.defaults.workspace,
            default_model=model,
        )

    # Check for credentials (API key or OAuth token)
    api_key = provider_api_keys.get(provider_name or "") or _resolve_api_key_with_refresh(config, model)
    if not api_key and not model.startswith("bedrock/"):
        console.print("[red]Error: No API key or OAuth token configured.[/red]")
        console.print("Set one in ~/.kabot/config.json under providers section")
        raise typer.Exit(1)

    return LiteLLMProvider(
        api_key=api_key,
        api_base=provider_api_bases.get(provider_name or "") or config.get_api_base(model),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=provider_name,
        fallbacks=runtime_fallbacks,
        provider_api_keys=provider_api_keys,
        provider_api_bases=provider_api_bases,
        provider_extra_headers=provider_extra_headers,
    )


def _inject_skill_env(config):
    """Inject skill environment variables from config into os.environ."""
    if not hasattr(config, "skills"):
        return

    from kabot.config.skills_settings import iter_skill_env_pairs

    count = 0
    for _, key, value in iter_skill_env_pairs(config.skills):
        if key and value and key not in os.environ:
            os.environ[key] = value
            count += 1
    if count > 0:
        console.print(f"[dim]Injected {count} skill environment variables[/dim]")


def _strip_reminder_context(message: str) -> str:
    """Compatibility wrapper for tests and existing imports."""
    return _strip_reminder_context_impl(message)


def _should_use_reminder_fallback(response: str | None) -> bool:
    """Compatibility wrapper for tests and existing imports."""
    return _should_use_reminder_fallback_impl(response)


def _resolve_cron_delivery_content(job_message: str, assistant_response: str | None) -> str:
    """Compatibility wrapper for tests and existing imports."""
    return _resolve_cron_delivery_content_impl(job_message, assistant_response)


async def _render_cron_delivery_with_ai(provider, model: str, job_message: str) -> str | None:
    """Compatibility wrapper for tests and existing imports."""
    return await _render_cron_delivery_with_ai_impl(provider, model, job_message)


def _cli_exec_approval_prompt(command: str, config_path: Path) -> str:
    """Interactive approval prompt for exec ASK-mode in CLI sessions."""
    from rich.prompt import Prompt

    console.print("\n[bold yellow]Security approval required[/bold yellow]")
    console.print(f"Command: [cyan]{command}[/cyan]")
    console.print(f"[dim]Policy file: {config_path}[/dim]")
    choice = Prompt.ask(
        "Allow this command?",
        choices=["once", "always", "deny"],
        default="deny",
    )
    if choice == "once":
        return "allow_once"
    if choice == "always":
        return "allow_always"
    return "deny"


def _wire_cli_exec_approval(agent_loop) -> None:
    """Attach CLI approval prompt callback to ExecTool when available."""
    exec_tool = agent_loop.tools.get("exec")
    if exec_tool and hasattr(exec_tool, "set_approval_callback"):
        exec_tool.set_approval_callback(_cli_exec_approval_prompt)


def _next_cli_reminder_delay_seconds(
    cron_service,
    channel: str = "cli",
    chat_id: str = "direct",
    max_wait_seconds: float | None = 300.0,
    job_ids: set[str] | None = None,
) -> float | None:
    """Return earliest pending CLI reminder delay (seconds), or None."""
    import time

    now_ms = int(time.time() * 1000)
    delays: list[float] = []
    for job in cron_service.list_jobs(include_disabled=False):
        if not job.payload.deliver:
            continue
        if job.payload.channel != channel or job.payload.to != chat_id:
            continue
        if job_ids is not None and job.id not in job_ids:
            continue
        if not job.state.next_run_at_ms:
            continue

        delay_s = max(0.0, (job.state.next_run_at_ms - now_ms) / 1000.0)
        delays.append(delay_s)

    if not delays:
        return None

    next_delay = min(delays)
    if max_wait_seconds is not None and next_delay > max_wait_seconds:
        return None
    return next_delay


def _collect_cli_delivery_job_ids(
    cron_service,
    channel: str = "cli",
    chat_id: str = "direct",
) -> set[str]:
    """Collect current deliverable cron jobs for a specific CLI destination."""
    ids: set[str] = set()
    for job in cron_service.list_jobs(include_disabled=False):
        if not job.payload.deliver:
            continue
        if job.payload.channel != channel or job.payload.to != chat_id:
            continue
        if not job.state.next_run_at_ms:
            continue
        ids.add(job.id)
    return ids


def _build_dashboard_config_summary(config: Any) -> dict[str, Any]:
    """Build a safe config snapshot for dashboard display (without secrets)."""
    gateway = getattr(config, "gateway", None)
    runtime = getattr(config, "runtime", None)
    tools = getattr(config, "tools", None)
    providers_cfg = getattr(config, "providers", None)

    default_model = ""
    default_fallbacks: list[str] = []
    try:
        default_model, default_fallbacks = _resolve_model_runtime(config)
    except Exception:
        default_model = ""
        default_fallbacks = []

    provider_available: list[str] = []
    provider_configured: list[str] = []
    try:
        from kabot.providers.registry import PROVIDERS

        provider_available = sorted({str(spec.name).strip() for spec in PROVIDERS if str(spec.name).strip()})
    except Exception:
        provider_available = []

    for provider_name in provider_available:
        provider_cfg = getattr(providers_cfg, provider_name, None) if providers_cfg is not None else None
        if provider_cfg is None:
            continue
        has_primary = bool(str(getattr(provider_cfg, "api_key", "") or "").strip())
        has_setup_token = bool(str(getattr(provider_cfg, "setup_token", "") or "").strip())
        has_profile_key = False
        profiles = getattr(provider_cfg, "profiles", {})
        if isinstance(profiles, dict):
            for profile in profiles.values():
                if bool(str(getattr(profile, "api_key", "") or "").strip()):
                    has_profile_key = True
                    break
        if has_primary or has_setup_token or has_profile_key:
            provider_configured.append(provider_name)

    gateway_summary = {
        "host": str(getattr(gateway, "host", "") or ""),
        "port": int(getattr(gateway, "port", 0) or 0),
        "bind_mode": str(getattr(gateway, "bind_mode", "") or ""),
        "tailscale": bool(getattr(gateway, "tailscale", False)),
        "auth_token_configured": bool(str(getattr(gateway, "auth_token", "") or "").strip()),
    }

    runtime_perf = getattr(runtime, "performance", None)
    runtime_summary = {
        "model": {
            "primary": str(default_model or ""),
            "fallbacks": [str(item).strip() for item in default_fallbacks if str(item).strip()],
        },
        "performance": {
            "token_mode": str(getattr(runtime_perf, "token_mode", "boros") or "boros").strip().lower(),
            "fast_first_response": bool(getattr(runtime_perf, "fast_first_response", True)),
            "defer_memory_warmup": bool(getattr(runtime_perf, "defer_memory_warmup", True)),
        }
    }

    web_tools = getattr(tools, "web", None)
    web_search = getattr(web_tools, "search", None)
    tools_summary = {
        "web": {
            "search_provider": str(getattr(web_search, "provider", "") or ""),
            "max_results": int(getattr(web_search, "max_results", 0) or 0),
            "api_key_configured": bool(str(getattr(web_search, "api_key", "") or "").strip()),
        }
    }

    providers_summary = {
        "available": provider_available,
        "configured": sorted(set(provider_configured)),
        "models_by_provider": _list_provider_models_for_dashboard(),
    }

    return {
        "gateway": gateway_summary,
        "runtime": runtime_summary,
        "tools": tools_summary,
        "providers": providers_summary,
    }


_DASHBOARD_PROVIDER_MODELS_CACHE_TS = 0.0
_DASHBOARD_PROVIDER_MODELS_CACHE: dict[str, list[str]] = {}


def _list_provider_models_for_dashboard(
    *,
    ttl_seconds: int = 300,
    per_provider_limit: int = 200,
) -> dict[str, list[str]]:
    """Return lightweight provider->model mapping for dashboard model suggestions."""
    global _DASHBOARD_PROVIDER_MODELS_CACHE_TS, _DASHBOARD_PROVIDER_MODELS_CACHE

    now = time.time()
    if (
        _DASHBOARD_PROVIDER_MODELS_CACHE
        and (now - _DASHBOARD_PROVIDER_MODELS_CACHE_TS) < max(10, int(ttl_seconds))
    ):
        return {
            provider: list(models)
            for provider, models in _DASHBOARD_PROVIDER_MODELS_CACHE.items()
        }

    mapping: dict[str, list[str]] = {}
    try:
        from kabot.providers.registry import ModelRegistry

        registry = ModelRegistry()
        for meta in registry.list_models():
            provider = str(getattr(meta, "provider", "") or "").strip().lower()
            model_id = str(getattr(meta, "id", "") or "").strip()
            if not provider or not model_id:
                continue
            bucket = mapping.setdefault(provider, [])
            if model_id in bucket:
                continue
            bucket.append(model_id)
    except Exception:
        mapping = {}

    limit = max(20, int(per_provider_limit))
    for provider_name, models in list(mapping.items()):
        models.sort()
        mapping[provider_name] = models[:limit]

    _DASHBOARD_PROVIDER_MODELS_CACHE_TS = now
    _DASHBOARD_PROVIDER_MODELS_CACHE = {
        provider: list(models)
        for provider, models in mapping.items()
    }
    return {
        provider: list(models)
        for provider, models in _DASHBOARD_PROVIDER_MODELS_CACHE.items()
    }


def _compose_model_override(model: str, provider: str) -> str:
    model_text = str(model or "").strip()
    provider_text = str(provider or "").strip().lower()
    if not model_text:
        return ""
    if "/" in model_text or not provider_text:
        return model_text
    return f"{provider_text}/{model_text}"


def _parse_model_fallbacks(raw: Any, provider: str = "") -> list[str]:
    values: list[str] = []
    if isinstance(raw, list):
        values = [str(item).strip() for item in raw if str(item).strip()]
    elif isinstance(raw, str):
        # Support comma/newline separated values for form and API payloads.
        values = [
            token.strip()
            for token in raw.replace("\n", ",").split(",")
            if token and token.strip()
        ]
    elif raw is not None:
        text = str(raw).strip()
        if text:
            values = [text]

    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        composed = _compose_model_override(item, provider=provider)
        if not composed or composed in seen:
            continue
        seen.add(composed)
        normalized.append(composed)
        if len(normalized) >= 8:
            break
    return normalized


def _build_dashboard_nodes(channels: Any) -> list[dict[str, Any]]:
    """Build lightweight runtime node list for dashboard node panel."""
    nodes = [
        {"id": "gateway", "kind": "runtime", "state": "running"},
        {"id": "agent:main", "kind": "agent", "state": "running"},
    ]
    try:
        channel_status = channels.get_status() if channels is not None else {}
    except Exception:
        channel_status = {}

    if isinstance(channel_status, dict):
        for name, payload in channel_status.items():
            running = False
            if isinstance(payload, dict):
                running = bool(payload.get("running", False))
            nodes.append(
                {
                    "id": f"channel:{name}",
                    "kind": "channel",
                    "state": "running" if running else "stopped",
                }
            )
    return nodes


def _build_dashboard_cost_payload(session_manager: Any) -> dict[str, Any]:
    try:
        from kabot.core.cost_tracker import CostTracker

        tracker = CostTracker(session_manager.sessions_dir)
        summary = tracker.get_summary()
    except Exception as exc:
        logger.warning(f"CostTracker failed: {exc}")
        summary = {}

    token_usage = summary.get("token_usage", {})
    if not isinstance(token_usage, dict):
        token_usage = {}

    model_usage = summary.get("model_usage", {})
    if not isinstance(model_usage, dict):
        model_usage = {}

    model_costs = summary.get("model_costs", {})
    if not isinstance(model_costs, dict):
        model_costs = {}

    cost_history = summary.get("cost_history", [])
    if not isinstance(cost_history, list):
        cost_history = []

    return {
        "costs": {
            "today": float(summary.get("today", 0) or 0),
            "total": float(summary.get("total", 0) or 0),
            "projected_monthly": float(summary.get("projected_monthly", 0) or 0),
            "by_model": {
                str(model): float(cost or 0)
                for model, cost in model_costs.items()
            },
        },
        "token_usage": {
            "input": int(token_usage.get("input", 0) or 0),
            "output": int(token_usage.get("output", 0) or 0),
            "total": int(token_usage.get("total", 0) or 0),
        },
        "model_usage": {
            str(model): int(tokens or 0)
            for model, tokens in model_usage.items()
        },
        "cost_history": [
            {
                "date": str(item.get("date") or ""),
                "cost": float(item.get("cost", 0) or 0),
                "tokens": int(item.get("tokens", 0) or 0),
            }
            for item in cost_history
            if isinstance(item, dict)
        ],
    }


def _format_dashboard_timestamp_ms(timestamp_ms: Any) -> str:
    try:
        ts_int = int(timestamp_ms or 0)
    except Exception:
        return "-"
    if ts_int <= 0:
        return "-"
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts_int / 1000))
    except Exception:
        return "-"


def _describe_dashboard_schedule(schedule: Any) -> str:
    kind = str(getattr(schedule, "kind", "") or "").strip().lower()
    if kind == "every":
        every_ms = int(getattr(schedule, "every_ms", 0) or 0)
        seconds = max(0, every_ms // 1000)
        if seconds >= 3600 and seconds % 3600 == 0:
            return f"every {seconds // 3600}h"
        if seconds >= 60 and seconds % 60 == 0:
            return f"every {seconds // 60}m"
        return f"every {seconds}s"
    if kind == "at":
        return _format_dashboard_timestamp_ms(getattr(schedule, "at_ms", 0))
    if kind == "cron":
        return str(getattr(schedule, "expr", "") or "-")
    return kind or "-"


def _build_dashboard_channel_rows(channel_status: Any, enabled_channels: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(channel_status, dict):
        for name, payload in channel_status.items():
            data = payload if isinstance(payload, dict) else {}
            if bool(data.get("connected")):
                state = "connected"
            elif bool(data.get("running")):
                state = "running"
            else:
                state = "stopped"
            rows.append(
                {
                    "name": str(name),
                    "type": str(data.get("type") or name),
                    "state": state,
                }
            )
    elif enabled_channels:
        for name in enabled_channels:
            rows.append({"name": str(name), "type": str(name), "state": "enabled"})
    return rows


def _build_dashboard_cron_snapshot(cron: Any, *, limit: int = 30) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        cron_status = cron.status() if hasattr(cron, "status") else {}
    except Exception:
        cron_status = {}
    if not isinstance(cron_status, dict):
        cron_status = {}

    try:
        jobs = list(cron.list_jobs(include_disabled=True)) if hasattr(cron, "list_jobs") else []
    except Exception:
        jobs = []

    rows: list[dict[str, Any]] = []
    for job in jobs[: max(1, int(limit))]:
        state = getattr(job, "state", None)
        run_history = list(getattr(state, "run_history", []) or [])
        latest_run = run_history[-1] if run_history else {}
        rows.append(
            {
                "id": str(getattr(job, "id", "") or ""),
                "name": str(getattr(job, "name", "") or ""),
                "schedule": _describe_dashboard_schedule(getattr(job, "schedule", None)),
                "state": "enabled" if bool(getattr(job, "enabled", False)) else "disabled",
                "last_run": _format_dashboard_timestamp_ms(getattr(state, "last_run_at_ms", 0)),
                "next_run": _format_dashboard_timestamp_ms(getattr(state, "next_run_at_ms", 0)),
                "last_status": str(getattr(state, "last_status", "") or ""),
                "last_error": str(getattr(state, "last_error", "") or ""),
                "duration_ms": int(latest_run.get("duration_ms", 0) or 0) if isinstance(latest_run, dict) else 0,
                "channel": str(getattr(getattr(job, "payload", None), "channel", "") or ""),
                "to": str(getattr(getattr(job, "payload", None), "to", "") or ""),
            }
        )
    return cron_status, rows


def _build_dashboard_skills_snapshot(config: Any) -> list[dict[str, Any]]:
    try:
        from kabot.agent.skills import SkillsLoader

        loader = SkillsLoader(
            workspace=config.workspace_path,
            skills_config=getattr(config, "skills", {}),
        )
        raw_skills = loader.list_skills(filter_unavailable=False)
    except Exception as exc:
        logger.warning(f"Skills snapshot failed: {exc}")
        raw_skills = []

    skills: list[dict[str, Any]] = []
    for item in raw_skills[:30]:
        if not isinstance(item, dict):
            continue
        missing = item.get("missing", {})
        if not isinstance(missing, dict):
            missing = {}
        disabled = bool(item.get("disabled", False))
        eligible = bool(item.get("eligible", False))
        if disabled:
            state = "disabled"
        elif eligible:
            state = "enabled"
        elif missing.get("env"):
            state = "missing_env"
        elif missing.get("bins"):
            state = "missing_bin"
        elif missing.get("os"):
            state = "unsupported_os"
        else:
            state = "available"
        skills.append(
            {
                "name": str(item.get("name") or ""),
                "skill_key": str(item.get("skill_key") or item.get("name") or ""),
                "state": state,
                "disabled": disabled,
                "eligible": eligible,
                "description": str(item.get("description") or ""),
                "primary_env": str(item.get("primaryEnv") or ""),
                "missing_env": [str(val) for val in missing.get("env", []) if str(val).strip()],
                "missing_bins": [str(val) for val in missing.get("bins", []) if str(val).strip()],
                "missing_os": [str(val) for val in missing.get("os", []) if str(val).strip()],
            }
        )
    return skills


def _build_dashboard_subagent_activity(agent: Any, *, limit: int = 10) -> list[dict[str, Any]]:
    registry = getattr(getattr(agent, "subagents", None), "registry", None)
    if registry is None or not hasattr(registry, "list_all"):
        return []
    try:
        runs = list(registry.list_all())
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for record in sorted(runs, key=lambda item: float(getattr(item, "created_at", 0) or 0), reverse=True)[:limit]:
        created_at = float(getattr(record, "created_at", 0) or 0)
        completed_at = float(getattr(record, "completed_at", 0) or 0)
        duration_ms = int(max(0.0, completed_at - created_at) * 1000) if completed_at and created_at else 0
        rows.append(
            {
                "run_id": str(getattr(record, "run_id", "") or ""),
                "label": str(getattr(record, "label", "") or ""),
                "task": str(getattr(record, "task", "") or ""),
                "status": str(getattr(record, "status", "") or ""),
                "created_at": created_at,
                "completed_at": completed_at or None,
                "duration_ms": duration_ms,
                "result": str(getattr(record, "result", "") or ""),
                "error": str(getattr(record, "error", "") or ""),
                "parent_session_key": str(getattr(record, "parent_session_key", "") or ""),
            }
        )
    return rows


def _build_dashboard_git_log(workspace: Path, *, limit: int = 8) -> list[dict[str, str]]:
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                f"-n{max(1, int(limit))}",
                "--pretty=format:%h|%s|%cI|%an",
            ],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return []

    if result.returncode != 0:
        return []

    rows: list[dict[str, str]] = []
    for line in str(result.stdout or "").splitlines():
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        sha, subject, timestamp, author = parts
        rows.append(
            {
                "sha": sha.strip(),
                "subject": subject.strip(),
                "timestamp": timestamp.strip(),
                "author": author.strip(),
            }
        )
    return rows


def _build_dashboard_status_payload(
    *,
    gateway_started_at: float,
    runtime_model: str,
    runtime_host: str,
    runtime_port: int,
    tailscale_mode: str,
    session_manager: Any,
    channels: Any,
    cron: Any,
    config: Any,
    agent: Any,
) -> dict[str, Any]:
    try:
        sessions = list(session_manager.list_sessions())[:20]
    except Exception:
        sessions = []
    try:
        channel_status = channels.get_status()
    except Exception:
        channel_status = {}

    cron_status, cron_jobs_list = _build_dashboard_cron_snapshot(cron)
    channels_enabled = list(getattr(channels, "enabled_channels", []))
    cost_payload = _build_dashboard_cost_payload(session_manager)
    skills = _build_dashboard_skills_snapshot(config)
    subagent_activity = _build_dashboard_subagent_activity(agent)
    git_log = _build_dashboard_git_log(config.workspace_path)

    return {
        "status": "running",
        "uptime_seconds": max(0, int(time.time() - gateway_started_at)),
        "model": runtime_model,
        "version": __version__,
        "channels_enabled": channels_enabled,
        "channels_status": channel_status if isinstance(channel_status, dict) else {},
        "channels": _build_dashboard_channel_rows(channel_status, channels_enabled),
        "cron_jobs": int(cron_status.get("jobs", 0) or 0),
        "cron_jobs_list": cron_jobs_list,
        "host": runtime_host,
        "port": runtime_port,
        "tailscale_mode": tailscale_mode,
        "sessions": sessions,
        "nodes": _build_dashboard_nodes(channels),
        "config": _build_dashboard_config_summary(config),
        "system": {
            "pid": os.getpid(),
            "memory_mb": 0,
        },
        "skills": skills,
        "subagent_activity": subagent_activity,
        "git_log": git_log,
        **cost_payload,
    }


async def _gateway_dashboard_control_action(
    *,
    action: str,
    args: dict[str, Any],
    config: Any,
    save_config_fn: Callable[[Any], None],
    agent: Any,
    session_manager: Any,
    channels: Any,
    cron: Any | None = None,
) -> dict[str, Any]:
    """Runtime control actions used by dashboard surface."""
    normalized = str(action or "").strip().lower()
    payload = args if isinstance(args, dict) else {}

    if normalized == "runtime.ping":
        return {"ok": True, "pong": True, "timestamp": int(time.time())}

    if normalized == "sessions.list":
        sessions = []
        try:
            sessions = list(session_manager.list_sessions())
        except Exception:
            sessions = []
        return {"ok": True, "sessions": sessions[:50]}

    if normalized == "sessions.clear":
        session_key = str(payload.get("session_key") or "").strip()
        if not session_key:
            return {
                "ok": False,
                "status_code": 400,
                "error": "missing_session_key",
                "message": "Missing session_key",
            }
        try:
            session = session_manager.get_or_create(session_key)
            session.clear()
            session_manager.save(session)
            return {
                "ok": True,
                "session_key": session_key,
                "message": f"Cleared session {session_key}",
            }
        except Exception as exc:
            return {
                "ok": False,
                "status_code": 500,
                "error": "session_clear_failed",
                "message": str(exc),
            }

    if normalized == "sessions.delete":
        session_key = str(payload.get("session_key") or "").strip()
        if not session_key:
            return {
                "ok": False,
                "status_code": 400,
                "error": "missing_session_key",
                "message": "Missing session_key",
            }
        try:
            deleted = bool(session_manager.delete(session_key))
        except Exception as exc:
            return {
                "ok": False,
                "status_code": 500,
                "error": "session_delete_failed",
                "message": str(exc),
            }
        if not deleted:
            return {
                "ok": False,
                "status_code": 404,
                "error": "session_not_found",
                "message": f"Session not found: {session_key}",
            }
        return {
            "ok": True,
            "session_key": session_key,
            "message": f"Deleted session {session_key}",
        }

    if normalized == "channels.status":
        try:
            status = channels.get_status()
        except Exception:
            status = {}
        return {"ok": True, "channels": status if isinstance(status, dict) else {}}

    if normalized in {"cron.enable", "cron.disable"}:
        job_id = str(payload.get("job_id") or "").strip()
        if not job_id:
            return {
                "ok": False,
                "status_code": 400,
                "error": "missing_job_id",
                "message": "Missing job_id",
            }
        enable_job = getattr(cron, "enable_job", None)
        if not callable(enable_job):
            return {
                "ok": False,
                "status_code": 501,
                "error": "cron_unavailable",
                "message": "Cron service is unavailable",
            }
        enabled = normalized == "cron.enable"
        try:
            job = enable_job(job_id, enabled=enabled)
        except Exception as exc:
            return {
                "ok": False,
                "status_code": 500,
                "error": "cron_update_failed",
                "message": str(exc),
            }
        if job is None:
            return {
                "ok": False,
                "status_code": 404,
                "error": "cron_job_not_found",
                "message": f"Cron job not found: {job_id}",
            }
        return {
            "ok": True,
            "job_id": job_id,
            "enabled": enabled,
            "message": f"Cron job {'enabled' if enabled else 'disabled'}: {job_id}",
        }

    if normalized == "cron.run":
        job_id = str(payload.get("job_id") or "").strip()
        if not job_id:
            return {
                "ok": False,
                "status_code": 400,
                "error": "missing_job_id",
                "message": "Missing job_id",
            }
        run_job = getattr(cron, "run_job", None)
        if not callable(run_job):
            return {
                "ok": False,
                "status_code": 501,
                "error": "cron_unavailable",
                "message": "Cron service is unavailable",
            }
        try:
            result = run_job(job_id, force=True)
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            return {
                "ok": False,
                "status_code": 500,
                "error": "cron_run_failed",
                "message": str(exc),
            }
        if not result:
            return {
                "ok": False,
                "status_code": 404,
                "error": "cron_job_not_found",
                "message": f"Cron job not found: {job_id}",
            }
        return {
            "ok": True,
            "job_id": job_id,
            "message": f"Cron job executed: {job_id}",
        }

    if normalized == "cron.delete":
        job_id = str(payload.get("job_id") or "").strip()
        if not job_id:
            return {
                "ok": False,
                "status_code": 400,
                "error": "missing_job_id",
                "message": "Missing job_id",
            }
        remove_job = getattr(cron, "remove_job", None)
        if not callable(remove_job):
            return {
                "ok": False,
                "status_code": 501,
                "error": "cron_unavailable",
                "message": "Cron service is unavailable",
            }
        try:
            removed = bool(remove_job(job_id))
        except Exception as exc:
            return {
                "ok": False,
                "status_code": 500,
                "error": "cron_delete_failed",
                "message": str(exc),
            }
        if not removed:
            return {
                "ok": False,
                "status_code": 404,
                "error": "cron_job_not_found",
                "message": f"Cron job not found: {job_id}",
            }
        return {
            "ok": True,
            "job_id": job_id,
            "message": f"Cron job deleted: {job_id}",
        }

    if normalized in {"nodes.start", "nodes.stop", "nodes.restart"}:
        node_id = str(payload.get("node_id") or "").strip()
        if not node_id:
            return {
                "ok": False,
                "status_code": 400,
                "error": "missing_node_id",
                "message": "Missing node_id",
            }
        if not node_id.startswith("channel:"):
            return {
                "ok": False,
                "status_code": 400,
                "error": "unsupported_node_kind",
                "message": "Only channel nodes are controllable",
            }
        channel_name = node_id.split(":", 1)[1].strip()
        if not channel_name:
            return {
                "ok": False,
                "status_code": 400,
                "error": "invalid_node_id",
                "message": "Invalid node_id",
            }
        get_channel = getattr(channels, "get_channel", None)
        channel = get_channel(channel_name) if callable(get_channel) else None
        if channel is None:
            return {
                "ok": False,
                "status_code": 404,
                "error": "node_not_found",
                "message": f"Node not found: {node_id}",
            }
        try:
            if normalized in {"nodes.stop", "nodes.restart"}:
                stop_result = channel.stop()
                if inspect.isawaitable(stop_result):
                    await stop_result
            if normalized in {"nodes.start", "nodes.restart"}:
                start_result = channel.start()
                if inspect.isawaitable(start_result):
                    await start_result
        except Exception as exc:
            return {
                "ok": False,
                "status_code": 500,
                "error": "node_action_failed",
                "message": str(exc),
            }
        state = "running" if normalized in {"nodes.start", "nodes.restart"} else "stopped"
        return {
            "ok": True,
            "node_id": node_id,
            "state": state,
            "message": f"{normalized} executed for {node_id}",
        }

    if normalized == "config.set_token_mode":
        mode = str(payload.get("token_mode") or "").strip().lower()
        if mode not in {"boros", "hemat"}:
            return {"ok": False, "status_code": 400, "error": "invalid_token_mode", "message": "token_mode must be boros or hemat"}
        config.runtime.performance.token_mode = mode
        save_config_fn(config)
        return {"ok": True, "token_mode": mode, "message": f"Token mode set to {mode}"}

    if normalized in {"skills.enable", "skills.disable"}:
        from kabot.config.skills_settings import set_skill_entry_enabled

        skill_key = str(payload.get("skill_key") or "").strip()
        if not skill_key:
            return {
                "ok": False,
                "status_code": 400,
                "error": "missing_skill_key",
                "message": "Missing skill_key",
            }
        enabled = normalized == "skills.enable"
        config.skills = set_skill_entry_enabled(
            config.skills,
            skill_key,
            enabled,
            persist_true=True,
        )
        save_config_fn(config)
        return {
            "ok": True,
            "skill_key": skill_key,
            "enabled": enabled,
            "message": f"Skill {'enabled' if enabled else 'disabled'}: {skill_key}",
        }

    if normalized == "skills.set_api_key":
        from kabot.config.schema import SkillsConfig
        from kabot.config.skills_settings import normalize_skills_settings

        skill_key = str(payload.get("skill_key") or "").strip()
        api_key = str(payload.get("api_key") or "").strip()
        if not skill_key:
            return {
                "ok": False,
                "status_code": 400,
                "error": "missing_skill_key",
                "message": "Missing skill_key",
            }
        if not api_key:
            return {
                "ok": False,
                "status_code": 400,
                "error": "missing_api_key",
                "message": "Missing api_key",
            }
        normalized_skills = normalize_skills_settings(config.skills)
        entries = normalized_skills.setdefault("entries", {})
        entry = entries.get(skill_key)
        if not isinstance(entry, dict):
            entry = {}
            entries[skill_key] = entry
        entry["api_key"] = api_key
        config.skills = SkillsConfig.from_raw(normalized_skills)
        save_config_fn(config)
        return {
            "ok": True,
            "skill_key": skill_key,
            "message": f"API key updated for skill: {skill_key}",
        }

    if normalized == "chat.send":
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            return {"ok": False, "status_code": 400, "error": "missing_prompt", "message": "Missing chat prompt"}
        session_key = str(payload.get("session_key") or "dashboard:web").strip() or "dashboard:web"
        channel = str(payload.get("channel") or "dashboard").strip() or "dashboard"
        chat_id = str(payload.get("chat_id") or "dashboard").strip() or "dashboard"
        provider = str(payload.get("provider") or "").strip().lower()
        model_input = str(payload.get("model") or "").strip()
        model_override = _compose_model_override(model_input, provider=provider)
        fallback_overrides = _parse_model_fallbacks(payload.get("fallbacks"), provider=provider)
        process_direct = getattr(agent, "process_direct", None)
        if not callable(process_direct):
            return {"ok": False, "status_code": 501, "error": "chat_unavailable", "message": "Runtime chat handler unavailable"}
        try:
            result = process_direct(
                prompt,
                session_key=session_key,
                channel=channel,
                chat_id=chat_id,
                model_override=model_override or None,
                fallback_overrides=fallback_overrides or None,
            )
        except TypeError:
            # Backward compatibility for custom runtimes with older signature.
            result = process_direct(prompt, session_key=session_key, channel=channel, chat_id=chat_id)
        if inspect.isawaitable(result):
            result = await result
        return {"ok": True, "content": str(result or "")}

    return {"ok": False, "status_code": 400, "error": "unsupported_action", "message": f"Unsupported action: {normalized}"}


def _gateway_dashboard_chat_history_provider(
    *,
    session_manager: Any,
    session_key: str,
    limit: int = 30,
    config: Any | None = None,
) -> list[dict[str, Any]]:
    """Read recent session messages for dashboard chat log/history views."""
    _ = config  # Reserved for future filtering; kept for stable helper signature.

    try:
        limit_int = int(limit)
    except Exception:
        limit_int = 30
    if limit_int < 1:
        limit_int = 1
    if limit_int > 200:
        limit_int = 200

    key = str(session_key or "").strip() or "dashboard:web"
    try:
        session = session_manager.get_or_create(key)
    except Exception:
        return []

    raw_messages = getattr(session, "messages", [])
    if not isinstance(raw_messages, list):
        return []

    items: list[dict[str, Any]] = []
    for item in raw_messages[-limit_int:]:
        if not isinstance(item, dict):
            continue
        payload_item = {
            "role": str(item.get("role") or "").strip().lower() or "assistant",
            "content": str(item.get("content") or ""),
            "timestamp": str(item.get("timestamp") or ""),
        }
        metadata = item.get("metadata")
        if isinstance(metadata, dict) and metadata:
            payload_item["metadata"] = metadata
        items.append(payload_item)
    return items


# ============================================================================
# Gateway / Server
# ============================================================================


@app.command()
def gateway(
    port: int | None = typer.Option(None, "--port", "-p", help="Gateway port (default: config.gateway.port)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Start the kabot gateway."""
    from kabot.config.loader import get_data_dir, load_config, save_config

    boot_started = time.perf_counter()
    console.print(f"{__logo__} Booting kabot gateway...")

    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    config = load_config()
    runtime_port = _resolve_gateway_runtime_port(config, port)
    runtime_host = config.gateway.host
    tailscale_mode = _resolve_tailscale_mode(config)

    console.print(f"{__logo__} Starting kabot gateway on port {runtime_port}...")

    if tailscale_mode in {"serve", "funnel"}:
        runtime_host = "127.0.0.1"
        tailscale_status = _configure_tailscale_runtime(tailscale_mode, runtime_port)
        if tailscale_status.get("ok"):
            https_url = str(tailscale_status.get("https_url") or "").strip()
            if https_url:
                console.print(
                    f"[green]*[/green] Tailscale {tailscale_mode} active: {https_url}"
                )
            else:
                console.print(
                    f"[green]*[/green] Tailscale {tailscale_mode} active"
                )
        else:
            reason = str(tailscale_status.get("error") or "unknown tailscale error")
            console.print(
                f"[yellow]Warning:[/yellow] Tailscale {tailscale_mode} setup failed: {reason}"
            )
            # bind_mode=tailscale implies tailscale is required for expected access path.
            if str(getattr(config.gateway, "bind_mode", "")).strip().lower() == "tailscale":
                raise typer.Exit(1)

    _preflight_gateway_port(runtime_host, runtime_port)

    import_started = time.perf_counter()
    from kabot.agent.loop import AgentLoop
    from kabot.bus.queue import MessageBus
    from kabot.channels.manager import ChannelManager
    from kabot.cron.service import CronService
    from kabot.heartbeat.service import HeartbeatService
    from kabot.session.manager import SessionManager
    imports_ms = int((time.perf_counter() - import_started) * 1000)
    console.print(f"[dim]* Runtime modules loaded in {imports_ms}ms[/dim]")
    bootstrap_ms = int((time.perf_counter() - boot_started) * 1000)
    console.print(f"[dim]* Bootstrap ready in {bootstrap_ms}ms[/dim]")

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

    runtime_model, model_fallbacks = _resolve_model_runtime(config)
    p = config.get_provider(runtime_model)
    runtime_fallbacks = _resolve_runtime_fallbacks(
        config=config,
        primary=runtime_model,
        model_fallbacks=model_fallbacks,
        provider_fallbacks=list(p.fallbacks) if p else [],
    )

    # Create agent with cron service
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=runtime_model,
        fallbacks=runtime_fallbacks,
        max_iterations=config.agents.defaults.max_tool_iterations,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        session_manager=session_manager,
        enable_hybrid_memory=config.agents.enable_hybrid_memory,
    )

    # Set cron callback (needs agent)
    async def _emit_cron_event(job, result):
        await agent.heartbeat.inject_cron_result(
            job_name=job.name,
            result=result,
            channel=job.payload.channel or "cli",
            chat_id=job.payload.to or "direct",
        )

    cron.on_job = build_bus_cron_callback(
        provider=provider,
        model=runtime_model,
        publish_outbound=bus.publish_outbound,
        on_system_event=_emit_cron_event,
    )

    # Create heartbeat service
    async def on_heartbeat(prompt: str) -> str:
        """Execute heartbeat through the agent."""
        return await agent.process_direct(prompt, session_key="heartbeat")

    hb_defaults = config.agents.defaults.heartbeat
    runtime_autopilot = getattr(config.runtime, "autopilot", None)
    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        on_heartbeat=on_heartbeat,
        interval_s=max(60, int(getattr(hb_defaults, "interval_minutes", 30) or 30) * 60),
        startup_delay_s=max(0, int(getattr(hb_defaults, "startup_delay_seconds", 120) or 120)),
        enabled=bool(getattr(hb_defaults, "enabled", True)),
        active_hours_start=str(getattr(hb_defaults, "active_hours_start", "") or ""),
        active_hours_end=str(getattr(hb_defaults, "active_hours_end", "") or ""),
        max_tasks_per_beat=max(1, int(getattr(runtime_autopilot, "max_actions_per_beat", 1) or 1)),
        autopilot_enabled=bool(getattr(runtime_autopilot, "enabled", True)),
        autopilot_prompt=str(getattr(runtime_autopilot, "prompt", "") or ""),
    )

    # Create channel manager
    channels = ChannelManager(config, bus, session_manager=session_manager)
    # Expose channel capabilities to runtime (e.g., keepalive/status behavior).
    setattr(agent, "channel_manager", channels)

    gateway_started_at = time.time()

    def _gateway_status_provider() -> dict[str, Any]:
        return _build_dashboard_status_payload(
            gateway_started_at=gateway_started_at,
            runtime_model=runtime_model,
            runtime_host=runtime_host,
            runtime_port=runtime_port,
            tailscale_mode=tailscale_mode,
            session_manager=session_manager,
            channels=channels,
            cron=cron,
            config=config,
            agent=agent,
        )

    async def _gateway_control_handler(action: str, args: dict[str, Any]) -> dict[str, Any]:
        return await _gateway_dashboard_control_action(
            action=action,
            args=args,
            config=config,
            save_config_fn=lambda updated_cfg: save_config(updated_cfg),
            agent=agent,
            session_manager=session_manager,
            channels=channels,
            cron=cron,
        )

    def _gateway_chat_history_provider(session_key: str, limit: int = 30) -> list[dict[str, Any]]:
        return _gateway_dashboard_chat_history_provider(
            session_manager=session_manager,
            session_key=session_key,
            limit=limit,
            config=config,
        )

    gateway_security_headers = getattr(getattr(config.gateway, "http", None), "security_headers", None)

    def _build_webhook_server():
        # Lazy import keeps startup-critical module import path shorter.
        from kabot.gateway.webhook_server import WebhookServer

        return WebhookServer(
            bus,
            auth_token=config.gateway.auth_token or None,
            meta_verify_token=getattr(getattr(config.integrations, "meta", None), "verify_token", None),
            meta_app_secret=getattr(getattr(config.integrations, "meta", None), "app_secret", None),
            strict_transport_security=bool(
                getattr(gateway_security_headers, "strict_transport_security", False)
            ),
            strict_transport_security_value=str(
                getattr(
                    gateway_security_headers,
                    "strict_transport_security_value",
                    "max-age=31536000; includeSubDomains",
                )
            ),
            status_provider=_gateway_status_provider,
            chat_history_provider=_gateway_chat_history_provider,
            control_handler=_gateway_control_handler,
        )

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

    console.print("[green]*[/green] Heartbeat: every 30m")
    console.print(f"[green]*[/green] Webhooks: listening on port {runtime_port}")

    async def run():
        webhook_runner = None
        try:
            await cron.start()
            await heartbeat.start()

            tasks = [
                asyncio.create_task(agent.run()),
                asyncio.create_task(channels.start_all()),
                asyncio.create_task(bus.dispatch_system_events()),
            ]

            # Start webhook server (using same port as gateway for simplicity in this phase)
            # In a real production setup, we might want separate ports or a reverse proxy
            # But here we are integrating into the main event loop
            webhook_server = _build_webhook_server()
            webhook_runner = await webhook_server.start(
                host=runtime_host,
                port=runtime_port,
            )

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
                tasks.append(asyncio.create_task(_recover()))

            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            console.print("\nShutting down...")
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()
            if webhook_runner is not None:
                await webhook_runner.cleanup()

    try:
        asyncio.run(run())
    except OSError as exc:
        if _is_port_in_use_error(exc):
            console.print(
                f"[yellow]Gateway port {runtime_port} is already in use.[/yellow]"
            )
            console.print(
                "[yellow]Another Kabot instance may already be running. "
                "Stop existing process first or change `gateway.port` in config.[/yellow]"
            )
            raise typer.Exit(code=78)
        raise




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
    from loguru import logger

    from kabot.agent.loop import AgentLoop
    from kabot.bus.queue import MessageBus
    from kabot.config.loader import get_data_dir, load_config
    from kabot.cron.service import CronService

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

    runtime_model, model_fallbacks = _resolve_model_runtime(config)
    p = config.get_provider(runtime_model)
    runtime_fallbacks = _resolve_runtime_fallbacks(
        config=config,
        primary=runtime_model,
        model_fallbacks=model_fallbacks,
        provider_fallbacks=list(p.fallbacks) if p else [],
    )

    # Initialize CronService (required for reminder tools)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=runtime_model,
        fallbacks=runtime_fallbacks,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        enable_hybrid_memory=config.agents.enable_hybrid_memory,
        cron_service=cron,  # Pass cron service to enable tools
    )
    if sys.stdin.isatty():
        _wire_cli_exec_approval(agent_loop)

    # Setup cron callback for CLI
    async def _emit_cli_cron_event(job, result):
        await agent_loop.heartbeat.inject_cron_result(
            job_name=job.name,
            result=result,
            channel=job.payload.channel or "cli",
            chat_id=job.payload.to or "direct",
        )

    cron.on_job = build_cli_cron_callback(
        provider=provider,
        model=runtime_model,
        on_print=lambda content: _print_agent_response(
            f"[Reminder] {content}",
            render_markdown=markdown,
        ),
        on_system_event=_emit_cli_cron_event,
    )

    # Show spinner when logs are off (no output to miss); skip when logs are on
    def _thinking_ctx():
        if logs:
            from contextlib import nullcontext
            return nullcontext()
        return console.status("[dim]kabot is thinking...[/dim]", spinner="dots")

    def _one_shot_message_needs_cron(prompt: str) -> bool:
        required_tool_for_query = getattr(agent_loop, "_required_tool_for_query", None)
        if callable(required_tool_for_query):
            try:
                return required_tool_for_query(prompt) == "cron"
            except Exception:
                pass
        return _should_use_reminder_fallback_impl(prompt)

    if message:
        # Single message mode
        async def run_once():
            cron_started = False
            baseline_cli_jobs: set[str] = set()
            # One-shot chat does not need the scheduler unless the prompt itself is
            # about reminders. Avoid paying startup cost for ordinary live probes.
            if _one_shot_message_needs_cron(message):
                try:
                    await cron.start()
                    cron_started = True
                    baseline_cli_jobs = _collect_cli_delivery_job_ids(
                        cron,
                        channel="cli",
                        chat_id="direct",
                    )
                except Exception as exc:
                    logger.warning(f"Cron unavailable in one-shot mode: {exc}")
                    console.print(
                        "[yellow]Cron scheduler unavailable for this run. "
                        "Reminders may be delivered by another running kabot instance.[/yellow]"
                    )
            try:
                with _thinking_ctx():
                    response = await agent_loop.process_direct(
                        message,
                        session_id,
                        suppress_post_response_warmup=True,
                        probe_mode=True,
                    )
                _print_agent_response(response, render_markdown=markdown)

                # Keep process alive briefly when a CLI reminder is due soon,
                # so one-shot calls like "ingatkan 2 menit lagi" can fire.
                if cron_started:
                    current_cli_jobs = _collect_cli_delivery_job_ids(
                        cron,
                        channel="cli",
                        chat_id="direct",
                    )
                    new_cli_jobs = current_cli_jobs - baseline_cli_jobs
                    if not new_cli_jobs:
                        return

                    wait_budget_s = 5 * 60.0
                    elapsed_s = 0.0
                    while elapsed_s < wait_budget_s:
                        remaining_s = wait_budget_s - elapsed_s
                        next_delay = _next_cli_reminder_delay_seconds(
                            cron,
                            channel="cli",
                            chat_id="direct",
                            max_wait_seconds=remaining_s,
                            job_ids=new_cli_jobs,
                        )
                        if next_delay is None:
                            break

                        rounded = max(1, int(round(next_delay)))
                        console.print(f"[dim]Waiting for scheduled reminder ({rounded}s)...[/dim]")
                        sleep_for = next_delay + 0.35
                        await asyncio.sleep(sleep_for)
                        elapsed_s += sleep_for

                    if elapsed_s == 0.0:
                        far_delay = _next_cli_reminder_delay_seconds(
                            cron,
                            channel="cli",
                            chat_id="direct",
                            max_wait_seconds=None,
                            job_ids=new_cli_jobs,
                        )
                        if far_delay is not None and far_delay > wait_budget_s:
                            console.print(
                                "[dim]Reminder scheduled for later. Keep `kabot gateway` or interactive mode running for delivery.[/dim]"
                            )
            finally:
                if cron_started:
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
            cron_started = False
            try:
                await cron.start()
                cron_started = True
            except Exception as exc:
                logger.warning(f"Cron unavailable in interactive mode: {exc}")
                console.print(
                    "[yellow]Cron scheduler unavailable. Reminder scheduling is disabled in this session.[/yellow]"
                )
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
                if cron_started:
                    cron.stop()

        asyncio.run(run_interactive())


app.add_typer(agents.app, name="agents")
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

@models_app.command("scan")
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


@models_app.command("info")
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


@models_app.command("set")
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
    from kabot.cli.bridge_utils import run_bridge_login
    from kabot.config.loader import load_config

    config = load_config()
    bridge_url = config.channels.whatsapp.bridge_url
    run_bridge_login(stop_when_connected=False, bridge_url=bridge_url)


# ============================================================================
# Auth Commands
# ============================================================================

auth_app = typer.Typer(help="Manage authentication")
app.add_typer(auth_app, name="auth")


@auth_app.command("list")
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


@auth_app.command("login")
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


@auth_app.command("methods")
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


@auth_app.command("status")
def auth_status():
    """Show authentication status."""
    from kabot.auth.manager import AuthManager
    manager = AuthManager()
    manager.get_status()


@auth_app.command("parity")
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


# ============================================================================
# Approvals Commands
# ============================================================================

approvals_app = typer.Typer(help="Manage exec approval policies and audit")
app.add_typer(approvals_app, name="approvals")

_APPROVAL_SCOPE_KEYS = {
    "channel",
    "tool",
    "agent_id",
    "account_id",
    "thread_id",
    "peer_kind",
    "peer_id",
    "team_id",
    "guild_id",
    "chat_id",
    "session_key",
}


def _approval_config_path(config: Path | None) -> Path:
    return config or (Path.home() / ".kabot" / "command_approvals.yaml")


def _parse_scope_args(scope_args: list[str]) -> dict[str, str]:
    """Parse repeated --scope KEY=VALUE args into a scope dict."""
    scope: dict[str, str] = {}
    for raw in scope_args:
        if "=" not in raw:
            raise ValueError(f"Invalid scope entry '{raw}'. Expected KEY=VALUE.")
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ValueError(f"Invalid scope entry '{raw}'. Expected KEY=VALUE.")
        if key not in _APPROVAL_SCOPE_KEYS:
            raise ValueError(f"Invalid scope key '{key}'. Allowed: {', '.join(sorted(_APPROVAL_SCOPE_KEYS))}")
        scope[key] = value
    return scope


def _pattern_entries(patterns: list[str], description_prefix: str) -> list[dict[str, str]]:
    """Convert patterns into normalized pattern dicts for firewall config."""
    result: list[dict[str, str]] = []
    for pattern in patterns:
        clean = pattern.strip()
        if not clean:
            continue
        result.append(
            {
                "pattern": clean,
                "description": f"{description_prefix}: {clean}",
            }
        )
    return result


@approvals_app.command("status")
def approvals_status(
    config: Path | None = typer.Option(None, "--config", help="Path to approval config YAML"),
):
    """Show command firewall policy status."""
    from kabot.security.command_firewall import CommandFirewall

    firewall = CommandFirewall(_approval_config_path(config))
    info = firewall.get_policy_info()

    table = Table(title="Approval Policy Status")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("policy", str(info["policy"]))
    table.add_row("allowlist_count", str(info["allowlist_count"]))
    table.add_row("denylist_count", str(info["denylist_count"]))
    table.add_row("scoped_policy_count", str(info.get("scoped_policy_count", 0)))
    table.add_row("integrity_verified", str(info["integrity_verified"]))
    table.add_row("config_path", str(info["config_path"]))
    table.add_row("audit_log_path", str(info.get("audit_log_path", "")))
    console.print(table)


@approvals_app.command("allow")
def approvals_allow(
    pattern: str = typer.Argument(..., help="Command pattern to add to allowlist"),
    description: str = typer.Option("Added via CLI", "--description", "-d", help="Pattern description"),
    config: Path | None = typer.Option(None, "--config", help="Path to approval config YAML"),
):
    """Add an allowlist pattern to approval policy."""
    from kabot.security.command_firewall import CommandFirewall

    firewall = CommandFirewall(_approval_config_path(config))
    if firewall.add_to_allowlist(pattern, description):
        console.print(f"[green]✓[/green] Added allowlist pattern: [cyan]{pattern}[/cyan]")
        return
    console.print("[red]Failed to add allowlist pattern[/red]")
    raise typer.Exit(1)


@approvals_app.command("scoped-list")
def approvals_scoped_list(
    config: Path | None = typer.Option(None, "--config", help="Path to approval config YAML"),
):
    """List scoped approval policies."""
    from kabot.security.command_firewall import CommandFirewall

    firewall = CommandFirewall(_approval_config_path(config))
    scoped = firewall.list_scoped_policies()
    if not scoped:
        console.print("No scoped policies configured.")
        return

    table = Table(title="Scoped Approval Policies")
    table.add_column("Name", style="cyan")
    table.add_column("Policy")
    table.add_column("Scope")
    table.add_column("Allow")
    table.add_column("Deny")
    table.add_column("Inherit")

    for item in scoped:
        scope = item.get("scope") or {}
        scope_text = ", ".join(f"{k}={v}" for k, v in scope.items()) if scope else "-"
        table.add_row(
            str(item.get("name", "")),
            str(item.get("policy", "")),
            scope_text,
            str(item.get("allowlist_count", 0)),
            str(item.get("denylist_count", 0)),
            "yes" if item.get("inherit_global", True) else "no",
        )

    console.print(table)


@approvals_app.command("scoped-add")
def approvals_scoped_add(
    name: str = typer.Option(..., "--name", help="Scoped policy name"),
    policy: str = typer.Option(..., "--policy", help="Policy mode: deny|ask|allowlist"),
    scope: list[str] = typer.Option(..., "--scope", help="Scope matcher KEY=VALUE (repeatable)"),
    allow: list[str] = typer.Option([], "--allow", help="Allowlist command pattern (repeatable)"),
    deny: list[str] = typer.Option([], "--deny", help="Denylist command pattern (repeatable)"),
    inherit_global: bool = typer.Option(
        True,
        "--inherit-global/--no-inherit-global",
        help="Merge global allow/deny lists into this scoped policy",
    ),
    replace: bool = typer.Option(False, "--replace", help="Replace existing scoped policy with same name"),
    config: Path | None = typer.Option(None, "--config", help="Path to approval config YAML"),
):
    """Add a scoped approval policy."""
    from kabot.security.command_firewall import CommandFirewall

    normalized_policy = policy.strip().lower()
    if normalized_policy not in {"deny", "ask", "allowlist"}:
        console.print("[red]Invalid policy mode. Use one of: deny, ask, allowlist[/red]")
        raise typer.Exit(1)

    try:
        scope_map = _parse_scope_args(scope)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    allow_entries = _pattern_entries(allow, "Scoped allow")
    deny_entries = _pattern_entries(deny, "Scoped deny")
    firewall = CommandFirewall(_approval_config_path(config))
    ok = firewall.add_scoped_policy(
        name=name.strip(),
        scope=scope_map,
        policy=normalized_policy,
        allowlist=allow_entries,
        denylist=deny_entries,
        inherit_global=inherit_global,
        replace=replace,
    )
    if not ok:
        console.print("[red]Failed to add scoped policy (already exists? use --replace)[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Added scoped policy: [cyan]{name}[/cyan]")


@approvals_app.command("scoped-remove")
def approvals_scoped_remove(
    name: str = typer.Argument(..., help="Scoped policy name to remove"),
    config: Path | None = typer.Option(None, "--config", help="Path to approval config YAML"),
):
    """Remove a scoped approval policy by name."""
    from kabot.security.command_firewall import CommandFirewall

    firewall = CommandFirewall(_approval_config_path(config))
    if firewall.remove_scoped_policy(name):
        console.print(f"[green]✓[/green] Removed scoped policy: [cyan]{name}[/cyan]")
        return
    console.print(f"[red]Scoped policy not found: {name}[/red]")
    raise typer.Exit(1)


@approvals_app.command("audit")
def approvals_audit(
    limit: int = typer.Option(20, "--limit", "-n", min=1, max=500, help="Max audit entries"),
    decision: str | None = typer.Option(None, "--decision", help="Filter by decision: allow/ask/deny"),
    channel: str | None = typer.Option(None, "--channel", help="Filter by channel"),
    agent_id: str | None = typer.Option(None, "--agent", help="Filter by agent id"),
    config: Path | None = typer.Option(None, "--config", help="Path to approval config YAML"),
):
    """Show recent command approval audit entries."""
    from kabot.security.command_firewall import CommandFirewall

    firewall = CommandFirewall(_approval_config_path(config))
    entries = firewall.get_recent_audit(
        limit=limit,
        decision=decision,
        channel=channel,
        agent_id=agent_id,
    )

    if not entries:
        console.print("No approval audit entries found.")
        return

    table = Table(title="Approval Audit (Recent)")
    table.add_column("Time", style="cyan")
    table.add_column("Decision")
    table.add_column("Channel")
    table.add_column("Agent")
    table.add_column("Command", style="white")

    for item in entries:
        ctx = item.get("context") or {}
        table.add_row(
            str(item.get("ts", "")),
            str(item.get("decision", "")),
            str(ctx.get("channel", "")),
            str(ctx.get("agent_id", "")),
            str(item.get("command", "")),
        )

    console.print(table)


def _resolve_remote_service(platform_name: str, requested: str) -> str:
    """Resolve service manager based on target platform."""
    requested = requested.lower().strip()
    if requested != "auto":
        return requested
    if platform_name == "termux":
        return "termux"
    if platform_name == "linux":
        return "systemd"
    if platform_name == "macos":
        return "launchd"
    if platform_name == "windows":
        return "windows"
    return "none"


def _remote_health_snapshot() -> list[tuple[str, bool, str]]:
    """Collect lightweight remote-readiness checks."""
    import shutil

    from kabot.config.loader import get_config_path, load_config

    checks: list[tuple[str, bool, str]] = []
    config_path = get_config_path()
    checks.append(("Config file", config_path.exists(), str(config_path)))

    try:
        cfg = load_config()
        workspace = cfg.workspace_path
        checks.append(("Workspace", workspace.exists(), str(workspace)))
    except Exception as exc:
        checks.append(("Workspace", False, f"config load failed: {exc}"))

    checks.append(("Python in PATH", bool(shutil.which("python") or shutil.which("python3")), "python/python3"))
    checks.append(("Kabot CLI in PATH", bool(shutil.which("kabot")), "kabot"))
    return checks


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
        console.print("[green]✓[/green] Job executed")
    else:
        console.print(f"[red]Failed to run job {job_id}[/red]")


@cron_app.command("status")
def cron_status():
    """Show cron service status."""
    from kabot.config.loader import get_data_dir
    from kabot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    status = service.status()

    import time
    next_wake = "none"
    if status.get("next_wake_at_ms"):
        next_wake = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(status["next_wake_at_ms"] / 1000))

    console.print(f"Cron Service: {'running' if status['enabled'] else 'stopped'}")
    console.print(f"Jobs: {status['jobs']}")
    console.print(f"Next wake: {next_wake}")


@cron_app.command("update")
def cron_update(
    job_id: str = typer.Argument(..., help="Job ID to update"),
    message: str | None = typer.Option(None, "--message", "-m", help="Update job message"),
    every: int | None = typer.Option(None, "--every", "-e", help="Update interval in seconds"),
    cron_expr: str | None = typer.Option(None, "--cron", "-c", help="Update cron expression"),
    at: str | None = typer.Option(None, "--at", help="Update one-shot time (ISO format)"),
    deliver: bool | None = typer.Option(None, "--deliver/--no-deliver", help="Enable/disable delivery"),
):
    """Update an existing scheduled job."""
    from kabot.config.loader import get_data_dir
    from kabot.cron.service import CronService
    from kabot.cron.types import CronSchedule

    updates: dict = {}
    if message is not None:
        updates["message"] = message
    if deliver is not None:
        updates["deliver"] = deliver

    schedule_args = [every is not None, cron_expr is not None, at is not None]
    if sum(schedule_args) > 1:
        console.print("[red]Error: Use only one of --every, --cron, or --at for schedule updates[/red]")
        raise typer.Exit(1)

    if every is not None:
        updates["schedule"] = CronSchedule(kind="every", every_ms=every * 1000)
    elif cron_expr is not None:
        updates["schedule"] = CronSchedule(kind="cron", expr=cron_expr)
    elif at is not None:
        import datetime
        dt = datetime.datetime.fromisoformat(at)
        updates["schedule"] = CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))

    if not updates:
        console.print("[red]Error: No updates provided[/red]")
        raise typer.Exit(1)

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    job = service.update_job(job_id, **updates)

    if job:
        console.print(f"[green]OK[/green] Updated job '{job.name}' ({job.id})")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("runs")
def cron_runs(
    job_id: str = typer.Argument(..., help="Job ID"),
):
    """Show run history for a job."""
    from kabot.config.loader import get_data_dir
    from kabot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    history = service.get_run_history(job_id)

    if not history:
        console.print(f"No run history for job {job_id}.")
        return

    table = Table(title=f"Run History: {job_id}")
    table.add_column("Run At", style="cyan")
    table.add_column("Status")
    table.add_column("Error")

    import time
    for run in history:
        run_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(run["run_at_ms"] / 1000))
        table.add_row(run_time, run.get("status", ""), run.get("error") or "")

    console.print(table)


# ============================================================================
# Status Commands
# ============================================================================


@app.command()
def status():
    """Show kabot status."""
    from kabot.config.loader import get_config_path, load_config

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} kabot Status\n")

    console.print(f"Config: {config_path} {'[green]OK[/green]' if config_path.exists() else '[red]MISSING[/red]'}")
    console.print(f"Workspace: {workspace} {'[green]OK[/green]' if workspace.exists() else '[red]MISSING[/red]'}")

    if config_path.exists():
        from kabot.providers.registry import PROVIDERS

        console.print(f"Model: {config.agents.defaults.model}")

        # Check API keys from registry
        for spec in PROVIDERS:
            # Map registry name to config field if different
            config_field = spec.name
            p = getattr(config.providers, config_field, None)

            if p is None:
                continue

            if spec.is_local:
                # Local deployments show api_base instead of api_key
                if p.api_base:
                    console.print(f"{spec.label}: [green]OK {p.api_base}[/green]")
                else:
                    console.print(f"{spec.label}: [dim]not set[/dim]")
            else:
                has_key = bool(p.api_key or getattr(p, "setup_token", None))
                if not has_key:
                    for profile in p.profiles.values():
                        if profile.api_key or profile.oauth_token or profile.setup_token:
                            has_key = True
                            break
                status_icon = "[green]OK[/green]" if has_key else "[dim]not set[/dim]"
                console.print(f"{spec.label}: {status_icon}")


@app.command("env-check")
def env_check(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed platform guidance"),
):
    """Show runtime environment diagnostics and recommended gateway mode."""
    from kabot.utils.environment import detect_runtime_environment, recommended_gateway_mode

    runtime = detect_runtime_environment()
    mode = recommended_gateway_mode(runtime)

    table = Table(title="Environment Check")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("platform", runtime.platform)
    table.add_row("is_windows", str(runtime.is_windows))
    table.add_row("is_macos", str(runtime.is_macos))
    table.add_row("is_linux", str(runtime.is_linux))
    table.add_row("is_wsl", str(runtime.is_wsl))
    table.add_row("is_termux", str(runtime.is_termux))
    table.add_row("is_vps", str(runtime.is_vps))
    table.add_row("is_headless", str(runtime.is_headless))
    table.add_row("is_ci", str(runtime.is_ci))
    table.add_row("has_display", str(runtime.has_display))
    console.print(table)

    console.print(f"\nRecommended gateway mode: [bold cyan]{mode}[/bold cyan]")

    if verbose:
        console.print("\n[bold]Suggested next steps:[/bold]")
        if runtime.is_termux:
            console.print("  - Install termux-services package and run kabot under runit.")
        elif runtime.is_windows:
            console.print("  - Use deployment/install-kabot-service.ps1 for service setup.")
        elif runtime.is_macos:
            console.print("  - Use launchd user service via `kabot remote-bootstrap --apply`.")
        elif runtime.is_linux:
            console.print("  - Use systemd user service via `kabot remote-bootstrap --apply`.")


@app.command("remote-bootstrap")
def remote_bootstrap(
    platform: str = typer.Option("auto", "--platform", help="Target platform: auto|linux|macos|windows|termux"),
    service: str = typer.Option("auto", "--service", help="Service manager: auto|systemd|launchd|windows|termux|none"),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Dry run (print steps) or apply"),
    healthcheck: bool = typer.Option(True, "--healthcheck/--no-healthcheck", help="Run lightweight readiness checks"),
):
    """Bootstrap remote operations with service + healthcheck guidance."""
    from kabot.core.daemon import (
        install_launchd_service,
        install_systemd_service,
        install_windows_task_service,
    )
    from kabot.utils.environment import detect_runtime_environment

    runtime = detect_runtime_environment()
    target_platform = runtime.platform if platform == "auto" else platform.strip().lower()
    service_kind = _resolve_remote_service(target_platform, service)

    console.print(f"{__logo__} [bold]Remote Bootstrap[/bold]")
    console.print(f"Platform: [cyan]{target_platform}[/cyan]")
    console.print(f"Service manager: [cyan]{service_kind}[/cyan]")
    console.print(f"Mode: {'dry-run' if dry_run else 'apply'}")

    if healthcheck:
        table = Table(title="Remote Readiness Checks")
        table.add_column("Check", style="cyan")
        table.add_column("Status")
        table.add_column("Detail")
        for name, ok, detail in _remote_health_snapshot():
            table.add_row(name, "[green]OK[/green]" if ok else "[yellow]WARN[/yellow]", detail)
        console.print(table)

    console.print("\n[bold]Recommended health commands:[/bold]")
    console.print("  1. kabot doctor --fix")
    console.print("  2. kabot status")
    console.print("  3. kabot approvals status")

    if dry_run:
        console.print("\n[bold]Dry-run service bootstrap plan:[/bold]")
        if service_kind == "systemd":
            console.print("  - systemctl --user enable kabot")
            console.print("  - systemctl --user start kabot")
            console.print("  - For system-level install: bash deployment/install-linux-service.sh")
        elif service_kind == "launchd":
            console.print("  - launchctl load ~/Library/LaunchAgents/com.kabot.agent.plist")
            console.print("  - launchctl start com.kabot.agent")
        elif service_kind == "windows":
            console.print("  - powershell -ExecutionPolicy Bypass -File deployment/install-kabot-service.ps1")
        elif service_kind == "termux":
            console.print("  - pkg install termux-services")
            console.print("  - sv-enable kabot (after creating service script in $PREFIX/var/service/kabot/run)")
            console.print("  - Start with: sv up kabot")
        else:
            console.print("  - No service manager selected (manual process supervision).")
        return

    if service_kind == "systemd":
        ok, msg = install_systemd_service()
        if ok:
            console.print(f"[green]✓[/green] {msg}")
            return
        console.print(f"[red]{msg}[/red]")
        raise typer.Exit(1)

    if service_kind == "launchd":
        ok, msg = install_launchd_service()
        if ok:
            console.print(f"[green]✓[/green] {msg}")
            return
        console.print(f"[red]{msg}[/red]")
        raise typer.Exit(1)

    if service_kind == "windows":
        ok, msg = install_windows_task_service()
        if ok:
            console.print(f"[green]✓[/green] {msg}")
            return
        console.print(f"[red]{msg}[/red]")
        raise typer.Exit(1)

    if service_kind == "termux":
        from kabot.core.daemon import install_termux_service
        ok, msg = install_termux_service()
        if ok:
            console.print(f"[green]✓[/green] {msg}")
            return
        console.print(f"[red]{msg}[/red]")
        raise typer.Exit(1)

    console.print("[yellow]No service action applied (service=none).[/yellow]")


@app.command("security-audit")
def security_audit():
    """Run a security audit on the workspace."""
    from rich.table import Table

    from kabot.config.loader import load_config
    from kabot.utils.security_audit import SecurityAuditor

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
    mode: str = typer.Argument(
        "health",
        help="Doctor mode: health|routing",
    ),
    agent: str = typer.Option("main", "--agent", "-a", help="Agent ID to check"),
    fix: bool = typer.Option(False, "--fix", help="Automatically fix critical integrity issues"),
    parity_report: bool = typer.Option(
        False,
        "--parity-report",
        help="Show parity-focused diagnostics (runtime/adapters/migration/bridge/skills).",
    ),
    parity_json: str = typer.Option(
        "",
        "--parity-json",
        help="With --parity-report, output raw parity JSON to file path or '-' for stdout.",
    ),
    bootstrap_sync: bool = typer.Option(
        False,
        "--bootstrap-sync",
        help="With --fix, also sync mismatched bootstrap files from baseline templates.",
    ),
):
    """Run system health and integrity checks."""
    from kabot.utils.doctor import KabotDoctor

    mode_normalized = str(mode or "health").strip().lower()
    doc = KabotDoctor(agent_id=agent)
    parity_json_path = parity_json.strip()
    if parity_json_path and not parity_report:
        console.print("[red]--parity-json requires --parity-report[/red]")
        raise typer.Exit(1)
    if mode_normalized == "routing":
        if parity_report:
            console.print("[red]routing mode cannot be combined with --parity-report[/red]")
            raise typer.Exit(1)
        if fix:
            console.print("[yellow]--fix ignored in routing mode[/yellow]")
        if bootstrap_sync:
            console.print("[yellow]--bootstrap-sync ignored in routing mode[/yellow]")
        doc.render_routing_report()
        return
    if mode_normalized not in {"health", "all"}:
        console.print(f"[red]Unknown doctor mode: {mode}[/red]")
        console.print("[dim]Supported modes: health, routing[/dim]")
        raise typer.Exit(1)
    if parity_report:
        if parity_json_path:
            report = doc.run_parity_diagnostic()
            payload = json.dumps(report, ensure_ascii=False, indent=2)
            if parity_json_path == "-":
                console.print(payload)
                return
            output_path = Path(parity_json_path).expanduser()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(payload + "\n", encoding="utf-8")
            console.print(f"[green]Parity report JSON written[/green]: {output_path}")
            return
        doc.render_parity_report()
        return
    doc.render_report(fix=fix, sync_bootstrap=bootstrap_sync)


@app.command("plugins")
def plugins_cmd(
    action: str = typer.Argument(
        "list",
        help="Action: list|install|update|enable|disable|remove|doctor|scaffold",
    ),
    target: str = typer.Option("", "--target", "-t", help="Plugin ID for update/enable/disable/remove/doctor"),
    source: Path | None = typer.Option(None, "--source", "-s", help="Local plugin directory for install/update"),
    git: str = typer.Option("", "--git", help="Git repository URL for install/update"),
    ref: str = typer.Option("", "--ref", help="Pinned git ref (tag/branch/commit) for --git installs"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing install target for install"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation for destructive actions"),
):
    """Manage plugin lifecycle (list/install/update/enable/disable/remove/doctor/scaffold)."""
    from kabot.config.loader import load_config
    from kabot.plugins.manager import PluginManager

    config = load_config()
    plugins_dir = config.workspace_path / "plugins"
    manager = PluginManager(plugins_dir)
    action = action.strip().lower()

    if action == "list":
        plugins_list = manager.list_plugins()
        if not plugins_list:
            console.print("[yellow]No plugins found.[/yellow]")
            console.print("[dim]Install from local path: kabot plugins install --source <dir>[/dim]")
            return

        table = Table(title="Installed Plugins")
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("Type")
        table.add_column("Version")
        table.add_column("Description")
        table.add_column("Status")
        table.add_column("Source")

        for p in plugins_list:
            status = "[green]Enabled[/green]" if p.get("enabled", False) else "[red]Disabled[/red]"
            table.add_row(
                str(p.get("id", "")),
                str(p.get("name", "")),
                str(p.get("type", "")),
                str(p.get("version", "-")),
                str(p.get("description", "")),
                status,
                str(p.get("source") or "-"),
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(plugins_list)} plugin(s)[/dim]")
        return

    if action == "install":
        has_source = source is not None
        has_git = bool(git.strip())
        if has_source == has_git:
            console.print("[red]Provide exactly one install source: --source <dir> OR --git <repo>[/red]")
            raise typer.Exit(1)
        try:
            if has_source and source is not None:
                plugin_id = manager.install_from_path(source, overwrite=force)
            else:
                plugin_id = manager.install_from_git(
                    git.strip(),
                    ref=ref.strip() or None,
                    overwrite=force,
                )
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)
        console.print(f"[green]✓[/green] Installed plugin: [cyan]{plugin_id}[/cyan]")
        return

    if action == "update":
        if not target:
            console.print("[red]--target is required for update[/red]")
            raise typer.Exit(1)
        source_path = source
        if git.strip():
            try:
                manager.install_from_git(
                    git.strip(),
                    ref=ref.strip() or None,
                    target_name=target,
                    overwrite=True,
                )
                ok = True
            except ValueError:
                ok = False
        else:
            ok = manager.update_plugin(target, source_path=source_path)
        if not ok:
            console.print("[red]Failed to update plugin (missing target or source link).[/red]")
            raise typer.Exit(1)
        console.print(f"[green]✓[/green] Updated plugin: [cyan]{target}[/cyan]")
        return

    if action == "enable":
        if not target:
            console.print("[red]--target is required for enable[/red]")
            raise typer.Exit(1)
        if not manager.set_enabled(target, True):
            console.print(f"[red]Plugin not found: {target}[/red]")
            raise typer.Exit(1)
        console.print(f"[green]✓[/green] Enabled plugin: [cyan]{target}[/cyan]")
        return

    if action == "disable":
        if not target:
            console.print("[red]--target is required for disable[/red]")
            raise typer.Exit(1)
        if not manager.set_enabled(target, False):
            console.print(f"[red]Plugin not found: {target}[/red]")
            raise typer.Exit(1)
        console.print(f"[green]✓[/green] Disabled plugin: [cyan]{target}[/cyan]")
        return

    if action in {"remove", "uninstall"}:
        if not target:
            console.print("[red]--target is required for remove[/red]")
            raise typer.Exit(1)
        if not yes and not typer.confirm(f"Remove plugin '{target}'?"):
            raise typer.Abort()
        if not manager.uninstall_plugin(target):
            console.print(f"[red]Plugin not found: {target}[/red]")
            raise typer.Exit(1)
        console.print(f"[green]✓[/green] Removed plugin: [cyan]{target}[/cyan]")
        return

    if action == "doctor":
        report = manager.doctor(target or None)
        rows = report if isinstance(report, list) else [report]
        if not rows:
            console.print("[yellow]No plugins to diagnose.[/yellow]")
            return
        table = Table(title="Plugin Doctor")
        table.add_column("Plugin", style="cyan")
        table.add_column("Status")
        table.add_column("Issues")
        for item in rows:
            issues = item.get("issues", [])
            issue_text = "; ".join(str(v) for v in issues) if issues else "-"
            status = "[green]OK[/green]" if item.get("ok") else "[red]FAIL[/red]"
            table.add_row(str(item.get("plugin", "")), status, issue_text)
        console.print(table)
        if not all(bool(item.get("ok")) for item in rows):
            raise typer.Exit(1)
        return

    if action == "scaffold":
        from kabot.plugins.scaffold import scaffold_plugin

        if not target:
            console.print("[red]--target is required for scaffold[/red]")
            raise typer.Exit(1)
        try:
            plugin_path = scaffold_plugin(plugins_dir, name=target, kind="dynamic", overwrite=force)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)

        console.print(f"[green]✓[/green] Scaffolded plugin: [cyan]{plugin_path}[/cyan]")
        return

    console.print(f"[red]Unknown action: {action}[/red]")
    console.print("[dim]Available actions: list, install, update, enable, disable, remove, doctor, scaffold[/dim]")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
