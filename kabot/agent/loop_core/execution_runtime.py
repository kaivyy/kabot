"""Execution loop and tool-call runtime extracted from AgentLoop."""

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
from kabot.agent.fallback_i18n import t
from kabot.agent.tools.stock import (
    extract_crypto_ids,
    extract_stock_name_candidates,
    extract_stock_symbols,
)
from kabot.bus.events import InboundMessage, OutboundMessage
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
    if isinstance(usage_data, dict):
        # Capture raw usage for persistence regardless of quota settings
        setattr(loop, "last_usage", {
            "prompt_tokens": int(usage_data.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage_data.get("completion_tokens", 0) or 0),
            "total_tokens": int(usage_data.get("total_tokens", 0) or 0),
            "model": getattr(response, "model", None) or getattr(loop, "model", None)
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


async def run_simple_response(loop: Any, msg: InboundMessage, messages: list) -> str | None:
    """Direct single-shot response for simple queries (no loop, no tools)."""
    try:
        models_to_try = loop._resolve_models_for_message(msg)
        model = models_to_try[0]

        if loop.context_guard.check_overflow(messages, model):
            logger.warning("Context overflow detected in simple response, compacting history")
            messages = await loop.compactor.compact(
                messages, loop.provider, model, keep_recent=10
            )
            if loop.context_guard.check_overflow(messages, model):
                logger.warning("Context still over limit after compaction")

        response, error = await loop._call_llm_with_fallback(messages, models_to_try)
        if not response:
            error_hint = _sanitize_error(str(error)) if error else "unknown error"
            return (
                "An error occurred while processing your message.\n"
                f"Error: {error_hint}\n\n"
                "Hint: use /switch <model> to change model, or try again in a moment."
            )

        return response.content or ""
    except Exception as e:
        logger.error(f"Simple response failed: {e}")
        error_hint = _sanitize_error(str(e))
        return (
            "An error occurred while processing your message.\n"
            f"Error: {error_hint}\n\n"
            "Hint: use /switch <model> to change model, or try again in a moment."
        )


async def run_agent_loop(loop: Any, msg: InboundMessage, messages: list, session: Any) -> str | None:
    """Full planner-executor-critic loop for complex tasks."""
    iteration = 0

    message_metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
    models_to_try = loop._resolve_models_for_message(msg)
    model = models_to_try[0]

    self_eval_retried = False
    critic_retried = 0
    max_tool_retry = max(0, int(getattr(_runtime_resilience_cfg(loop), "max_tool_retry_per_turn", 1)))
    tool_enforcement_retries = 0
    status_updates_sent: set[str] = set()
    draft_updates_sent: set[str] = set()
    reasoning_updates_sent: set[str] = set()
    suppress_required_tool_inference = bool(message_metadata.get("suppress_required_tool_inference", False))
    required_tool = None if suppress_required_tool_inference else loop._required_tool_for_query(msg.content)
    raw_user_text = str(msg.content or "").strip()
    raw_user_word_count = len([part for part in raw_user_text.split() if part])
    effective_content = str(message_metadata.get("effective_content") or "").strip()
    question_text = effective_content or raw_user_text
    question_word_count = len([part for part in question_text.split() if part])
    route_profile = str(message_metadata.get("route_profile", "")).strip().upper()
    runtime_locale = str(message_metadata.get("runtime_locale") or "").strip() or None
    tools_registry = getattr(loop, "tools", None)
    has_tool = getattr(tools_registry, "has", None)
    resolved_required_tool = str(message_metadata.get("required_tool") or "").strip()
    if resolved_required_tool:
        if callable(has_tool):
            try:
                if has_tool(resolved_required_tool):
                    required_tool = resolved_required_tool
            except Exception:
                required_tool = resolved_required_tool
        else:
            required_tool = resolved_required_tool
    elif suppress_required_tool_inference:
        required_tool = None
    has_web_search_tool = False
    if callable(has_tool):
        try:
            has_web_search_tool = bool(has_tool("web_search"))
        except Exception:
            has_web_search_tool = False
    if not required_tool and has_web_search_tool and _looks_like_live_research_query(raw_user_text):
        required_tool = "web_search"
        logger.info("Live-research safety latch: forcing required_tool=web_search")
    if (
        not required_tool
        and route_profile == "RESEARCH"
        and has_web_search_tool
        and _looks_like_live_research_query(question_text)
    ):
        required_tool = "web_search"
        logger.info("Research route safety latch: forcing required_tool=web_search")
    # OpenClaw-like responsiveness: skip expensive critic retries for short/chat/required-tool turns.
    skip_critic_for_speed = (
        bool(message_metadata.get("skip_critic_for_speed", False))
        or
        bool(required_tool)
        or raw_user_word_count <= 12
        or question_word_count <= 10
        or _looks_like_short_confirmation(raw_user_text)
        or _looks_like_short_confirmation(question_text)
        or _looks_like_live_research_query(raw_user_text)
        or "[follow-up context]" in question_text.lower()
        or route_profile in {"CHAT", "RESEARCH"}
    )
    is_background_task = (
        (msg.channel or "").lower() == "system"
        or (msg.sender_id or "").lower() == "system"
        or (
            isinstance(msg.content, str)
            and msg.content.strip().lower().startswith("heartbeat task:")
        )
    )
    # Synthetic/system callbacks (cron completion, heartbeat, etc.) should not
    # trigger hard tool-enforcement loops from reminder/weather keywords inside
    # system-generated text.
    if is_background_task:
        required_tool = None
    tools_executed = False

    is_weak_model = loop._is_weak_model(model)
    max_critic_retries = 1 if is_weak_model else 2
    critic_threshold = 5 if is_weak_model else 7

    first_score = None
    skill_creation_phase = _skill_creation_status_phase(message_metadata)

    def _phase_text(phase: str) -> str:
        key = f"runtime.status.{phase}"
        fallback_map = {
            "thinking": "runtime.status.thinking",
            "discovery": "runtime.status.thinking",
            "planning": "runtime.status.thinking",
            "executing": "runtime.status.thinking",
            "verified": "runtime.status.done",
        }
        fallback = fallback_map.get(phase, key)
        translated = t(key, locale=runtime_locale, text=question_text)
        if translated == key and fallback != key:
            return t(fallback, locale=runtime_locale, text=question_text)
        return translated

    async def _publish_phase(phase: str) -> None:
        if is_background_task:
            return
        mutable_status_lane = message_metadata.get("status_mutable_lane")
        if (
            isinstance(mutable_status_lane, bool)
            and not mutable_status_lane
            and phase in {"thinking", "done", "error"}
        ):
            return
        if phase == "thinking" and bool(message_metadata.get("suppress_initial_thinking_status", False)):
            message_metadata["suppress_initial_thinking_status"] = False
            return
        bus = getattr(loop, "bus", None)
        publish = getattr(bus, "publish_outbound", None)
        if not callable(publish):
            return
        text = _phase_text(phase)
        dedupe_key = f"{phase}:{text}"
        if dedupe_key in status_updates_sent:
            return
        status_updates_sent.add(dedupe_key)
        try:
            await publish(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=text,
                    metadata={"type": "status_update", "phase": phase, "lane": "status"},
                )
            )
        except Exception:
            return

    async def _publish_draft(text: str, *, phase: str = "thinking") -> None:
        if is_background_task:
            return
        bus = getattr(loop, "bus", None)
        publish = getattr(bus, "publish_outbound", None)
        if not callable(publish):
            return
        normalized = ensure_utf8_text(text or "").strip()
        if not normalized:
            return
        # Keep draft previews short to avoid progress-message flooding.
        if len(normalized) > 600:
            normalized = normalized[:597].rstrip() + "..."
        dedupe_key = f"{phase}:{normalized}"
        if dedupe_key in draft_updates_sent:
            return
        draft_updates_sent.add(dedupe_key)
        try:
            await publish(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=normalized,
                    metadata={"type": "draft_update", "phase": phase, "lane": "partial"},
                )
            )
        except Exception:
            return

    async def _publish_reasoning(reasoning_text: str) -> None:
        if is_background_task:
            return
        bus = getattr(loop, "bus", None)
        publish = getattr(bus, "publish_outbound", None)
        if not callable(publish):
            return
        normalized = ensure_utf8_text(reasoning_text or "").strip()
        if not normalized:
            return
        if len(normalized) > 600:
            normalized = normalized[:597].rstrip() + "..."
        dedupe_key = normalized
        if dedupe_key in reasoning_updates_sent:
            return
        reasoning_updates_sent.add(dedupe_key)
        try:
            await publish(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=normalized,
                    metadata={"type": "reasoning_update", "phase": "thinking", "lane": "reasoning"},
                )
            )
        except Exception:
            return

    async def _return_with_phase(content: str, *, phase: str = "done") -> str:
        if phase == "done" and skill_creation_phase == "executing":
            phase = "verified"
        await _publish_phase(phase)
        return content

    await _publish_phase(skill_creation_phase or "thinking")

    # === FAST PATH: Execute deterministic tools directly, skip LLM tool-call step ===
    # This bypasses fragile tool-call protocols for deterministic intents.
    direct_tools = {
        "read_file",
        "list_dir",
        "get_process_memory",
        "get_system_info",
        "cleanup_system",
        "web_search",
        "weather",
        "speedtest",
        "stock",
        "crypto",
        "server_monitor",
        "check_update",
        "system_update",
    }
    raw_direct_tools = {
        "read_file",
        "list_dir",
        "cleanup_system",
        "get_process_memory",
        "web_search",
        "check_update",
        "system_update",
        "weather",
        "stock",
        "crypto",
    }
    if required_tool and required_tool in direct_tools:
        await _publish_phase("tool")
        direct_result = await loop._execute_required_tool_fallback(required_tool, msg)
        if direct_result is not None:
            logger.info(f"Direct tool execution (bypassed LLM tool-call): {required_tool}")
            metadata = getattr(msg, "metadata", None)
            summarize_file_analysis = bool(
                required_tool == "read_file"
                and isinstance(metadata, dict)
                and metadata.get("file_analysis_mode")
            )
            if required_tool in raw_direct_tools and not summarize_file_analysis:
                return await _return_with_phase(direct_result)
            # Read-only direct tools still get an LLM-formatted summary.
            summary_messages = messages + [
                {
                    "role": "user",
                    "content": (
                        f"[TOOL RESULT: {required_tool}]\n{direct_result}\n\n"
                        "Use this tool result to answer the user's actual request in a clear, friendly "
                        "response in the same language the user used. Do not ask the user to resend a "
                        "path or repeat the same file reference. Be concise and highlight the most "
                        "important information."
                    ),
                }
            ]
            try:
                summary_response = await loop.provider.chat(
                    messages=summary_messages,
                    model=model,
                )
                if summary_response and summary_response.content:
                    return await _return_with_phase(summary_response.content)
            except Exception as e:
                logger.warning(f"LLM summary failed for {required_tool}, returning raw result: {e}")
            # Fallback: return raw result if LLM still fails
            return await _return_with_phase(direct_result)
    # === END FAST PATH ===

    skip_plan_for_speed = (
        not is_background_task
        and (
        bool(required_tool)
        or raw_user_word_count <= 12
        or _looks_like_short_confirmation(raw_user_text)
        or route_profile in {"CHAT", "RESEARCH"}
        )
    )
    plan = None
    if not required_tool and not skip_plan_for_speed:
        plan = await loop._plan_task(question_text)
        if plan:
            messages.append({"role": "user", "content": f"[SYSTEM PLAN]\n{plan}\n\nNow execute this plan step by step."})
    else:
        if required_tool:
            logger.info(f"Skipping plan for immediate-action task: required_tool={required_tool}")
        else:
            logger.info("Skipping plan for speed: short/follow-up/research route")

    messages = loop._apply_think_mode(messages, session)

    while iteration < loop.max_iterations:
        iteration += 1

        if loop.context_guard.check_overflow(messages, model):
            logger.warning("Context overflow detected, compacting history")
            messages = await loop.compactor.compact(
                messages, loop.provider, model, keep_recent=10
            )
            if loop.context_guard.check_overflow(messages, model):
                logger.warning("Context still over limit after compaction")

        response, error = await loop._call_llm_with_fallback(messages, models_to_try)
        if not response:
            # User-friendly error: never expose raw exception / internal URLs
            error_hint = _sanitize_error(str(error)) if error else "unknown error"
            return await _return_with_phase(
                f"WARNING: All available AI models failed to respond.\n"
                f"Error: {error_hint}\n\n"
                f"Tip: Try /switch <model> to change model, or try again in a moment."
                ,
                phase="error",
            )

        if required_tool and response.has_tool_calls:
            if any(tc.name == required_tool for tc in response.tool_calls):
                required_tool = None
                tool_enforcement_retries = 0
            else:
                wrong_tools = ", ".join(tc.name for tc in response.tool_calls)
                if tool_enforcement_retries < max_tool_retry:
                    tool_enforcement_retries += 1
                    logger.warning(
                        f"Tool enforcement: expected '{required_tool}' but got other tools ({wrong_tools}) (iter {iteration})"
                    )
                    if response.content:
                        messages = loop.context.add_assistant_message(
                            messages, response.content, reasoning_content=response.reasoning_content
                        )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"SYSTEM: This request REQUIRES the '{required_tool}' tool. "
                                f"You called [{wrong_tools}] which is incorrect for this task. "
                                "Call the required tool now."
                            ),
                        }
                    )
                    continue

                fallback_result = await loop._execute_required_tool_fallback(required_tool, msg)
                if fallback_result is not None:
                    logger.warning(
                        f"Tool enforcement fallback executed for '{required_tool}' after wrong tool calls"
                    )
                    return await _return_with_phase(fallback_result)
        if response.has_tool_calls:
            tools_executed = True

        if required_tool and not response.has_tool_calls:
            if tool_enforcement_retries < max_tool_retry:
                tool_enforcement_retries += 1
                logger.warning(
                    f"Tool enforcement: expected '{required_tool}' but got text-only response (iter {iteration})"
                )
                if response.content:
                    messages = loop.context.add_assistant_message(
                        messages, response.content, reasoning_content=response.reasoning_content
                    )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"SYSTEM: For this request, you MUST call the '{required_tool}' tool now. "
                            "Do not answer from memory or estimation. Return a tool call."
                        ),
                    }
                )
                continue

            fallback_result = await loop._execute_required_tool_fallback(required_tool, msg)
            if fallback_result is not None:
                logger.warning(f"Tool enforcement fallback executed for '{required_tool}'")
                return await _return_with_phase(fallback_result)

        if response.has_tool_calls:
            await _publish_phase("tool")

        if response.content:
            if response.reasoning_content:
                await _publish_reasoning(response.reasoning_content)
            if not response.has_tool_calls and not self_eval_retried and not is_background_task:
                passed, nudge = loop._self_evaluate(question_text, response.content)
                if not passed and nudge:
                    self_eval_retried = True
                    logger.warning(f"Self-eval: refusal detected, retrying (iter {iteration})")
                    await _publish_draft(response.content, phase="thinking")
                    messages = loop.context.add_assistant_message(messages, response.content, reasoning_content=response.reasoning_content)
                    messages.append({"role": "user", "content": nudge})
                    continue

            if (
                not response.has_tool_calls
                and critic_retried < max_critic_retries
                and not is_weak_model
                and not tools_executed
                and not is_background_task
                and not skip_critic_for_speed
            ):
                score, feedback = await loop._critic_evaluate(question_text, response.content, model)
                if first_score is None:
                    first_score = score

                if score < critic_threshold and critic_retried < max_critic_retries:
                    critic_retried += 1
                    logger.warning(
                        f"Critic: score {score}/10 (threshold: {critic_threshold}), retrying ({critic_retried}/{max_critic_retries})"
                    )
                    await _publish_draft(response.content, phase="thinking")
                    messages = loop.context.add_assistant_message(messages, response.content, reasoning_content=response.reasoning_content)
                    messages.append({"role": "user", "content": (
                        f"[CRITIC FEEDBACK - Score: {score}/10]\n{feedback}\n\n"
                        f"Please improve your response based on this feedback."
                    )})
                    continue
                else:
                    if critic_retried > 0:
                        await loop._log_lesson(
                            question=question_text,
                            feedback=feedback,
                            score_before=first_score or 0,
                            score_after=score,
                        )

            messages = loop.context.add_assistant_message(messages, response.content, reasoning_content=response.reasoning_content)
            if not response.has_tool_calls:
                return await _return_with_phase(response.content)

        if response.has_tool_calls:
            messages = await loop._process_tool_calls(msg, messages, response, session)
        else:
            return await _return_with_phase(response.content)
    return await _return_with_phase("I've completed processing but have no response to give.")


async def call_llm_with_fallback(loop: Any, messages: list, models: list) -> tuple[Any | None, Exception | None]:
    """Call provider with deterministic, bounded fallback state machine."""
    if not models:
        return None, RuntimeError("No models configured")

    resilience_cfg = _runtime_resilience_cfg(loop)
    max_attempts_cfg = int(getattr(resilience_cfg, "max_model_attempts_per_turn", 4))
    max_attempts = max(1, min(len(models), max_attempts_cfg))

    chain_snapshot = tuple(models)
    turn_id = str(getattr(loop, "_active_turn_id", "turn-unknown"))
    last_error: Exception | None = None

    def _provider_response_is_error(response: Any) -> bool:
        """Detect provider-level synthetic error payloads that should trigger model fallback."""
        finish_reason = str(getattr(response, "finish_reason", "") or "").lower()
        if finish_reason == "error":
            return True
        content = str(getattr(response, "content", "") or "")
        return content.startswith("All models failed. Last error:")

    async def _chat_single_model(model_name: str, *, include_tools: bool) -> Any:
        """
        Execute provider call for one explicit model only.

        Runtime already owns model fallback order; provider-level fallback chain
        is temporarily disabled to avoid double-fallback ambiguity and misleading
        observability (e.g., primary logs "success" while fallback actually answered).
        """
        provider = loop.provider
        restore_fallbacks: list[str] | None = None
        current_fallbacks = getattr(provider, "fallbacks", None)
        if isinstance(current_fallbacks, list):
            restore_fallbacks = list(current_fallbacks)
            provider.fallbacks = []
        try:
            kwargs: dict[str, Any] = {
                "messages": messages,
                "model": model_name,
            }
            if include_tools:
                kwargs["tools"] = loop.tools.get_definitions()
            return await provider.chat(**kwargs)
        finally:
            if restore_fallbacks is not None:
                provider.fallbacks = restore_fallbacks

    for attempt_idx, current_model in enumerate(chain_snapshot[:max_attempts], start=1):
        state = "primary" if attempt_idx == 1 else "model_fallback"
        original_key = None
        _emit_runtime_event(
            loop,
            "llm_attempt",
            turn_id=turn_id,
            model_chain=list(chain_snapshot),
            attempt_index=attempt_idx,
            model=current_model,
            state=state,
        )

        allowed_by_quota, quota_message = _check_quota_guard(
            loop,
            messages,
            current_model,
            turn_id=turn_id,
            attempt_index=attempt_idx,
        )
        if quota_message:
            logger.warning(quota_message)
        if not allowed_by_quota:
            return None, RuntimeError(f"Quota exceeded: {quota_message}")

        if loop.auth_rotation and hasattr(loop.provider, "api_key"):
            current_key = loop.auth_rotation.current_key()
            original_key = loop.provider.api_key
            loop.provider.api_key = current_key

        try:
            response = await _chat_single_model(current_model, include_tools=True)
            if _provider_response_is_error(response):
                raise RuntimeError(str(getattr(response, "content", "Provider returned error response")))
            if original_key is not None:
                loop.provider.api_key = original_key

            loop.last_model_used = current_model
            loop.last_fallback_used = bool(current_model != chain_snapshot[0])
            loop.last_model_chain = list(chain_snapshot)
            _apply_response_quota_usage(loop, response)
            if hasattr(loop, "resilience"):
                loop.resilience.on_success()
            logger.info(
                f"turn_id={turn_id} attempt={attempt_idx}/{max_attempts} state={state} "
                f"model={current_model} result=success"
            )
            _emit_runtime_event(
                loop,
                "llm_attempt_result",
                turn_id=turn_id,
                model_chain=list(chain_snapshot),
                attempt_index=attempt_idx,
                model=current_model,
                state=state,
                result="success",
                error_class="",
            )
            return response, None
        except Exception as exc:
            if original_key is not None:
                loop.provider.api_key = original_key

            status_code = _extract_status_code(exc)
            error_class = _classify_runtime_error(loop, exc, status_code=status_code)
            last_error = exc
            logger.warning(
                f"turn_id={turn_id} attempt={attempt_idx}/{max_attempts} state={state} "
                f"model={current_model} class={error_class} error={exc}"
            )
            _emit_runtime_event(
                loop,
                "llm_attempt_result",
                turn_id=turn_id,
                model_chain=list(chain_snapshot),
                attempt_index=attempt_idx,
                model=current_model,
                state=state,
                result="error",
                error_class=error_class,
            )

            # State: auth_rotate (one attempt on same model with rotated key)
            if (
                loop.auth_rotation
                and hasattr(loop.provider, "api_key")
                and error_class in {"auth", "rate_limit"}
            ):
                current_key = loop.auth_rotation.current_key()
                reason = "rate_limit" if error_class == "rate_limit" else "auth_error"
                loop.auth_rotation.mark_failed(current_key, reason)
                next_key = loop.auth_rotation.rotate()
                if next_key and next_key != current_key:
                    try:
                        state = "auth_rotate"
                        original_key = loop.provider.api_key
                        loop.provider.api_key = next_key
                        logger.info(
                            f"turn_id={turn_id} attempt={attempt_idx}/{max_attempts} "
                            f"state={state} model={current_model} reason={reason}"
                        )
                        response = await _chat_single_model(current_model, include_tools=True)
                        if _provider_response_is_error(response):
                            raise RuntimeError(str(getattr(response, "content", "Provider returned error response")))
                        loop.provider.api_key = original_key
                        loop.last_model_used = current_model
                        loop.last_fallback_used = bool(current_model != chain_snapshot[0])
                        loop.last_model_chain = list(chain_snapshot)
                        if hasattr(loop, "resilience"):
                            loop.resilience.on_success()
                        return response, None
                    except Exception as rotate_exc:
                        if original_key is not None:
                            loop.provider.api_key = original_key
                        last_error = rotate_exc
                        status_code = _extract_status_code(rotate_exc)
                        error_class = _classify_runtime_error(loop, rotate_exc, status_code=status_code)
                        logger.warning(
                            f"turn_id={turn_id} attempt={attempt_idx}/{max_attempts} state=auth_rotate "
                            f"model={current_model} class={error_class} error={rotate_exc}"
                        )

            # State: text_only_retry (tool protocol mismatch only).
            if error_class == "tool_protocol":
                try:
                    logger.warning(
                        f"turn_id={turn_id} attempt={attempt_idx}/{max_attempts} "
                        f"state=text_only_retry model={current_model}"
                    )
                    response = await _chat_single_model(current_model, include_tools=False)
                    if _provider_response_is_error(response):
                        raise RuntimeError(str(getattr(response, "content", "Provider returned error response")))
                    loop.last_model_used = current_model
                    loop.last_fallback_used = bool(current_model != chain_snapshot[0])
                    loop.last_model_chain = list(chain_snapshot)
                    if hasattr(loop, "resilience"):
                        loop.resilience.on_success()
                    return response, None
                except Exception as text_only_exc:
                    last_error = text_only_exc
                    logger.warning(
                        f"turn_id={turn_id} attempt={attempt_idx}/{max_attempts} state=text_only_retry "
                        f"model={current_model} class={_classify_runtime_error(loop, text_only_exc)} "
                        f"error={text_only_exc}"
                    )

            if hasattr(loop, "resilience"):
                try:
                    await loop.resilience.handle_error(exc, status_code=status_code)
                except Exception:
                    pass

            # Continue to next model in immutable snapshot.
            continue

    loop.last_model_chain = list(chain_snapshot)
    return None, last_error


async def process_tool_calls(loop: Any, msg: InboundMessage, messages: list, response: Any, session: Any) -> list:
    """Execute tool calls and append results to conversation context."""
    resilience_cfg = _runtime_resilience_cfg(loop)
    dedupe_enabled = bool(getattr(resilience_cfg, "dedupe_tool_calls", True))
    ttl_seconds = max(30, int(getattr(resilience_cfg, "idempotency_ttl_seconds", 600)))
    turn_id = str(getattr(loop, "_active_turn_id", f"{msg.session_key}:{int(msg.timestamp.timestamp() * 1000)}"))

    payload_cache = getattr(loop, "_tool_payload_cache", None)
    if not isinstance(payload_cache, dict):
        payload_cache = {}
        setattr(loop, "_tool_payload_cache", payload_cache)

    call_id_cache = getattr(loop, "_tool_call_id_cache", None)
    if not isinstance(call_id_cache, dict):
        call_id_cache = {}
        setattr(loop, "_tool_call_id_cache", call_id_cache)

    if dedupe_enabled:
        _prune_expiring_cache(payload_cache)
        _prune_expiring_cache(call_id_cache)

    tool_call_dicts = [
        {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
        for tc in response.tool_calls
    ]
    if response.content:
        # Keep tool_calls attached to assistant messages even when content exists.
        # Without this, tool outputs can become orphaned in history and codex
        # backend may reject the request with "No tool call found ...".
        attached_to_last = False
        if messages and isinstance(messages[-1], dict):
            last = messages[-1]
            last_tool_ids = {
                str(tc.get("id"))
                for tc in (last.get("tool_calls") or [])
                if isinstance(tc, dict) and tc.get("id")
            }
            current_ids = {str(tc.get("id")) for tc in tool_call_dicts if tc.get("id")}
            if (
                last.get("role") == "assistant"
                and str(last.get("content", "")) == str(response.content or "")
                and current_ids
                and current_ids.issubset(last_tool_ids)
            ):
                attached_to_last = True
            elif (
                last.get("role") == "assistant"
                and "tool_calls" not in last
                and str(last.get("content", "")) == str(response.content or "")
            ):
                last["tool_calls"] = tool_call_dicts
                if response.reasoning_content and not last.get("reasoning_content"):
                    last["reasoning_content"] = response.reasoning_content
                attached_to_last = True

        if not attached_to_last:
            messages = loop.context.add_assistant_message(
                messages,
                response.content,
                tool_call_dicts,
                reasoning_content=response.reasoning_content,
            )
    else:
        messages = loop.context.add_assistant_message(
            messages, None, tool_call_dicts, reasoning_content=response.reasoning_content
        )

    tc_data = [{"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in response.tool_calls]
    if not _should_skip_memory_persistence(msg):
        if _should_defer_memory_write(loop):
            _schedule_memory_write(
                loop,
                loop.memory.add_message(msg.session_key, "assistant", response.content or "", tool_calls=tc_data),
                label="tool-assistant-envelope",
            )
        else:
            await loop.memory.add_message(msg.session_key, "assistant", response.content or "", tool_calls=tc_data)

    permissions = loop._get_tool_permissions(session)
    if permissions.get("auto_approve") or loop.exec_auto_approve:
        logger.debug("Elevated mode active: auto_approve=True, restrict_to_workspace=False")

    exec_tool = loop.tools.get("exec")
    if exec_tool and hasattr(exec_tool, "auto_approve"):
        exec_tool.auto_approve = bool(
            loop.exec_auto_approve or permissions.get("auto_approve", False)
        )

    sent_status_updates: set[str] = set()
    token_mode = _resolve_token_mode(_runtime_performance_cfg(loop))
    for tc in response.tool_calls:
        args_raw = tc.arguments
        tool_params = args_raw if isinstance(args_raw, dict) else {}

        payload_key = _stable_tool_payload_hash(
            session_key=msg.session_key,
            turn_id=turn_id,
            tool_name=tc.name,
            tool_args=tool_params,
        )
        if dedupe_enabled and tc.id in call_id_cache:
            _, cached_result = call_id_cache[tc.id]
            logger.warning(
                f"tool_idempotency_hit=1 reason=tool_call_id_replay tool={tc.name} "
                f"tool_call_id={tc.id} turn_id={turn_id}"
            )
            _emit_runtime_event(
                loop,
                "tool_idempotency_hit",
                turn_id=turn_id,
                tool_name=tc.name,
                tool_call_id=tc.id,
                reason="tool_call_id_replay",
                tool_idempotency_hit=1,
            )
            # Prevent duplicate function_call_output entries for the same call_id.
            # Duplicate outputs can trigger backend validation errors in strict
            # tool-call protocols ("No tool call found ..." for replayed output).
            has_existing_output = any(
                isinstance(existing, dict)
                and existing.get("role") == "tool"
                and str(existing.get("tool_call_id", "")) == str(tc.id)
                for existing in messages
            )
            if not has_existing_output:
                messages = loop.context.add_tool_result(messages, tc.id, tc.name, cached_result)
            continue
        if dedupe_enabled and payload_key in payload_cache:
            _, cached_result = payload_cache[payload_key]
            expires_at = time.time() + ttl_seconds
            call_id_cache[tc.id] = (expires_at, cached_result)
            logger.warning(
                f"tool_idempotency_hit=1 reason=payload_duplicate tool={tc.name} "
                f"tool_call_id={tc.id} turn_id={turn_id}"
            )
            _emit_runtime_event(
                loop,
                "tool_idempotency_hit",
                turn_id=turn_id,
                tool_name=tc.name,
                tool_call_id=tc.id,
                reason="payload_duplicate",
                tool_idempotency_hit=1,
            )
            messages = loop.context.add_tool_result(messages, tc.id, tc.name, cached_result)
            continue

        skill_creation_guard_reason = _skill_creation_guard_reason(msg, tc.name)
        if skill_creation_guard_reason:
            blocked_result = (
                "TOOL_CALL_BLOCKED_SKILL_CREATION_APPROVAL: "
                f"'{tc.name}' blocked ({skill_creation_guard_reason}). "
                "Stay in discovery/planning mode, present a short implementation plan, and wait for explicit approval before writing files or running code."
            )
            if loop._should_log_verbose(session):
                token_count = loop.truncator._count_tokens(blocked_result)
                blocked_result = loop._format_verbose_output(
                    tc.name,
                    blocked_result,
                    token_count,
                )
            logger.warning(
                f"tool_call_blocked=1 tool={tc.name} reason={skill_creation_guard_reason} "
                f"turn_id={turn_id} chat_id={msg.chat_id}"
            )
            result_for_llm = loop._format_tool_result(blocked_result)
            result_for_llm = _apply_channel_tool_result_hard_cap(
                result_for_llm,
                channel=msg.channel,
                tool_name=tc.name,
                token_mode=token_mode,
            )
            messages = loop.context.add_tool_result(messages, tc.id, tc.name, result_for_llm)
            if dedupe_enabled:
                expires_at = time.time() + ttl_seconds
                payload_cache[payload_key] = (expires_at, result_for_llm)
                call_id_cache[tc.id] = (expires_at, result_for_llm)
            if not _should_skip_memory_persistence(msg):
                if _should_defer_memory_write(loop):
                    _schedule_memory_write(
                        loop,
                        loop.memory.add_message(
                            msg.session_key,
                            "tool",
                            blocked_result,
                            tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": blocked_result[:1000]}],
                        ),
                        label="tool-blocked-skill-creation",
                    )
                else:
                    await loop.memory.add_message(
                        msg.session_key,
                        "tool",
                        blocked_result,
                        tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": blocked_result[:1000]}],
                    )
            continue

        mismatch_reason = _tool_call_intent_mismatch_reason(loop, msg, tc.name)
        if mismatch_reason:
            blocked_result = (
                "TOOL_CALL_BLOCKED_INTENT_MISMATCH: "
                f"'{tc.name}' blocked ({mismatch_reason}). "
                "Re-evaluate current user intent and choose the correct tool or respond without tool calls."
            )
            if loop._should_log_verbose(session):
                token_count = loop.truncator._count_tokens(blocked_result)
                blocked_result = loop._format_verbose_output(
                    tc.name,
                    blocked_result,
                    token_count,
                )
            logger.warning(
                f"tool_call_blocked=1 tool={tc.name} reason={mismatch_reason} "
                f"turn_id={turn_id} chat_id={msg.chat_id}"
            )
            result_for_llm = loop._format_tool_result(blocked_result)
            result_for_llm = _apply_channel_tool_result_hard_cap(
                result_for_llm,
                channel=msg.channel,
                tool_name=tc.name,
                token_mode=token_mode,
            )
            messages = loop.context.add_tool_result(messages, tc.id, tc.name, result_for_llm)
            if dedupe_enabled:
                expires_at = time.time() + ttl_seconds
                payload_cache[payload_key] = (expires_at, result_for_llm)
                call_id_cache[tc.id] = (expires_at, result_for_llm)
            if not _should_skip_memory_persistence(msg):
                if _should_defer_memory_write(loop):
                    _schedule_memory_write(
                        loop,
                        loop.memory.add_message(
                            msg.session_key,
                            "tool",
                            blocked_result,
                            tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": blocked_result[:1000]}],
                        ),
                        label="tool-blocked",
                    )
                else:
                    await loop.memory.add_message(
                        msg.session_key,
                        "tool",
                        blocked_result,
                        tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": blocked_result[:1000]}],
                    )
            continue

        # Check for tool loops before execution
        loop_result = loop.loop_detector.check(tc.name, tool_params)
        if loop_result.stuck:
            if loop_result.level == "critical":
                # Block execution and return error
                error_msg = f"WARNING: Tool loop detected: {loop_result.message}"
                logger.warning(f"Tool loop blocked: {tc.name} - {loop_result.message}")
                messages = loop.context.add_tool_result(messages, tc.id, tc.name, error_msg)
                if not _should_skip_memory_persistence(msg):
                    if _should_defer_memory_write(loop):
                        _schedule_memory_write(
                            loop,
                            loop.memory.add_message(
                                msg.session_key,
                                "tool",
                                error_msg,
                                tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": error_msg}],
                            ),
                            label="tool-loop-block",
                        )
                    else:
                        await loop.memory.add_message(
                            msg.session_key, "tool", error_msg,
                            tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": error_msg}],
                        )
                continue
            else:
                # Warning level - log but allow execution
                logger.warning(f"Tool loop warning: {tc.name} - {loop_result.message}")

        status = loop._get_tool_status_message(tc.name, tool_params)
        if status and status not in sent_status_updates:
            sent_status_updates.add(status)
            await loop.bus.publish_outbound(OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=f"_{status}_",
                metadata={"type": "status_update", "phase": "tool", "lane": "status"},
            ))

        if tc.name == "weather":
            tool_params.setdefault("context_text", msg.content)
        if tc.name == "cron":
            tool_params.setdefault("context_text", msg.content)
        if tc.name == "exec":
            tool_params["_session_key"] = msg.session_key
            tool_params["_channel"] = msg.channel
            tool_params["_chat_id"] = msg.chat_id
            tool_params["_agent_id"] = loop._resolve_agent_id_for_message(msg)
            tool_params["_account_id"] = msg.account_id or ""
            tool_params["_thread_id"] = msg.thread_id or ""
            tool_params["_peer_kind"] = msg.peer_kind or ""
            tool_params["_peer_id"] = msg.peer_id or ""

        result = await loop.tools.execute(tc.name, tool_params)

        # Record tool call for loop detection
        loop.loop_detector.record(tc.name, tool_params, tc.id)
        result_str = str(result)
        truncated_result = loop.truncator.truncate(result_str, tc.name)

        if loop._should_log_verbose(session):
            token_count = loop.truncator._count_tokens(result_str)
            verbose_output = loop._format_verbose_output(tc.name, result_str, token_count)
            truncated_result += verbose_output

        result_for_llm = loop._format_tool_result(truncated_result)
        result_for_llm = _apply_channel_tool_result_hard_cap(
            result_for_llm,
            channel=msg.channel,
            tool_name=tc.name,
            token_mode=token_mode,
        )
        messages = loop.context.add_tool_result(messages, tc.id, tc.name, result_for_llm)
        if dedupe_enabled:
            expires_at = time.time() + ttl_seconds
            payload_cache[payload_key] = (expires_at, result_for_llm)
            call_id_cache[tc.id] = (expires_at, result_for_llm)

        if not _should_skip_memory_persistence(msg):
            if _should_defer_memory_write(loop):
                _schedule_memory_write(
                    loop,
                    loop.memory.add_message(
                        msg.session_key, "tool", str(result),
                        tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": str(result)[:1000]}],
                    ),
                    label="tool-result",
                )
            else:
                await loop.memory.add_message(
                    msg.session_key, "tool", str(result),
                    tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": str(result)[:1000]}],
                )
    return messages


def format_tool_result(loop: Any, result: Any) -> str:
    """Format tool result for LLM context."""
    return str(result)
