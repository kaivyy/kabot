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
from kabot.agent.loop_core.tool_enforcement_parts.filesystem_paths import _PATHLIKE_QUERY_RE

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
)
_CONTEXTUAL_FOLLOWUP_EXACT = {
    "naik ya",
    "turun ya",
}
_DIRECT_FETCH_VERB_RE = re.compile(
    r"(?i)\b(fetch|open|visit|read|scrape|crawl|ambil|buka|baca|ringkas|summari[sz]e|isi website|isi halaman|konten website|konten halaman)\b"
)
_DIRECT_FETCH_URL_RE = re.compile(r"(?i)\bhttps?://[^\s]+")
_DIRECT_FETCH_DOMAIN_RE = re.compile(
    r"(?i)\b(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s]*)?\b"
)


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
    """Resolve required tool for immediate-action query types."""
    if loop.tools.has("web_fetch") and _looks_like_direct_page_fetch_request(question):
        return "web_fetch"

    resolved_tool = required_tool_for_query(
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
    if resolved_tool == "read_file":
        action_tool, _ = infer_action_required_tool_for_loop(loop, question)
        if action_tool == "message":
            return "message"

    if resolved_tool in {"stock", "stock_analysis", "crypto"}:
        # Keep legacy finance tools available for the model as fallback, but stop
        # forcing them through deterministic parser routing.
        return None
    return resolved_tool


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
    if normalized in _CONTEXTUAL_FOLLOWUP_EXACT:
        return True
    if "trend" in normalized:
        return True
    return any(phrase in normalized for phrase in _CONTEXTUAL_FOLLOWUP_PHRASES)


def make_unique_schedule_title_for_loop(loop: Any, base_title: str) -> str:
    return nlp_make_unique_schedule_title(base_title, existing_schedule_titles(loop))


def build_group_id_for_loop(loop: Any, title: str) -> str:
    stamp = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    return nlp_build_group_id(title, now_ms=stamp)
