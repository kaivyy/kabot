"""Extracted CLI command helpers from kabot.cli.commands."""

import asyncio
import inspect
import json
import shutil
import subprocess
import time
from typing import Any, Callable

import typer
from rich.console import Console

from kabot import __logo__
from kabot.cli.commands_provider_runtime import (
    _inject_skill_env,
    _make_provider,
)
from kabot.cli.dashboard_payloads import (
    _build_dashboard_status_payload,
    _compose_model_override,
    _parse_model_fallbacks,
    _resolve_model_runtime,
    _resolve_runtime_fallbacks,
)
from kabot.cron.callbacks import build_bus_cron_callback

console = Console()


def _resolve_commands_override(name: str, fallback):
    try:
        from kabot.cli import commands as commands_module
    except Exception:
        return fallback
    return getattr(commands_module, name, fallback)

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

    _resolve_commands_override("_inject_skill_env", _inject_skill_env)(config)

    # Configure logger
    from kabot.core.logger import configure_logger
    from kabot.memory.sqlite_store import SQLiteMetadataStore

    db_path = get_data_dir() / "metadata.db"
    store = SQLiteMetadataStore(db_path)
    configure_logger(config, store)

    bus = MessageBus()
    provider = _resolve_commands_override("_make_provider", _make_provider)(config)
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
        config=config,
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
    channels = ChannelManager(
        config,
        bus,
        session_manager=session_manager,
        command_router=agent.command_router,
        agent_loop=agent,
    )
    # Expose channel capabilities to runtime (e.g., keepalive/status behavior).
    setattr(agent, "channel_manager", channels)

    gateway_started_at = time.time()

    def _gateway_status_provider() -> dict[str, Any]:
        return _build_dashboard_status_payload(
            gateway_started_at=gateway_started_at,
            runtime_model=runtime_model,
            runtime_fallbacks=runtime_fallbacks,
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
            tailscale_only=bool(getattr(config.gateway, "tailscale", False)),
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
