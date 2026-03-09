"""Extracted CLI command helpers from kabot.cli.commands."""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

console = Console()

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


def _resolve_commands_override(name: str, fallback):
    try:
        from kabot.cli import commands as commands_module
    except Exception:
        return fallback
    return getattr(commands_module, name, fallback)

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
