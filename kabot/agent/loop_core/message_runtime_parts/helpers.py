"""Helper utilities extracted from message_runtime."""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from kabot.bus.events import InboundMessage
from kabot.i18n.locale import detect_locale


def _runtime_observability_cfg(loop: Any) -> Any:
    return getattr(loop, "runtime_observability", None)


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
    payload = {"event": event_name, **fields}
    try:
        logger.info(f"runtime_event={json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}")
    except Exception:
        logger.info(f"runtime_event={payload}")


def _is_probe_mode_message(msg: InboundMessage) -> bool:
    metadata = getattr(msg, "metadata", None)
    return bool(isinstance(metadata, dict) and metadata.get("probe_mode"))


def _should_persist_probe_history(msg: InboundMessage) -> bool:
    metadata = getattr(msg, "metadata", None)
    return bool(isinstance(metadata, dict) and metadata.get("persist_history"))


from kabot.agent.loop_core.message_runtime_parts.followup import (  # noqa: E402,I001
    _ABORT_REQUEST_TRIGGERS,
    _FILELIKE_EXTENSION_RE,
    _FILESYSTEM_LOCATION_QUERY_PATTERNS,
    _FILE_CONTEXT_FOLLOWUP_MARKERS,
    _KEEPALIVE_INTERVAL_SECONDS,
    _KEEPALIVE_INITIAL_DELAY_SECONDS,
    _KEEPALIVE_PASSTHROUGH_CHANNELS,
    _MUTABLE_STATUS_LANE_CHANNELS,
    _NON_ACTION_FOLLOWUP_MARKERS,
    _NON_ACTION_TOPIC_MARKERS,
    _PATHLIKE_TEXT_RE,
    _RUNTIME_META_FEEDBACK_MARKERS,
    _SHORT_INTERROGATIVE_RE,
    _SKILL_CREATION_APPROVAL_MARKERS,
    _SKILL_CREATION_FLOW_KEY,
    _SKILL_CREATION_FLOW_TTL_SECONDS,
    _TRAILING_ABORT_PUNCT_RE,
    _WEATHER_CONTEXT_FOLLOWUP_MARKERS,
    _clear_pending_followup_intent,
    _clear_pending_followup_tool,
    _get_last_tool_execution,
    _get_last_tool_context,
    _get_pending_followup_intent,
    _get_pending_followup_tool,
    _set_last_tool_context,
    _set_pending_followup_intent,
    _set_pending_followup_tool,
)
from kabot.agent.loop_core.message_runtime_parts.user_profile import (  # noqa: E402,I001
    build_user_profile_memory_facts,
    looks_like_self_identity_recall,
)
from kabot.agent.tools.stock import (  # noqa: E402,I001
    extract_crypto_ids,
    extract_stock_symbols,
)

__all__ = [
    "_KEEPALIVE_INITIAL_DELAY_SECONDS",
    "_KEEPALIVE_INTERVAL_SECONDS",
    "_build_temporal_context_note",
    "_build_grounded_filesystem_inspection_note",
    "_build_session_continuity_action_note",
    "_classify_assistant_followup_intent_kind",
    "_clear_pending_followup_intent",
    "_clear_pending_followup_tool",
    "_extract_explicit_mcp_tool_name",
    "_extract_assistant_followup_offer_text",
    "_extract_option_selection_reference",
    "_extract_referenced_answer_item",
    "_infer_recent_assistant_option_prompt_from_history",
    "_infer_recent_assistant_answer_from_history",
    "_infer_recent_created_skill_name_from_path",
    "_extract_user_supplied_option_prompt_text",
    "_get_last_tool_execution",
    "_get_last_tool_context",
    "_get_pending_followup_intent",
    "_get_pending_followup_tool",
    "_looks_like_answer_reference_followup",
    "_looks_like_assistant_offer_context_followup",
    "_looks_like_coding_build_request",
    "_looks_like_contextual_followup_request",
    "_looks_like_existing_skill_use_followup",
    "_looks_like_skill_workflow_followup_detail",
    "_looks_like_web_search_demotion_followup",
    "_looks_like_memory_recall_turn",
    "_resolve_relevant_memory_facts",
    "_looks_like_message_delivery_request",
    "_looks_like_side_effect_request",
    "_normalize_text",
    "_resolve_runtime_locale",
    "_set_last_tool_context",
    "_set_pending_followup_intent",
    "_set_pending_followup_tool",
]

_EXPLICIT_MCP_TOOL_ALIAS_RE = re.compile(r"\bmcp\.([A-Za-z0-9_-]+)\.([A-Za-z0-9_.-]+)\b")


def _extract_read_file_path_proxy(text: str) -> str:
    from kabot.agent.loop_core import message_runtime as message_runtime_module

    return message_runtime_module._extract_read_file_path(text)


def _build_skill_creation_workflow_note(
    *,
    first_turn: bool,
    approved: bool = False,
    kind: str = "create",
) -> str:
    workflow_subject = (
        "installing or updating an external Kabot skill"
        if kind == "install"
        else "creating or updating a Kabot skill/capability"
    )
    if approved:
        return (
            "[Skill Workflow]\n"
            f"- The user has explicitly approved the plan for {workflow_subject} in this conversation.\n"
            "- Understand the user's language and answer in that language unless they explicitly ask for a different language.\n"
            "- You may now execute the approved plan, write files if needed, and run focused verification for the approved scope.\n"
            "- Prefer the bundled skill-creator helpers when they fit: scaffold with `scripts/init_skill.py`, validate with `scripts/quick_validate.py`, and package with `scripts/package_skill.py` when distribution matters.\n"
            "- If this is an API-backed skill, keep the implementation grounded in the real endpoint/auth/request/response examples already established in the conversation.\n"
            "- Keep the implementation inside the workspace skills directory unless the user asked for a different target.\n"
            "- Never hardcode API keys or secrets; use env/config requirements instead.\n"
            "- Before calling the skill done, verify the created files and any new scripts."
        )
    if first_turn:
        return (
            "[Skill Workflow]\n"
            f"- This request is for {workflow_subject}.\n"
            "- Understand the user's language and answer in that language unless they explicitly ask for a different language.\n"
            "- Do not create files yet.\n"
            "- Stay in discovery mode on this turn: ask only the minimum questions needed about scope, source/target, auth/dependencies, and trust/overwrite implications.\n"
            "- Try to ground the design in one or two concrete trigger/output examples before planning.\n"
            "- For API skills, capture the real endpoint/auth/request/response shape first; use any JSON, payload, or error sample the user already gave as the starting source of truth.\n"
            "- Do not claim the work is already being executed yet."
        )
    return (
        "[Skill Workflow]\n"
        "- Stay in skill-workflow mode unless the user clearly changes topic.\n"
        "- Understand the user's language and answer in that language unless they explicitly ask for a different language.\n"
        "- Do not create or modify files until the user explicitly approves a written plan in this conversation.\n"
        "- If requirements are still incomplete, continue discovery with concise follow-up questions.\n"
        "- If requirements are complete but no plan has been approved yet, present a short implementation plan and ask for approval.\n"
        "- For API skills, the plan should name the endpoint/auth/request/response shape and which parts will live in `SKILL.md`, `references/`, `scripts/`, or `assets/`.\n"
        "- Only after explicit approval may you scaffold files, write code, or run verification."
    )


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _normalized_contains_marker(text: str, marker: str) -> bool:
    normalized_text = str(text or "")
    normalized_marker = str(marker or "").strip().lower()
    if not normalized_text or not normalized_marker:
        return False
    if re.search(r"[a-z0-9]", normalized_marker):
        pattern = rf"(?<!\w){re.escape(normalized_marker)}(?!\w)"
        return bool(re.search(pattern, normalized_text))
    return normalized_marker in normalized_text


def _normalize_abort_trigger_text(text: str) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return ""
    normalized = normalized.replace("\u2019", "'").replace("`", "'")
    while True:
        updated = _TRAILING_ABORT_PUNCT_RE.sub("", normalized).strip()
        if updated == normalized:
            break
        normalized = updated
    return normalized


def _extract_explicit_mcp_tool_name(text: str) -> str | None:
    raw_text = str(text or "").strip()
    if not raw_text:
        return None
    match = _EXPLICIT_MCP_TOOL_ALIAS_RE.search(raw_text)
    if not match:
        return None
    from kabot.mcp.registry import qualify_mcp_tool_name

    server_name, tool_name = match.groups()
    return qualify_mcp_tool_name(server_name, tool_name)


def _is_abort_request_text(text: str) -> bool:
    normalized = _normalize_abort_trigger_text(text)
    if not normalized:
        return False
    if normalized == "/stop":
        return True
    if normalized.startswith("/stop@") and " " not in normalized:
        return True
    return normalized in _ABORT_REQUEST_TRIGGERS


def _is_low_information_turn(text: str, *, max_tokens: int, max_chars: int) -> bool:
    """
    Detect short follow-up acknowledgements without language-specific keyword catalogs.

    The decision is structural (length + payload shape), so it remains multilingual.
    """
    raw_text = str(text or "")
    normalized = _normalize_text(raw_text)
    if not normalized:
        return False
    if normalized.startswith("/"):
        return False
    if any(mark in raw_text for mark in ("?", "ï¼Ÿ", "Â¿", "ØŸ")):
        return False

    tokens = normalized.split()
    if len(tokens) == 0 or len(tokens) > max_tokens:
        return False
    if len(normalized) > max_chars:
        return False

    # Languages/scripts that are commonly written without spaces should not be
    # treated as low-information when the raw utterance is substantive.
    if not any(ch.isspace() for ch in raw_text):
        if re.search(r"[\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF\u0E00-\u0E7F\u0600-\u06FF]", raw_text):
            if len(raw_text) >= 5:
                return False

    # Rich payloads usually indicate fresh intent, not lightweight continuation.
    if re.search(r"(https?://|www\.)", normalized):
        return False
    if re.search(r"[@#]\w+", normalized):
        return False
    if re.search(r"\d{3,}", normalized):
        return False
    if any(ch in raw_text for ch in "{}[]=`\\/"):
        return False
    return True


def _normalize_locale_tag(value: Any) -> str | None:
    raw = str(value or "").strip().lower().replace("_", "-")
    if not raw:
        return None
    base = raw.split("-", 1)[0].strip()
    return base or None


def _resolve_runtime_locale(session: Any, msg: InboundMessage, text: str) -> str:
    """Resolve stable runtime locale for per-turn status messaging."""
    session_meta = getattr(session, "metadata", None)
    if not isinstance(session_meta, dict):
        session_meta = {}
        try:
            setattr(session, "metadata", session_meta)
        except Exception:
            pass

    msg_meta = msg.metadata if isinstance(msg.metadata, dict) else {}
    explicit = _normalize_locale_tag(
        msg_meta.get("runtime_locale") or msg_meta.get("locale") or msg_meta.get("language") or msg_meta.get("lang")
    )
    detected = _normalize_locale_tag(detect_locale(text)) or "en"
    session_meta["input_locale"] = detected
    if explicit:
        session_meta["runtime_locale"] = explicit
        return explicit

    cached = _normalize_locale_tag(session_meta.get("runtime_locale"))
    if detected and detected != "en":
        session_meta["runtime_locale"] = detected
        return detected
    if cached:
        return cached
    session_meta["runtime_locale"] = detected
    return detected


def _tool_registry_has(loop: Any, tool_name: str) -> bool:
    tools = getattr(loop, "tools", None)
    if tools is None:
        return False
    has_fn = getattr(tools, "has", None)
    if callable(has_fn):
        try:
            return bool(has_fn(tool_name))
        except Exception:
            return False
    names = getattr(tools, "tool_names", None)
    if isinstance(names, list):
        return tool_name in names
    return False


def _channel_supports_keepalive_passthrough(loop: Any, channel_name: str) -> bool:
    """Return whether the current channel should receive periodic keepalive pulses."""
    normalized = str(channel_name or "").strip()
    if not normalized:
        return False

    manager = getattr(loop, "channel_manager", None)
    channels_map = getattr(manager, "channels", None) if manager is not None else None
    if isinstance(channels_map, dict):
        channel_obj = channels_map.get(normalized)
        if channel_obj is None:
            lowered = normalized.lower()
            channel_obj = channels_map.get(lowered)
        if channel_obj is not None:
            allow_keepalive = getattr(channel_obj, "_allow_keepalive_passthrough", None)
            if callable(allow_keepalive):
                try:
                    return bool(allow_keepalive())
                except Exception:
                    pass

    channel_base = normalized.lower().split(":", 1)[0]
    return channel_base in _KEEPALIVE_PASSTHROUGH_CHANNELS


def _channel_uses_mutable_status_lane(loop: Any, channel_name: str) -> bool:
    """Return whether status phases should be emitted as full mutable lifecycle."""
    normalized = str(channel_name or "").strip()
    if not normalized:
        return False

    manager = getattr(loop, "channel_manager", None)
    channels_map = getattr(manager, "channels", None) if manager is not None else None
    if isinstance(channels_map, dict):
        channel_obj = channels_map.get(normalized)
        if channel_obj is None:
            channel_obj = channels_map.get(normalized.lower())
        if channel_obj is not None:
            mutable_status = getattr(channel_obj, "_uses_mutable_status_lane", None)
            if callable(mutable_status):
                try:
                    return bool(mutable_status())
                except Exception:
                    pass

    channel_base = normalized.lower().split(":", 1)[0]
    return channel_base in _MUTABLE_STATUS_LANE_CHANNELS


_PRIMARY_INTENT_TAIL_MARKERS = (
    "dari sini",
    "dari jawaban ini",
    "berdasarkan ini",
    "from this",
    "based on this",
    "from here",
    "using this",
)
_PRIMARY_INTENT_ACTION_RE = re.compile(
    r"(?i)\b("
    r"hitung|calculate|calc|jelaskan|explain|ringkas|summarize|buat|bikin|lanjut|"
    r"tolong|please|berapa|apa|kenapa|bagaimana|gimana|bisa|bisakah|"
    r"hr|heart rate|detak jantung|zona|zone|karvonen"
    r")\b"
)
_PERSONAL_HR_CALC_RE = re.compile(
    r"(?i)\b("
    r"zona hr|hr zona|hr zone|heart rate zone|detak jantung|"
    r"karvonen|resting hr|max hr|hr max"
    r")\b"
)


def _extract_primary_intent_text(text: str) -> str:
    raw = str(text or "").strip()
    if len(raw) < 140:
        return raw

    lines = [line.strip(" \t>") for line in raw.splitlines() if line.strip()]
    if len(lines) < 3:
        return raw

    candidates: list[str] = []
    if lines:
        candidates.append(lines[-1])
    if len(lines) >= 2:
        candidates.append(" ".join(lines[-2:]).strip())

    for candidate in candidates:
        normalized = _normalize_text(candidate)
        if not normalized or len(normalized) > 220:
            continue
        if "?" in candidate or _PRIMARY_INTENT_ACTION_RE.search(candidate):
            return candidate.strip()
        if any(marker in normalized for marker in _PRIMARY_INTENT_TAIL_MARKERS):
            return candidate.strip()
    return raw


def _looks_like_live_research_query(text: str) -> bool:
    focused = _extract_primary_intent_text(text)
    normalized = _normalize_text(focused)
    if not normalized:
        return False
    if _looks_like_memory_commit_turn(normalized):
        return False
    if _PERSONAL_HR_CALC_RE.search(normalized):
        return False

    has_stock_symbol = False
    has_crypto_symbol = False
    try:
        has_stock_symbol = bool(extract_stock_symbols(focused))
    except Exception:
        has_stock_symbol = False
    try:
        has_crypto_symbol = bool(extract_crypto_ids(focused))
    except Exception:
        has_crypto_symbol = False
    has_finance_domain = bool(
        has_stock_symbol
        or has_crypto_symbol
        or re.search(
            r"(?i)\b("
            r"stock|stocks|saham|ticker|tickers|quote|quotes|market|markets|"
            r"harga|price|crypto|bitcoin|btc|ethereum|eth|coin|coins|token|tokens|"
            r"forex|fx|kurs|rate|exchange(?:\s+rate)?|usd|idr|rupiah|ihsg|idx|jkse|nasdaq|dow|nikkei"
            r")\b",
            normalized,
        )
    )
    has_finance_value_request = bool(
        re.search(
            r"(?i)\b("
            r"berapa|how much|what(?:'s| is)|harga(?:nya)?|price|quote|nilai|value|"
            r"kurs|rate|last|latest|current|now|today|hari ini|sekarang|saat ini|"
            r"terbaru|terkini|real[\s-]?time|live|open|close|closing|high|low"
            r")\b",
            normalized,
        )
    )
    if has_finance_domain and has_finance_value_request:
        return True

    # Time-sensitive or "latest" wording should always force live search.
    live_marker_patterns = (
        r"\blatest\b",
        r"\btoday\b",
        r"\bnow\b",
        r"\bcurrent\b",
        r"\bbreaking\b",
        r"\bheadline\b",
        r"\bheadlines\b",
        r"\bnews\b",
    )
    if any(re.search(pattern, normalized) for pattern in live_marker_patterns):
        return True

    if re.search(r"\bnews\s+update(s)?\b", normalized):
        return True

    # Date/year queries generally imply external verification.
    if re.search(r"\b(19|20)\d{2}\b", normalized):
        return True

    # Search verbs in multilingual variants.
    search_verbs = (
        "find",
        "search",
        "look up",
    )
    if any(normalized.startswith(f"{verb} ") for verb in search_verbs):
        return True

    return False


_EXPLICIT_TOOL_USE_PATTERNS = (
    r"\buse the tool\b",
    r"\buse tool\b",
    r"\bgunakan tool\b",
    r"\bpake tool\b",
    r"\bpakai tool\b",
    r"\btool mcp\b",
    r"\bmcp tool\b",
    r"\bgunakan mcp\b",
    r"\bpakai mcp\b",
    r"\bcall the tool\b",
    r"\bjalankan tool\b",
    r"\bpakai alat\b",
    r"\bgunakan alat\b",
    r"使用工具",
    r"用这个工具",
    r"このツールを使",
    r"ツールを使",
    r"ใช้เครื่องมือ",
    r"ใช้ทูล",
)


def _looks_like_explicit_tool_use_request(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if any(re.search(pattern, normalized) for pattern in _EXPLICIT_TOOL_USE_PATTERNS[:12]):
        return True
    return any(re.search(pattern, raw) for pattern in _EXPLICIT_TOOL_USE_PATTERNS[12:])


_TEMPORAL_CONTEXT_RE = re.compile(
    r"(?i)\b("
    r"hari apa|what day|day is it|tanggal berapa|what date|jam berapa|what time|"
    r"hari ini|today|besok|tomorrow|kemarin|yesterday|lusa|seminggu|next week|"
    r"timezone|time zone|zona waktu|utc\s*[+-]?\s*\d{1,2}|wib|sekarang hari|hari sekarang"
    r")\b"
)
_TEMPORAL_CONTEXT_NON_LATIN_PHRASES = (
    "今天星期几",
    "今天星期幾",
    "今天是星期几",
    "今天是星期幾",
    "今天是什么星期",
    "今天是什麼星期",
    "今日は何曜日",
    "今日何曜日",
    "ตอนนี้วันอะไร",
    "วันนี้วันอะไร",
)

def _looks_like_temporal_context_query(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if _TEMPORAL_CONTEXT_RE.search(normalized):
        return True
    return any(phrase in raw for phrase in _TEMPORAL_CONTEXT_NON_LATIN_PHRASES)


_MEMORY_COMMIT_RE = re.compile(
    r"(?i)\b("
    r"save(?: it| this| that)?|remember(?: it| this| that)?|"
    r"note(?: it| this| that)?|save to memory|"
    r"save this to memory|save that to memory|commit to memory|save in memory"
    r")\b"
)


def _looks_like_memory_commit_turn(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    return bool(_MEMORY_COMMIT_RE.search(normalized))


_MEMORY_RECALL_INTERROGATIVE_RE = re.compile(
    r"(?i)\b("
    r"who|what|which|when|where|why|how|"
    r"tell|show|reply|answer"
    r")\b"
)
_MEMORY_RECALL_ACTION_RE = re.compile(
    r"(?i)\b("
    r"remember|remembered|save|saved|store|stored|recall|memory|"
    r"preference|preferences|code|call(?:ed)?|address(?:ed)?"
    r")\b"
)
_MEMORY_RECALL_CONTEXT_RE = re.compile(
    r"(?i)\b("
    r"before|earlier|previous(?:ly)?|prior|last|just"
    r")\b"
)
_MEMORY_RECALL_WORK_RE = re.compile(
    r"(?i)\b("
    r"decide|decided|decision|agree|agreed|plan|planned|todo|task|deadline|status"
    r")\b"
)
_MEMORY_RECALL_SUBJECT_RE = re.compile(
    r"(?i)\b("
    r"i|me|my|mine|myself|we|us|our|ours"
    r")\b"
)


def _looks_like_memory_recall_turn(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if raw.startswith("/"):
        return False
    if looks_like_self_identity_recall(raw):
        return True
    if len(normalized) > 240:
        return False
    interrogative_turn = bool(
        raw.endswith(("?", "？"))
        or _MEMORY_RECALL_INTERROGATIVE_RE.search(normalized)
    )
    if _looks_like_memory_commit_turn(raw) and not interrogative_turn:
        return False
    if not interrogative_turn:
        return False
    has_memory_anchor = bool(_MEMORY_RECALL_ACTION_RE.search(normalized))
    has_context_anchor = bool(_MEMORY_RECALL_CONTEXT_RE.search(normalized))
    has_work_anchor = bool(_MEMORY_RECALL_WORK_RE.search(normalized))
    has_subject_anchor = bool(_MEMORY_RECALL_SUBJECT_RE.search(normalized))
    if has_memory_anchor and (has_subject_anchor or has_work_anchor):
        return True
    if has_context_anchor and has_work_anchor:
        return True
    return False


async def _resolve_relevant_memory_facts(
    loop: Any,
    *,
    session: Any | None = None,
    session_key: str,
    text: str,
    limit: int = 3,
) -> list[str]:
    """Return bounded fact-like snippets for explicit memory recall turns."""
    if not _looks_like_memory_recall_turn(text):
        return []

    max_items = max(1, int(limit or 3))
    facts: list[str] = []
    seen: set[str] = set()
    normalized_query = _normalize_text(text)

    def _add_fact(value: str) -> None:
        cleaned = str(value or "").strip()
        if not cleaned:
            return
        normalized = _normalize_text(cleaned)
        if not normalized or normalized == normalized_query or normalized in seen:
            return
        facts.append(cleaned)
        seen.add(normalized)

    if session is not None:
        for fact in build_user_profile_memory_facts(session, limit=max_items):
            _add_fact(fact)
            if len(facts) >= max_items:
                return facts

    memory_obj = getattr(loop, "memory", None)
    search_memory = getattr(memory_obj, "search_memory", None)
    if not callable(search_memory):
        return facts

    try:
        result = search_memory(query=str(text or ""), session_id=session_key, limit=limit)
    except TypeError:
        try:
            result = search_memory(str(text or ""), session_key, limit)
        except Exception as exc:
            logger.debug(f"memory recall search skipped: {exc}")
            return []
    except Exception as exc:
        logger.debug(f"memory recall search skipped: {exc}")
        return []

    if asyncio.iscoroutine(result):
        try:
            result = await result
        except Exception as exc:
            logger.debug(f"memory recall search await skipped: {exc}")
            return facts

    if not isinstance(result, list):
        return facts

    for item in result:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or item.get("value") or "").strip()
        if not content:
            continue
        role = str(item.get("role") or "").strip().lower()
        if role == "user" and _looks_like_memory_recall_turn(content):
            continue
        _add_fact(content)
        if len(facts) >= max_items:
            break
    return facts


def _is_short_context_followup(text: str) -> bool:
    return _is_low_information_turn(text, max_tokens=6, max_chars=64)


def _looks_like_short_confirmation(text: str) -> bool:
    if not _is_low_information_turn(text, max_tokens=4, max_chars=40):
        return False
    normalized = _normalize_text(text)
    # Short interrogatives like "saranmu apa" should open a new turn,
    # not continue stale pending tool/intent context.
    if _SHORT_INTERROGATIVE_RE.search(normalized):
        return False
    informative_tokens = [
        token
        for token in re.findall(r"\w+", normalized, flags=re.UNICODE)
        if len(token) >= 3 and token not in _ASSISTANT_OFFER_CONTEXT_STOPWORDS
    ]
    if len(informative_tokens) >= 2:
        return False
    return True


_ASSISTANT_OFFER_CONTEXT_STOPWORDS = {
    "a",
    "an",
    "and",
    "apa",
    "are",
    "bagaimana",
    "berikan",
    "bisa",
    "buat",
    "deh",
    "do",
    "dong",
    "gimana",
    "hadeh",
    "how",
    "i",
    "ini",
    "is",
    "itu",
    "kah",
    "kalau",
    "kalo",
    "kamu",
    "ke",
    "lah",
    "mau",
    "me",
    "my",
    "nomor",
    "number",
    "oke",
    "ok",
    "opsi",
    "option",
    "or",
    "please",
    "pilihan",
    "saya",
    "sih",
    "that",
    "the",
    "this",
    "to",
    "tolong",
    "what",
    "yang",
    "ya",
    "yeah",
}

from kabot.agent.loop_core.message_runtime_parts.reference_resolution import (
    _assistant_followup_text_looks_committed_action,
    _classify_assistant_followup_intent_kind,
    _extract_assistant_followup_offer_text,
    _extract_option_selection_reference,
    _extract_referenced_answer_item,
    _extract_user_supplied_option_prompt_text,
    _looks_like_answer_reference_followup,
    _looks_like_assistant_offer_context_followup,
    _looks_like_closing_acknowledgement,
    _looks_like_coding_build_request,
    _looks_like_contextual_followup_request,
    _looks_like_file_context_followup,
    _looks_like_message_delivery_request,
    _looks_like_non_action_meta_feedback,
    _looks_like_side_effect_request,
    _looks_like_short_greeting_smalltalk,
    _looks_like_web_search_demotion_followup,
    _looks_like_weather_context_followup,
)
from kabot.agent.loop_core.message_runtime_parts.context_notes import (
    _assistant_response_looks_like_skill_plan,
    _build_budget_hints,
    _build_explicit_file_analysis_note,
    _build_grounded_filesystem_inspection_note,
    _build_filesystem_location_context_note,
    _build_session_continuity_action_note,
    _build_temporal_context_note,
    _build_untrusted_context_payload,
    _clear_skill_creation_flow,
    _get_skill_creation_flow,
    _infer_recent_assistant_answer_from_history,
    _infer_recent_assistant_option_prompt_from_history,
    _infer_recent_created_skill_name_from_path,
    _infer_recent_file_path_from_history,
    _looks_like_explicit_new_request,
    _looks_like_existing_skill_use_followup,
    _looks_like_filesystem_location_query,
    _looks_like_skill_creation_approval,
    _looks_like_skill_workflow_followup_detail,
    _message_needs_full_skill_context,
    _resolve_token_mode,
    _schedule_context_truncation_memory_fact,
    _set_skill_creation_flow,
    _should_store_followup_intent,
    _update_skill_creation_flow_after_response,
)
