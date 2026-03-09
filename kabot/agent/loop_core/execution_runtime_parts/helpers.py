"""Helper utilities extracted from execution_runtime."""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import re
import time
from typing import Any

from loguru import logger

from kabot.agent.cron_fallback_nlp import required_tool_for_query
from kabot.agent.tools.stock import (
    extract_crypto_ids,
    extract_stock_name_candidates,
    extract_stock_symbols,
)
from kabot.bus.events import InboundMessage
from kabot.core.failover_error import resolve_failover_reason
from kabot.utils.text_safety import ensure_utf8_text


def _sanitize_error(error_str: str) -> str:
    """Strip internal URLs, API keys, and verbose tracebacks from user-facing errors."""
    import re
    # Remove full URLs (internal API endpoints)
    sanitized = re.sub(r'https?://\S+', '[API endpoint]', error_str)
    # Remove anything that looks like an API key
    sanitized = re.sub(r'(sk-|key-|Bearer )[a-zA-Z0-9_-]{10,}', '[redacted]', sanitized)
    # Truncate excessively long messages
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


def _should_skip_memory_persistence(msg: InboundMessage) -> bool:
    metadata = getattr(msg, "metadata", None)
    return bool(isinstance(metadata, dict) and metadata.get("probe_mode"))


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _is_low_information_turn(text: str, *, max_tokens: int, max_chars: int) -> bool:
    raw_text = str(text or "")
    normalized = _normalize_text(raw_text)
    if not normalized:
        return False
    if normalized.startswith("/"):
        return False
    if "?" in raw_text:
        return False
    tokens = normalized.split()
    if len(tokens) == 0 or len(tokens) > max_tokens:
        return False
    if len(normalized) > max_chars:
        return False
    if not any(ch.isspace() for ch in raw_text):
        if re.search(r"[\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF\u0E00-\u0E7F\u0600-\u06FF]", raw_text):
            if len(raw_text) >= 5:
                return False
    if re.search(r"(https?://|www\.)", normalized):
        return False
    if re.search(r"[@#]\w+", normalized):
        return False
    if re.search(r"\d{3,}", normalized):
        return False
    if any(ch in raw_text for ch in "{}[]=`\\/"):
        return False
    return True


def _looks_like_short_confirmation(text: str) -> bool:
    return _is_low_information_turn(text, max_tokens=4, max_chars=40)


def _looks_like_live_research_query(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False

    live_markers = (
        "latest",
        "today",
        "now",
        "current",
        "breaking",
        "headline",
        "headlines",
        "news",
        "berita",
        "terbaru",
        "terkini",
        "sekarang",
    )
    if any(marker in normalized for marker in live_markers):
        return True
    if re.search(r"\b(news|berita)\s+update(s)?\b", normalized):
        return True
    if re.search(r"\b(19|20)\d{2}\b", normalized):
        news_context_markers = (
            "news",
            "berita",
            "headline",
            "headlines",
            "war",
            "conflict",
            "election",
            "market",
            "price",
            "update",
        )
        if any(marker in normalized for marker in news_context_markers):
            return True
    return False


_GUARDED_TOOL_CALLS = {
    "read_file",
    "web_search",
    "stock",
    "crypto",
    "cron",
    "weather",
    "get_system_info",
    "get_process_memory",
    "cleanup_system",
    "speedtest",
    "server_monitor",
    "check_update",
    "system_update",
}
_IMAGE_TOOL_NAME_RE = re.compile(
    r"(?i)(^|_)(image|img|picture|photo|illustration|art|draw|render|generate_image|image_gen)(_|$)"
)
_TTS_TOOL_NAME_RE = re.compile(
    r"(?i)(^|_)(tts|text_to_speech|speech|voice|speak|narrat|audio|say)(_|$)"
)
_REMINDER_MARKER_RE = re.compile(
    r"(?i)\b(remind|reminder|ingat|ingatkan|pengingat|jadwal|schedule|alarm|timer|cron)\b"
)
_REMINDER_STRUCTURE_RE = re.compile(
    r"(?i)(\b\d+\s*(menit|jam|detik|hari|min(?:ute)?s?|hour(?:s)?|sec(?:ond)?s?|day(?:s)?)\b|\b\d{1,2}(?::\d{2})\b)"
)
_FILELIKE_QUERY_RE = re.compile(
    r"\b[\w\-]+\.(json|ya?ml|toml|ini|cfg|conf|env|md|txt|csv|log|pdf|docx?|xlsx?|py|js|ts|tsx|jsx|html|css|xml)\b",
    re.IGNORECASE,
)
_PATHLIKE_QUERY_RE = re.compile(r"([a-zA-Z]:\\|\\\\|/[\w\-./]+|[\w\-./]+\\[\w\-./]+)")
_WEATHER_MARKER_RE = re.compile(
    r"(?i)\b(weather|temperature|forecast|cuaca|suhu|temperatur|prakiraan|ramalan)\b"
)
_IMAGE_MARKER_RE = re.compile(
    r"(?i)\b(image|gambar|photo|foto|picture|draw|sketch|illustrat(?:e|ion)|render|generate\s+image|buat(?:kan)?\s+gambar)\b"
)
_TTS_MARKER_RE = re.compile(
    r"(?i)\b(tts|text\s*to\s*speech|voice|suara|audio|narrat(?:e|ion)|bacakan|read\s+aloud|speak|ucapkan)\b"
)
_NON_ACTION_MARKER_RE = re.compile(
    r"(?i)\b(stop|hentikan|berhenti|jangan|bukan|dont|don't|do not|cancel|batalkan|ga usah|gak usah|nggak usah|tidak usah|no need)\b"
)
_NON_ACTION_STOCK_TOPIC_RE = re.compile(
    r"(?i)\b(stock|saham|ticker|market|harga|price|idx|ihsg)\b"
)
_SKILL_CREATION_GUARDED_TOOLS = {"write_file", "edit_file", "exec"}


def _tools_has(loop: Any, tool_name: str, *, default: bool = True) -> bool:
    tools_registry = getattr(loop, "tools", None)
    has_method = getattr(tools_registry, "has", None)
    if callable(has_method):
        try:
            return bool(has_method(tool_name))
        except Exception:
            return default
    return default


def _is_image_like_tool(tool_name: str) -> bool:
    normalized = str(tool_name or "").strip().lower()
    if not normalized:
        return False
    return bool(_IMAGE_TOOL_NAME_RE.search(normalized))


def _is_tts_like_tool(tool_name: str) -> bool:
    normalized = str(tool_name or "").strip().lower()
    if not normalized:
        return False
    return bool(_TTS_TOOL_NAME_RE.search(normalized))


def _resolve_query_text_from_message(msg: InboundMessage) -> str:
    metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
    effective = str(metadata.get("effective_content") or "").strip()
    if effective:
        return effective
    return str(msg.content or "").strip()


def _skill_creation_status_phase(message_metadata: dict[str, Any] | None) -> str | None:
    if not isinstance(message_metadata, dict):
        return None
    guard = message_metadata.get("skill_creation_guard")
    if not isinstance(guard, dict):
        return None
    if not bool(guard.get("active")):
        return None
    if bool(guard.get("approved")):
        return "executing"
    stage = str(guard.get("stage") or "discovery").strip().lower() or "discovery"
    if stage == "planning":
        return "planning"
    return "discovery"


def _resolve_expected_tool_for_query(loop: Any, msg: InboundMessage) -> str | None:
    metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
    cached_expected_tool = str(metadata.get("_expected_tool_for_guard") or "").strip()
    if cached_expected_tool:
        return cached_expected_tool

    explicit_required_tool = str(metadata.get("required_tool") or "").strip()
    if explicit_required_tool:
        metadata["_expected_tool_for_guard"] = explicit_required_tool
        return explicit_required_tool

    query_text = _resolve_query_text_from_message(msg)
    if not query_text:
        return None

    expected = required_tool_for_query(
        question=query_text,
        has_weather_tool=_tools_has(loop, "weather"),
        has_cron_tool=_tools_has(loop, "cron"),
        has_system_info_tool=_tools_has(loop, "get_system_info"),
        has_cleanup_tool=_tools_has(loop, "cleanup_system"),
        has_speedtest_tool=_tools_has(loop, "speedtest"),
        has_process_memory_tool=_tools_has(loop, "get_process_memory"),
        has_stock_tool=_tools_has(loop, "stock"),
        has_stock_analysis_tool=_tools_has(loop, "stock_analysis"),
        has_crypto_tool=_tools_has(loop, "crypto"),
        has_server_monitor_tool=_tools_has(loop, "server_monitor"),
        has_web_search_tool=_tools_has(loop, "web_search"),
        has_read_file_tool=_tools_has(loop, "read_file"),
        has_check_update_tool=_tools_has(loop, "check_update"),
        has_system_update_tool=_tools_has(loop, "system_update"),
    )
    if expected:
        metadata["_expected_tool_for_guard"] = expected
    return expected


def _query_has_explicit_payload_for_tool(tool_name: str, query_text: str) -> bool:
    normalized_tool = str(tool_name or "").strip().lower()
    text = str(query_text or "").strip()
    if not text:
        return False

    if normalized_tool in {"stock", "stock_analysis"}:
        symbols = extract_stock_symbols(text)
        if symbols:
            return True

        normalized = _normalize_text(text)
        if _NON_ACTION_MARKER_RE.search(normalized) and _NON_ACTION_STOCK_TOPIC_RE.search(normalized):
            return False

        if _FILELIKE_QUERY_RE.search(text) or _PATHLIKE_QUERY_RE.search(text):
            return False

        names = extract_stock_name_candidates(text)
        if not names:
            return False

        stock_markers = (
            "stock",
            "saham",
            "ticker",
            "quote",
            "harga",
            "price",
            "market",
            "idx",
            "ihsg",
        )
        value_markers = ("berapa", "how much", "nilai", "worth", "berapa rupiah")
        news_conflict_markers = (
            "berita",
            "news",
            "headline",
            "breaking",
            "war",
            "perang",
            "konflik",
            "conflict",
            "politik",
            "politic",
            "iran",
            "israel",
            "gaza",
            "ukraine",
            "russia",
            "amerika",
            "america",
            "usa",
        )
        if any(marker in normalized for marker in stock_markers):
            return True
        if any(marker in normalized for marker in news_conflict_markers):
            return False
        if any(marker in normalized for marker in value_markers):
            return True

        # Allow concise company-only asks from novice users ("adaro", "toyota").
        token_count = len([token for token in normalized.split(" ") if token])
        if token_count <= 3:
            return True
        return False
    if normalized_tool == "crypto":
        return bool(extract_crypto_ids(text))
    if normalized_tool == "cron":
        if _REMINDER_MARKER_RE.search(text):
            return True
        return bool(_REMINDER_STRUCTURE_RE.search(text))
    if normalized_tool == "weather":
        return bool(_WEATHER_MARKER_RE.search(text))
    if normalized_tool == "read_file":
        return bool(_FILELIKE_QUERY_RE.search(text) or _PATHLIKE_QUERY_RE.search(text))
    if normalized_tool == "web_search":
        normalized = _normalize_text(text)
        if len([part for part in normalized.split(" ") if part]) < 3:
            return False
        if _looks_like_live_research_query(text):
            return True
        search_markers = (
            "search",
            "find",
            "look up",
            "lookup",
            "cari",
            "carikan",
            "telusuri",
            "googling",
            "google",
            "browse",
            "berita",
            "news",
            "headline",
            "headlines",
            "latest",
            "terbaru",
            "update",
        )
        return any(marker in normalized for marker in search_markers)
    if _is_image_like_tool(normalized_tool):
        return bool(_IMAGE_MARKER_RE.search(text))
    if _is_tts_like_tool(normalized_tool):
        return bool(_TTS_MARKER_RE.search(text))
    # For guarded deterministic tools outside specialized parsers, require
    # router-level expected-tool agreement instead of permissive payload guess.
    return False


def _tool_call_intent_mismatch_reason(loop: Any, msg: InboundMessage, tool_name: str) -> str | None:
    normalized_tool = str(tool_name or "").strip().lower()
    is_guarded = (
        normalized_tool in _GUARDED_TOOL_CALLS
        or _is_image_like_tool(normalized_tool)
        or _is_tts_like_tool(normalized_tool)
    )
    if not is_guarded:
        return None

    query_text = _resolve_query_text_from_message(msg)
    expected_tool = _resolve_expected_tool_for_query(loop, msg)

    if expected_tool and expected_tool != normalized_tool:
        return f"expected '{expected_tool}'"
    if expected_tool and expected_tool == normalized_tool:
        # When runtime/router already pinned the required tool, trust that
        # decision so multilingual prompts are not blocked by lexical payload
        # heuristics (especially for web-search/news across non-Latin scripts).
        return None

    if _query_has_explicit_payload_for_tool(normalized_tool, query_text):
        return None

    if _is_low_information_turn(query_text, max_tokens=6, max_chars=64):
        return "low-information turn"

    return "missing explicit payload for current query"


def _skill_creation_guard_reason(msg: InboundMessage, tool_name: str) -> str | None:
    if str(tool_name or "").strip().lower() not in _SKILL_CREATION_GUARDED_TOOLS:
        return None
    metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
    guard = metadata.get("skill_creation_guard")
    if not isinstance(guard, dict):
        return None
    if not bool(guard.get("active")):
        return None
    if bool(guard.get("approved")):
        return None
    stage = str(guard.get("stage") or "discovery").strip().lower() or "discovery"
    if stage == "planning":
        return "skill plan not approved yet"
    return "skill discovery/planning still in progress"


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
    """Cheap token estimate for quota guardrail checks (char/4 heuristic)."""
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

    # LiteLLM returns Usage objects, not dicts. Convert to dict if possible.
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
                "total_tokens": getattr(usage_data, "total_tokens", 0)
            }
        else:
            usage_data = {}

    if isinstance(usage_data, dict):
        # Capture raw usage for persistence regardless of quota settings
        setattr(loop, "last_usage", {
            "prompt_tokens": int(usage_data.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage_data.get("completion_tokens", 0) or 0),
            "total_tokens": int(usage_data.get("total_tokens", 0) or 0),
            "model": getattr(response, "model", None) or getattr(loop, "last_model_used", None)
        })

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
    """Classify errors for deterministic fallback decisions."""
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
    # billing/model_not_found are fatal for current model but fallback can still continue.
    return "fatal"


def _prune_expiring_cache(cache: dict[str, tuple[float, str]]) -> None:
    now = time.time()
    expired = [key for key, (expires_at, _) in cache.items() if expires_at <= now]
    for key in expired:
        cache.pop(key, None)


def _stable_tool_payload_hash(
    session_key: str,
    turn_id: str,
    tool_name: str,
    tool_args: dict[str, Any],
) -> str:
    normalized_args = json.dumps(tool_args, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    raw = f"{session_key}|{turn_id}|{tool_name}|{normalized_args}"
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def _should_defer_memory_write(loop: Any) -> bool:
    perf_cfg = _runtime_performance_cfg(loop)
    if not perf_cfg:
        return False
    return bool(getattr(perf_cfg, "fast_first_response", True))


def _schedule_memory_write(loop: Any, coro: Any, *, label: str) -> None:
    task = asyncio.create_task(coro)
    pending = getattr(loop, "_pending_memory_tasks", None)
    if not isinstance(pending, set):
        pending = set()
        setattr(loop, "_pending_memory_tasks", pending)
    pending.add(task)

    def _done_callback(done_task: asyncio.Task) -> None:
        pending.discard(done_task)
        try:
            done_task.result()
        except asyncio.CancelledError:
            # Expected during shutdown when pending memory writes are cancelled.
            return
        except Exception as exc:
            logger.warning(f"Background memory write failed ({label}): {exc}")

    task.add_done_callback(_done_callback)
