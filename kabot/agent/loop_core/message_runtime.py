"""Message/session runtime helpers extracted from AgentLoop."""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import re
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from loguru import logger

from kabot.agent.cron_fallback_nlp import (
    extract_weather_location,
    looks_like_meta_skill_or_workflow_prompt,
)
from kabot.agent.fallback_i18n import t
from kabot.agent.loop_core.tool_enforcement import (
    _extract_list_dir_path,
    _extract_read_file_path,
    _query_has_tool_payload,
)
from kabot.agent.semantic_intent import arbitrate_semantic_intent
from kabot.agent.skills import (
    looks_like_skill_creation_request,
    looks_like_skill_install_request,
)
from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.core.command_router import CommandContext
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


_PENDING_FOLLOWUP_TOOL_KEY = "pending_followup_tool"
_PENDING_FOLLOWUP_INTENT_KEY = "pending_followup_intent"
_PENDING_FOLLOWUP_TTL_SECONDS = 15 * 60
_LAST_TOOL_CONTEXT_KEY = "last_tool_context"
_LAST_TOOL_CONTEXT_TTL_SECONDS = 2 * 60 * 60
_SKILL_CREATION_FLOW_KEY = "skill_creation_flow"
_SKILL_CREATION_FLOW_TTL_SECONDS = 60 * 60
_KEEPALIVE_INITIAL_DELAY_SECONDS = 1.0
_KEEPALIVE_INTERVAL_SECONDS = 4.0
_KEEPALIVE_PASSTHROUGH_CHANNELS = {
    "telegram",
    "discord",
    "signal",
    "matrix",
    "teams",
    "google_chat",
    "mattermost",
    "webex",
    "line",
}
_MUTABLE_STATUS_LANE_CHANNELS = {
    "telegram",
    "discord",
    "slack",
    "signal",
    "matrix",
    "teams",
    "google_chat",
    "mattermost",
    "webex",
    "line",
}
_ABORT_REQUEST_TRIGGERS = {
    "stop",
    "abort",
    "halt",
    "interrupt",
    "exit",
    "wait",
    "please stop",
    "stop please",
    "stop kabot",
    "kabot stop",
    "stop action",
    "stop current action",
    "stop run",
    "stop current run",
    "stop agent",
    "stop the agent",
    "stop do not do anything",
    "stop don't do anything",
    "stop dont do anything",
    "stop doing anything",
    "do not do that",
    # Indonesian / Malay
    "berhenti",
    "hentikan",
    "stop dulu",
    "jangan lakukan itu",
    "jangan lakukan",
    # Spanish / French / German / Portuguese
    "detente",
    "deten",
    "arrete",
    "stopp",
    "anhalten",
    "aufhoren",
    "hoer auf",
    "pare",
    # Chinese / Japanese / Hindi / Arabic / Russian
    "\u505c\u6b62",
    "\u3084\u3081\u3066",
    "\u6b62\u3081\u3066",
    "\u0930\u0941\u0915\u094b",
    "\u062a\u0648\u0642\u0641",
    "\u0441\u0442\u043e\u043f",
    "\u043e\u0441\u0442\u0430\u043d\u043e\u0432\u0438",
    "\u043e\u0441\u0442\u0430\u043d\u043e\u0432\u0438\u0441\u044c",
    "\u043f\u0440\u0435\u043a\u0440\u0430\u0442\u0438",
}
_TRAILING_ABORT_PUNCT_RE = re.compile(r"[.!?,;:'\"\u2019\u201d)\]\}]+$", re.UNICODE)
_NON_ACTION_FOLLOWUP_MARKERS = (
    "stop",
    "hentikan",
    "berhenti",
    "jangan",
    "bukan",
    "dont",
    "don't",
    "do not",
    "not now",
    "cancel",
    "batalkan",
    "ga usah",
    "gak usah",
    "nggak usah",
    "tidak usah",
    "no need",
)
_NON_ACTION_TOPIC_MARKERS = (
    "bahas",
    "tentang",
    "soal",
    "about",
    "topic",
    "topik",
    "saham",
    "stock",
    "crypto",
    "berita",
    "news",
    "cuaca",
    "weather",
    "reminder",
    "ingat",
    "update",
)
_RUNTIME_META_FEEDBACK_MARKERS = (
    "lama",
    "lambat",
    "slow",
    "delay",
    "loading",
    "stuck",
    "hang",
    "lag",
    "ngelag",
)
_FILESYSTEM_LOCATION_QUERY_PATTERNS = (
    r"\bwhere are you now\b",
    r"\bwhere (?:are|r) you\b",
    r"\bcurrent (?:folder|directory|working directory|workspace)\b",
    r"\bwhat (?:folder|directory) are you in\b",
    r"\b(?:cwd|pwd)\b",
    r"\blokasi(?:mu)?(?: sekarang)? dimana\b",
    r"\bfolder(?:mu)?(?: sekarang)? dimana\b",
    r"\bdirektori(?:mu)?(?: sekarang)? dimana\b",
    r"\bpath(?:mu)?(?: sekarang)? dimana\b",
    r"你现在在哪个(?:文件夹|資料夾|目录|目錄)",
    r"你現在在哪個(?:文件夾|資料夾|目錄|目录)",
    r"今どの(?:フォルダ|ディレクトリ)にいる",
    r"現在どの(?:フォルダ|ディレクトリ)にいる",
    r"ตอนนี้คุณอยู่(?:โฟลเดอร์|ไดเรกทอรี)ไหน",
    r"ตอนนี้อยู่(?:โฟลเดอร์|ไดเรกทอรี)ไหน",
)
_SKILL_CREATION_APPROVAL_MARKERS = (
    "yes",
    "ok",
    "okay",
    "oke",
    "okey",
    "yup",
    "sure",
    "approve",
    "approved",
    "go ahead",
    "proceed",
    "continue",
    "lanjut",
    "lanjutkan",
    "gas",
    "setuju",
    "boleh",
    "silakan",
    "buat sekarang",
    "bikin sekarang",
    "jalankan",
    "eksekusi",
    "はい",
    "お願いします",
    "好的",
    "可以",
    "行",
    "ได้",
    "โอเค",
)
_WEATHER_CONTEXT_FOLLOWUP_MARKERS = (
    "angin",
    "berangin",
    "wind",
    "windy",
    "arah angin",
    "kecepatan angin",
    "windspeed",
    "wind speed",
    "wind direction",
    "hujan",
    "gerimis",
    "berawan",
    "cloudy",
    "sunny",
    "rain",
    "humidity",
    "kelembapan",
)
_FILELIKE_EXTENSION_RE = re.compile(
    r"\b[\w\-]+\.(json|ya?ml|toml|ini|cfg|conf|env|md|txt|csv|log|pdf|docx?|xlsx?|py|js|ts|tsx|jsx|html|css|xml)\b",
    re.IGNORECASE,
)
_PATHLIKE_TEXT_RE = re.compile(
    r"([a-zA-Z]:\\|\\\\|/[\w\-./]+|[\w\-./]+\\[\w\-./]+)"
)
_SHORT_INTERROGATIVE_RE = re.compile(
    r"\b(what|why|how|when|where|which|who|apa|kenapa|bagaimana|gimana|kapan|mana|siapa|berapa)\b",
    re.IGNORECASE,
)


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
    if any(mark in raw_text for mark in ("?", "？", "¿", "؟")):
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
    if any(mark in raw for mark in ("?", "ï¼Ÿ", "Â¿", "ØŸ")):
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


def _get_pending_followup_tool(session: Any, now_ts: float) -> dict[str, str] | None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return None
    pending = metadata.get(_PENDING_FOLLOWUP_TOOL_KEY)
    if not isinstance(pending, dict):
        return None

    tool_name = str(pending.get("tool") or "").strip()
    expires_at = pending.get("expires_at")
    try:
        expires_ts = float(expires_at)
    except Exception:
        expires_ts = 0.0

    if not tool_name or expires_ts <= now_ts:
        metadata.pop(_PENDING_FOLLOWUP_TOOL_KEY, None)
        return None
    source = str(pending.get("source") or "").strip()
    result = {"tool": tool_name}
    if source:
        result["source"] = source
    return result


def _get_last_tool_context(session: Any, now_ts: float) -> dict[str, Any] | None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return None
    payload = metadata.get(_LAST_TOOL_CONTEXT_KEY)
    if not isinstance(payload, dict):
        return None
    updated_at = payload.get("updated_at")
    try:
        updated_ts = float(updated_at)
    except Exception:
        updated_ts = 0.0
    if updated_ts and updated_ts + _LAST_TOOL_CONTEXT_TTL_SECONDS < now_ts:
        metadata.pop(_LAST_TOOL_CONTEXT_KEY, None)
        return None
    return payload


def _set_last_tool_context(session: Any, tool_name: str, now_ts: float, source_text: str) -> None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return
    normalized_tool = str(tool_name or "").strip()
    normalized_source = _normalize_text(source_text)[:200]
    if not normalized_tool or not normalized_source:
        return
    payload: dict[str, Any] = {
        "tool": normalized_tool,
        "source": normalized_source,
        "updated_at": now_ts,
    }
    previous = metadata.get(_LAST_TOOL_CONTEXT_KEY)
    previous_context = previous if isinstance(previous, dict) else None
    if normalized_tool == "stock":
        payload["symbol"] = normalized_source
    elif normalized_tool == "weather":
        previous_location = ""
        if isinstance(previous, dict):
            previous_location = str(previous.get("location") or "").strip()
        candidate_location = extract_weather_location(source_text) or ""
        if previous_location:
            looks_degraded = (
                not candidate_location
                or len(candidate_location) > max(12, len(previous_location) + 4)
                or any(marker in candidate_location for marker in ("wind", "angin", "風", "风", "ลม"))
            )
            if looks_degraded:
                candidate_location = previous_location
        payload["location"] = candidate_location or normalized_source
    elif normalized_tool == "list_dir":
        candidate_path = _extract_list_dir_path(source_text, last_tool_context=previous_context)
        if candidate_path:
            payload["path"] = candidate_path
    elif normalized_tool == "read_file":
        candidate_path = _extract_read_file_path(source_text)
        if candidate_path:
            payload["path"] = candidate_path
    metadata[_LAST_TOOL_CONTEXT_KEY] = payload


def _set_pending_followup_tool(session: Any, tool_name: str, now_ts: float, source_text: str) -> None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return
    normalized_source = _normalize_text(source_text)[:160]
    metadata[_PENDING_FOLLOWUP_TOOL_KEY] = {
        "tool": tool_name,
        "source": normalized_source,
        "updated_at": now_ts,
        "expires_at": now_ts + _PENDING_FOLLOWUP_TTL_SECONDS,
    }


def _clear_pending_followup_tool(session: Any) -> None:
    metadata = getattr(session, "metadata", None)
    if isinstance(metadata, dict):
        metadata.pop(_PENDING_FOLLOWUP_TOOL_KEY, None)


def _get_pending_followup_intent(session: Any, now_ts: float) -> dict[str, str] | None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return None
    pending = metadata.get(_PENDING_FOLLOWUP_INTENT_KEY)
    if not isinstance(pending, dict):
        return None

    intent_text = str(pending.get("text") or "").strip()
    profile = str(pending.get("profile") or "").strip().upper() or "GENERAL"
    expires_at = pending.get("expires_at")
    try:
        expires_ts = float(expires_at)
    except Exception:
        expires_ts = 0.0

    if not intent_text or expires_ts <= now_ts:
        metadata.pop(_PENDING_FOLLOWUP_INTENT_KEY, None)
        return None
    return {"text": intent_text, "profile": profile}


def _set_pending_followup_intent(session: Any, intent_text: str, profile: str, now_ts: float) -> None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return
    normalized_intent = _normalize_text(intent_text)[:220]
    if not normalized_intent:
        return
    metadata[_PENDING_FOLLOWUP_INTENT_KEY] = {
        "text": normalized_intent,
        "profile": str(profile or "GENERAL").strip().upper(),
        "updated_at": now_ts,
        "expires_at": now_ts + _PENDING_FOLLOWUP_TTL_SECONDS,
    }


def _clear_pending_followup_intent(session: Any) -> None:
    metadata = getattr(session, "metadata", None)
    if isinstance(metadata, dict):
        metadata.pop(_PENDING_FOLLOWUP_INTENT_KEY, None)


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
        if stripped.startswith(("- ", "* ", "• ", "1.", "2.", "3.", "4.")):
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


async def process_message(loop: Any, msg: InboundMessage) -> OutboundMessage | None:
    """Process a regular inbound message."""
    if msg.channel == "system":
        return await process_system_message(loop, msg)

    turn_started = time.perf_counter()
    turn_id = f"{msg.channel}:{msg.chat_id}:{int(msg.timestamp.timestamp() * 1000)}"
    setattr(loop, "_active_turn_id", turn_id)
    _emit_runtime_event(
        loop,
        "turn_start",
        turn_id=turn_id,
        channel=msg.channel,
        chat_id=msg.chat_id,
    )
    perf_cfg = getattr(loop, "runtime_performance", None)
    token_mode = _resolve_token_mode(perf_cfg)

    approval_action = loop._parse_approval_command(msg.content)
    if approval_action:
        action, approval_id = approval_action
        return await process_pending_exec_approval(
            loop,
            msg,
            action=action,
            approval_id=approval_id,
        )

    # OpenClaw-style abort shortcut: standalone stop/cancel intent should
    # immediately halt follow-up continuation and clear pending intent state.
    if _is_abort_request_text(msg.content):
        session = await loop._init_session(msg)
        _clear_pending_followup_tool(session)
        _clear_pending_followup_intent(session)
        runtime_locale = _resolve_runtime_locale(session, msg, msg.content)
        stop_text = t("runtime.abort.ack", locale=runtime_locale, text=msg.content)
        _emit_runtime_event(loop, "turn_abort_shortcut", turn_id=turn_id)
        return await loop._finalize_session(msg, session, stop_text)

    # Phase 8: Intercept slash commands BEFORE routing to LLM
    if loop.command_router.is_command(msg.content):
        ctx = CommandContext(
            message=msg.content,
            args=[],
            sender_id=msg.sender_id,
            channel=msg.channel,
            chat_id=msg.chat_id,
            session_key=msg.session_key,
            agent_loop=loop,
        )
        result = await loop.command_router.route(msg.content, ctx)
        if result:
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=result,
            )

    session = await loop._init_session(msg)
    if not bool(getattr(loop, "_cold_start_reported", False)):
        boot_started = getattr(loop, "_boot_started_at", None)
        startup_ready = getattr(loop, "_startup_ready_at", None)
        if isinstance(boot_started, (int, float)) and isinstance(startup_ready, (int, float)):
            cold_start_ms = int((startup_ready - boot_started) * 1000)
            logger.info(f"cold_start_ms={max(0, cold_start_ms)}")
        elif isinstance(boot_started, (int, float)):
            cold_start_ms = int((time.perf_counter() - boot_started) * 1000)
            logger.info(f"cold_start_ms={cold_start_ms}")
        loop._cold_start_reported = True

    # Phase 9: Parse directives from message body
    clean_body, directives = loop.directive_parser.parse(msg.content)
    effective_content = clean_body or msg.content
    intent_source_for_followup = effective_content

    # Store directives in session metadata
    if directives.raw_directives:
        active = loop.directive_parser.format_active_directives(directives)
        logger.info(f"Directives active: {active}")

        session.metadata["directives"] = {
            "think": directives.think,
            "verbose": directives.verbose,
            "elevated": directives.elevated,
        }
        # Ensure metadata persists
        loop.sessions.save(session)

    # Phase 9: Model override via directive
    if directives.model:
        logger.info(f"Directive override: model -> {directives.model}")
        if isinstance(msg.metadata, dict):
            override = str(directives.model).strip()
            if override:
                msg.metadata["model_override"] = override
                msg.metadata["model_override_source"] = "directive"

    # Phase 13: Detect document uploads and inject hint for KnowledgeLearnTool
    if hasattr(msg, "media") and msg.media:
        document_paths = []
        for path in msg.media:
            ext = Path(path).suffix.lower()
            if ext in [".pdf", ".txt", ".md", ".csv"]:
                document_paths.append(path)

        if document_paths:
            hint = "\n\n[System Note: Document(s) detected: " + ", ".join(document_paths) + ". If the user wants you to 'learn' or 'memorize' these permanently, use the 'knowledge_learn' tool.]"
            effective_content += hint
            logger.info(f"Document hint injected: {len(document_paths)} files")

    required_tool = loop._required_tool_for_query(effective_content)
    required_tool_query = effective_content
    now_ts = time.time()
    is_background_task = (
        (msg.channel or "").lower() == "system"
        or (msg.sender_id or "").lower() == "system"
        or (
            isinstance(msg.content, str)
            and msg.content.strip().lower().startswith("heartbeat task:")
        )
    )

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
        "stock_analysis",
        "crypto",
        "server_monitor",
        "check_update",
        "system_update",
    }
    fast_direct_context = bool(
        perf_cfg
        and bool(getattr(perf_cfg, "fast_first_response", True))
        and required_tool in direct_tools
    )

    history_limit = 30
    if perf_cfg and bool(getattr(perf_cfg, "fast_first_response", True)):
        warmup_task = getattr(loop, "_memory_warmup_task", None)
        if warmup_task is not None and not warmup_task.done():
            history_limit = 12
    if fast_direct_context:
        history_limit = min(history_limit, 6)

    probe_mode = _is_probe_mode_message(msg)
    conversation_history: list[dict[str, Any]] = []
    skip_history_for_speed = bool(
        perf_cfg
        and bool(getattr(perf_cfg, "fast_first_response", True))
        and _looks_like_live_research_query(effective_content)
    )
    if not probe_mode and not fast_direct_context and not skip_history_for_speed:
        conversation_history = loop.memory.get_conversation_context(msg.session_key, max_messages=history_limit)
        if conversation_history:
            conversation_history = [m for m in conversation_history if isinstance(m, dict)]

    # Router triase: SIMPLE vs COMPLEX
    decision = await loop.router.route(effective_content)
    logger.info(f"Route: profile={decision.profile}, complex={decision.is_complex}")
    try:
        msg.metadata["route_profile"] = decision.profile
        msg.metadata["route_complex"] = bool(decision.is_complex)
    except Exception:
        pass

    pending_followup_tool_payload = _get_pending_followup_tool(session, now_ts)
    pending_followup_tool = (
        str(pending_followup_tool_payload.get("tool") or "").strip()
        if isinstance(pending_followup_tool_payload, dict)
        else None
    )
    pending_followup_source = (
        str(pending_followup_tool_payload.get("source") or "").strip()
        if isinstance(pending_followup_tool_payload, dict)
        else ""
    )
    last_tool_context = _get_last_tool_context(session, now_ts)
    pending_followup_intent = _get_pending_followup_intent(session, now_ts)
    is_short_confirmation = bool(not required_tool and _looks_like_short_confirmation(effective_content))
    is_closing_ack = _looks_like_closing_acknowledgement(effective_content)
    is_short_greeting = _looks_like_short_greeting_smalltalk(effective_content)
    is_non_action_feedback = _looks_like_non_action_meta_feedback(effective_content)
    raw_is_explicit_new_request = _looks_like_explicit_new_request(effective_content)
    is_weather_context_followup = bool(
        pending_followup_tool == "weather"
        and _looks_like_weather_context_followup(effective_content)
    )
    is_explicit_new_request = bool(raw_is_explicit_new_request and not is_weather_context_followup)
    semantic_hint = arbitrate_semantic_intent(
        effective_content,
        parser_tool=required_tool,
        pending_followup_tool=pending_followup_tool,
        pending_followup_source=pending_followup_source,
        last_tool_context=last_tool_context,
        payload_checker=_query_has_tool_payload,
    )
    meta_skill_reference_turn = looks_like_meta_skill_or_workflow_prompt(effective_content)
    if semantic_hint.kind in {"advice_turn", "meta_feedback"}:
        required_tool = None
        required_tool_query = effective_content
    elif semantic_hint.required_tool:
        required_tool = semantic_hint.required_tool
        required_tool_query = str(semantic_hint.required_tool_query or effective_content).strip()
    if meta_skill_reference_turn:
        required_tool = None
        required_tool_query = effective_content
    is_non_action_feedback = bool(is_non_action_feedback or semantic_hint.kind == "meta_feedback")

    if (
        required_tool
        and pending_followup_tool
        and required_tool == pending_followup_tool
        and pending_followup_source
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
    ):
        enrich_from_pending = bool(
            is_weather_context_followup
            or _is_short_context_followup(effective_content)
            or is_short_confirmation
        )
        if enrich_from_pending:
            try:
                raw_has_payload = _query_has_tool_payload(required_tool, effective_content)
                pending_has_payload = _query_has_tool_payload(required_tool, pending_followup_source)
            except Exception:
                raw_has_payload = False
                pending_has_payload = False
            if pending_has_payload and not raw_has_payload:
                required_tool_query = f"{pending_followup_source} {effective_content}".strip()

    if is_closing_ack or is_short_greeting or is_non_action_feedback or semantic_hint.clear_pending:
        _clear_pending_followup_tool(session)
        _clear_pending_followup_intent(session)
    elif is_explicit_new_request and not required_tool:
        # Fresh explicit asks (file/config/path/URL/command-like payload) should
        # not inherit stale pending follow-up state from previous turns.
        _clear_pending_followup_tool(session)
        _clear_pending_followup_intent(session)
        pending_followup_tool = None
        pending_followup_source = ""
        pending_followup_intent = None

    if (
        not required_tool
        and str(decision.profile).upper() == "RESEARCH"
        and _tool_registry_has(loop, "web_search")
        and _looks_like_live_research_query(effective_content)
    ):
        required_tool = "web_search"
        required_tool_query = effective_content
        decision.is_complex = True
        logger.info(
            f"Research safety latch: '{_normalize_text(effective_content)[:120]}' -> required_tool=web_search"
        )
        fast_direct_context = bool(
            perf_cfg
            and bool(getattr(perf_cfg, "fast_first_response", True))
            and required_tool in direct_tools
        )

    if (
        pending_followup_tool
        and not decision.is_complex
        and not required_tool
        and (is_short_confirmation or is_weather_context_followup)
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not is_explicit_new_request
    ):
        required_tool = pending_followup_tool
        if pending_followup_source:
            if is_weather_context_followup:
                required_tool_query = f"{pending_followup_source} {effective_content}".strip()
            else:
                required_tool_query = pending_followup_source
        decision.is_complex = True
        logger.info(
            f"Session follow-up inference: '{_normalize_text(effective_content)}' -> required_tool={required_tool}"
        )
        fast_direct_context = bool(
            perf_cfg
            and bool(getattr(perf_cfg, "fast_first_response", True))
            and required_tool in direct_tools
        )

    # Infer required tool for short follow-ups before context building, so
    # confirmations like "gas"/"ambil sekarang" can take the direct fast path.
    if (
        not decision.is_complex
        and not required_tool
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not is_explicit_new_request
    ):
        normalized_followup = _normalize_text(effective_content)
        if _looks_like_short_confirmation(normalized_followup):
            inferred_tool = None
            inferred_source = None
            infer_from_history = getattr(loop, "_infer_required_tool_from_history", None)
            if callable(infer_from_history):
                try:
                    inferred_tool, inferred_source = infer_from_history(
                        effective_content,
                        conversation_history,
                    )
                except Exception:
                    inferred_tool, inferred_source = None, None
            else:
                # Backward-compatible fallback for lightweight test doubles
                # that don't expose the loop facade helper yet.
                for item in reversed(conversation_history[-8:]):
                    role = str(item.get("role", "") or "").strip().lower()
                    candidate = str(item.get("content", "") or "").strip()
                    if not candidate:
                        continue
                    # Never infer required tools from assistant text. Assistant
                    # summaries/offers can contain rich keywords/tickers that are
                    # not fresh user intent and can cause rigid/hallucinated routing.
                    if role != "user":
                        continue
                    candidate_norm = _normalize_text(candidate)
                    if not candidate_norm or candidate_norm == normalized_followup:
                        continue
                    if _looks_like_short_confirmation(candidate):
                        continue
                    inferred = loop._required_tool_for_query(candidate)
                    if inferred:
                        inferred_tool = inferred
                        inferred_source = candidate
                        break
            if inferred_tool:
                required_tool = inferred_tool
                required_tool_query = str(inferred_source or required_tool_query or effective_content).strip()
                decision.is_complex = True
                logger.info(
                    f"Pre-context follow-up inference: '{normalized_followup}' -> required_tool={inferred_tool}"
                )
                fast_direct_context = bool(
                    perf_cfg
                    and bool(getattr(perf_cfg, "fast_first_response", True))
                    and required_tool in direct_tools
                )

    if (
        pending_followup_intent
        and not required_tool
        and is_short_confirmation
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not is_explicit_new_request
    ):
        intent_text = str(pending_followup_intent.get("text") or "").strip()
        intent_profile = str(pending_followup_intent.get("profile") or "GENERAL").strip().upper()
        inferred_tool = loop._required_tool_for_query(intent_text) if intent_text else None
        if inferred_tool:
            required_tool = inferred_tool
            required_tool_query = intent_text
            decision.is_complex = True
            logger.info(
                f"Session intent follow-up inference: '{_normalize_text(effective_content)}' -> required_tool={inferred_tool}"
            )
            fast_direct_context = bool(
                perf_cfg
                and bool(getattr(perf_cfg, "fast_first_response", True))
                and required_tool in direct_tools
            )
        else:
            # Preserve non-tool intent context so short confirms like
            # "ya/lanjut/gas" still continue the previous actionable flow.
            effective_content = (
                f"{effective_content}\n\n[Follow-up Context]\n{intent_text}"
                if intent_text
                else effective_content
            )
            if not decision.is_complex and str(decision.profile).upper() == "CHAT":
                decision.profile = intent_profile if intent_profile else decision.profile
                if intent_profile in {"CODING", "RESEARCH", "GENERAL"}:
                    decision.is_complex = True
            logger.info(
                f"Session intent context continued: '{_normalize_text(effective_content)[:120]}' profile={decision.profile} complex={decision.is_complex}"
            )

    current_skill_flow = _get_skill_creation_flow(session, now_ts)
    current_skill_flow_kind = str((current_skill_flow or {}).get("kind") or "create").strip().lower() or "create"
    skill_creation_followup = bool(
        current_skill_flow
        and current_skill_flow_kind != "install"
        and (
            is_short_confirmation
            or _looks_like_skill_creation_approval(msg.content)
        )
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not is_explicit_new_request
    )
    skill_install_followup = bool(
        current_skill_flow
        and current_skill_flow_kind == "install"
        and (
            is_short_confirmation
            or _looks_like_skill_creation_approval(msg.content)
        )
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not is_explicit_new_request
    )
    skill_creation_intent = bool(
        looks_like_skill_creation_request(effective_content) or skill_creation_followup
    )
    skill_install_intent = bool(
        looks_like_skill_install_request(effective_content) or skill_install_followup
    )
    if skill_install_intent:
        skill_creation_intent = False
    forced_skill_names: list[str] | None = None
    llm_current_message = effective_content
    filesystem_location_context_note = ""
    explicit_file_analysis_note = ""
    skill_creation_stage = str((current_skill_flow or {}).get("stage") or "discovery").strip().lower() or "discovery"
    skill_workflow_kind = "install" if skill_install_intent else current_skill_flow_kind
    skill_creation_request_text = str((current_skill_flow or {}).get("request_text") or effective_content).strip()
    skill_creation_approved = False
    if skill_creation_intent or skill_install_intent:
        # Skill workflows must outrank deterministic tool routing; otherwise
        # ordinary domain words like "weather" or repo-like text can hijack
        # create/update/install requests into stock/weather direct tools.
        required_tool = None
        required_tool_query = ""
        if (skill_creation_followup or skill_install_followup) and current_skill_flow:
            skill_creation_request_text = str(current_skill_flow.get("request_text") or skill_creation_request_text).strip()
            effective_content = (
                f"{effective_content}\n\n[Follow-up Context]\n{skill_creation_request_text}"
                if skill_creation_request_text and "[Follow-up Context]" not in effective_content
                else effective_content
            )
        if skill_creation_stage == "planning" and _looks_like_skill_creation_approval(msg.content):
            skill_creation_stage = "approved"
            skill_creation_approved = True
        if not decision.is_complex:
            decision.is_complex = True
            logger.info(
                f"Skill workflow latch: '{_normalize_text(effective_content)[:120]}' -> complex route"
            )
        forced_skill_names = ["skill-installer"] if skill_install_intent else ["skill-creator"]
        first_turn = "[Follow-up Context]" not in effective_content
        llm_current_message = (
            f"{effective_content}\n\n{_build_skill_creation_workflow_note(first_turn=first_turn, approved=skill_creation_approved, kind=skill_workflow_kind)}"
        ).strip()
        _set_skill_creation_flow(
            session,
            skill_creation_request_text,
            now_ts,
            stage=skill_creation_stage,
            kind=skill_workflow_kind,
        )
    elif current_skill_flow and is_explicit_new_request:
        _clear_skill_creation_flow(session)

    if (
        not required_tool
        and not skill_creation_intent
        and not skill_install_intent
        and _looks_like_filesystem_location_query(effective_content)
    ):
        filesystem_location_context_note = _build_filesystem_location_context_note(loop, session, last_tool_context)
        if filesystem_location_context_note:
            llm_current_message = f"{effective_content}\n\n{filesystem_location_context_note}".strip()
    elif not required_tool and not skill_creation_intent and not skill_install_intent:
        explicit_file_path = _extract_read_file_path(effective_content)
        if explicit_file_path:
            explicit_file_analysis_note = _build_explicit_file_analysis_note(explicit_file_path)
            if explicit_file_analysis_note:
                llm_current_message = f"{effective_content}\n\n{explicit_file_analysis_note}".strip()

    if required_tool:
        _set_pending_followup_tool(session, required_tool, now_ts, str(required_tool_query or effective_content))
        _set_last_tool_context(session, required_tool, now_ts, str(required_tool_query or effective_content))
    elif not is_short_confirmation:
        _clear_pending_followup_tool(session)

    if _should_store_followup_intent(
        intent_source_for_followup,
        required_tool=required_tool,
        decision_profile=str(decision.profile),
        decision_is_complex=bool(decision.is_complex),
    ):
        _set_pending_followup_intent(session, intent_source_for_followup, str(decision.profile), now_ts)
    elif not _looks_like_short_confirmation(intent_source_for_followup):
        _clear_pending_followup_intent(session)

    runtime_locale = _resolve_runtime_locale(session, msg, effective_content)
    if isinstance(msg.metadata, dict):
        msg.metadata["runtime_locale"] = runtime_locale
        msg.metadata["effective_content"] = effective_content
        if forced_skill_names:
            msg.metadata["forced_skill_names"] = list(forced_skill_names)
        else:
            msg.metadata.pop("forced_skill_names", None)
        if last_tool_context:
            msg.metadata["last_tool_context"] = last_tool_context
        else:
            msg.metadata.pop("last_tool_context", None)
        if semantic_hint.kind != "none":
            msg.metadata["semantic_intent_hint"] = semantic_hint.kind
        else:
            msg.metadata.pop("semantic_intent_hint", None)
        msg.metadata["suppress_required_tool_inference"] = bool(
            semantic_hint.kind in {"advice_turn", "meta_feedback"}
            or meta_skill_reference_turn
            or skill_creation_intent
            or skill_install_intent
        )
        if required_tool:
            msg.metadata["required_tool"] = required_tool
            msg.metadata["required_tool_query"] = str(required_tool_query or effective_content).strip()
        else:
            msg.metadata.pop("required_tool", None)
            msg.metadata.pop("required_tool_query", None)
        msg.metadata["skip_critic_for_speed"] = bool(
            required_tool
            or _is_short_context_followup(msg.content)
            or _is_short_context_followup(effective_content)
            or _looks_like_short_confirmation(msg.content)
            or _looks_like_short_confirmation(effective_content)
        )
        msg.metadata["status_mutable_lane"] = bool(
            _channel_uses_mutable_status_lane(loop, msg.channel)
        )
        if skill_creation_intent or skill_install_intent:
            msg.metadata["skill_creation_guard"] = {
                "active": True,
                "stage": skill_creation_stage,
                "approved": skill_creation_approved,
                "kind": skill_workflow_kind,
                "request_text": skill_creation_request_text,
            }
        else:
            msg.metadata.pop("skill_creation_guard", None)

    fast_simple_context = bool(
        perf_cfg
        and bool(getattr(perf_cfg, "fast_first_response", True))
        and not decision.is_complex
        and not required_tool
        and not filesystem_location_context_note
        and not explicit_file_analysis_note
    )

    queue_meta = msg.metadata if isinstance(msg.metadata, dict) else {}
    queue_info = queue_meta.get("queue") if isinstance(queue_meta.get("queue"), dict) else {}
    dropped_count = int(queue_info.get("dropped_count", 0) or 0)
    dropped_preview = queue_info.get("dropped_preview", [])
    preview_items = [str(item).strip() for item in dropped_preview if str(item).strip()]
    untrusted_context = _build_untrusted_context_payload(
        msg,
        dropped_count=dropped_count,
        dropped_preview=preview_items,
    )

    queued_status = t("runtime.status.queued", locale=runtime_locale, text=effective_content)
    if dropped_count > 0:
        queued_status += " " + t(
            "runtime.status.queued_merged",
            locale=runtime_locale,
            text=effective_content,
            count=dropped_count,
        )
        merge_note = f"[Queue Merge] {dropped_count} pending message(s) were merged before processing."
        if preview_items:
            merge_note += " Earlier snippets: " + " | ".join(preview_items[:2])
        effective_content = f"{effective_content}\n\n{merge_note}"
    thinking_status = t("runtime.status.thinking", locale=runtime_locale, text=effective_content)
    approved_status = t("runtime.status.approved", locale=runtime_locale, text=effective_content)
    done_status = t("runtime.status.done", locale=runtime_locale, text=effective_content)
    error_status = t("runtime.status.error", locale=runtime_locale, text=effective_content)

    async def _publish_status(text: str, phase: str, *, keepalive: bool = False) -> None:
        bus = getattr(loop, "bus", None)
        publish = getattr(bus, "publish_outbound", None)
        if not callable(publish):
            return
        try:
            metadata = {"type": "status_update", "phase": phase}
            metadata["lane"] = "status"
            if keepalive:
                metadata["keepalive"] = True
            await publish(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=text,
                    metadata=metadata,
                )
            )
        except Exception:
            return

    keepalive_stop = asyncio.Event()
    keepalive_task: asyncio.Task | None = None

    async def _keepalive_loop() -> None:
        try:
            try:
                await asyncio.wait_for(
                    keepalive_stop.wait(),
                    timeout=float(_KEEPALIVE_INITIAL_DELAY_SECONDS),
                )
                return
            except asyncio.TimeoutError:
                pass

            while not keepalive_stop.is_set():
                await _publish_status(thinking_status, "thinking", keepalive=True)
                try:
                    await asyncio.wait_for(
                        keepalive_stop.wait(),
                        timeout=float(_KEEPALIVE_INTERVAL_SECONDS),
                    )
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            return

    mutable_status_lane = bool(_channel_uses_mutable_status_lane(loop, msg.channel))
    keepalive_enabled = bool(
        not is_background_task and _channel_supports_keepalive_passthrough(loop, msg.channel)
    )
    if not is_background_task:
        await _publish_status(queued_status, "queued")
        if skill_creation_approved and mutable_status_lane:
            await _publish_status(approved_status, "approved")
        if keepalive_enabled and isinstance(msg.metadata, dict):
            msg.metadata["suppress_initial_thinking_status"] = True
        if keepalive_enabled:
            keepalive_task = asyncio.create_task(_keepalive_loop())
    try:
        context_builder = loop.context
        resolve_context = getattr(loop, "_resolve_context_for_message", None)
        if callable(resolve_context):
            try:
                resolved_context = resolve_context(msg)
                if resolved_context is not None:
                    context_builder = resolved_context
            except Exception as exc:
                logger.warning(f"Failed to resolve routed context builder: {exc}")

        if fast_simple_context and _message_needs_full_skill_context(
            context_builder,
            llm_current_message,
            str(decision.profile),
        ):
            fast_simple_context = False

        if fast_direct_context or fast_simple_context:
            messages = [{"role": "user", "content": effective_content}]
            context_build_ms = 0
        else:
            context_started = time.perf_counter()
            budget_hints = _build_budget_hints(
                history_limit=history_limit,
                dropped_count=dropped_count,
                fast_path=bool(fast_direct_context or fast_simple_context),
                skip_history_for_speed=skip_history_for_speed,
                token_mode=token_mode,
                probe_mode=probe_mode,
            )
            messages = await asyncio.to_thread(
                context_builder.build_messages,
                history=conversation_history,
                current_message=llm_current_message,
                skill_names=forced_skill_names,
                media=msg.media if hasattr(msg, "media") else None,
                channel=msg.channel,
                chat_id=msg.chat_id,
                profile=decision.profile,
                tool_names=loop.tools.tool_names,
                untrusted_context=untrusted_context,
                budget_hints=budget_hints,
            )
            truncation_summary = None
            consume_summary = getattr(context_builder, "consume_last_truncation_summary", None)
            if callable(consume_summary):
                try:
                    truncation_summary = consume_summary()
                except Exception as exc:
                    logger.debug(f"Failed reading context truncation summary: {exc}")
            await _schedule_context_truncation_memory_fact(
                loop,
                session_key=msg.session_key,
                summary_meta=truncation_summary,
            )
            context_build_ms = int((time.perf_counter() - context_started) * 1000)
        max_context_build_ms = int(getattr(perf_cfg, "max_context_build_ms", 500)) if perf_cfg else 500
        logger.info(f"turn_id={turn_id} context_build_ms={context_build_ms}")
        _emit_runtime_event(
            loop,
            "context_built",
            turn_id=turn_id,
            context_build_ms=context_build_ms,
        )
        if context_build_ms > max_context_build_ms:
            logger.warning(
                f"turn_id={turn_id} context_build_ms={context_build_ms} exceeded budget={max_context_build_ms}"
            )

        if decision.is_complex or required_tool:
            if required_tool and not decision.is_complex:
                logger.info(f"Route override: simple -> complex (required_tool={required_tool})")
            final_content = await loop._run_agent_loop(msg, messages, session)
        else:
            if not is_background_task and mutable_status_lane:
                await _publish_status(thinking_status, "thinking")
            final_content = await loop._run_simple_response(msg, messages)
            if not is_background_task and mutable_status_lane:
                await _publish_status(done_status if final_content else error_status, "done" if final_content else "error")

        _update_skill_creation_flow_after_response(
            session,
            msg,
            final_content,
            now_ts=time.time(),
        )
    finally:
        keepalive_stop.set()
        if keepalive_task is not None:
            keepalive_task.cancel()
            with suppress(asyncio.CancelledError):
                await keepalive_task

    first_response_ms = int((time.perf_counter() - turn_started) * 1000)
    logger.info(f"turn_id={turn_id} first_response_ms={first_response_ms}")
    warmup_ms: int | None = None
    started_at = getattr(loop, "_memory_warmup_started_at", None)
    completed_at = getattr(loop, "_memory_warmup_completed_at", None)
    if isinstance(started_at, (int, float)) and isinstance(completed_at, (int, float)) and completed_at >= started_at:
        warmup_ms = int((completed_at - started_at) * 1000)
    _emit_runtime_event(
        loop,
        "turn_end",
        turn_id=turn_id,
        first_response_ms=first_response_ms,
        memory_warmup_ms=warmup_ms if warmup_ms is not None else -1,
    )
    max_first_response_soft = int(getattr(perf_cfg, "max_first_response_ms_soft", 4000)) if perf_cfg else 4000
    if first_response_ms > max_first_response_soft:
        logger.warning(
            f"turn_id={turn_id} first_response_ms={first_response_ms} exceeded soft_target={max_first_response_soft}"
        )

    # Start memory warmup after first response path when defer mode is active.
    suppress_post_response_warmup = bool(
        isinstance(getattr(msg, "metadata", None), dict)
        and msg.metadata.get("suppress_post_response_warmup")
    )
    if (
        perf_cfg
        and bool(getattr(perf_cfg, "defer_memory_warmup", True))
        and not suppress_post_response_warmup
    ):
        ensure_warmup = getattr(loop, "_ensure_memory_warmup_task", None)
        if callable(ensure_warmup):
            ensure_warmup()

    return await loop._finalize_session(msg, session, final_content)


async def process_pending_exec_approval(
    loop: Any,
    msg: InboundMessage,
    action: str,
    approval_id: str | None = None,
) -> OutboundMessage:
    """Handle explicit approval commands for pending exec actions."""
    session = await loop._init_session(msg)
    exec_tool = loop.tools.get("exec")
    if not exec_tool or not hasattr(exec_tool, "consume_pending_approval"):
        return await loop._finalize_session(
            msg,
            session,
            "No executable approval flow is available in this session.",
        )

    if action == "deny":
        cleared = exec_tool.clear_pending_approval(msg.session_key, approval_id)
        if cleared:
            return await loop._finalize_session(
                msg,
                session,
                "Pending command approval denied.",
            )
        return await loop._finalize_session(
            msg,
            session,
            "No matching pending command approval found.",
        )

    pending = exec_tool.consume_pending_approval(msg.session_key, approval_id)
    if not pending:
        return await loop._finalize_session(
            msg,
            session,
            "No matching pending command approval found.",
        )

    command = pending.get("command")
    if not isinstance(command, str) or not command.strip():
        return await loop._finalize_session(
            msg,
            session,
            "Pending approval entry is invalid.",
        )

    working_dir = pending.get("working_dir")
    result = await exec_tool.execute(
        command=command,
        working_dir=working_dir if isinstance(working_dir, str) else None,
        _session_key=msg.session_key,
        _approved_by_user=True,
    )
    return await loop._finalize_session(msg, session, result)


async def process_system_message(loop: Any, msg: InboundMessage) -> OutboundMessage | None:
    """Process synthetic/system messages (e.g., cron callbacks)."""
    logger.info(f"Processing system message from {msg.sender_id}")
    if ":" in msg.chat_id:
        parts = msg.chat_id.split(":", 1)
        origin_channel, origin_chat_id = parts[0], parts[1]
    else:
        origin_channel, origin_chat_id = "cli", msg.chat_id

    session_key = f"{origin_channel}:{origin_chat_id}"
    session = loop.sessions.get_or_create(session_key)

    for tool_name in ["message", "spawn", "cron"]:
        tool = loop.tools.get(tool_name)
        if hasattr(tool, "set_context"):
            tool.set_context(origin_channel, origin_chat_id)

    context_builder = loop.context
    resolve_context = getattr(loop, "_resolve_context_for_channel_chat", None)
    if callable(resolve_context):
        try:
            resolved_context = resolve_context(origin_channel, origin_chat_id)
            if resolved_context is not None:
                context_builder = resolved_context
        except Exception as exc:
            logger.warning(f"Failed to resolve system routed context builder: {exc}")

    messages = context_builder.build_messages(
        history=session.get_history(),
        current_message=msg.content,
        channel=origin_channel,
        chat_id=origin_chat_id,
    )

    final_content = await loop._run_agent_loop(msg, messages, session)
    session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
    if final_content:
        session.add_message("assistant", final_content)
    try:
        loop.sessions.save(session)
    except Exception as exc:
        logger.warning(f"Session save failed for {session_key}: {exc}")
    return OutboundMessage(
        channel=origin_channel,
        chat_id=origin_chat_id,
        content=final_content or "",
    )


async def process_isolated(
    loop: Any,
    content: str,
    channel: str = "cli",
    chat_id: str = "direct",
    job_id: str = "",
) -> str:
    """Process a message in a fully isolated session."""
    session_key = f"isolated:cron:{job_id}" if job_id else f"isolated:{int(time.time())}"
    msg = InboundMessage(
        channel=channel,
        sender_id="system",
        chat_id=chat_id,
        content=content,
        _session_key=session_key,
    )

    # Set context for tools without loading history
    for tool_name in ["message", "spawn", "cron"]:
        tool = loop.tools.get(tool_name)
        if hasattr(tool, "set_context"):
            tool.set_context(channel, chat_id)

    # Build messages without history: fresh context
    context_builder = loop.context
    resolve_context = getattr(loop, "_resolve_context_for_channel_chat", None)
    if callable(resolve_context):
        try:
            resolved_context = resolve_context(channel, chat_id)
            if resolved_context is not None:
                context_builder = resolved_context
        except Exception as exc:
            logger.warning(f"Failed to resolve isolated routed context builder: {exc}")

    messages = context_builder.build_messages(
        history=[],
        current_message=content,
        channel=channel,
        chat_id=chat_id,
        profile="GENERAL",
        tool_names=loop.tools.tool_names,
    )

    # Create a minimal session for isolated execution
    session = loop.sessions.get_or_create(session_key)

    # Run the full loop for isolated jobs.
    final_content = await loop._run_agent_loop(msg, messages, session)
    return final_content or ""
