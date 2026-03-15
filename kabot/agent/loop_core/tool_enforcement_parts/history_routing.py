"""History-driven tool inference helpers for tool enforcement."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from kabot.agent.cron_fallback_nlp import required_tool_for_query
from kabot.agent.cron_fallback_nlp import build_group_id as nlp_build_group_id
from kabot.agent.cron_fallback_nlp import make_unique_schedule_title as nlp_make_unique_schedule_title
from kabot.agent.loop_core.tool_enforcement_parts.action_requests import (
    infer_action_required_tool_for_loop,
)
from kabot.agent.loop_core.tool_enforcement_parts.common import (
    _is_low_information_followup,
    _normalize_text,
)
from kabot.agent.loop_core.tool_enforcement_parts.filesystem_paths import (
    _PATHLIKE_QUERY_RE,
    _extract_list_dir_path,
    _extract_read_file_path,
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
_OPTION_SELECTION_CJK_ORDINAL_RE = re.compile(
    r"第(?P<ref>[一二三四五\d]{1,2})(?:个|個|番|つ目)?"
)
_OPTION_SELECTION_JA_NUMERIC_RE = re.compile(r"(?P<ref>\d{1,2})番")
_OPTION_SELECTION_THAI_NUMERIC_RE = re.compile(r"ข้อ\s*(?P<ref>\d{1,2})")
_OPTION_SELECTION_THAI_ORDINAL_RE = re.compile(
    r"(?:ข้อ\s*)?(?:ที่)?(?P<ref>แรก|หนึ่ง|สอง|สาม|สี่|ห้า)"
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
    "แรก": "1",
    "หนึ่ง": "1",
    "สอง": "2",
    "สาม": "3",
    "สี่": "4",
    "ห้า": "5",
}
_DIRECT_FETCH_VERB_RE = re.compile(
    r"(?i)\b(fetch|open|visit|read|scrape|crawl|ambil|buka|baca|ringkas|summari[sz]e|isi website|isi halaman|konten website|konten halaman)\b"
)
_DIRECT_FETCH_URL_RE = re.compile(r"(?i)\bhttps?://[^\s]+")
_DIRECT_FETCH_DOMAIN_RE = re.compile(
    r"(?i)\b(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s]*)?\b"
)
_READ_FILE_VERB_RE = re.compile(
    r"(?i)\b(read|open|show|display|inspect|view|cat|baca|lihat|lihatkan|tampilkan|periksa|cek)\b"
)
_DETERMINISTIC_PARSER_TOOL_WHITELIST = {
    "save_memory",
    "cron",
    "get_system_info",
    "cleanup_system",
    "speedtest",
    "get_process_memory",
    "server_monitor",
    "check_update",
    "system_update",
}
def _extract_direct_fetch_url_candidate(text: str) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    url_match = _DIRECT_FETCH_URL_RE.search(raw)
    if url_match:
        return url_match.group(0).rstrip(").,!?")
    if _PATHLIKE_QUERY_RE.search(raw) or re.search(
        r"\b[\w\-]+\.(json|ya?ml|toml|ini|cfg|conf|env|md|txt|csv|log|pdf|docx?|xlsx?|py|js|ts|tsx|jsx|html|css|xml)\b",
        raw,
        re.IGNORECASE,
    ):
        return None
    domain_match = _DIRECT_FETCH_DOMAIN_RE.search(raw)
    if not domain_match:
        return None
    candidate = domain_match.group(0).rstrip(").,!?")
    parsed = urlparse(f"https://{candidate}")
    if not parsed.netloc:
        return None
    return f"https://{candidate}"


def _looks_like_direct_page_fetch_request(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    if not _extract_direct_fetch_url_candidate(raw):
        return False
    return bool(_DIRECT_FETCH_VERB_RE.search(raw))


def _looks_like_explicit_read_file_request(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    if not _extract_read_file_path(raw):
        return False
    if _extract_list_dir_path(raw):
        return False
    return bool(_READ_FILE_VERB_RE.search(raw))


def _resolve_parser_tool_hint_for_loop(loop: Any, question: str) -> str | None:
    return required_tool_for_query(
        question=question,
        has_weather_tool=loop.tools.has("weather"),
        has_cron_tool=loop.tools.has("cron"),
        has_system_info_tool=loop.tools.has("get_system_info"),
        has_cleanup_tool=loop.tools.has("cleanup_system"),
        has_speedtest_tool=loop.tools.has("speedtest"),
        has_process_memory_tool=loop.tools.has("get_process_memory"),
        has_save_memory_tool=loop.tools.has("save_memory"),
        has_stock_tool=loop.tools.has("stock"),
        has_stock_analysis_tool=loop.tools.has("stock_analysis"),
        has_crypto_tool=loop.tools.has("crypto"),
        has_server_monitor_tool=loop.tools.has("server_monitor"),
        has_web_search_tool=loop.tools.has("web_search"),
        has_read_file_tool=loop.tools.has("read_file"),
        has_list_dir_tool=loop.tools.has("list_dir"),
        has_check_update_tool=loop.tools.has("check_update"),
        has_system_update_tool=loop.tools.has("system_update"),
    )

def existing_schedule_titles(loop: Any) -> list[str]:
    """Collect existing grouped schedule titles from cron service."""
    if not getattr(loop, "cron_service", None):
        return []
    titles: list[str] = []
    try:
        for job in loop.cron_service.list_jobs(include_disabled=True):
            title = (job.payload.group_title or "").strip()
            if title:
                titles.append(title)
    except Exception:
        return []
    return titles


def required_tool_for_query_for_loop(loop: Any, question: str) -> str | None:
    """Resolve safety-critical or payload-grounded tool routes only.

    OpenClaw-style turns should usually flow through model + skill selection.
    This wrapper keeps deterministic routing only for explicit payload/action
    cases (URLs, filesystem targets, reminders, system ops), while leaving
    generic knowledge/live-data turns to later skill/live-research latches.
    """
    if loop.tools.has("web_fetch") and _looks_like_direct_page_fetch_request(question):
        return "web_fetch"
    action_tool, _ = infer_action_required_tool_for_loop(loop, question)
    if action_tool:
        return action_tool
    if (
        loop.tools.has("list_dir")
        and not _extract_read_file_path(question)
        and _extract_list_dir_path(question)
    ):
        return "list_dir"
    if loop.tools.has("read_file") and _looks_like_explicit_read_file_request(question):
        return "read_file"

    resolved_tool = _resolve_parser_tool_hint_for_loop(loop, question)
    if resolved_tool == "read_file":
        return "read_file" if loop.tools.has("read_file") and _looks_like_explicit_read_file_request(question) else None
    if resolved_tool in _DETERMINISTIC_PARSER_TOOL_WHITELIST:
        return resolved_tool
    # Keep parser-scored weather/news/finance lookups available as soft signals
    # inside the runtime, but stop forcing them through deterministic routing.
    return None


def infer_required_tool_from_history_for_loop(
    loop: Any,
    followup_text: str,
    history: list[dict[str, Any]] | None,
    *,
    max_scan: int = 8,
) -> tuple[str | None, str | None]:
    """
    Infer required tool for low-information follow-up turns from recent user intent.

    Rules:
    - only trigger for short/low-information follow-up text
    - scan recent history from newest to oldest
    - only consider user turns
    - skip low-information prior user turns ("ya", "oke", etc.)
    """
    normalized_followup = _normalize_text(followup_text)
    if not normalized_followup:
        return None, None
    if not _is_low_information_followup(followup_text):
        return None, None
    if _looks_like_contextual_followup_request_for_history(followup_text):
        return None, None
    if not isinstance(history, list) or not history:
        return None, None

    resolver = getattr(loop, "_required_tool_for_query", None)
    if not callable(resolver):
        def _resolver(candidate: str) -> str | None:
            return required_tool_for_query_for_loop(loop, candidate)

        resolver = _resolver

    for item in reversed(history[-max_scan:]):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "") or "").strip().lower()
        if role != "user":
            continue
        candidate = str(item.get("content", "") or "").strip()
        if not candidate:
            continue

        candidate_norm = _normalize_text(candidate)
        if not candidate_norm or candidate_norm == normalized_followup:
            continue
        if _is_low_information_followup(candidate, max_tokens=3, max_chars=24):
            continue

        inferred = resolver(candidate)
        if inferred:
            return inferred, candidate

    return None, None


def _looks_like_contextual_followup_request_for_history(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if not _is_low_information_followup(raw, max_tokens=8, max_chars=96):
        return False
    if re.search(r"(https?://|www\.)", normalized):
        return False
    if _PATHLIKE_QUERY_RE.search(raw):
        return False
    if _OPTION_SELECTION_NUMERIC_RE.fullmatch(normalized):
        return True
    if _OPTION_SELECTION_REFERENCE_RE.search(normalized):
        return True
    for pattern in (
        _OPTION_SELECTION_CJK_ORDINAL_RE,
        _OPTION_SELECTION_JA_NUMERIC_RE,
        _OPTION_SELECTION_THAI_NUMERIC_RE,
        _OPTION_SELECTION_THAI_ORDINAL_RE,
    ):
        match = pattern.search(raw)
        if not match:
            continue
        ref = str(match.group("ref") or "").strip()
        if not ref:
            continue
        if ref.isdigit() or _OPTION_SELECTION_ORDINAL_MAP.get(ref):
            return True
    return False


def make_unique_schedule_title_for_loop(loop: Any, base_title: str) -> str:
    return nlp_make_unique_schedule_title(base_title, existing_schedule_titles(loop))


def build_group_id_for_loop(loop: Any, title: str) -> str:
    stamp = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    return nlp_build_group_id(title, now_ms=stamp)
