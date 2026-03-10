"""CLI commands for kabot."""

import asyncio
import atexit
import os
import select
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from kabot import __logo__, __version__
from kabot.cli import agents, mode
from kabot.cli.dashboard_payloads import (
    _build_dashboard_channel_rows,
    _build_dashboard_config_summary,
    _build_dashboard_cost_payload,
    _build_dashboard_cron_snapshot,
    _build_dashboard_git_log,
    _build_dashboard_nodes,
    _build_dashboard_skills_snapshot,
    _build_dashboard_status_payload,
    _build_dashboard_subagent_activity,
    _compose_model_override,
    _implicit_runtime_fallbacks,
    _list_provider_models_for_dashboard,
    _merge_fallbacks,
    _parse_model_fallbacks,
    _provider_has_credentials,
    _resolve_model_runtime,
    _resolve_runtime_fallbacks,
)

if __name__ == "__main__":
    # Running via `python -m kabot.cli.commands` names this module `__main__`.
    # Refactor modules still import `kabot.cli.commands`, so alias the live
    # module instance to avoid a second partially-initialized import.
    sys.modules.setdefault("kabot.cli.commands", sys.modules[__name__])

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
    if render_markdown:
        try:
            body = Markdown(content)
        except Exception:
            body = Text(content)
    else:
        body = Text(content)
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


def backup_create(
    source_dir: Path | None = typer.Option(
        None,
        "--source-dir",
        help="Directory to archive. Defaults to ~/.kabot.",
    ),
    dest_dir: Path | None = typer.Option(
        None,
        "--dest-dir",
        help="Directory where the backup zip will be written.",
    ),
    only_config: bool = typer.Option(
        True,
        "--only-config/--include-runtime",
        help="Exclude runtime-heavy directories like sessions and old backups.",
    ),
) -> None:
    """Create a local backup archive."""
    from kabot.config.loader import get_config_path
    from kabot.core.backup import create_backup

    source_root = source_dir or get_config_path().parent
    try:
        archive_path = create_backup(source_root, dest_dir=dest_dir, only_config=only_config)
    except Exception as exc:
        typer.echo(f"Backup failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Backup created: {archive_path}")

from kabot.cli.commands_agent_command import agent  # noqa: E402,I001
from kabot.cli.commands_approvals import (  # noqa: E402,I001
    _approval_config_path,
    _parse_scope_args,
    _pattern_entries,
    approvals_allow,
    approvals_audit,
    approvals_scoped_add,
    approvals_scoped_list,
    approvals_scoped_remove,
    approvals_status,
)
from kabot.cli.commands_gateway import (  # noqa: E402,I001
    _configure_tailscale_runtime,
    _extract_tailnet_host,
    _gateway_dashboard_chat_history_provider,
    _gateway_dashboard_control_action,
    _is_port_in_use_error,
    _parse_tailscale_status,
    _preflight_gateway_port,
    _resolve_gateway_runtime_port,
    _resolve_tailscale_mode,
    _run_tailscale_cli,
    gateway,
)
from kabot.cli.commands_models_auth import (  # noqa: E402,I001
    auth_list,
    auth_login,
    auth_methods,
    auth_parity,
    auth_status,
    channels_login,
    channels_status,
    models_info,
    models_list,
    models_scan,
    models_set,
)
from kabot.cli.commands_provider_runtime import (  # noqa: E402,I001
    _cli_exec_approval_prompt,
    _collect_cli_delivery_job_ids,
    _inject_skill_env,
    _make_provider,
    _next_cli_reminder_delay_seconds,
    _render_cron_delivery_with_ai,
    _resolve_api_key_with_refresh,
    _resolve_cron_delivery_content,
    _should_use_reminder_fallback,
    _strip_reminder_context,
    _wire_cli_exec_approval,
)
from kabot.cli.commands_setup import (  # noqa: E402,I001
    _collect_skill_env_requirements,
    _create_workspace_templates,
    _handle_skill_onboarding,
    _inject_skill_persona,
    _is_secret_env_name,
    _load_skill_persona_snippet,
    config,
    google_auth,
    onboard,
    setup,
    skills_install,
    train,
)
from kabot.cli.commands_system import (  # noqa: E402,I001
    _remote_health_snapshot,
    _resolve_remote_service,
    cron_add,
    cron_enable,
    cron_list,
    cron_remove,
    cron_run,
    cron_runs,
    cron_status,
    cron_update,
    doctor,
    env_check,
    plugins_cmd,
    remote_bootstrap,
    security_audit,
    status,
)

__all__ = [
    "EXIT_COMMANDS",
    "_approval_config_path",
    "_build_dashboard_channel_rows",
    "_build_dashboard_config_summary",
    "_build_dashboard_cost_payload",
    "_build_dashboard_cron_snapshot",
    "_build_dashboard_git_log",
    "_build_dashboard_nodes",
    "_build_dashboard_skills_snapshot",
    "_build_dashboard_status_payload",
    "_build_dashboard_subagent_activity",
    "_cli_exec_approval_prompt",
    "_collect_cli_delivery_job_ids",
    "_collect_skill_env_requirements",
    "_compose_model_override",
    "_configure_tailscale_runtime",
    "_create_workspace_templates",
    "_enable_line_editing",
    "_extract_tailnet_host",
    "_flush_pending_tty_input",
    "_gateway_dashboard_chat_history_provider",
    "_gateway_dashboard_control_action",
    "_handle_skill_onboarding",
    "_implicit_runtime_fallbacks",
    "_inject_skill_env",
    "_inject_skill_persona",
    "_is_exit_command",
    "_is_port_in_use_error",
    "_is_secret_env_name",
    "_list_provider_models_for_dashboard",
    "_load_skill_persona_snippet",
    "_make_provider",
    "_merge_fallbacks",
    "_next_cli_reminder_delay_seconds",
    "_parse_model_fallbacks",
    "_parse_scope_args",
    "_parse_tailscale_status",
    "_pattern_entries",
    "_preflight_gateway_port",
    "_print_agent_response",
    "_prompt_text",
    "_provider_has_credentials",
    "_read_interactive_input_async",
    "_remote_health_snapshot",
    "_render_cron_delivery_with_ai",
    "_resolve_api_key_with_refresh",
    "_resolve_cron_delivery_content",
    "_resolve_gateway_runtime_port",
    "_resolve_model_runtime",
    "_resolve_remote_service",
    "_resolve_runtime_fallbacks",
    "_resolve_tailscale_mode",
    "_restore_terminal",
    "_run_tailscale_cli",
    "_save_history",
    "_should_use_reminder_fallback",
    "_strip_reminder_context",
    "_terminal_safe",
    "_wire_cli_exec_approval",
    "agent",
    "app",
    "approvals_allow",
    "approvals_app",
    "approvals_audit",
    "approvals_scoped_add",
    "approvals_scoped_list",
    "approvals_scoped_remove",
    "approvals_status",
    "auth_app",
    "backup_app",
    "backup_create",
    "auth_list",
    "auth_login",
    "auth_methods",
    "auth_parity",
    "auth_status",
    "channels_app",
    "channels_login",
    "channels_status",
    "config",
    "console",
    "cron_add",
    "cron_app",
    "cron_enable",
    "cron_list",
    "cron_remove",
    "cron_run",
    "cron_runs",
    "cron_status",
    "cron_update",
    "doctor",
    "env_check",
    "gateway",
    "google_auth",
    "main",
    "mode",
    "models_app",
    "models_info",
    "models_list",
    "models_scan",
    "models_set",
    "onboard",
    "plugins_cmd",
    "remote_bootstrap",
    "security_audit",
    "setup",
    "skills_app",
    "skills_install",
    "status",
    "subprocess",
    "train",
    "version_callback",
]


skills_app = typer.Typer(help="Manage external skills")
app.add_typer(skills_app, name="skills")

models_app = typer.Typer(help="Manage AI models and metadata")
app.add_typer(models_app, name="models")

channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")

auth_app = typer.Typer(help="Manage authentication")
app.add_typer(auth_app, name="auth")

approvals_app = typer.Typer(help="Manage exec approval policies and audit")
app.add_typer(approvals_app, name="approvals")

cron_app = typer.Typer(help="Manage scheduled tasks")
app.add_typer(cron_app, name="cron")

backup_app = typer.Typer(help="Create and inspect backups")
app.add_typer(backup_app, name="backup")

app.add_typer(agents.app, name="agents")
app.add_typer(mode.app, name="mode")

app.command()(onboard)
app.command("google-auth")(google_auth)
app.command("train")(train)
app.command()(setup)
app.command()(config)
skills_app.command("install")(skills_install)
app.command()(gateway)
app.command()(agent)
models_app.command("list")(models_list)
models_app.command("scan")(models_scan)
models_app.command("info")(models_info)
models_app.command("set")(models_set)
channels_app.command("status")(channels_status)
channels_app.command("login")(channels_login)
auth_app.command("list")(auth_list)
auth_app.command("login")(auth_login)
auth_app.command("methods")(auth_methods)
auth_app.command("status")(auth_status)
auth_app.command("parity")(auth_parity)
approvals_app.command("status")(approvals_status)
approvals_app.command("allow")(approvals_allow)
approvals_app.command("scoped-list")(approvals_scoped_list)
approvals_app.command("scoped-add")(approvals_scoped_add)
approvals_app.command("scoped-remove")(approvals_scoped_remove)
approvals_app.command("audit")(approvals_audit)
cron_app.command("list")(cron_list)
cron_app.command("add")(cron_add)
cron_app.command("remove")(cron_remove)
cron_app.command("enable")(cron_enable)
cron_app.command("run")(cron_run)
cron_app.command("status")(cron_status)
cron_app.command("update")(cron_update)
cron_app.command("runs")(cron_runs)
backup_app.command("create")(backup_create)
app.command()(status)
app.command("env-check")(env_check)
app.command("remote-bootstrap")(remote_bootstrap)
app.command("security-audit")(security_audit)
app.command("doctor")(doctor)
app.command("plugins")(plugins_cmd)


if __name__ == "__main__":
    app()
