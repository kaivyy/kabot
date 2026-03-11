"""Observability, quota, and error helpers for execution runtime."""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
from typing import Any

from loguru import logger

from kabot.core.failover_error import resolve_failover_reason
from kabot.utils.text_safety import ensure_utf8_text


def _sanitize_error(error_str: str) -> str:
    """Strip internal URLs, API keys, and verbose tracebacks from user-facing errors."""
    sanitized = re.sub(r"https?://\S+", "[API endpoint]", error_str)
    sanitized = re.sub(r"(sk-|key-|Bearer )[a-zA-Z0-9_-]{10,}", "[redacted]", sanitized)
    if len(sanitized) > 200:
        sanitized = sanitized[:200] + "..."
    return ensure_utf8_text(sanitized)


def _runtime_resilience_cfg(loop: Any) -> Any:
    return getattr(loop, "runtime_resilience", None)


def _runtime_performance_cfg(loop: Any) -> Any:
    return getattr(loop, "runtime_performance", None)


def _runtime_observability_cfg(loop: Any) -> Any:
    return getattr(loop, "runtime_observability", None)


def _runtime_quotas_cfg(loop: Any) -> Any:
    return getattr(loop, "runtime_quotas", None)


def _should_skip_memory_persistence(msg: Any) -> bool:
    metadata = getattr(msg, "metadata", None)
    return bool(isinstance(metadata, dict) and metadata.get("probe_mode"))


_TOOL_RESULT_HARD_CAP_BY_CHANNEL: dict[str, int] = {
    "telegram": 8000,
    "whatsapp": 8000,
    "line": 9000,
    "discord": 12000,
    "slack": 12000,
    "feishu": 12000,
    "cli": 24000,
}
_TOOL_RESULT_HARD_CAP_DEFAULT = 16000
_TOOL_RESULT_HARD_CAP_BY_CHANNEL_HEMAT: dict[str, int] = {
    "telegram": 6000,
    "whatsapp": 6000,
    "line": 7000,
    "discord": 9000,
    "slack": 9000,
    "feishu": 9000,
    "cli": 18000,
}
_TOOL_RESULT_HARD_CAP_DEFAULT_HEMAT = 12000


def _resolve_token_mode(perf_cfg: Any) -> str:
    raw = str(
        getattr(perf_cfg, "token_mode", None)
        or getattr(perf_cfg, "economy_mode", None)
        or "boros"
    ).strip().lower()
    if raw in {"hemat", "economy", "eco", "saving", "enabled", "on", "true", "1"}:
        return "hemat"
    return "boros"


def _apply_channel_tool_result_hard_cap(
    content: str,
    *,
    channel: str | None,
    tool_name: str,
    token_mode: str = "boros",
) -> str:
    raw = str(content or "")
    channel_key = str(channel or "").strip().lower()
    if str(token_mode or "").strip().lower() == "hemat":
        cap = _TOOL_RESULT_HARD_CAP_BY_CHANNEL_HEMAT.get(channel_key, _TOOL_RESULT_HARD_CAP_DEFAULT_HEMAT)
    else:
        cap = _TOOL_RESULT_HARD_CAP_BY_CHANNEL.get(channel_key, _TOOL_RESULT_HARD_CAP_DEFAULT)
    if len(raw) <= cap:
        return raw

    removed = len(raw) - cap
    notice = (
        f"\n\n[... truncated {removed} chars for {str(channel or 'default').lower()} "
        f"tool-result budget ({tool_name}) ...]"
    )
    keep = max(0, cap - len(notice))
    if keep <= 0:
        return raw[:cap]
    return f"{raw[:keep]}{notice}"


def _redact_observability_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        key_l = str(key).lower()
        if any(token in key_l for token in ("token", "secret", "api_key", "apikey", "password")):
            redacted[key] = "[redacted]"
            continue
        redacted[key] = value
    return redacted


def _emit_runtime_event(loop: Any, event_name: str, **fields: Any) -> None:
    cfg = _runtime_observability_cfg(loop)
    if not cfg or not bool(getattr(cfg, "enabled", True)):
        return
    if not bool(getattr(cfg, "emit_structured_events", True)):
        return
    sample_rate = float(getattr(cfg, "sample_rate", 1.0))
    if sample_rate <= 0:
        return
    if sample_rate < 1.0 and random.random() > sample_rate:
        return

    payload: dict[str, Any] = {"event": event_name, **fields}
    if bool(getattr(cfg, "redact_secrets", True)):
        payload = _redact_observability_payload(payload)
    try:
        logger.info(f"runtime_event={json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}")
    except Exception:
        logger.info(f"runtime_event={payload}")


def _estimate_message_tokens(messages: list[dict[str, Any]]) -> int:
    try:
        serialized = json.dumps(messages, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        serialized = str(messages)
    return max(1, len(serialized) // 4)


def _quota_bucket(loop: Any) -> dict[str, Any]:
    usage = getattr(loop, "_quota_usage", None)
    if not isinstance(usage, dict):
        usage = {}
        setattr(loop, "_quota_usage", usage)
    now = time.time()
    current_hour = int(now // 3600)
    current_day = int(now // 86400)
    if usage.get("hour_bucket") != current_hour:
        usage["hour_bucket"] = current_hour
        usage["tokens_this_hour"] = 0
    if usage.get("day_bucket") != current_day:
        usage["day_bucket"] = current_day
        usage["cost_today_usd"] = 0.0
    usage.setdefault("tokens_this_hour", 0)
    usage.setdefault("cost_today_usd", 0.0)
    return usage


def _check_quota_guard(
    loop: Any,
    messages: list[dict[str, Any]],
    model: str,
    *,
    turn_id: str,
    attempt_index: int,
) -> tuple[bool, str | None]:
    quotas = _runtime_quotas_cfg(loop)
    if not quotas or not bool(getattr(quotas, "enabled", False)):
        return True, None

    mode = str(getattr(quotas, "enforcement_mode", "warn") or "warn").strip().lower()
    if mode not in {"warn", "hard"}:
        mode = "warn"
    max_tokens_per_hour = int(getattr(quotas, "max_tokens_per_hour", 0) or 0)
    max_cost_per_day = float(getattr(quotas, "max_cost_per_day_usd", 0.0) or 0.0)
    estimated_tokens = _estimate_message_tokens(messages)
    usage = _quota_bucket(loop)

    if max_tokens_per_hour > 0:
        projected = int(usage.get("tokens_this_hour", 0)) + estimated_tokens
        if projected > max_tokens_per_hour:
            message = (
                f"quota {mode}: max_tokens_per_hour exceeded "
                f"(projected={projected}, limit={max_tokens_per_hour}, model={model})"
            )
            _emit_runtime_event(
                loop,
                "quota_guard",
                turn_id=turn_id,
                attempt_index=attempt_index,
                model=model,
                scope="tokens_per_hour",
                mode=mode,
                projected=projected,
                limit=max_tokens_per_hour,
                blocked=(mode == "hard"),
            )
            if mode == "hard":
                return False, message
            return True, message

    if max_cost_per_day > 0:
        current_cost = float(usage.get("cost_today_usd", 0.0))
        if current_cost >= max_cost_per_day:
            message = (
                f"quota {mode}: max_cost_per_day_usd exceeded "
                f"(used={current_cost:.6f}, limit={max_cost_per_day:.6f}, model={model})"
            )
            _emit_runtime_event(
                loop,
                "quota_guard",
                turn_id=turn_id,
                attempt_index=attempt_index,
                model=model,
                scope="cost_per_day",
                mode=mode,
                used=current_cost,
                limit=max_cost_per_day,
                blocked=(mode == "hard"),
            )
            if mode == "hard":
                return False, message
            return True, message

    usage["tokens_this_hour"] = int(usage.get("tokens_this_hour", 0)) + estimated_tokens
    return True, None


def _apply_response_quota_usage(loop: Any, response: Any) -> None:
    usage_data = getattr(response, "usage", None) if response is not None else None

    if usage_data is not None:
        usage_module = str(getattr(type(usage_data), "__module__", "") or "")
        if asyncio.iscoroutine(usage_data) or usage_module.startswith("unittest.mock"):
            usage_data = None

    if usage_data is not None and not isinstance(usage_data, dict):
        dict_method = getattr(usage_data, "dict", None)
        if callable(dict_method) and not asyncio.iscoroutinefunction(dict_method):
            usage_data = dict_method()
        elif hasattr(usage_data, "__dict__"):
            usage_data = vars(usage_data)
        elif hasattr(usage_data, "prompt_tokens"):
            usage_data = {
                "prompt_tokens": getattr(usage_data, "prompt_tokens", 0),
                "completion_tokens": getattr(usage_data, "completion_tokens", 0),
                "total_tokens": getattr(usage_data, "total_tokens", 0),
            }
        else:
            usage_data = {}

    if isinstance(usage_data, dict):
        setattr(
            loop,
            "last_usage",
            {
                "prompt_tokens": int(usage_data.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(usage_data.get("completion_tokens", 0) or 0),
                "total_tokens": int(usage_data.get("total_tokens", 0) or 0),
                "model": getattr(response, "model", None) or getattr(loop, "last_model_used", None),
            },
        )

    quotas = _runtime_quotas_cfg(loop)
    if not quotas or not bool(getattr(quotas, "enabled", False)):
        return

    usage = _quota_bucket(loop)
    if isinstance(usage_data, dict):
        total_tokens = int(usage_data.get("total_tokens", 0) or 0)
        if total_tokens > 0:
            usage["tokens_this_hour"] = int(usage.get("tokens_this_hour", 0)) + total_tokens
        estimated_cost = usage_data.get("estimated_cost_usd")
        try:
            estimated_cost_val = float(estimated_cost)
        except Exception:
            estimated_cost_val = 0.0
        if estimated_cost_val > 0:
            usage["cost_today_usd"] = float(usage.get("cost_today_usd", 0.0)) + estimated_cost_val


def _extract_status_code(exc: Exception) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    text = str(exc)
    for token in (" 400 ", " 401 ", " 402 ", " 403 ", " 404 ", " 408 ", " 409 ", " 429 ", " 500 ", " 502 ", " 503 ", " 504 "):
        if token in text:
            try:
                return int(token.strip())
            except Exception:
                return None
    return None


def _classify_runtime_error(loop: Any, exc: Exception, status_code: int | None = None) -> str:
    msg = str(exc or "")
    msg_lower = msg.lower()
    status = status_code if isinstance(status_code, int) else _extract_status_code(exc)

    if "no tool call found for function call output" in msg_lower:
        return "tool_protocol"

    strict = bool(getattr(_runtime_resilience_cfg(loop), "strict_error_classification", True))
    if not strict:
        if status == 401:
            return "auth"
        if status == 429 or "rate" in msg_lower:
            return "rate_limit"
        if status in {500, 502, 503, 504}:
            return "transient"
        if status == 400:
            return "tool_protocol"
        return "fatal"

    reason = resolve_failover_reason(status=status, message=msg)
    if reason == "auth":
        return "auth"
    if reason == "rate_limit":
        return "rate_limit"
    if reason in {"timeout", "unknown"}:
        return "transient"
    if reason == "format":
        return "tool_protocol"
    return "fatal"
