"""Extracted CLI command helpers from kabot.cli.commands."""

import asyncio
import hashlib
import os
import signal
import sys
import time
from pathlib import Path

import typer
from click.core import ParameterSource
from loguru import logger
from rich.console import Console

from kabot import __logo__
from kabot.cli.commands import (
    _enable_line_editing,
    _flush_pending_tty_input,
    _is_exit_command,
    _print_agent_response,
    _read_interactive_input_async,
    _restore_terminal,
    _save_history,
)
from kabot.cli.commands_provider_runtime import (
    _collect_cli_delivery_job_ids,
    _inject_skill_env,
    _make_provider,
    _next_cli_reminder_delay_seconds,
    _wire_cli_exec_approval,
)
from kabot.cli.dashboard_payloads import (
    _resolve_model_runtime,
    _resolve_runtime_fallbacks,
)
from kabot.cron.callbacks import build_cli_cron_callback
from kabot.cron.callbacks import should_use_reminder_fallback as _should_use_reminder_fallback_impl
from kabot.utils.text_safety import repair_common_mojibake_text

console = Console()


def _resolve_commands_override(name: str, fallback):
    try:
        from kabot.cli import commands as commands_module
    except Exception:
        return fallback
    return getattr(commands_module, name, fallback)


def _normalize_cli_message_text(value: str | None) -> str:
    return repair_common_mojibake_text(value or "")


def _make_ephemeral_one_shot_session_id(message: str) -> str:
    digest = hashlib.sha1(str(message or "").encode("utf-8", "ignore")).hexdigest()[:10]
    return f"cli:oneshot:{int(time.time() * 1000)}:{digest}"


def _session_option_was_explicit(ctx: typer.Context | None) -> bool:
    if ctx is None:
        return False
    get_source = getattr(ctx, "get_parameter_source", None)
    if not callable(get_source):
        return False
    try:
        source = get_source("session_id")
    except Exception:
        return False
    return source is not None and source != ParameterSource.DEFAULT


def _resolve_one_shot_session_id(
    ctx: typer.Context | None,
    session_id: str,
    *,
    message: str | None,
) -> str:
    normalized_session = str(session_id or "").strip() or "cli:default"
    if not message:
        return normalized_session
    if _session_option_was_explicit(ctx):
        return normalized_session
    if normalized_session != "cli:default":
        return normalized_session
    return _make_ephemeral_one_shot_session_id(message)


def agent(
    ctx: typer.Context,
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:default", "--session", "-s", help="Session ID"),
    markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render assistant output as Markdown"),
    logs: bool = typer.Option(False, "--logs/--no-logs", help="Show kabot runtime logs during chat"),
):
    """Interact with the agent directly."""

    from kabot.agent.agent_scope import resolve_agent_id_for_workspace, resolve_agent_workspace
    from kabot.agent.loop import AgentLoop
    from kabot.bus.queue import MessageBus
    from kabot.config.loader import get_data_dir, load_config
    from kabot.cron.service import CronService

    message = _normalize_cli_message_text(message)
    resolved_one_shot_session_id = _resolve_one_shot_session_id(
        ctx,
        session_id,
        message=message,
    )
    config = load_config()
    _resolve_commands_override("_inject_skill_env", _inject_skill_env)(config)

    # Configure logger
    from kabot.core.logger import configure_logger
    from kabot.memory.sqlite_store import SQLiteMetadataStore

    db_path = get_data_dir() / "metadata.db"
    store = SQLiteMetadataStore(db_path)
    configure_logger(config, store)

    bus = MessageBus()
    provider = _resolve_commands_override("_make_provider", _make_provider)(config)

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
    bound_agent_id = resolve_agent_id_for_workspace(config, Path.cwd())
    bound_workspace = resolve_agent_workspace(config, bound_agent_id)

    # Initialize CronService (required for reminder tools)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=bound_workspace,
        config=config,
        model=runtime_model,
        fallbacks=runtime_fallbacks,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        enable_hybrid_memory=config.agents.enable_hybrid_memory,
        cron_service=cron,  # Pass cron service to enable tools
        lazy_probe_memory=bool(message),
    )
    agent_loop._direct_agent_binding = bound_agent_id
    if sys.stdin.isatty():
        _resolve_commands_override("_wire_cli_exec_approval", _wire_cli_exec_approval)(agent_loop)

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
        async def _close_runtime_resources() -> None:
            close_resources = getattr(agent_loop, "close_runtime_resources", None)
            if callable(close_resources):
                await close_resources()

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
                        resolved_one_shot_session_id,
                        suppress_post_response_warmup=True,
                        probe_mode=True,
                        persist_history=True,
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
                await _close_runtime_resources()

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
                        user_input = _normalize_cli_message_text(user_input)
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
                close_resources = getattr(agent_loop, "close_runtime_resources", None)
                if callable(close_resources):
                    await close_resources()

        asyncio.run(run_interactive())
