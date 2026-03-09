"""Extracted CLI command helpers from kabot.cli.commands."""

import asyncio
import os
import time
from pathlib import Path

import typer
from rich.console import Console

from kabot.cli.dashboard_payloads import (
    _resolve_model_runtime,
    _resolve_runtime_fallbacks,
)
from kabot.cron.callbacks import render_cron_delivery_with_ai as _render_cron_delivery_with_ai_impl
from kabot.cron.callbacks import (
    resolve_cron_delivery_content as _resolve_cron_delivery_content_impl,
)
from kabot.cron.callbacks import should_use_reminder_fallback as _should_use_reminder_fallback_impl
from kabot.cron.callbacks import strip_reminder_context as _strip_reminder_context_impl

console = Console()


def _resolve_commands_override(name: str, fallback):
    try:
        from kabot.cli import commands as commands_module
    except Exception:
        return fallback
    return getattr(commands_module, name, fallback)

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

    # Pre-seed ALL providers from config so that model overrides during execution have credentials ready
    if hasattr(config, "providers") and config.providers:
        prov_dict = {}
        if hasattr(config.providers, 'model_dump'):
            prov_dict = config.providers.model_dump()
        elif hasattr(config.providers, 'dict'):
            prov_dict = config.providers.dict()
        else:
            try:
                prov_dict = vars(config.providers)
            except Exception:
                pass

        for p_name, p_config in prov_dict.items():
            if not p_name:
                continue
            dummy_model = f"{p_name}/default"
            key = _resolve_api_key_with_refresh(config, dummy_model)
            if key:
                provider_api_keys[p_name] = key

            base = config.get_api_base(dummy_model)
            if base:
                provider_api_bases[p_name] = base

            obj = getattr(config.providers, p_name, None)
            headers = getattr(obj, "extra_headers", None) if obj else None
            if headers:
                provider_extra_headers[p_name] = dict(headers)

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
