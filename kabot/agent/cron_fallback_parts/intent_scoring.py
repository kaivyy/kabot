"""NLP helpers for cron/reminder fallback parsing.

This module keeps parsing logic out of AgentLoop so reminder behavior is easier
to maintain and test in isolation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from kabot.agent.cron_fallback_parts.constants import (
    _CRYPTO_SYMBOL_MARKERS,
    _DISK_SPACE_MARKERS,
    _EMAIL_WORKFLOW_MARKERS,
    _FILELIKE_QUERY_RE,
    _FX_CONVERSION_AMOUNT_RE,
    _FX_PAIR_MARKERS,
    _FX_RATE_MARKERS,
    _GEO_NEWS_STRONG_TOPIC_MARKERS,
    _GEO_NEWS_TOPIC_MARKERS,
    _INTENT_AMBIGUITY_DELTA,
    _INTENT_MIN_SCORE,
    _INTENT_STRONG_SCORE,
    _LIST_DIR_ACTION_MARKERS,
    _LIST_DIR_SUBJECT_MARKERS,
    _LIST_DIR_TARGET_MARKERS,
    _LIVE_QUERY_MARKERS,
    _META_FEEDBACK_MARKERS,
    _META_REFERENCE_VERBS,
    _META_TASK_SCOPE_MARKERS,
    _META_TOPIC_MARKERS,
    _META_WORKFLOW_REFERENCE_MARKERS,
    _NON_ACTION_MARKERS,
    _PATHLIKE_QUERY_RE,
    _PERSONAL_CHAT_MARKERS,
    _PRODUCTIVITY_DOC_MARKERS,
    _RAM_CAPACITY_MARKERS,
    _RAM_USAGE_MARKERS,
    _READ_FILE_ACTION_MARKERS,
    _READ_FILE_SUBJECT_MARKERS,
    _REMINDER_TIME_RE,
    _RESEARCH_VERB_MARKERS,
    _STOCK_TRACKING_MARKERS,
    _STOCK_VALUE_QUERY_MARKERS,
    _UPDATE_APPLY_INTENT_MARKERS,
    _UPDATE_CHECK_VERBS,
    _UPDATE_CONTEXT_MARKERS,
    _UPDATE_TARGET_MARKERS,
    _WEATHER_WIND_MARKERS,
    APPLY_UPDATE_KEYWORDS,
    CHECK_UPDATE_KEYWORDS,
    CLEANUP_ACTION_KEYWORDS,
    CLEANUP_KEYWORDS,
    CRON_MANAGEMENT_OPS,
    CRON_MANAGEMENT_TERMS,
    CRYPTO_KEYWORDS,
    NEWS_KEYWORDS,
    PROCESS_RAM_KEYWORDS,
    REMINDER_KEYWORDS,
    SERVER_MONITOR_KEYWORDS,
    SPEEDTEST_KEYWORDS,
    STOCK_KEYWORDS,
    SYSTEM_INFO_KEYWORDS,
    WEATHER_KEYWORDS,
)
from kabot.agent.tools.stock import extract_stock_name_candidates, extract_stock_symbols

__all__ = [
    "CRON_MANAGEMENT_OPS",
    "CRON_MANAGEMENT_TERMS",
    "CRYPTO_KEYWORDS",
    "REMINDER_KEYWORDS",
    "STOCK_KEYWORDS",
    "ToolIntentScore",
    "WEATHER_KEYWORDS",
    "_INTENT_AMBIGUITY_DELTA",
    "_INTENT_MIN_SCORE",
    "_INTENT_STRONG_SCORE",
    "_RAM_CAPACITY_MARKERS",
    "_RAM_USAGE_MARKERS",
    "_STOCK_TRACKING_MARKERS",
    "_WEATHER_WIND_MARKERS",
    "_contains_any",
    "_looks_like_meta_skill_or_workflow_prompt",
    "_normalize_query",
    "looks_like_meta_skill_or_workflow_prompt",
    "score_required_tool_intents",
]


@dataclass(frozen=True)
class ToolIntentScore:
    """Scored tool-intent candidate for deterministic fallback routing."""

    tool: str
    score: float
    reason: str


def _normalize_query(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _tokenize_latin_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _is_edit_distance_leq_one(left: str, right: str) -> bool:
    """Fast bounded Levenshtein check (distance <= 1)."""
    if left == right:
        return True
    len_left = len(left)
    len_right = len(right)
    if abs(len_left - len_right) > 1:
        return False
    if len_left == len_right:
        mismatches = 0
        for idx in range(len_left):
            if left[idx] != right[idx]:
                mismatches += 1
                if mismatches > 1:
                    return False
        return True
    if len_left > len_right:
        left, right = right, left
        len_left, len_right = len_right, len_left
    # now right is longer by exactly 1 char
    i = 0
    j = 0
    skipped = False
    while i < len_left and j < len_right:
        if left[i] == right[j]:
            i += 1
            j += 1
            continue
        if skipped:
            return False
        skipped = True
        j += 1
    return True


def _contains_any(text: str, terms: Iterable[str], *, fuzzy_latin: bool = False) -> bool:
    normalized_text = _normalize_query(text)
    for raw_term in terms:
        term = _normalize_query(raw_term)
        if not term:
            continue
        if re.fullmatch(r"[a-z0-9]+(?: [a-z0-9]+)*", term):
            pattern = r"(?<![a-z0-9])" + re.escape(term).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
            if re.search(pattern, normalized_text):
                return True
            continue
        if term in normalized_text:
            return True
    if not fuzzy_latin:
        return False
    tokens = _tokenize_latin_words(normalized_text)
    if not tokens:
        return False
    for raw_term in terms:
        term = _normalize_query(raw_term)
        if not term:
            continue
        if " " in term:
            parts = [part for part in term.split(" ") if part]
            if len(parts) < 2:
                continue
            latin_parts = [part for part in parts if re.fullmatch(r"[a-z0-9]+", part)]
            if len(latin_parts) != len(parts):
                continue
            matched_parts = 0
            for part in parts:
                if len(part) < 4:
                    continue
                if any(len(token) >= 4 and _is_edit_distance_leq_one(token, part) for token in tokens):
                    matched_parts += 1
            if matched_parts >= max(2, len(parts)):
                return True
            continue
        # Keep fuzzy matching conservative to reduce false positives.
        if len(term) < 5 or not re.fullmatch(r"[a-z0-9]+", term):
            continue
        for token in tokens:
            if len(token) < 4:
                continue
            if _is_edit_distance_leq_one(token, term):
                return True
    return False


_LARGE_FILE_SCAN_SUBJECT_MARKERS = (
    "file",
    "files",
    "folder",
    "folders",
    "berkas",
    "direktori",
    "directory",
)
_LARGE_FILE_SCAN_SIZE_MARKERS = (
    "large",
    "largest",
    "big",
    "biggest",
    "ukuran besar",
    "yang ukurannya besar",
    "paling besar",
    "besar",
    "makan ruang",
    "memakan ruang",
    "space hog",
    "space hogs",
    "folder size",
)


def _looks_like_large_file_scan_request(text: str) -> bool:
    normalized = _normalize_query(text)
    if not normalized:
        return False
    has_subject = _contains_any(normalized, _LARGE_FILE_SCAN_SUBJECT_MARKERS, fuzzy_latin=True)
    if not has_subject:
        return False
    has_size_marker = (
        _contains_any(normalized, _LARGE_FILE_SCAN_SIZE_MARKERS, fuzzy_latin=True)
        or bool(re.search(r"\b(size|ukuran)\b", normalized))
    )
    return has_size_marker


def _extract_weather_location_proxy(text: str) -> str | None:
    """Lazy proxy to avoid circular imports after splitting facade helpers."""
    from kabot.agent import cron_fallback_nlp as cron_fallback_module

    return cron_fallback_module.extract_weather_location(text)


def _looks_like_meta_skill_or_workflow_prompt(text: str) -> bool:
    """Detect prompts that discuss workflows/skills rather than requesting domain execution."""
    q_lower = _normalize_query(text)
    if not q_lower:
        return False

    has_meta_reference = _contains_any(q_lower, _META_WORKFLOW_REFERENCE_MARKERS, fuzzy_latin=True)
    if not has_meta_reference:
        return False

    has_meta_intent = _contains_any(q_lower, _META_REFERENCE_VERBS, fuzzy_latin=True) or _contains_any(
        q_lower, _META_TASK_SCOPE_MARKERS, fuzzy_latin=True
    )
    if not has_meta_intent:
        return False

    weather_location = _extract_weather_location_proxy(text)
    weather_payload = bool(weather_location) and not _contains_any(
        _normalize_query(weather_location),
        (
            *_META_WORKFLOW_REFERENCE_MARKERS,
            *_META_REFERENCE_VERBS,
            *_META_TASK_SCOPE_MARKERS,
            *_META_TOPIC_MARKERS,
            *_NON_ACTION_MARKERS,
        ),
        fuzzy_latin=True,
    )
    has_structural_payload = any(
        (
            bool(_REMINDER_TIME_RE.search(q_lower)),
            weather_payload,
            bool(_extract_stock_symbol_candidates(text)),
            bool(_FILELIKE_QUERY_RE.search(text) or _PATHLIKE_QUERY_RE.search(text)),
            bool(re.search(r"\b\d{1,2}:\d{2}\b", str(text or ""))),
            _contains_any(q_lower, _LIST_DIR_TARGET_MARKERS, fuzzy_latin=True),
        )
    )
    return not has_structural_payload


def looks_like_meta_skill_or_workflow_prompt(text: str) -> bool:
    """Public wrapper for meta workflow/skill reference detection."""
    return _looks_like_meta_skill_or_workflow_prompt(text)


def _extract_stock_symbol_candidates(question: str) -> list[str]:
    # Reuse stock-tool parser so deterministic router and stock tool stay aligned.
    return extract_stock_symbols(question or "")


def _extract_stock_name_candidates(question: str) -> list[str]:
    # Reuse stock-tool novice-name parser for consistent cross-module behavior.
    return extract_stock_name_candidates(question or "")


def score_required_tool_intents(
    question: str,
    *,
    has_weather_tool: bool,
    has_cron_tool: bool,
    has_system_info_tool: bool = False,
    has_cleanup_tool: bool = False,
    has_speedtest_tool: bool = False,
    has_process_memory_tool: bool = False,
    has_stock_tool: bool = False,
    has_stock_analysis_tool: bool = False,
    has_crypto_tool: bool = False,
    has_server_monitor_tool: bool = False,
    has_web_search_tool: bool = False,
    has_read_file_tool: bool = False,
    has_list_dir_tool: bool = False,
    has_check_update_tool: bool = False,
    has_system_update_tool: bool = False,
) -> list[ToolIntentScore]:
    """
    Score tool intents using mixed structural signals + multilingual lexicon.

    This keeps deterministic fallback robust while reducing rigid keyword-only behavior.
    """
    text = str(question or "").strip()
    q_lower = _normalize_query(text)
    if not q_lower:
        return []

    available = {
        "weather": has_weather_tool,
        "cron": has_cron_tool,
        "get_system_info": has_system_info_tool,
        "cleanup_system": has_cleanup_tool,
        "speedtest": has_speedtest_tool,
        "get_process_memory": has_process_memory_tool,
        "stock": has_stock_tool,
        "stock_analysis": has_stock_analysis_tool,
        "crypto": has_crypto_tool,
        "server_monitor": has_server_monitor_tool,
        "web_search": has_web_search_tool,
        "read_file": has_read_file_tool,
        "list_dir": has_list_dir_tool,
        "check_update": has_check_update_tool,
        "system_update": has_system_update_tool,
    }
    scores: dict[str, float] = {}
    reasons: dict[str, str] = {}

    def add(tool: str, points: float, reason: str) -> None:
        if not available.get(tool, False):
            return
        if points <= 0:
            return
        current = scores.get(tool, 0.0)
        next_score = min(1.0, current + float(points))
        scores[tool] = next_score
        reasons.setdefault(tool, reason)

    has_non_action_marker = _contains_any(q_lower, _NON_ACTION_MARKERS, fuzzy_latin=True)
    has_meta_feedback_marker = _contains_any(q_lower, _META_FEEDBACK_MARKERS, fuzzy_latin=True)
    has_meta_topic_marker = _contains_any(q_lower, _META_TOPIC_MARKERS, fuzzy_latin=True)

    def _is_non_action_meta_domain_turn(
        *,
        has_domain_marker: bool,
        has_structural_payload: bool = False,
    ) -> bool:
        """Suppress lexicon-only domain routing for meta/negation chat turns."""
        if not has_domain_marker:
            return False
        if has_structural_payload:
            return False
        if not has_non_action_marker:
            return False
        return has_meta_feedback_marker or has_meta_topic_marker

    # 1) High-priority deterministic updates.
    if _contains_any(q_lower, CHECK_UPDATE_KEYWORDS, fuzzy_latin=True):
        add("check_update", 0.98, "explicit-check-update")
    if _contains_any(q_lower, APPLY_UPDATE_KEYWORDS, fuzzy_latin=True):
        add("system_update", 0.98, "explicit-apply-update")
    has_update_context = _contains_any(q_lower, _UPDATE_CONTEXT_MARKERS, fuzzy_latin=True)
    has_update_check_intent = has_update_context and _contains_any(
        q_lower, _UPDATE_CHECK_VERBS, fuzzy_latin=True
    )
    has_update_apply_intent = has_update_context and _contains_any(
        q_lower, _UPDATE_APPLY_INTENT_MARKERS, fuzzy_latin=True
    )
    if has_update_check_intent:
        add("check_update", 1.0, "check-update-verb")
    if has_update_apply_intent and not has_update_check_intent:
        add("system_update", 0.08, "apply-update-verb")

    # 2) Cron/reminder intent (management + creation).
    if _contains_any(q_lower, CRON_MANAGEMENT_OPS, fuzzy_latin=True) and _contains_any(
        q_lower, CRON_MANAGEMENT_TERMS, fuzzy_latin=True
    ):
        add("cron", 0.96, "cron-management")
    if _contains_any(q_lower, REMINDER_KEYWORDS, fuzzy_latin=True):
        add("cron", 0.72, "reminder-lexicon")
    if _REMINDER_TIME_RE.search(q_lower) and _contains_any(
        q_lower, ("ingat", "remind", "alarm", "timer", "schedule", "jadwal")
    ):
        add("cron", 0.22, "time-plus-reminder-structure")
    if _REMINDER_TIME_RE.search(q_lower):
        looks_like_question = ("?" in text) or bool(
            re.match(
                r"(?i)^(what|why|how|when|where|who|berapa|kenapa|kapan|gimana|bagaimana|siapa|mana)\b",
                q_lower,
            )
        )
        has_other_domain_marker = any(
            (
                _contains_any(q_lower, WEATHER_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, STOCK_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, CRYPTO_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, SERVER_MONITOR_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, SYSTEM_INFO_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, SPEEDTEST_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, NEWS_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, CHECK_UPDATE_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, APPLY_UPDATE_KEYWORDS, fuzzy_latin=True),
            )
        )
        if not looks_like_question and not has_other_domain_marker:
            add("cron", 0.58, "time-action-structure")

    # 3) Weather.
    has_weather_marker = _contains_any(q_lower, WEATHER_KEYWORDS, fuzzy_latin=True) or _contains_any(
        q_lower,
        _WEATHER_WIND_MARKERS,
        fuzzy_latin=True,
    )
    location_candidate = _extract_weather_location_proxy(text)
    location_candidate_lower = _normalize_query(location_candidate or "")
    location_looks_meta = _contains_any(
        location_candidate_lower,
        (*_META_TOPIC_MARKERS, *_NON_ACTION_MARKERS),
        fuzzy_latin=True,
    )
    has_weather_structural_payload = bool(location_candidate) and not location_looks_meta
    if has_weather_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=has_weather_structural_payload,
    ):
        add("weather", 0.64, "weather-lexicon")
    if has_weather_marker and has_weather_structural_payload:
        add("weather", 0.24, "weather-location")
    if has_weather_marker and _contains_any(q_lower, ("today", "hari ini", "now", "sekarang")):
        add("weather", 0.08, "weather-live-time")
    if (
        has_weather_marker
        and has_weather_structural_payload
        and has_update_context
        and not _contains_any(q_lower, _UPDATE_TARGET_MARKERS, fuzzy_latin=True)
    ):
        scores.pop("check_update", None)
        scores.pop("system_update", None)
        reasons.pop("check_update", None)
        reasons.pop("system_update", None)

    # 4) System/process monitoring.
    has_server_monitor_marker = _contains_any(q_lower, SERVER_MONITOR_KEYWORDS, fuzzy_latin=True)
    if has_server_monitor_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=False,
    ):
        add("server_monitor", 0.82, "server-monitor-lexicon")
    has_process_ram_marker = _contains_any(q_lower, PROCESS_RAM_KEYWORDS, fuzzy_latin=True)
    if has_process_ram_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=False,
    ):
        add("get_process_memory", 0.76, "process-memory-lexicon")
    has_ram_capacity_marker = _contains_any(q_lower, _RAM_CAPACITY_MARKERS, fuzzy_latin=True)
    if has_ram_capacity_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=False,
    ):
        add("get_system_info", 0.82, "ram-capacity-structure")
    has_large_file_scan_marker = _looks_like_large_file_scan_request(text)
    has_system_info_marker = _contains_any(q_lower, SYSTEM_INFO_KEYWORDS, fuzzy_latin=True) or _contains_any(
        q_lower, _DISK_SPACE_MARKERS, fuzzy_latin=True
    )
    if (
        has_system_info_marker
        and not has_large_file_scan_marker
        and not _is_non_action_meta_domain_turn(
            has_domain_marker=True,
            has_structural_payload=False,
        )
    ):
        add("get_system_info", 0.66, "system-info-lexicon")
    if has_large_file_scan_marker:
        scores.pop("get_system_info", None)
        reasons.pop("get_system_info", None)
    if _contains_any(q_lower, _RAM_USAGE_MARKERS, fuzzy_latin=True) and _contains_any(
        q_lower, ("ram", "memory", "memori"), fuzzy_latin=True
    ):
        add("get_process_memory", 0.16, "ram-usage-structure")

    # 4b) Directory listing/navigation requests.
    has_list_dir_action = _contains_any(q_lower, _LIST_DIR_ACTION_MARKERS, fuzzy_latin=True)
    has_list_dir_subject = _contains_any(q_lower, _LIST_DIR_SUBJECT_MARKERS, fuzzy_latin=True)
    has_list_dir_target = _contains_any(q_lower, _LIST_DIR_TARGET_MARKERS, fuzzy_latin=True)
    has_path_payload = bool(_PATHLIKE_QUERY_RE.search(text))
    if has_list_dir_action and (has_list_dir_subject or has_list_dir_target or has_path_payload):
        add("list_dir", 0.96, "list-dir-action")
    elif has_list_dir_subject and (has_list_dir_target or has_path_payload):
        add("list_dir", 0.84, "list-dir-subject-plus-target")

    # 4c) File-reading requests.
    has_read_file_action = _contains_any(q_lower, _READ_FILE_ACTION_MARKERS, fuzzy_latin=True)
    has_read_file_subject = _contains_any(q_lower, _READ_FILE_SUBJECT_MARKERS, fuzzy_latin=True)
    has_file_payload = bool(_FILELIKE_QUERY_RE.search(text) or has_path_payload)
    if has_read_file_action and has_file_payload:
        add("read_file", 0.93, "read-file-action-plus-path")
    elif has_read_file_action and has_read_file_subject:
        add("read_file", 0.74, "read-file-action-plus-subject")
    elif has_file_payload and has_read_file_subject:
        add("read_file", 0.58, "read-file-subject-plus-path")

    # 5) Stock/crypto with structural entity detection.
    has_geo_news_strong_marker = _contains_any(
        q_lower, _GEO_NEWS_STRONG_TOPIC_MARKERS, fuzzy_latin=True
    )
    has_email_workflow_marker = _contains_any(q_lower, _EMAIL_WORKFLOW_MARKERS, fuzzy_latin=True)
    has_productivity_doc_marker = _contains_any(q_lower, _PRODUCTIVITY_DOC_MARKERS, fuzzy_latin=True)
    stock_symbols = _extract_stock_symbol_candidates(text)
    crypto_symbol_set = {str(token).lower() for token in _CRYPTO_SYMBOL_MARKERS}
    stock_symbols_non_crypto = [
        symbol
        for symbol in stock_symbols
        if str(symbol).strip().lower() not in crypto_symbol_set
    ]
    stock_name_candidates = _extract_stock_name_candidates(text)
    has_stock_marker = (
        _contains_any(q_lower, STOCK_KEYWORDS, fuzzy_latin=True)
        and not has_email_workflow_marker
        and not has_productivity_doc_marker
    )
    has_stock_tracking_marker = _contains_any(q_lower, _STOCK_TRACKING_MARKERS, fuzzy_latin=True)
    has_fx_pair_marker = (
        _contains_any(q_lower, _FX_PAIR_MARKERS, fuzzy_latin=True)
        or bool(re.search(r"\busd\s*(?:/|to|ke|-)?\s*(?:idr|rupiah)\b", q_lower))
        or bool(re.search(r"\b(?:idr|rupiah)\s*(?:/|to|ke|-)?\s*usd\b", q_lower))
    )
    has_fx_rate_marker = _contains_any(q_lower, _FX_RATE_MARKERS, fuzzy_latin=True)
    has_fx_conversion_amount = bool(_FX_CONVERSION_AMOUNT_RE.search(text))
    stock_has_structural_payload = bool(stock_symbols_non_crypto)
    if has_fx_pair_marker and (has_fx_rate_marker or _contains_any(q_lower, _STOCK_VALUE_QUERY_MARKERS, fuzzy_latin=True)):
        add("stock", 0.94, "fx-rate-query")
        stock_has_structural_payload = True
    if len(stock_symbols_non_crypto) >= 2:
        add("stock", 0.88, "multi-stock-symbols")
    elif len(stock_symbols_non_crypto) == 1:
        symbol = stock_symbols_non_crypto[0]
        if "." in symbol or has_stock_marker:
            add("stock", 0.8, "explicit-stock-symbol")
        else:
            add("stock", 0.64, "known-stock-symbol")
    if has_stock_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=stock_has_structural_payload,
    ):
        add("stock", 0.32 if has_stock_tracking_marker else 0.56, "stock-lexicon")
    if stock_name_candidates and not stock_symbols_non_crypto:
        has_value_query_marker = _contains_any(q_lower, _STOCK_VALUE_QUERY_MARKERS, fuzzy_latin=True)
        stock_has_structural_payload = bool(stock_has_structural_payload or has_value_query_marker)
        has_personal_chat_marker = _contains_any(q_lower, _PERSONAL_CHAT_MARKERS, fuzzy_latin=True)
        is_currency_conversion_without_explicit_market = (
            has_fx_rate_marker
            and not has_fx_pair_marker
            and not has_stock_marker
            and not stock_symbols_non_crypto
        )
        has_conflicting_domain = any(
            (
                has_weather_marker,
                has_geo_news_strong_marker,
                _contains_any(q_lower, CRYPTO_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, _CRYPTO_SYMBOL_MARKERS),
                _contains_any(q_lower, REMINDER_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, SERVER_MONITOR_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, SYSTEM_INFO_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, CLEANUP_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, SPEEDTEST_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, NEWS_KEYWORDS, fuzzy_latin=True),
                has_email_workflow_marker,
                has_productivity_doc_marker,
            )
        )
        if (
            has_value_query_marker
            and not has_personal_chat_marker
            and not has_conflicting_domain
            and not is_currency_conversion_without_explicit_market
        ):
            add("stock", 0.62, "stock-company-name-value-query")
        if (
            has_fx_rate_marker
            and (has_fx_conversion_amount or has_value_query_marker)
            and not has_personal_chat_marker
            and not has_conflicting_domain
        ):
            add("stock", 0.9, "stock-company-fx-conversion")

    stock_analysis_has_payload = bool(
        stock_symbols_non_crypto
        or stock_name_candidates
        or has_stock_marker
        or has_fx_pair_marker
    )
    if has_stock_tracking_marker and stock_analysis_has_payload and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=stock_analysis_has_payload,
    ):
        add("stock_analysis", 0.92, "stock-tracking-analysis")

    has_crypto_marker = _contains_any(q_lower, CRYPTO_KEYWORDS, fuzzy_latin=True)
    has_crypto_symbol = _contains_any(q_lower, _CRYPTO_SYMBOL_MARKERS)
    if has_crypto_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=has_crypto_symbol,
    ):
        add("crypto", 0.66, "crypto-lexicon")
    if has_crypto_symbol:
        add("crypto", 0.86, "crypto-symbol-strong")

    # 6) Search/news intent with structural live-query hints.
    has_news_marker = _contains_any(q_lower, NEWS_KEYWORDS, fuzzy_latin=True)
    has_live_marker = _contains_any(q_lower, _LIVE_QUERY_MARKERS, fuzzy_latin=True)
    has_research_verb = _contains_any(q_lower, _RESEARCH_VERB_MARKERS, fuzzy_latin=True)
    has_year = bool(re.search(r"\b(19|20)\d{2}\b", q_lower))
    has_local_ops_marker = any(
        (
            _contains_any(q_lower, REMINDER_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, WEATHER_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, PROCESS_RAM_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, SYSTEM_INFO_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, CLEANUP_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, SPEEDTEST_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, STOCK_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, CRYPTO_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, _EMAIL_WORKFLOW_MARKERS, fuzzy_latin=True),
            _contains_any(q_lower, _PRODUCTIVITY_DOC_MARKERS, fuzzy_latin=True),
            _contains_any(q_lower, _READ_FILE_ACTION_MARKERS, fuzzy_latin=True),
            _contains_any(q_lower, _READ_FILE_SUBJECT_MARKERS, fuzzy_latin=True),
            _contains_any(q_lower, _LIST_DIR_ACTION_MARKERS, fuzzy_latin=True),
            _contains_any(q_lower, _LIST_DIR_SUBJECT_MARKERS, fuzzy_latin=True),
            _contains_any(q_lower, CHECK_UPDATE_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, APPLY_UPDATE_KEYWORDS, fuzzy_latin=True),
        )
    )
    has_meta_feedback_marker = _contains_any(q_lower, _META_FEEDBACK_MARKERS, fuzzy_latin=True)
    has_news_structural_payload = has_research_verb or has_live_marker or has_year or has_geo_news_strong_marker
    if has_news_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=has_news_structural_payload,
    ):
        if has_meta_feedback_marker and not (has_geo_news_strong_marker or has_year):
            add("web_search", 0.4, "news-meta-chat-soft")
        elif has_research_verb or has_live_marker or has_year or has_geo_news_strong_marker:
            add("web_search", 0.74, "news-lexicon")
        else:
            add("web_search", 0.45, "news-soft")
    if has_geo_news_strong_marker and (has_live_marker or has_research_verb or ("?" in text)):
        add("web_search", 0.7, "geo-news-topic")
    if has_live_marker and (has_research_verb or has_year) and not has_local_ops_marker:
        add("web_search", 0.62, "live-query-structure")
    if has_year and _contains_any(q_lower, _GEO_NEWS_TOPIC_MARKERS):
        add("web_search", 0.2, "dated-geo-topic")

    # 7) Speedtest / cleanup.
    has_speedtest_marker = _contains_any(q_lower, SPEEDTEST_KEYWORDS, fuzzy_latin=True)
    if has_speedtest_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=False,
    ):
        add("speedtest", 0.8, "speedtest-lexicon")
    has_cleanup_marker = _contains_any(q_lower, CLEANUP_KEYWORDS, fuzzy_latin=True)
    has_cleanup_action_marker = _contains_any(q_lower, CLEANUP_ACTION_KEYWORDS, fuzzy_latin=True)
    if (
        has_cleanup_marker
        and has_cleanup_action_marker
        and not _is_non_action_meta_domain_turn(has_domain_marker=True, has_structural_payload=False)
    ):
        add("cleanup_system", 0.86, "cleanup-action")
    elif has_cleanup_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=False,
    ):
        add("cleanup_system", 0.45, "cleanup-soft")

    ranked = sorted(
        (ToolIntentScore(tool=tool, score=score, reason=reasons.get(tool, "")) for tool, score in scores.items()),
        key=lambda item: item.score,
        reverse=True,
    )
    return ranked
