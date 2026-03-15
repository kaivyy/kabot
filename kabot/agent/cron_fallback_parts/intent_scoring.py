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
    _PRODUCTIVITY_OUTPUT_ACTION_MARKERS,
    _PRODUCTIVITY_PLAN_SUBJECT_MARKERS,
    _PRODUCTIVITY_SCHEDULE_DOC_MARKERS,
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
from kabot.agent.tools.stock import extract_stock_symbols

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


def _looks_like_verbose_non_query_blob(value: str) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    normalized = _normalize_query(raw)
    if len(normalized) < 80:
        return False
    tokens = [part for part in normalized.split(" ") if part]
    if len(tokens) < 14:
        return False
    sentence_like = raw.count(".") + raw.count("!") + raw.count("?") >= 2
    structured = any(marker in raw for marker in ("\n", "•", "|"))
    return sentence_like or structured


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
_MEMORY_COMMIT_INTENT_RE = re.compile(
    r"(?i)\b("
    r"simpan|save(?: it| this| that)?|ingat(?:kan)?|remember(?: it| this| that)?|"
    r"catat(?:kan)?|note(?: it| this| that)?|save to memory|simpan ke memory|"
    r"commit ke memory|masukkan ke memory"
    r")\b"
)
_PERSONAL_HR_CALC_RE = re.compile(
    r"(?i)\b("
    r"zona hr|hr zona|hr zone|heart rate zone|detak jantung|"
    r"karvonen|resting hr|max hr|hr max"
    r")\b"
)
_EXPLICIT_REMINDER_MARKERS = (
    "remind",
    "reminder",
    "set reminder",
    "set a reminder",
    "add reminder",
    "add a reminder",
    "create reminder",
    "create a reminder",
    "alarm",
    "set alarm",
    "timer",
    "set timer",
    "wake me",
    "ingatkan",
    "ingatkn",
    "pengingat",
    "buat reminder",
    "buat pengingat",
    "buat alarm",
    "buat timer",
    "jadwalkan pengingat",
    "jadwalkan reminder",
    "jadwalkan alarm",
    "bangunkan",
    "bangunin",
    "peringatan",
    "ตั้งเตือน",
    "การเตือน",
    "เตือน",
    "提醒",
    "闹钟",
    "定时提醒",
)
_REMINDER_SUBJECT_MARKERS = (
    "reminder",
    "alarm",
    "timer",
    "wake me",
    "pengingat",
    "peringatan",
    "เตือน",
    "การเตือน",
    "提醒",
    "闹钟",
)
_SCHEDULE_PLANNING_MARKERS = (
    "schedule",
    "jadwal",
    "jadual",
    "日程",
    "计划",
    "ตาราง",
)
_REMINDER_CREATION_VERBS = (
    "set",
    "add",
    "create",
    "buat",
    "bikin",
    "jadwalkan",
    "atur",
    "pasang",
    "schedule",
    "tetapkan",
    "ตั้ง",
    "设置",
)
_CRON_MANAGEMENT_DIRECT_MARKERS = (
    "cron",
    "reminder",
    "pengingat",
    "peringatan",
    "เตือน",
    "การเตือน",
    "提醒",
)
_CRON_GROUP_MARKERS = (
    "group",
    "grup",
    "kelompok",
    "team",
    "shift",
    "jadwal shift",
)
_CRON_GROUP_ID_RE = re.compile(r"(?i)\bgrp_[a-z0-9_]+\b")
_UPDATE_STRONG_TARGET_MARKERS = (
    "kabot",
    "bot",
    "agent",
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
        normalized = _normalize_query(candidate)
        if not normalized or len(normalized) > 220:
            continue
        if "?" in candidate or _PRIMARY_INTENT_ACTION_RE.search(candidate):
            return candidate.strip()
        if any(marker in normalized for marker in _PRIMARY_INTENT_TAIL_MARKERS):
            return candidate.strip()
    return raw


def _looks_like_personal_hr_or_memory_request(text: str) -> bool:
    normalized = _normalize_query(text)
    if not normalized:
        return False
    if _PERSONAL_HR_CALC_RE.search(normalized):
        return True
    return bool(_MEMORY_COMMIT_INTENT_RE.search(normalized) and re.search(r"\b(19|20)\d{2}\b", normalized))


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


_NON_MARKET_DOTTED_SUFFIXES = {
    "txt",
    "md",
    "json",
    "yaml",
    "yml",
    "csv",
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "html",
    "js",
    "ts",
    "py",
    "java",
    "cpp",
    "c",
    "rs",
    "go",
    "php",
}

_RAW_STOCKISH_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{2,12}(?:\.[A-Za-z]{1,8})?)(?![A-Za-z0-9])")
_EXPLICIT_CRYPTO_SHORT_SYMBOLS = {"btc", "eth", "sol", "doge", "xrp", "bnb", "usdt"}


def _extract_structural_stock_symbols(question: str) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    raw_text = str(question or "")
    for match in _RAW_STOCKISH_TOKEN_RE.finditer(raw_text):
        token = str(match.group(1) or "").strip()
        if not token:
            continue
        token_lower = token.lower()
        if "." in token_lower:
            suffix = token_lower.rsplit(".", 1)[-1]
            if suffix in _NON_MARKET_DOTTED_SUFFIXES:
                continue
        resolved_candidates = _extract_stock_symbol_candidates(token)
        if not resolved_candidates:
            continue
        token_root = token_lower.split(".", 1)[0]
        for symbol in resolved_candidates:
            raw = str(symbol or "").strip()
            if not raw:
                continue
            symbol_root = raw.lower().split(".", 1)[0]
            if symbol_root != token_root:
                continue
            if raw in seen:
                continue
            seen.add(raw)
            cleaned.append(raw)
    return cleaned


def _has_explicit_stock_symbol_payload(question: str) -> bool:
    normalized = _normalize_query(question)
    if not normalized:
        return False
    for symbol in _extract_structural_stock_symbols(question):
        raw = str(symbol).strip()
        if not raw:
            continue
        root = raw.split(".", 1)[0].lower()
        raw_lower = raw.lower()
        if raw_lower in normalized:
            return True
        if re.search(rf"(?<![a-z0-9]){re.escape(root)}(?![a-z0-9])", normalized):
            return True
    return False


def _has_explicit_crypto_symbol_payload(question: str) -> bool:
    normalized = _normalize_query(question)
    if not normalized:
        return False
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(symbol)}(?![a-z0-9])", normalized)
        for symbol in _EXPLICIT_CRYPTO_SHORT_SYMBOLS
    )


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
    text = _extract_primary_intent_text(question)
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
    has_strong_update_target = _contains_any(q_lower, _UPDATE_STRONG_TARGET_MARKERS, fuzzy_latin=True)
    if _contains_any(q_lower, CHECK_UPDATE_KEYWORDS, fuzzy_latin=True) and has_strong_update_target:
        add("check_update", 0.98, "explicit-check-update")
    if _contains_any(q_lower, APPLY_UPDATE_KEYWORDS, fuzzy_latin=True):
        add("system_update", 0.98, "explicit-apply-update")
    has_update_context = _contains_any(q_lower, _UPDATE_CONTEXT_MARKERS, fuzzy_latin=True)
    has_update_check_intent = has_update_context and has_strong_update_target and _contains_any(
        q_lower, _UPDATE_CHECK_VERBS, fuzzy_latin=True
    )
    has_update_apply_intent = has_update_context and has_strong_update_target and _contains_any(
        q_lower, _UPDATE_APPLY_INTENT_MARKERS, fuzzy_latin=True
    )
    if has_update_check_intent:
        add("check_update", 1.0, "check-update-verb")
    if has_update_apply_intent and not has_update_check_intent:
        add("system_update", 0.08, "apply-update-verb")

    # 2) Cron/reminder intent (management + creation).
    has_productivity_doc_marker = _contains_any(q_lower, _PRODUCTIVITY_DOC_MARKERS, fuzzy_latin=True)
    has_productivity_output_action = _contains_any(
        q_lower, _PRODUCTIVITY_OUTPUT_ACTION_MARKERS, fuzzy_latin=True
    )
    has_schedule_doc_marker = _contains_any(
        q_lower, _PRODUCTIVITY_SCHEDULE_DOC_MARKERS, fuzzy_latin=True
    )
    has_plan_subject_marker = _contains_any(
        q_lower, _PRODUCTIVITY_PLAN_SUBJECT_MARKERS, fuzzy_latin=True
    )
    looks_like_schedule_document_request = (
        has_schedule_doc_marker
        and has_productivity_output_action
        and (has_productivity_doc_marker or has_plan_subject_marker)
    )
    has_explicit_reminder_marker = _contains_any(q_lower, _EXPLICIT_REMINDER_MARKERS)
    has_reminder_subject_marker = _contains_any(q_lower, _REMINDER_SUBJECT_MARKERS)
    has_schedule_planning_marker = _contains_any(q_lower, _SCHEDULE_PLANNING_MARKERS)
    has_reminder_creation_verb = _contains_any(q_lower, _REMINDER_CREATION_VERBS)
    has_schedule_reminder_intent = (
        has_schedule_planning_marker
        and has_reminder_subject_marker
        and (has_reminder_creation_verb or bool(_REMINDER_TIME_RE.search(q_lower)))
    )
    has_explicit_cron_creation_intent = has_explicit_reminder_marker or has_schedule_reminder_intent
    has_cron_management_payload = any(
        (
            has_reminder_subject_marker,
            _contains_any(q_lower, _CRON_MANAGEMENT_DIRECT_MARKERS),
            _contains_any(q_lower, _CRON_GROUP_MARKERS),
            bool(_CRON_GROUP_ID_RE.search(text)),
        )
    )
    has_cron_management_intent = (
        _contains_any(q_lower, CRON_MANAGEMENT_OPS, fuzzy_latin=True)
        and has_cron_management_payload
    )
    if has_cron_management_intent:
        add("cron", 0.96, "cron-management")
    if has_explicit_cron_creation_intent and not looks_like_schedule_document_request:
        add("cron", 0.72, "explicit-reminder-lexicon")
    if (
        _REMINDER_TIME_RE.search(q_lower)
        and not looks_like_schedule_document_request
        and has_explicit_cron_creation_intent
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
        if (
            has_explicit_cron_creation_intent
            and not looks_like_question
            and not has_other_domain_marker
            and not looks_like_schedule_document_request
        ):
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
    elif has_file_payload and has_read_file_subject and not _looks_like_verbose_non_query_blob(text):
        add("read_file", 0.58, "read-file-subject-plus-path")

    # 5) Stock/crypto with structural entity detection.
    has_geo_news_strong_marker = _contains_any(
        q_lower, _GEO_NEWS_STRONG_TOPIC_MARKERS, fuzzy_latin=True
    )
    has_email_workflow_marker = _contains_any(q_lower, _EMAIL_WORKFLOW_MARKERS, fuzzy_latin=True)
    stock_symbols = _extract_structural_stock_symbols(text)
    crypto_symbol_set = {str(token).lower() for token in _CRYPTO_SYMBOL_MARKERS}
    stock_symbols_non_crypto = [
        symbol
        for symbol in stock_symbols
        if str(symbol).strip().lower() not in crypto_symbol_set
    ]
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
    has_explicit_stock_symbol = _has_explicit_stock_symbol_payload(text)
    stock_has_structural_payload = bool(stock_symbols_non_crypto and has_explicit_stock_symbol)
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
    if has_stock_marker and stock_has_structural_payload and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=stock_has_structural_payload,
    ):
        add("stock", 0.18 if has_stock_tracking_marker else 0.28, "stock-lexicon-explicit")

    stock_analysis_has_payload = bool(
        stock_symbols_non_crypto
        and has_explicit_stock_symbol
        or has_fx_pair_marker
    )
    if has_stock_tracking_marker and stock_analysis_has_payload and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=stock_analysis_has_payload,
    ):
        add("stock_analysis", 0.92, "stock-tracking-analysis")

    has_crypto_marker = _contains_any(q_lower, CRYPTO_KEYWORDS, fuzzy_latin=True)
    has_crypto_symbol = _has_explicit_crypto_symbol_payload(text)
    if has_crypto_marker and has_crypto_symbol and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=has_crypto_symbol,
    ):
        add("crypto", 0.28, "crypto-lexicon-explicit")
    if has_crypto_symbol:
        add("crypto", 0.86, "crypto-symbol-strong")

    # 6) Search/news intent with structural live-query hints.
    has_news_marker = _contains_any(q_lower, NEWS_KEYWORDS, fuzzy_latin=True)
    has_live_marker = _contains_any(q_lower, _LIVE_QUERY_MARKERS, fuzzy_latin=True)
    has_research_verb = _contains_any(q_lower, _RESEARCH_VERB_MARKERS, fuzzy_latin=True)
    has_year = bool(re.search(r"\b(19|20)\d{2}\b", q_lower))
    has_local_ops_marker = any(
        (
            has_explicit_cron_creation_intent or has_cron_management_intent,
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
    if (
        has_live_marker
        and (has_research_verb or has_year)
        and not has_local_ops_marker
        and not _looks_like_personal_hr_or_memory_request(text)
    ):
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
