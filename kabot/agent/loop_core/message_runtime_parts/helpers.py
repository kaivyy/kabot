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
    _get_last_tool_context,
    _get_pending_followup_intent,
    _get_pending_followup_tool,
    _set_last_tool_context,
    _set_pending_followup_intent,
    _set_pending_followup_tool,
)

__all__ = [
    "_KEEPALIVE_INITIAL_DELAY_SECONDS",
    "_KEEPALIVE_INTERVAL_SECONDS",
    "_build_temporal_context_note",
    "_clear_pending_followup_intent",
    "_clear_pending_followup_tool",
    "_extract_assistant_followup_offer_text",
    "_extract_option_selection_reference",
    "_infer_recent_assistant_option_prompt_from_history",
    "_infer_recent_assistant_answer_from_history",
    "_extract_user_supplied_option_prompt_text",
    "_get_last_tool_context",
    "_get_pending_followup_intent",
    "_get_pending_followup_tool",
    "_looks_like_answer_reference_followup",
    "_looks_like_assistant_offer_context_followup",
    "_looks_like_contextual_followup_request",
    "_normalize_text",
    "_resolve_runtime_locale",
    "_set_last_tool_context",
    "_set_pending_followup_intent",
    "_set_pending_followup_tool",
]


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
            "- Reply in the same language as the user and keep the tone natural, collaborative, and concise.\n"
            "- You may now execute the approved plan, write files if needed, and run focused verification for the approved scope.\n"
            "- Keep the implementation inside the workspace skills directory unless the user asked for a different target.\n"
            "- Never hardcode API keys or secrets; use env/config requirements instead."
        )
    if first_turn:
        return (
            "[Skill Workflow]\n"
            f"- This request is for {workflow_subject}.\n"
            "- Reply in the same language as the user and keep the tone natural, collaborative, and concise.\n"
            "- Do not create files yet.\n"
            "- Stay in discovery mode on this turn: ask only the minimum questions needed about scope, source/target, auth/dependencies, and trust/overwrite implications.\n"
            "- Do not claim the work is already being executed yet."
        )
    return (
        "[Skill Workflow]\n"
        "- Stay in skill-workflow mode unless the user clearly changes topic.\n"
        "- Reply in the same language as the user and keep the tone natural, collaborative, and concise.\n"
        "- Do not create or modify files until the user explicitly approves a written plan in this conversation.\n"
        "- If requirements are still incomplete, continue discovery with concise follow-up questions.\n"
        "- If requirements are complete but no plan has been approved yet, present a short implementation plan and ask for approval.\n"
        "- Only after explicit approval may you scaffold files, write code, or run verification."
    )


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


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
        msg_meta.get("locale") or msg_meta.get("language") or msg_meta.get("lang")
    )
    if explicit:
        session_meta["runtime_locale"] = explicit
        return explicit

    detected = _normalize_locale_tag(detect_locale(text))
    cached = _normalize_locale_tag(session_meta.get("runtime_locale"))
    if detected and detected != "en":
        session_meta["runtime_locale"] = detected
        return detected
    if cached:
        return cached
    return detected or "en"


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


def _looks_like_live_research_query(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False

    # Time-sensitive or "latest" wording should always force live search.
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

    # Date/year queries generally imply external verification.
    if re.search(r"\b(19|20)\d{2}\b", normalized):
        return True

    # Search verbs in multilingual variants.
    search_verbs = (
        "find",
        "search",
        "look up",
        "cari",
        "carikan",
        "telusuri",
        "buscar",
        "rechercher",
    )
    if any(normalized.startswith(f"{verb} ") for verb in search_verbs):
        return True

    return False


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
    r"simpan|save(?: it| this| that)?|ingat(?:kan)?|remember(?: it| this| that)?|"
    r"catat(?:kan)?|note(?: it| this| that)?|save to memory|simpan ke memory|"
    r"commit ke memory|masukkan ke memory"
    r")\b"
)


def _looks_like_memory_commit_turn(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    return bool(_MEMORY_COMMIT_RE.search(normalized))


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

_CONTEXTUAL_FOLLOWUP_PHRASES = (
    "ya lanjut",
    "lanjut rencana",
    "lanjut analisis",
    "lanjut yang",
    "maksudnya",
    "kenapa",
    "kok",
    "yang formal",
    "yang kedua",
    "nomor 2",
    "coba ulang",
    "jelasin",
    "jelaskan",
    "trend nya",
    "trendnya",
    "再简短一点",
    "更短一点",
    "这是什么意思",
    "什么意思",
    "もっと短く",
    "それどういう意味",
    "สั้นกว่านี้",
    "หมายความว่าไง",
)

_CONTEXTUAL_FOLLOWUP_EXACT = {
    "naik ya",
    "turun ya",
}
_ANSWER_REFERENCE_FOLLOWUP_PHRASES = (
    "yang pertama",
    "yang kedua",
    "yang ketiga",
    "yang keempat",
    "yang kelima",
    "nomor 1",
    "nomor 2",
    "nomor 3",
    "nomor 4",
    "nomor 5",
    "opsi 1",
    "opsi 2",
    "opsi 3",
    "opsi 4",
    "opsi 5",
    "the first",
    "the second",
    "the third",
    "the fourth",
    "the fifth",
    "maksudnya",
    "coba ulang",
    "ulang dari awal",
    "versi singkat",
    "versi pendek",
    "jelasin lagi",
    "jelaskan lagi",
    "再简短一点",
    "再短一点",
    "更短一点",
    "这是什么意思",
    "這是什麼意思",
    "什么意思",
    "什麼意思",
    "もっと短く",
    "短くして",
    "それどういう意味",
    "どういう意味",
    "สั้นกว่านี้",
    "หมายความว่าไง",
    "หมายความว่าอะไร",
)

_OPTION_SELECTION_NUMERIC_RE = re.compile(
    r"^(?:(?:opsi|option|nomor|number)\s+)?(?P<ref>\d{1,2})$"
)
_OPTION_SELECTION_REFERENCE_RE = re.compile(
    r"\b(?:(?:opsi|option|nomor|number|yang|the)\s+)?"
    r"(?P<ref>pertama|kedua|ketiga|keempat|kelima|first|second|third|fourth|fifth|\d{1,2})"
    r"(?:\s+one)?\b",
    re.IGNORECASE,
)
_OPTION_SELECTION_ORDINAL_MAP = {
    "pertama": "1",
    "kedua": "2",
    "ketiga": "3",
    "keempat": "4",
    "kelima": "5",
    "first": "1",
    "second": "2",
    "third": "3",
    "fourth": "4",
    "fifth": "5",
    "一": "1",
    "二": "2",
    "三": "3",
    "四": "4",
    "五": "5",
}
_OPTION_SELECTION_CJK_ORDINAL_RE = re.compile("\\u7b2c(?P<ref>[\\u4e00\\u4e8c\\u4e09\\u56db\\u4e94\\d]{1,2})(?:\\u4e2a|\\u500b|\\u756a|\\u3064\\u76ee)?")
_OPTION_SELECTION_JA_NUMERIC_RE = re.compile("(?P<ref>\\d{1,2})\\u756a")
_OPTION_SELECTION_THAI_NUMERIC_RE = re.compile("\\u0e02\\u0e49\\u0e2d\\s*(?P<ref>\\d{1,2})")

def _tokenize_context_tokens(text: str) -> set[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return set()
    tokens = re.findall(r"\w+", normalized, flags=re.UNICODE)
    result: set[str] = set()
    for token in tokens:
        if not token:
            continue
        if token in _ASSISTANT_OFFER_CONTEXT_STOPWORDS:
            continue
        if token.isdigit():
            result.add(token)
            continue
        if len(token) < 2:
            continue
        result.add(token)
    return result


def _looks_like_assistant_offer_context_followup(text: str, offer_text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if _looks_like_short_confirmation(raw):
        return True
    if not _is_low_information_turn(raw, max_tokens=7, max_chars=96):
        return False
    if re.search(r"(https?://|www\.)", normalized):
        return False
    if _PATHLIKE_TEXT_RE.search(raw):
        return False
    current_tokens = _tokenize_context_tokens(raw)
    offer_tokens = _tokenize_context_tokens(offer_text)
    if not current_tokens or not offer_tokens:
        return False
    return bool(current_tokens & offer_tokens)


def _extract_option_selection_reference(text: str) -> str | None:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return None
    if not _is_low_information_turn(raw, max_tokens=8, max_chars=96):
        return None
    if re.search(r"(https?://|www\.)", normalized):
        return None
    if _PATHLIKE_TEXT_RE.search(raw):
        return None

    numeric_match = _OPTION_SELECTION_NUMERIC_RE.fullmatch(normalized)
    if numeric_match:
        return str(numeric_match.group("ref") or "").strip() or None

    for pattern in (
        _OPTION_SELECTION_CJK_ORDINAL_RE,
        _OPTION_SELECTION_JA_NUMERIC_RE,
        _OPTION_SELECTION_THAI_NUMERIC_RE,
    ):
        extra_match = pattern.search(raw)
        if not extra_match:
            continue
        ref = str(extra_match.group("ref") or "").strip()
        if not ref:
            continue
        if ref.isdigit():
            return ref
        mapped = _OPTION_SELECTION_ORDINAL_MAP.get(ref)
        if mapped:
            return mapped

    match = _OPTION_SELECTION_REFERENCE_RE.search(normalized)
    if not match:
        return None
    ref = str(match.group("ref") or "").strip().lower()
    if not ref:
        return None
    if ref.isdigit():
        return ref
    return _OPTION_SELECTION_ORDINAL_MAP.get(ref)


def _looks_like_answer_reference_followup(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if re.search(r"(https?://|www\.)", normalized):
        return False
    if _PATHLIKE_TEXT_RE.search(raw):
        return False
    if _extract_option_selection_reference(raw):
        return True
    if any(phrase in normalized for phrase in _ANSWER_REFERENCE_FOLLOWUP_PHRASES):
        return True
    if not _is_low_information_turn(raw, max_tokens=10, max_chars=120):
        return False
    return False


def _looks_like_contextual_followup_request(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if not _is_low_information_turn(raw, max_tokens=8, max_chars=96):
        return False
    if re.search(r"(https?://|www\.)", normalized):
        return False
    if _PATHLIKE_TEXT_RE.search(raw):
        return False
    if _extract_option_selection_reference(raw):
        return True
    if normalized in _CONTEXTUAL_FOLLOWUP_EXACT:
        return True
    if "trend" in normalized:
        return True
    return any(phrase in normalized for phrase in _CONTEXTUAL_FOLLOWUP_PHRASES)


_ASSISTANT_FOLLOWUP_OFFER_LEAD_MARKERS = (
    "if you want",
    "if you'd like",
    "if you would like",
    "if you like",
    "kalau mau",
    "kalau kamu mau",
    "kalau lo mau",
    "kalau lu mau",
    "kalau anda mau",
    "jika mau",
    "jika anda mau",
    "jika kamu mau",
    "jika anda ingin",
    "jika kamu ingin",
    "bila mau",
    "bila anda mau",
    "bila kamu mau",
    "bila anda ingin",
    "bila kamu ingin",
    "kalau ingin",
    "mau aku",
    "mau saya",
    "si quieres",
    "se quiser",
    "si tu veux",
    "si vous voulez",
    "wenn du willst",
    "wenn sie m?chten",
    "如果你想",
    "如果你愿意",
    "如果你想要",
    "よければ",
    "必要なら",
    "ถ้าต้องการ",
    "ถ้าอยาก",
)

_ASSISTANT_FOLLOWUP_OFFER_CAPABILITY_MARKERS = (
    "i can",
    "i can also",
    "can also",
    "aku bisa",
    "aku juga bisa",
    "saya bisa",
    "saya juga bisa",
    "bisa juga",
    "bisa kasih",
    "bisa berikan",
    "bisa bikinin",
    "bisa bantu",
    "puedo",
    "je peux",
    "ich kann",
    "我也可以",
    "我可以",
    "可以帮你",
    "できます",
    "お伝えできます",
    "ช่วยได้",
    "ช่วยคุณได้",
)

_ASSISTANT_FOLLOWUP_OFFER_EXCLUDE_MARKERS = (
    "what can i help you with today",
    "what can i help you with",
    "apa yang bisa saya bantu",
    "ada yang bisa saya bantu",
    "silakan beri tahu apa yang ingin",
    "tolong beri tahu apa yang ingin",
)

_ASSISTANT_FOLLOWUP_SELECTION_MARKERS = (
    "balas hanya angka",
    "balas angka",
    "balas hanya nomor",
    "silakan balas",
    "silakan pilih",
    "reply with just",
    "reply only with",
    "reply with only",
    "reply with",
    "choose 1",
    "choose one",
    "pick 1",
    "pick one",
    "select 1",
    "select one",
    "选一个",
    "選一個",
    "选择一个",
    "選擇一個",
    "1つ選んでください",
    "一つ選んでください",
    "選んでください",
    "เลือกหนึ่งแบบ",
    "เลือกหนึ่งข้อ",
    "เลือกหนึ่งอย่าง",
)

_ASSISTANT_FOLLOWUP_OPTION_INTRO_MARKERS = (
    "opsi",
    "pilihan",
    "option",
    "options",
    "choice",
    "choices",
    "tingkat formalitas",
    "formalitas",
    "版本",
    "版",
    "文体",
    "文體",
    "แบบ",
)

_ASSISTANT_FOLLOWUP_CHOICE_LINE_RE = re.compile(
    r"^\s*(?:\d{1,2}[.)\uFF09\uFF0E\u3002]|[-*\u2022])\s*\S+"
)


_INLINE_NUMBERED_CHOICE_RE = re.compile(r"(?:^|\s)\d{1,2}(?:[.)）．。]|\s*[\(（])", re.UNICODE)
_USER_OPTION_PROMPT_SELECTION_MARKERS = (
    *_ASSISTANT_FOLLOWUP_SELECTION_MARKERS,
    "pilih satu",
    "pilih salah satu",
    "pilih ya",
    "pilih dulu",
    "choose one",
    "pick one",
    "select one",
    "选一个",
    "選一個",
    "1つ選んでください",
    "เลือกหนึ่งแบบ",
)

_INLINE_CHOICE_QUESTION_MARKERS = (
    "mau yang",
    "yang mana",
    "pilihanmu",
    "pilihan anda",
    "pilihan kamu",
    "which one",
    "选哪个",
    "選哪個",
    "どれ",
    "どちら",
    "เลือกแบบไหน",
)

_USER_OPTION_PROMPT_EXPLICIT_CHOOSE_FOR_ME_MARKERS = (
    "menurutmu pilih yang mana",
    "menurut anda pilih yang mana",
    "which one should i choose",
    "which should i choose",
    "choose for me",
    "pick for me",
    "pilihkan",
    "pilihin",
    "pilih yang terbaik",
    "rekomendasikan yang mana",
)

def _extract_assistant_followup_offer_text(text: str) -> str | None:
    """Extract a concise assistant offer sentence that can anchor a short follow-up."""
    raw = str(text or "").strip()
    if not raw:
        return None

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    normalized_lines = [_normalize_text(line) for line in lines]
    normalized_raw = _normalize_text(raw)

    def _is_offer_anchor(normalized: str) -> bool:
        if not normalized:
            return False
        if any(marker in normalized for marker in _ASSISTANT_FOLLOWUP_OFFER_EXCLUDE_MARKERS):
            return False
        has_lead = any(marker in normalized for marker in _ASSISTANT_FOLLOWUP_OFFER_LEAD_MARKERS)
        has_capability = any(marker in normalized for marker in _ASSISTANT_FOLLOWUP_OFFER_CAPABILITY_MARKERS)
        return has_lead and has_capability

    def _looks_like_option_intro(normalized: str, next_lines: list[str]) -> bool:
        if not normalized:
            return False
        has_intro_marker = any(
            marker in normalized for marker in _ASSISTANT_FOLLOWUP_OPTION_INTRO_MARKERS
        )
        has_selection_marker = any(
            marker in normalized for marker in _ASSISTANT_FOLLOWUP_SELECTION_MARKERS
        )
        if not (has_intro_marker or has_selection_marker):
            return False
        return any(_ASSISTANT_FOLLOWUP_CHOICE_LINE_RE.match(line) for line in next_lines[:4])

    def _has_inline_choice_prompt(normalized: str, raw_value: str) -> bool:
        if not normalized:
            return False
        if len(_INLINE_NUMBERED_CHOICE_RE.findall(raw_value)) < 2:
            return False
        return any(marker in normalized for marker in _USER_OPTION_PROMPT_SELECTION_MARKERS) or any(
            marker in normalized for marker in _INLINE_CHOICE_QUESTION_MARKERS
        )

    def _collect_followup_block(start_idx: int) -> str | None:
        if start_idx < 0 or start_idx >= len(lines):
            return None
        block = [lines[start_idx]]
        for idx in range(start_idx + 1, min(len(lines), start_idx + 7)):
            line = lines[idx]
            normalized = normalized_lines[idx]
            if _ASSISTANT_FOLLOWUP_CHOICE_LINE_RE.match(line):
                block.append(line)
                continue
            if any(marker in normalized for marker in _ASSISTANT_FOLLOWUP_SELECTION_MARKERS):
                block.append(line)
                continue
            break
        joined = "\n".join(block).strip()
        return joined if joined else None

    if len(lines) > 1:
        for idx, normalized in enumerate(normalized_lines):
            if _looks_like_option_intro(normalized, lines[idx + 1 :]):
                return _collect_followup_block(idx)

        for idx, normalized in enumerate(normalized_lines):
            if _is_offer_anchor(normalized):
                return _collect_followup_block(idx) or lines[idx]

    if _has_inline_choice_prompt(normalized_raw, raw):
        return raw

    candidates = [segment.strip() for segment in re.split(r"(?<=[.!?ã€‚ï¼ï¼Ÿ])\s+|\n+", raw) if segment.strip()]
    if not candidates:
        candidates = [raw]

    for candidate in reversed(candidates[-4:]):
        normalized = _normalize_text(candidate)
        if not normalized or len(candidate) > 260:
            continue
        if _is_offer_anchor(normalized):
            return candidate
        if _has_inline_choice_prompt(normalized, candidate):
            return candidate
    return None


def _extract_user_supplied_option_prompt_text(text: str) -> str | None:
    """Detect user-authored assistant-like option prompts without auto-selecting for them."""
    raw = str(text or "").strip()
    if not raw:
        return None

    normalized = _normalize_text(raw)
    if not normalized:
        return None
    if any(marker in normalized for marker in _USER_OPTION_PROMPT_EXPLICIT_CHOOSE_FOR_ME_MARKERS):
        return None

    offer_text = _extract_assistant_followup_offer_text(raw)
    if not offer_text:
        return None

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    choice_count = sum(1 for line in lines if _ASSISTANT_FOLLOWUP_CHOICE_LINE_RE.match(line))
    choice_count += len(_INLINE_NUMBERED_CHOICE_RE.findall(raw))
    has_selection_prompt = any(marker in normalized for marker in _USER_OPTION_PROMPT_SELECTION_MARKERS)
    if choice_count < 2 or not has_selection_prompt:
        return None
    return raw

def _looks_like_closing_acknowledgement(text: str) -> bool:
    """Detect short gratitude/closure replies that should not trigger pending actions."""
    raw = str(text or "")
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if not _is_low_information_turn(raw, max_tokens=8, max_chars=80):
        return False

    patterns = (
        r"\b(thanks|thank you|thx|ty)\b",
        r"\b(makasih|mksh|terima kasih|trimakasih)\b",
        r"\b(merci|gracias|arigato|arigatou|obrigad[oa])\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def _looks_like_short_greeting_smalltalk(text: str) -> bool:
    """Detect short greeting/opening messages that should reset pending follow-ups."""
    raw = str(text or "")
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if not _is_low_information_turn(raw, max_tokens=5, max_chars=48):
        return False
    patterns = (
        r"^(hi|hai|halo|hello|hey|yo)\b",
        r"^(assalamualaikum|salam)\b",
        r"^good (morning|afternoon|evening|night)\b",
        r"^selamat (pagi|siang|sore|malam)\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def _looks_like_non_action_meta_feedback(text: str) -> bool:
    """Detect short non-action feedback turns that should clear pending continuations."""
    raw = str(text or "")
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if not _is_low_information_turn(raw, max_tokens=10, max_chars=96):
        return False
    if "?" in raw:
        return False
    if any(marker in normalized for marker in _RUNTIME_META_FEEDBACK_MARKERS):
        return True
    has_non_action = any(marker in normalized for marker in _NON_ACTION_FOLLOWUP_MARKERS)
    if not has_non_action:
        return False
    has_topic = any(marker in normalized for marker in _NON_ACTION_TOPIC_MARKERS)
    return has_topic


def _looks_like_weather_context_followup(text: str) -> bool:
    raw = str(text or "")
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if normalized.startswith("/"):
        return False
    if len(raw.strip()) > 96:
        return False
    tokens = [part for part in normalized.split(" ") if part]
    if len(tokens) > 8:
        return False
    return any(marker in normalized for marker in _WEATHER_CONTEXT_FOLLOWUP_MARKERS)


def _looks_like_file_context_followup(text: str) -> bool:
    raw = str(text or "")
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if normalized.startswith("/"):
        return False
    if len(raw.strip()) > 120:
        return False
    if _extract_read_file_path_proxy(raw):
        return False
    return any(marker in normalized for marker in _FILE_CONTEXT_FOLLOWUP_MARKERS)


def _looks_like_filesystem_location_query(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if len(normalized) > 120:
        return False
    return any(re.search(pattern, normalized) for pattern in _FILESYSTEM_LOCATION_QUERY_PATTERNS)


def _build_filesystem_location_context_note(loop: Any, session: Any, last_tool_context: dict[str, Any] | None) -> str:
    workspace = getattr(loop, "workspace", None)
    workspace_path = ""
    if isinstance(workspace, Path):
        workspace_path = str(workspace.expanduser().resolve())
    elif isinstance(workspace, str) and str(workspace).strip():
        try:
            workspace_path = str(Path(workspace).expanduser().resolve())
        except Exception:
            workspace_path = str(workspace).strip()

    last_path = ""
    if isinstance(last_tool_context, dict):
        last_path = str(last_tool_context.get("path") or "").strip()

    lines = ["[System Note: Filesystem location context]"]
    if workspace_path:
        lines.append(f"Current workspace path: {workspace_path}")
    if last_path:
        lines.append(f"Last navigated filesystem path: {last_path}")
    lines.append(
        "Answer naturally in the user's language. If they ask where you are now, use the concrete path context above."
    )
    return "\n".join(lines)


def _build_temporal_context_note(*, now_local: datetime | None = None) -> str:
    current = now_local or datetime.now().astimezone()
    yesterday = current - timedelta(days=1)
    tomorrow = current + timedelta(days=1)
    next_week = current + timedelta(days=7)

    tz_name = str(current.tzname() or "Local")
    offset = current.utcoffset()
    total_minutes = int(offset.total_seconds() // 60) if offset is not None else 0
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    tz_offset = f"UTC{sign}{hours:02d}:{minutes:02d}"

    lines = ["[System Note: Temporal context]"]
    lines.append(f"Local timestamp: {current.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Local timezone: {tz_name} ({tz_offset})")
    lines.append(f"Today local date: {current.strftime('%Y-%m-%d')}")
    lines.append(f"Today local weekday: {current.strftime('%A')}")
    lines.append(f"Yesterday local weekday: {yesterday.strftime('%A')}")
    lines.append(f"Tomorrow local weekday: {tomorrow.strftime('%A')}")
    lines.append(f"Seven days from today weekday: {next_week.strftime('%A')}")
    lines.append("Use these exact local-time facts for day/date/time follow-up questions, then answer naturally in the user's language.")
    return "\n".join(lines)


def _build_explicit_file_analysis_note(path: str) -> str:
    normalized_path = str(path or "").strip()
    if not normalized_path:
        return ""
    return "\n".join(
        (
            "[System Note: Explicit file reference]",
            f"- The user referenced this concrete file path: {normalized_path}",
            "- If the user is asking about the file's contents, structure, styling, config, or attributes, call read_file on that path before answering.",
            "- Do not ask the user to resend the file path when it is already present.",
            "- After reading, answer the real question naturally in the user's language instead of dumping the file unless they explicitly ask for the raw content.",
        )
    )


def _message_needs_full_skill_context(context_builder: Any, message: str, profile: str) -> bool:
    """Preserve full context when the current turn would auto-load skills."""
    if not str(message or "").strip():
        return False

    skills_loader = getattr(context_builder, "skills", None)
    matcher = getattr(skills_loader, "match_skills", None)
    if not callable(matcher):
        return False

    try:
        matches = matcher(message, profile)
    except TypeError:
        try:
            matches = matcher(message)
        except Exception as exc:
            logger.debug(f"Skill fast-path bypass check failed: {exc}")
            return False
    except Exception as exc:
        logger.debug(f"Skill fast-path bypass check failed: {exc}")
        return False

    if isinstance(matches, (list, tuple, set)):
        return len(matches) > 0
    return False


def _looks_like_explicit_new_request(text: str) -> bool:
    """
    Detect short-but-substantive turns that should not inherit pending follow-up tool state.

    This keeps continuation UX for lightweight confirms ("ya", "gas"), while
    preventing stale tool carry-over for fresh asks like file/config operations.
    """
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if normalized.startswith("/"):
        return True
    if any(mark in raw for mark in ("?", "Ã¯Â¼Å¸", "Ã‚Â¿", "Ã˜Å¸")):
        return True
    if re.search(r"(https?://|www\.)", normalized):
        return True
    if _FILELIKE_EXTENSION_RE.search(normalized):
        return True
    if _PATHLIKE_TEXT_RE.search(raw):
        return True

    tokens = [part for part in normalized.split(" ") if part]
    has_file_action_marker = any(
        marker in normalized for marker in ("baca", "read", "open", "buka", "lihat", "show", "display", "print", "cat")
    )
    has_file_subject_marker = any(
        marker in normalized for marker in ("config", "settings", "setting", "file", "berkas", "folder", "direktori", "path")
    )
    if has_file_subject_marker and (has_file_action_marker or len(tokens) >= 3):
        return True
    if has_file_action_marker and any(ch in raw for ch in (".", "/", "\\")):
        return True

    if len(tokens) >= 4 and any(
        marker in normalized
        for marker in (
            "what",
            "why",
            "how",
            "when",
            "where",
            "which",
            "who",
            "apa",
            "kenapa",
            "gimana",
            "bagaimana",
            "kapan",
            "mana",
            "siapa",
            "berapa",
        )
    ):
        return True
    return False


def _infer_recent_file_path_from_history(history: list[dict[str, Any]]) -> str:
    for item in reversed(history[-10:]):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = str(item.get("content", "") or "").strip()
        if not content:
            continue
        path = _extract_read_file_path_proxy(content)
        if path:
            return path
    return ""


def _infer_recent_assistant_option_prompt_from_history(history: list[dict[str, Any]]) -> str:
    for item in reversed(history[-10:]):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "") or "").strip().lower()
        if role != "assistant":
            continue
        content = str(item.get("content", "") or "").strip()
        if not content:
            continue
        prompt = _extract_assistant_followup_offer_text(content) or ""
        if prompt:
            return prompt
    return ""


def _infer_recent_assistant_answer_from_history(history: list[dict[str, Any]]) -> str:
    for item in reversed(history[-10:]):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "") or "").strip().lower()
        if role != "assistant":
            continue
        content = str(item.get("content", "") or "").strip()
        if not content:
            continue
        if _extract_assistant_followup_offer_text(content):
            continue
        return content
    return ""


def _get_skill_creation_flow(session: Any, now_ts: float) -> dict[str, Any] | None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return None
    flow = metadata.get(_SKILL_CREATION_FLOW_KEY)
    if not isinstance(flow, dict):
        return None

    request_text = str(flow.get("request_text") or "").strip()
    stage = str(flow.get("stage") or "discovery").strip().lower() or "discovery"
    kind = str(flow.get("kind") or "create").strip().lower() or "create"
    expires_at = flow.get("expires_at")
    try:
        expires_ts = float(expires_at)
    except Exception:
        expires_ts = 0.0

    if not request_text or expires_ts <= now_ts:
        metadata.pop(_SKILL_CREATION_FLOW_KEY, None)
        return None
    return {
        "request_text": request_text,
        "stage": stage,
        "kind": kind,
    }


def _set_skill_creation_flow(
    session: Any,
    request_text: str,
    now_ts: float,
    *,
    stage: str,
    kind: str = "create",
) -> None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return
    normalized_request = str(request_text or "").strip()
    normalized_stage = str(stage or "discovery").strip().lower() or "discovery"
    normalized_kind = str(kind or "create").strip().lower() or "create"
    if not normalized_request:
        return
    metadata[_SKILL_CREATION_FLOW_KEY] = {
        "request_text": normalized_request[:280],
        "stage": normalized_stage,
        "kind": normalized_kind,
        "updated_at": now_ts,
        "expires_at": now_ts + _SKILL_CREATION_FLOW_TTL_SECONDS,
    }


def _clear_skill_creation_flow(session: Any) -> None:
    metadata = getattr(session, "metadata", None)
    if isinstance(metadata, dict):
        metadata.pop(_SKILL_CREATION_FLOW_KEY, None)


def _looks_like_skill_creation_approval(text: str) -> bool:
    raw = str(text or "")
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if _looks_like_short_confirmation(raw):
        return True
    return any(marker in normalized for marker in _SKILL_CREATION_APPROVAL_MARKERS)


def _assistant_response_looks_like_skill_plan(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False

    if any(marker in normalized for marker in ("skill.md", "/skills/", "references/", "scripts/")):
        return True

    bullet_lines = 0
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("- ", "* ", "â€¢ ", "1.", "2.", "3.", "4.")):
            bullet_lines += 1
    if bullet_lines >= 2 and any(
        marker in normalized
        for marker in ("plan", "rencana", "approval", "approve", "setuju", "langkah", "workflow", "implement")
    ):
        return True
    return False


def _update_skill_creation_flow_after_response(
    session: Any,
    msg: InboundMessage,
    final_content: str | None,
    *,
    now_ts: float,
) -> None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return

    msg_meta = msg.metadata if isinstance(msg.metadata, dict) else {}
    guard = msg_meta.get("skill_creation_guard")
    if not isinstance(guard, dict):
        return
    if not bool(guard.get("active")):
        return

    request_text = str(guard.get("request_text") or msg.content or "").strip()
    stage = str(guard.get("stage") or "discovery").strip().lower() or "discovery"
    kind = str(guard.get("kind") or "create").strip().lower() or "create"
    approved = bool(guard.get("approved"))

    if approved:
        _set_skill_creation_flow(session, request_text, now_ts, stage="approved", kind=kind)
        return

    if _assistant_response_looks_like_skill_plan(final_content or ""):
        _set_skill_creation_flow(session, request_text, now_ts, stage="planning", kind=kind)
        return

    _set_skill_creation_flow(session, request_text, now_ts, stage=stage, kind=kind)


def _should_store_followup_intent(
    text: str,
    *,
    required_tool: str | None = None,
    decision_profile: str = "GENERAL",
    decision_is_complex: bool = False,
) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    if normalized.startswith("/"):
        return False
    if required_tool:
        return True
    # Keep live/current-fact intent even when prompt is short, so
    # confirmations like "ya/gas/ambil sekarang" can continue deterministically.
    if _looks_like_live_research_query(normalized):
        return True
    if _looks_like_short_confirmation(normalized):
        return False
    if _is_short_context_followup(normalized):
        return False
    profile = str(decision_profile or "").strip().upper()
    # Prefer storing follow-up intent for actionable/complex turns only, to avoid
    # carrying unrelated chat context into short confirmations.
    if decision_is_complex:
        return True
    return profile in {"CODING", "RESEARCH"}


def _build_untrusted_context_payload(
    msg: InboundMessage,
    *,
    dropped_count: int,
    dropped_preview: list[str],
) -> dict[str, Any]:
    """Build explicit untrusted metadata payload for prompt hardening."""
    payload: dict[str, Any] = {
        "channel": str(getattr(msg, "channel", "") or ""),
        "chat_id": str(getattr(msg, "chat_id", "") or ""),
        "sender_id": str(getattr(msg, "sender_id", "") or ""),
    }
    for key in ("account_id", "peer_kind", "peer_id", "guild_id", "team_id", "thread_id"):
        value = getattr(msg, key, None)
        if isinstance(value, str) and value.strip():
            payload[key] = value.strip()
    if dropped_count > 0:
        payload["queue_merge"] = {
            "dropped_count": dropped_count,
            "preview": dropped_preview[:2],
        }
    meta = msg.metadata if isinstance(msg.metadata, dict) else {}
    raw_meta = meta.get("raw")
    if isinstance(raw_meta, (dict, list, str, int, float, bool)):
        payload["raw_metadata"] = raw_meta
    return payload


def _build_budget_hints(
    *,
    history_limit: int,
    dropped_count: int,
    fast_path: bool,
    skip_history_for_speed: bool,
    token_mode: str,
    probe_mode: bool = False,
) -> dict[str, Any]:
    load_level = "normal"
    if dropped_count > 0 or history_limit <= 12 or fast_path or skip_history_for_speed:
        load_level = "high"
    if dropped_count >= 3 and history_limit <= 8:
        load_level = "critical"
    return {
        "load_level": load_level,
        "history_limit": max(0, int(history_limit)),
        "dropped_count": max(0, int(dropped_count)),
        "fast_path": bool(fast_path),
        "probe_mode": bool(probe_mode),
        "token_mode": str(token_mode or "boros").strip().lower(),
    }


def _resolve_token_mode(perf_cfg: Any) -> str:
    raw = str(
        getattr(perf_cfg, "token_mode", None)
        or getattr(perf_cfg, "economy_mode", None)
        or "boros"
    ).strip().lower()
    if raw in {"hemat", "economy", "eco", "saving", "enabled", "on", "true", "1"}:
        return "hemat"
    return "boros"


async def _schedule_context_truncation_memory_fact(
    loop: Any,
    *,
    session_key: str,
    summary_meta: dict[str, Any] | None,
) -> None:
    if not isinstance(summary_meta, dict):
        return

    summary = str(summary_meta.get("summary") or "").strip()
    if not summary:
        return

    dropped_count = int(summary_meta.get("dropped_count", 0) or 0)
    fingerprint = str(summary_meta.get("fingerprint") or "").strip()
    if not fingerprint:
        fingerprint = hashlib.sha1(summary.encode("utf-8", errors="ignore")).hexdigest()[:16]

    cache = getattr(loop, "_context_truncation_fact_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        setattr(loop, "_context_truncation_fact_cache", cache)
    cache_key = str(session_key)
    if cache.get(cache_key) == fingerprint:
        return
    cache[cache_key] = fingerprint
    if len(cache) > 256:
        oldest_key = next(iter(cache.keys()))
        cache.pop(oldest_key, None)

    memory_obj = getattr(loop, "memory", None)
    remember_fact = getattr(memory_obj, "remember_fact", None)
    if not callable(remember_fact):
        return

    fact_text = f"Context compression summary ({dropped_count} dropped): {summary}"

    async def _persist() -> None:
        try:
            result = remember_fact(
                fact=fact_text,
                category="context_compression",
                session_id=session_key,
                confidence=0.55,
            )
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            logger.debug(f"context compression memory save skipped: {exc}")

    pending_tasks = getattr(loop, "_pending_memory_tasks", None)
    if isinstance(pending_tasks, set):
        task = asyncio.create_task(_persist())
        pending_tasks.add(task)
        task.add_done_callback(pending_tasks.discard)
        return
    await _persist()


