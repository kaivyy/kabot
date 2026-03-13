"""Dashboard payload and runtime helper functions for the CLI layer."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from loguru import logger

from kabot import __version__
from kabot.core.command_surfaces import (
    build_command_surface_specs,
    is_basic_slash_command_name,
    normalize_slash_command_name,
)

_DASHBOARD_PROVIDER_MODELS_CACHE_TS = 0.0
_DASHBOARD_PROVIDER_MODELS_CACHE: dict[str, list[str]] = {}
_DASHBOARD_STATIC_COMMANDS: tuple[tuple[str, str], ...] = (
    ("start", "Start or resume the conversation"),
    ("reset", "Clear conversation context"),
    ("help", "Show available commands"),
)


def _resolve_commands_override(name: str, fallback: Any) -> Any:
    """Honor monkeypatches applied via `kabot.cli.commands` for backward-compatible tests."""
    commands_mod = sys.modules.get("kabot.cli.commands")
    candidate = getattr(commands_mod, name, None) if commands_mod is not None else None
    if callable(candidate) and candidate is not fallback:
        return candidate
    return fallback


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
    """Build implicit runtime fallback chain when user did not configure one explicitly."""
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

        provider_available = sorted(
            {str(spec.name).strip() for spec in PROVIDERS if str(spec.name).strip()}
        )
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
    model_chain = [str(default_model or "").strip()]
    model_chain.extend(
        _merge_fallbacks(
            str(default_model or "").strip(),
            [str(item).strip() for item in default_fallbacks if str(item).strip()],
        )
    )
    runtime_summary = {
        "model": {
            "primary": str(default_model or ""),
            "fallbacks": [str(item).strip() for item in default_fallbacks if str(item).strip()],
            "chain": [item for item in model_chain if item],
        },
        "performance": {
            "token_mode": str(getattr(runtime_perf, "token_mode", "boros") or "boros").strip().lower(),
            "fast_first_response": bool(getattr(runtime_perf, "fast_first_response", True)),
            "defer_memory_warmup": bool(getattr(runtime_perf, "defer_memory_warmup", True)),
        },
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
        "models_by_provider": _resolve_commands_override(
            "_list_provider_models_for_dashboard",
            _list_provider_models_for_dashboard,
        )(),
    }

    return {
        "gateway": gateway_summary,
        "runtime": runtime_summary,
        "tools": tools_summary,
        "providers": providers_summary,
    }


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
        values = [token.strip() for token in raw.replace("\n", ",").split(",") if token and token.strip()]
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


def _build_dashboard_recent_turn_snapshot(session_manager: Any) -> dict[str, Any]:
    """Extract the latest message metadata that helps explain continuity/routing decisions."""
    list_sessions = getattr(session_manager, "list_sessions", None)
    get_or_create = getattr(session_manager, "get_or_create", None)
    if not callable(list_sessions) or not callable(get_or_create):
        return {}

    try:
        sessions = list(list_sessions())
    except Exception:
        return {}
    if not sessions:
        return {}

    latest_key = ""
    for item in sessions:
        if isinstance(item, dict):
            latest_key = str(item.get("key") or "").strip()
        else:
            latest_key = str(item or "").strip()
        if latest_key:
            break
    if not latest_key:
        return {}

    try:
        session = get_or_create(latest_key)
    except Exception:
        return {}
    session_metadata = getattr(session, "metadata", None)
    if not isinstance(session_metadata, dict):
        session_metadata = {}
    messages = getattr(session, "messages", None)
    if not isinstance(messages, list):
        return {}

    for item in reversed(messages):
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata")
        message_metadata = metadata if isinstance(metadata, dict) else {}
        continuity_source = str(message_metadata.get("continuity_source") or "").strip()
        route_profile = str(message_metadata.get("route_profile") or "").strip()
        required_tool = str(message_metadata.get("required_tool") or "").strip()
        turn_category = str(
            message_metadata.get("turn_category")
            or session_metadata.get("last_turn_category")
            or ""
        ).strip()
        completion_evidence = message_metadata.get("completion_evidence")
        if not isinstance(completion_evidence, dict):
            completion_evidence = session_metadata.get("last_completion_evidence")
        if not isinstance(completion_evidence, dict):
            completion_evidence = {}
        pending_interrupt_count = int(
            message_metadata.get("pending_interrupt_count")
            or session_metadata.get("pending_interrupt_count")
            or 0
        )
        if not (continuity_source or route_profile or required_tool or turn_category or completion_evidence):
            continue
        snapshot = {
            "session_key": latest_key,
            "role": str(item.get("role") or "").strip().lower() or "assistant",
            "timestamp": str(item.get("timestamp") or "").strip(),
            "continuity_source": continuity_source or "none",
            "turn_category": turn_category or "none",
            "route_profile": route_profile,
            "route_complex": bool(message_metadata.get("route_complex")),
            "required_tool": required_tool,
            "required_tool_query": str(message_metadata.get("required_tool_query") or "").strip(),
            "pending_interrupt_count": pending_interrupt_count,
            "completion_evidence": dict(completion_evidence) if completion_evidence else {},
        }
        return snapshot
    return {}


def _build_dashboard_cost_payload(
    session_manager: Any,
    *,
    runtime_models: list[str] | None = None,
) -> dict[str, Any]:
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
    model_usage_map = {
        str(model): int(tokens or 0)
        for model, tokens in model_usage.items()
        if str(model).strip()
    }

    model_costs = summary.get("model_costs", {})
    if not isinstance(model_costs, dict):
        model_costs = {}
    model_costs_map = {
        str(model): float(cost or 0)
        for model, cost in model_costs.items()
        if str(model).strip()
    }

    runtime_chain = [str(model).strip() for model in (runtime_models or []) if str(model).strip()]
    for runtime_model in runtime_chain:
        model_usage_map.setdefault(runtime_model, 0)
        model_costs_map.setdefault(runtime_model, 0.0)

    cost_history = summary.get("cost_history", [])
    if not isinstance(cost_history, list):
        cost_history = []

    raw_usage_windows = summary.get("usage_windows", {})
    if not isinstance(raw_usage_windows, dict):
        raw_usage_windows = {}

    usage_windows: dict[str, dict[str, Any]] = {}
    for window_key in ("7d", "30d", "all"):
        raw_window = raw_usage_windows.get(window_key, {})
        if not isinstance(raw_window, dict):
            raw_window = {}
        raw_tokens = raw_window.get("token_usage", {})
        if not isinstance(raw_tokens, dict):
            raw_tokens = {}
        raw_window_usage = raw_window.get("model_usage", {})
        if not isinstance(raw_window_usage, dict):
            raw_window_usage = {}
        raw_window_costs = raw_window.get("model_costs", {})
        if not isinstance(raw_window_costs, dict):
            raw_window_costs = {}
        raw_window_cost_payload = raw_window.get("costs", {})
        if not isinstance(raw_window_cost_payload, dict):
            raw_window_cost_payload = {}
        if not raw_window_costs:
            candidate_by_model = raw_window_cost_payload.get("by_model", {})
            if isinstance(candidate_by_model, dict):
                raw_window_costs = candidate_by_model
        raw_window_history = raw_window.get("cost_history", [])
        if not isinstance(raw_window_history, list):
            raw_window_history = []

        window_usage_map = {
            str(model): int(tokens or 0)
            for model, tokens in raw_window_usage.items()
            if str(model).strip()
        }
        window_costs_map = {
            str(model): float(cost or 0)
            for model, cost in raw_window_costs.items()
            if str(model).strip()
        }
        for runtime_model in runtime_chain:
            window_usage_map.setdefault(runtime_model, 0)
            window_costs_map.setdefault(runtime_model, 0.0)

        usage_windows[window_key] = {
            "label": str(raw_window.get("label") or window_key),
            "token_usage": {
                "input": int(raw_tokens.get("input", 0) or 0),
                "output": int(raw_tokens.get("output", 0) or 0),
                "total": int(raw_tokens.get("total", 0) or 0),
            },
            "model_usage": window_usage_map,
            "costs": {
                "total": float(raw_window_cost_payload.get("total", sum(window_costs_map.values())) or 0),
                "by_model": window_costs_map,
            },
            "cost_history": [
                {
                    "date": str(item.get("date") or ""),
                    "cost": float(item.get("cost", 0) or 0),
                    "tokens": int(item.get("tokens", 0) or 0),
                }
                for item in raw_window_history
                if isinstance(item, dict)
            ],
        }

    return {
        "costs": {
            "today": float(summary.get("today", 0) or 0),
            "total": float(summary.get("total", 0) or 0),
            "projected_monthly": float(summary.get("projected_monthly", 0) or 0),
            "by_model": {model: cost for model, cost in model_costs_map.items()},
        },
        "token_usage": {
            "input": int(token_usage.get("input", 0) or 0),
            "output": int(token_usage.get("output", 0) or 0),
            "total": int(token_usage.get("total", 0) or 0),
        },
        "model_usage": model_usage_map,
        "cost_history": [
            {
                "date": str(item.get("date") or ""),
                "cost": float(item.get("cost", 0) or 0),
                "tokens": int(item.get("tokens", 0) or 0),
            }
            for item in cost_history
            if isinstance(item, dict)
        ],
        "usage_windows": usage_windows,
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
            rows.append({"name": str(name), "type": str(data.get("type") or name), "state": state})
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


def _build_dashboard_command_surface(agent: Any, config: Any) -> list[dict[str, Any]]:
    workspace = getattr(agent, "workspace", None)
    if workspace is None:
        workspace = getattr(config, "workspace_path", None)

    build_specs = _resolve_commands_override(
        "build_command_surface_specs",
        build_command_surface_specs,
    )
    normalize_name = _resolve_commands_override(
        "normalize_slash_command_name",
        normalize_slash_command_name,
    )
    is_valid_name = _resolve_commands_override(
        "is_basic_slash_command_name",
        is_basic_slash_command_name,
    )
    try:
        specs = build_specs(
            static_commands=_DASHBOARD_STATIC_COMMANDS,
            router=getattr(agent, "command_router", None),
            workspace=workspace,
            normalize_name=normalize_name,
            is_valid_name=is_valid_name,
        )
    except Exception as exc:
        logger.warning(f"Command surface snapshot failed: {exc}")
        return []

    rows: list[dict[str, Any]] = []
    for spec in specs:
        rows.append(
            {
                "name": str(getattr(spec, "name", "") or ""),
                "description": str(getattr(spec, "description", "") or ""),
                "source": str(getattr(spec, "source", "") or ""),
                "skill_name": str(getattr(spec, "skill_name", "") or ""),
                "admin_only": bool(getattr(spec, "admin_only", False)),
            }
        )
    return rows


def _build_dashboard_subagent_activity(agent: Any, *, limit: int = 10) -> list[dict[str, Any]]:
    registry = getattr(getattr(agent, "subagents", None), "registry", None)
    if registry is None or not hasattr(registry, "list_all"):
        return []
    try:
        runs = list(registry.list_all())
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for record in sorted(
        runs,
        key=lambda item: float(getattr(item, "created_at", 0) or 0),
        reverse=True,
    )[:limit]:
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
            ["git", "log", f"-n{max(1, int(limit))}", "--pretty=format:%h|%s|%cI|%an"],
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
    runtime_fallbacks: list[str] | None = None,
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

    runtime_models = [str(runtime_model or "").strip()]
    runtime_models.extend(
        _merge_fallbacks(
            str(runtime_model or "").strip(),
            [str(item).strip() for item in (runtime_fallbacks or []) if str(item).strip()],
        )
    )

    cron_status, cron_jobs_list = _build_dashboard_cron_snapshot(cron)
    channels_enabled = list(getattr(channels, "enabled_channels", []))
    recent_turn = _build_dashboard_recent_turn_snapshot(session_manager)
    cost_payload = _build_dashboard_cost_payload(
        session_manager,
        runtime_models=[item for item in runtime_models if item],
    )
    skills = _build_dashboard_skills_snapshot(config)
    command_surface = _build_dashboard_command_surface(agent, config)
    subagent_activity = _build_dashboard_subagent_activity(agent)
    git_log = _build_dashboard_git_log(config.workspace_path)

    return {
        "status": "running",
        "uptime_seconds": max(0, int(time.time() - gateway_started_at)),
        "model": runtime_model,
        "runtime_models": [item for item in runtime_models if item],
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
        "recent_turn": recent_turn,
        "nodes": _build_dashboard_nodes(channels),
        "config": _build_dashboard_config_summary(config),
        "system": {"pid": os.getpid(), "memory_mb": 0},
        "skills": skills,
        "command_surface": command_surface,
        "subagent_activity": subagent_activity,
        "git_log": git_log,
        **cost_payload,
    }


__all__ = [
    "_build_dashboard_channel_rows",
    "_build_dashboard_command_surface",
    "_build_dashboard_config_summary",
    "_build_dashboard_cost_payload",
    "_build_dashboard_cron_snapshot",
    "_build_dashboard_git_log",
    "_build_dashboard_nodes",
    "_build_dashboard_skills_snapshot",
    "_build_dashboard_status_payload",
    "_build_dashboard_subagent_activity",
    "_compose_model_override",
    "_describe_dashboard_schedule",
    "_format_dashboard_timestamp_ms",
    "_implicit_runtime_fallbacks",
    "_list_provider_models_for_dashboard",
    "_merge_fallbacks",
    "_parse_model_fallbacks",
    "_provider_has_credentials",
    "_resolve_model_runtime",
    "_resolve_runtime_fallbacks",
]
