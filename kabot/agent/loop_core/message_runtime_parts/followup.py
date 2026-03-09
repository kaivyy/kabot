"""Follow-up tool/context state helpers extracted from message_runtime."""

from __future__ import annotations

import re
from typing import Any


def _normalize_followup_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _extract_weather_location_proxy(text: str) -> str | None:
    from kabot.agent.loop_core import message_runtime as message_runtime_module

    return message_runtime_module.extract_weather_location(text)


def _extract_list_dir_path_proxy(
    text: str,
    *,
    last_tool_context: dict[str, Any] | None = None,
) -> str:
    from kabot.agent.loop_core import message_runtime as message_runtime_module

    return message_runtime_module._extract_list_dir_path(text, last_tool_context=last_tool_context)


def _extract_read_file_path_proxy(text: str) -> str:
    from kabot.agent.loop_core import message_runtime as message_runtime_module

    return message_runtime_module._extract_read_file_path(text)


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
_FILE_CONTEXT_FOLLOWUP_MARKERS = (
    "file ini",
    "berkas ini",
    "this file",
    "that file",
    "this html",
    "this css",
    "this config",
    "html ini",
    "css ini",
    "config ini",
    "font di file",
    "font pada file",
    "font yang dipakai",
    "isi file ini",
    "open this html",
    "check this css",
    "read this config",
    "这个文件",
    "这个 html",
    "这个 css",
    "这个配置",
    "字体是什么",
    "这个网页",
    "このファイル",
    "この html",
    "この css",
    "この設定",
    "フォントは",
    "このサイト",
    "ไฟล์นี้",
    "html นี้",
    "css นี้",
    "config นี้",
    "ฟอนต์ในไฟล์นี้",
    "ฟอนต์คืออะไร",
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
    normalized_source = _normalize_followup_text(source_text)[:200]
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
        candidate_location = _extract_weather_location_proxy(source_text) or ""
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
        candidate_path = _extract_list_dir_path_proxy(source_text, last_tool_context=previous_context)
        if candidate_path:
            payload["path"] = candidate_path
    elif normalized_tool == "read_file":
        candidate_path = _extract_read_file_path_proxy(source_text)
        if candidate_path:
            payload["path"] = candidate_path
    metadata[_LAST_TOOL_CONTEXT_KEY] = payload


def _set_pending_followup_tool(session: Any, tool_name: str, now_ts: float, source_text: str) -> None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return
    normalized_source = _normalize_followup_text(source_text)[:160]
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
    normalized_intent = _normalize_followup_text(intent_text)[:220]
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
