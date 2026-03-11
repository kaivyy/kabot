"""Extracted CLI command helpers from kabot.cli.commands."""

import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from kabot import __logo__

console = Console()


def _resolve_commands_override(name: str, fallback):
    try:
        from kabot.cli import commands as commands_module
    except Exception:
        return fallback
    return getattr(commands_module, name, fallback)

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

def cron_status():
    """Show cron service status."""
    from kabot.config.loader import get_data_dir
    from kabot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    status = service.status()

    next_wake = "none"
    if status.get("next_wake_at_ms"):
        next_wake = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(status["next_wake_at_ms"] / 1000))

    console.print(f"Cron Service: {'running' if status['enabled'] else 'stopped'}")
    console.print(f"Jobs: {status['jobs']}")
    console.print(f"Next wake: {next_wake}")

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

    for run in history:
        run_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(run["run_at_ms"] / 1000))
        table.add_row(run_time, run.get("status", ""), run.get("error") or "")

    console.print(table)

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

def doctor(
    mode: str = typer.Argument(
        "health",
        help="Doctor mode: health|routing|smoke-agent",
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
    smoke_json: bool = typer.Option(
        False,
        "--smoke-json",
        help="With doctor smoke-agent, print smoke matrix results as JSON.",
    ),
    smoke_no_default_cases: bool = typer.Option(
        False,
        "--smoke-no-default-cases",
        help="With doctor smoke-agent, skip built-in temporal/filesystem cases.",
    ),
    smoke_all_skills: bool = typer.Option(
        False,
        "--smoke-all-skills",
        help="With doctor smoke-agent, add explicit-skill smoke cases for all available skills.",
    ),
    smoke_skill: list[str] | None = typer.Option(
        None,
        "--smoke-skill",
        help="With doctor smoke-agent, add explicit-skill smoke case(s). Repeatable.",
    ),
    smoke_skill_locales: str = typer.Option(
        "en",
        "--smoke-skill-locales",
        help="With doctor smoke-agent, comma-separated locales for explicit-skill prompts.",
    ),
    smoke_timeout: int = typer.Option(
        120,
        "--smoke-timeout",
        help="With doctor smoke-agent, subprocess timeout in seconds.",
    ),
    smoke_python: str = typer.Option(
        sys.executable,
        "--smoke-python",
        help="With doctor smoke-agent, Python executable used for subprocess runs.",
    ),
    smoke_os_profile: str = typer.Option(
        "auto",
        "--smoke-os-profile",
        help="With doctor smoke-agent, prompt profile: auto|windows|posix.",
    ),
    smoke_cwd: Path | None = typer.Option(
        None,
        "--smoke-cwd",
        help="With doctor smoke-agent, working directory for smoke subprocess runs.",
    ),
    smoke_max_context_build_ms: int = typer.Option(
        0,
        "--smoke-max-context-build-ms",
        help="With doctor smoke-agent, fail if context_build_ms exceeds this threshold.",
    ),
    smoke_max_first_response_ms: int = typer.Option(
        0,
        "--smoke-max-first-response-ms",
        help="With doctor smoke-agent, fail if first_response_ms exceeds this threshold.",
    ),
    smoke_mcp_local_echo: bool = typer.Option(
        False,
        "--smoke-mcp-local-echo",
        help="With doctor smoke-agent, add a local Python MCP echo smoke case.",
    ),
):
    """Run system health and integrity checks."""
    mode_normalized = str(mode or "health").strip().lower()
    parity_json_path = parity_json.strip()
    if parity_json_path and not parity_report:
        console.print("[red]--parity-json requires --parity-report[/red]")
        raise typer.Exit(1)
    if mode_normalized == "smoke-agent":
        if parity_report:
            console.print("[red]smoke-agent mode cannot be combined with --parity-report[/red]")
            raise typer.Exit(1)
        if fix:
            console.print("[yellow]--fix ignored in smoke-agent mode[/yellow]")
        if bootstrap_sync:
            console.print("[yellow]--bootstrap-sync ignored in smoke-agent mode[/yellow]")
        from kabot.cli import agent_smoke_matrix

        smoke_argv: list[str] = ["--os-profile", str(smoke_os_profile or "auto"), "--python", str(smoke_python)]
        if smoke_cwd is not None:
            smoke_argv.extend(["--cwd", str(smoke_cwd)])
        if smoke_json:
            smoke_argv.append("--json")
        if smoke_no_default_cases:
            smoke_argv.append("--no-default-cases")
        if smoke_all_skills:
            smoke_argv.append("--all-skills")
        for skill_name in smoke_skill or []:
            if str(skill_name or "").strip():
                smoke_argv.extend(["--skill", str(skill_name).strip()])
        if str(smoke_skill_locales or "").strip():
            smoke_argv.extend(["--skill-locales", str(smoke_skill_locales).strip()])
        if smoke_timeout > 0:
            smoke_argv.extend(["--timeout", str(smoke_timeout)])
        if smoke_max_context_build_ms > 0:
            smoke_argv.extend(["--max-context-build-ms", str(smoke_max_context_build_ms)])
        if smoke_max_first_response_ms > 0:
            smoke_argv.extend(["--max-first-response-ms", str(smoke_max_first_response_ms)])
        if smoke_mcp_local_echo:
            smoke_argv.append("--mcp-local-echo")
        raise typer.Exit(agent_smoke_matrix.main(smoke_argv))

    from kabot.utils.doctor import KabotDoctor

    doc = KabotDoctor(agent_id=agent)
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
        console.print("[dim]Supported modes: health, routing, smoke-agent[/dim]")
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
