"""Intent and required-tool routing helpers for execution runtime."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from kabot.agent.skills_matching import looks_like_explicit_skill_use_request
from kabot.agent.loop_core.tool_enforcement_parts.action_requests import (
    _extract_find_files_kind,
    _extract_find_files_query,
    _looks_like_list_dir_request,
)
from kabot.agent.tools.stock import (
    extract_crypto_ids,
    extract_stock_symbols,
)
from kabot.bus.events import InboundMessage


_NON_MARKET_DOTTED_SUFFIXES = {
    "MD",
    "TXT",
    "JSON",
    "YAML",
    "YML",
    "TOML",
    "CSV",
    "LOG",
    "PDF",
    "DOC",
    "DOCX",
    "XLS",
    "XLSX",
    "PY",
    "JS",
    "TS",
    "TSX",
    "JSX",
    "HTML",
    "CSS",
    "XML",
    "INI",
    "CFG",
    "CONF",
    "ENV",
}


def _extract_structural_stock_symbols(raw: str) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return []

    result: list[str] = []
    seen: set[str] = set()
    tokens = [token for token in re.split(r"[\s,]+", text) if token]
    for token_raw in tokens:
        token = token_raw.strip().strip("()[]{}\"'`")
        token = token.strip(".,;:!?")
        if not token:
            continue
        upper = token.upper()
        if upper.endswith("=X") and re.fullmatch(r"[A-Z]{3,10}=X", upper):
            if upper not in seen:
                seen.add(upper)
                result.append(upper)
            continue
        if upper.startswith("^") and re.fullmatch(r"\^[A-Z]{2,8}", upper):
            if upper not in seen:
                seen.add(upper)
                result.append(upper)
            continue
        if "." in upper and re.fullmatch(r"[A-Z0-9]{1,10}\.[A-Z]{1,5}", upper):
            _left, right = upper.split(".", 1)
            if right in _NON_MARKET_DOTTED_SUFFIXES:
                continue
            if upper not in seen:
                seen.add(upper)
                result.append(upper)
            continue
        if token == token.upper() and re.fullmatch(r"[A-Z]{2,8}", upper):
            if upper not in seen:
                seen.add(upper)
                result.append(upper)
    return result


def _has_explicit_stock_symbol_payload(raw: str) -> bool:
    text = str(raw or "").strip()
    if not text:
        return False

    explicit_tokens: set[str] = set()
    for token_raw in re.split(r"[\s,]+", text):
        token = token_raw.strip().strip("()[]{}\"'`")
        token = token.strip(".,;:!?")
        if not token:
            continue
        explicit_tokens.add(token.upper())

    for symbol in extract_stock_symbols(text):
        normalized = str(symbol or "").strip().upper()
        if not normalized:
            continue
        if normalized in explicit_tokens:
            return True
        root = normalized.split(".", 1)[0]
        if root.endswith("=X"):
            root = root[:-2]
        if root and root in explicit_tokens:
            return True
    return False


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


_LIVE_FINANCE_DOMAIN_RE = re.compile(
    r"(?i)\b("
    r"stock|stocks|ticker|tickers|quote|quotes|market|markets|"
    r"price|crypto|bitcoin|btc|ethereum|eth|coin|coins|token|tokens|"
    r"forex|fx|rate|exchange(?:\s+rate)?|usd|idr|idx|jkse|nasdaq|dow|nikkei"
    r")\b"
)
_LIVE_FINANCE_VALUE_RE = re.compile(
    r"(?i)\b("
    r"how much|what(?:'s| is)|price|quote|value|"
    r"rate|last|latest|current|now|today|"
    r"real[\s-]?time|live|open|close|closing|high|low"
    r")\b"
)
_LIVE_DATA_REFRESH_KEYWORDS = frozenset({
    "latest", "current", "newest", "fresh", "freshest",
    "live",
})
_LIVE_DATA_REFRESH_PHRASES = (
    "up to date",
    "real time",
    "use latest data",
    "use current data",
    "use real time data",
)


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


_PRIMARY_INTENT_TAIL_MARKERS = (
    "from this",
    "based on this",
    "from here",
    "using this",
)
_PRIMARY_INTENT_ACTION_RE = re.compile(
    r"(?i)\b("
    r"calculate|calc|explain|summarize|continue|"
    r"please|how much|what|why|how|can|could|"
    r"hr|heart rate|zone|karvonen"
    r")\b"
)
_MEMORY_COMMIT_INTENT_RE = re.compile(
    r"(?i)\b("
    r"save(?: it| this| that)?|remember(?: it| this| that)?|"
    r"note(?: it| this| that)?|save to memory|commit to memory"
    r")\b"
)
_PERSONAL_HR_CALC_RE = re.compile(
    r"(?i)\b("
    r"hr zone|heart rate zone|"
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


def _looks_like_live_finance_lookup(text: str) -> bool:
    focused = _extract_primary_intent_text(text)
    normalized = _normalize_text(focused)
    if not normalized:
        return False
    if _PERSONAL_HR_CALC_RE.search(normalized):
        return False
    if _MEMORY_COMMIT_INTENT_RE.search(normalized):
        return False

    has_stock_symbol = False
    has_crypto_symbol = False
    try:
        has_stock_symbol = bool(
            _extract_structural_stock_symbols(focused)
            or _has_explicit_stock_symbol_payload(focused)
            or extract_stock_symbols(focused)
        )
    except Exception:
        has_stock_symbol = False
    try:
        has_crypto_symbol = bool(extract_crypto_ids(focused))
    except Exception:
        has_crypto_symbol = False

    has_finance_domain = bool(
        has_stock_symbol or has_crypto_symbol or _LIVE_FINANCE_DOMAIN_RE.search(normalized)
    )
    if not has_finance_domain:
        return False
    return bool(_LIVE_FINANCE_VALUE_RE.search(normalized))


def _looks_like_live_research_query(text: str) -> bool:
    focused = _extract_primary_intent_text(text)
    normalized = _normalize_text(focused)
    if not normalized:
        return False
    if _PERSONAL_HR_CALC_RE.search(normalized):
        return False
    if _MEMORY_COMMIT_INTENT_RE.search(normalized):
        return False
    if _looks_like_live_finance_lookup(focused):
        return True

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
    if re.search(r"\b(19|20)\d{2}\b", normalized):
        news_context_markers = (
            "news",
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


def _should_defer_live_research_latch_to_skill(
    loop: Any,
    text: str,
    *,
    profile: str = "GENERAL",
    message_metadata: dict[str, Any] | None = None,
    session_metadata: dict[str, Any] | None = None,
) -> bool:
    """Return True when a grounded external skill should outrank live-search forcing."""
    active_metadata = getattr(loop, "_active_message_metadata", None)
    current_turn_skill_lane = any(
        isinstance(metadata, dict) and metadata.get("external_skill_lane")
        for metadata in (message_metadata, active_metadata)
    )
    if current_turn_skill_lane:
        return True

    prior_session_skill_lane = bool(
        isinstance(session_metadata, dict) and session_metadata.get("external_skill_lane")
    )

    explicit_skill_request = looks_like_explicit_skill_use_request(text)

    context_builder = getattr(loop, "context", None)
    skills_loader = getattr(context_builder, "skills", None)
    matcher = getattr(skills_loader, "should_prefer_external_finance_skill", None)
    if callable(matcher):
        try:
            if bool(matcher(text, profile=profile)):
                return True
        except Exception:
            pass
    external_match = getattr(skills_loader, "has_preferred_external_skill_match", None)
    if callable(external_match):
        try:
            if bool(external_match(text, profile=profile)):
                return True
        except Exception:
            return False
    if not explicit_skill_request and not prior_session_skill_lane:
        return False
    return False


_GUARDED_TOOL_CALLS = {
    "find_files",
    "message",
    "read_file",
    "save_memory",
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
    r"(?i)\b(remind|reminder|schedule|alarm|timer|cron)\b"
)
_REMINDER_STRUCTURE_RE = re.compile(
    r"(?i)(\b\d+\s*(min(?:ute)?s?|hour(?:s)?|sec(?:ond)?s?|day(?:s)?)\b|\b\d{1,2}(?::\d{2})\b)"
)
_FILELIKE_QUERY_RE = re.compile(
    r"\b[\w\-]+\.(json|ya?ml|toml|ini|cfg|conf|env|md|txt|csv|log|pdf|docx?|xlsx?|py|js|ts|tsx|jsx|html|css|xml)\b",
    re.IGNORECASE,
)
_PATHLIKE_QUERY_RE = re.compile(r"([a-zA-Z]:\\|\\\\|/[\w\-./]+|[\w\-./]+\\[\w\-./]+)")
_FIND_FILE_MARKER_RE = re.compile(
    r"(?i)\b(find|search|locate|look for)\b"
)
_SEND_FILE_MARKER_RE = re.compile(
    r"(?i)\b(send|share|attach|upload)\b"
)
_WEATHER_MARKER_RE = re.compile(
    r"(?i)\b(weather|temperature|forecast)\b"
)
_IMAGE_MARKER_RE = re.compile(
    r"(?i)\b(image|photo|picture|draw|sketch|illustrat(?:e|ion)|render|generate\s+image)\b"
)
_TTS_MARKER_RE = re.compile(
    r"(?i)\b(tts|text\s*to\s*speech|voice|audio|narrat(?:e|ion)|read\s+aloud|speak)\b"
)
_BROWSER_INTERACTION_MARKER_RE = re.compile(
    r"(?i)\b("
    r"browser|playwright|screenshot|screen\s*shot|capture|full\s*page|"
    r"click|klik|tap|press|fill|type|input|selector|dom|snapshot|"
    r"login|log\s*in|signin|sign\s*in|hover|scroll|form|"
    r"interact(?:ive|ion)?|popup|modal"
    r")\b"
)
_DIRECT_FETCH_VERB_RE = re.compile(
    r"(?i)\b(fetch|open|visit|read|scrape|crawl|summari[sz]e)\b"
)
_DIRECT_FETCH_URL_RE = re.compile(r"(?i)\bhttps?://[^\s]+")
_DIRECT_FETCH_DOMAIN_RE = re.compile(
    r"(?i)\b(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s]*)?\b"
)
_DIRECT_FETCH_SITE_RE = re.compile(r"(?i)\bsite:(?P<domain>[a-z0-9.-]+\.[a-z]{2,})\b")
_WEB_RESULT_URL_RE = re.compile(r"(?i)\bhttps?://[^\s<>()\[\]\"']+")
_WEB_SOURCE_SELECTION_LEAD_RE = re.compile(
    r"(?i)\b(use|via|from|source|provider|try)\b"
)
_NON_ACTION_MARKER_RE = re.compile(
    r"(?i)\b(stop|dont|don't|do not|cancel|no need)\b"
)
_NON_ACTION_STOCK_TOPIC_RE = re.compile(
    r"(?i)\b(stock|ticker|market|price|idx)\b"
)
_SKILL_CREATION_GUARDED_TOOLS = {"write_file", "edit_file", "exec"}
_WEB_SOURCE_ALIAS_DOMAINS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("yahoo finance", ("finance.yahoo.com",)),
    ("google finance", ("google.com",)),
    ("stockbit", ("stockbit.com",)),
    ("rti", ("rti.co.id",)),
    ("idx", ("idx.co.id",)),
    ("indonesia stock exchange", ("idx.co.id",)),
    ("tradingview", ("tradingview.com",)),
    ("investing", ("investing.com",)),
)


def _extract_direct_fetch_url_candidate(text: str) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    url_match = _DIRECT_FETCH_URL_RE.search(raw)
    if url_match:
        return url_match.group(0).rstrip(").,!?")
    if _FILELIKE_QUERY_RE.search(raw):
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


def _normalize_web_domain_candidate(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if raw.startswith("site:"):
        raw = raw[5:].strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    try:
        parsed = urlparse(raw)
    except Exception:
        return ""
    candidate = str(parsed.netloc or parsed.path or "").strip().lower()
    if not candidate:
        return ""
    if "@" in candidate:
        candidate = candidate.split("@", 1)[-1]
    if ":" in candidate:
        candidate = candidate.split(":", 1)[0]
    if candidate.startswith("www."):
        candidate = candidate[4:]
    return candidate.lstrip(".")


def _extract_preferred_web_domains(text: str, *, include_aliases: bool = True) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []

    result: list[str] = []
    seen: set[str] = set()

    explicit_url = _extract_direct_fetch_url_candidate(raw)
    if explicit_url:
        explicit_domain = _normalize_web_domain_candidate(explicit_url)
        if explicit_domain and explicit_domain not in seen:
            seen.add(explicit_domain)
            result.append(explicit_domain)

    for match in _DIRECT_FETCH_SITE_RE.finditer(raw):
        candidate = _normalize_web_domain_candidate(match.group("domain"))
        if candidate and candidate not in seen:
            seen.add(candidate)
            result.append(candidate)

    normalized = _normalize_text(raw)
    if include_aliases and normalized:
        for alias, domains in _WEB_SOURCE_ALIAS_DOMAINS:
            if alias not in normalized:
                continue
            for domain in domains:
                candidate = _normalize_web_domain_candidate(domain)
                if candidate and candidate not in seen:
                    seen.add(candidate)
                    result.append(candidate)

    return result


def _looks_like_web_source_selection_followup(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if raw.startswith("/"):
        return False
    explicit_url = _extract_direct_fetch_url_candidate(raw)
    if (_PATHLIKE_QUERY_RE.search(raw) or _FILELIKE_QUERY_RE.search(raw)) and not explicit_url:
        return False
    preferred_domains = _extract_preferred_web_domains(raw)
    if not preferred_domains:
        return False
    if explicit_url:
        return True
    if _WEB_SOURCE_SELECTION_LEAD_RE.search(raw):
        return True
    return _is_low_information_turn(raw, max_tokens=8, max_chars=96)


def _looks_like_live_data_refresh_followup(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if raw.startswith("/"):
        return False
    explicit_url = _extract_direct_fetch_url_candidate(raw)
    if (_PATHLIKE_QUERY_RE.search(raw) or _FILELIKE_QUERY_RE.search(raw)) and not explicit_url:
        return False
    if explicit_url:
        return False
    if len(normalized) > 120:
        return False
    refresh_tokens = {token for token in normalized.split() if token}
    if not (
        refresh_tokens & _LIVE_DATA_REFRESH_KEYWORDS
        or any(phrase in normalized for phrase in _LIVE_DATA_REFRESH_PHRASES)
    ):
        return False
    return _is_low_information_turn(raw, max_tokens=8, max_chars=120)


def _looks_like_browser_interaction_request(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    if _looks_like_direct_page_fetch_request(raw):
        return False
    return bool(_BROWSER_INTERACTION_MARKER_RE.search(raw))


def _build_source_constrained_web_search_query(base_query: str, source_text: str) -> str | None:
    preferred_domains = _extract_preferred_web_domains(source_text)
    if not preferred_domains:
        return None

    base = " ".join(str(_extract_primary_intent_text(base_query) or base_query or "").split()).strip()
    if not base:
        return None

    domain = preferred_domains[0]
    if f"site:{domain}" in _normalize_text(base):
        return base
    return f"{base} site:{domain}".strip()


def _extract_web_search_result_urls(result_text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for match in _WEB_RESULT_URL_RE.finditer(str(result_text or "")):
        candidate = str(match.group(0) or "").rstrip(").,!?]>}")
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        urls.append(candidate)
    return urls


def _select_web_fetch_url_from_search_result(query_text: str, result_text: str) -> str | None:
    urls = _extract_web_search_result_urls(result_text)
    if not urls:
        return None

    preferred_domains = _extract_preferred_web_domains(query_text, include_aliases=False)
    if preferred_domains:
        normalized_urls = [
            (_normalize_web_domain_candidate(url), url)
            for url in urls
        ]
        for preferred_domain in preferred_domains:
            normalized_preferred = _normalize_web_domain_candidate(preferred_domain)
            if not normalized_preferred:
                continue
            for candidate_domain, candidate_url in normalized_urls:
                if not candidate_domain:
                    continue
                if (
                    candidate_domain == normalized_preferred
                    or candidate_domain.endswith(f".{normalized_preferred}")
                    or normalized_preferred.endswith(f".{candidate_domain}")
                ):
                    return candidate_url
        return None

    site_match = _DIRECT_FETCH_SITE_RE.search(str(query_text or ""))
    if site_match:
        preferred_domain = _normalize_web_domain_candidate(site_match.group("domain"))
        if preferred_domain:
            for candidate_url in urls:
                candidate_domain = _normalize_web_domain_candidate(candidate_url)
                if (
                    candidate_domain == preferred_domain
                    or candidate_domain.endswith(f".{preferred_domain}")
                ):
                    return candidate_url

    if len(urls) == 1:
        return urls[0]
    return None


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


def _session_metadata(loop: Any, msg: InboundMessage) -> dict[str, Any] | None:
    try:
        session = loop.sessions.get_or_create(msg.session_key)
    except Exception:
        return None
    metadata = getattr(session, "metadata", None)
    if isinstance(metadata, dict):
        return metadata
    return None


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
    if _tools_has(loop, "web_fetch") and _looks_like_direct_page_fetch_request(query_text):
        metadata["_expected_tool_for_guard"] = "web_fetch"
        return "web_fetch"

    try:
        from kabot.agent.loop_core.tool_enforcement import infer_action_required_tool_for_loop

        action_tool, _action_query = infer_action_required_tool_for_loop(loop, query_text)
    except Exception:
        action_tool = None
    if action_tool:
        metadata["_expected_tool_for_guard"] = action_tool
        return action_tool

    try:
        from kabot.agent.loop_core.tool_enforcement import required_tool_for_query_for_loop

        expected = required_tool_for_query_for_loop(loop, query_text)
    except Exception:
        expected = None
    if expected:
        metadata["_expected_tool_for_guard"] = expected
    return expected


def _query_has_explicit_payload_for_tool(tool_name: str, query_text: str) -> bool:
    normalized_tool = str(tool_name or "").strip().lower()
    text = str(query_text or "").strip()
    if not text:
        return False

    if normalized_tool in {"stock", "stock_analysis"}:
        normalized = _normalize_text(text)
        if _NON_ACTION_MARKER_RE.search(normalized) and _NON_ACTION_STOCK_TOPIC_RE.search(normalized):
            return False
        if _FILELIKE_QUERY_RE.search(text) or _PATHLIKE_QUERY_RE.search(text):
            return False
        return bool(_extract_structural_stock_symbols(text)) or _has_explicit_stock_symbol_payload(text)
    if normalized_tool == "crypto":
        return bool(extract_crypto_ids(text))
    if normalized_tool == "cron":
        if _REMINDER_MARKER_RE.search(text):
            return True
        return bool(_REMINDER_STRUCTURE_RE.search(text))
    if normalized_tool == "weather":
        return bool(_WEATHER_MARKER_RE.search(text))
    if normalized_tool == "web_fetch":
        return bool(_looks_like_direct_page_fetch_request(text))
    if normalized_tool == "read_file":
        return bool(_FILELIKE_QUERY_RE.search(text) or _PATHLIKE_QUERY_RE.search(text))
    if normalized_tool == "find_files":
        query = _extract_find_files_query(text)
        if not query:
            return False
        if _extract_find_files_kind(text) == "dir":
            return not _looks_like_list_dir_request(text)
        return bool(_FIND_FILE_MARKER_RE.search(text) or _FILELIKE_QUERY_RE.search(text))
    if normalized_tool == "message":
        normalized = _normalize_text(text)
        has_target = bool(_FILELIKE_QUERY_RE.search(text) or _PATHLIKE_QUERY_RE.search(text))
        has_delivery_target = any(
            marker in normalized for marker in ("chat here", "send it here", "channel")
        )
        has_imperative_send = bool(_SEND_FILE_MARKER_RE.search(text) and has_target)
        return bool(has_imperative_send and (has_delivery_target or has_target))
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
            "googling",
            "google",
            "browse",
            "news",
            "headline",
            "headlines",
            "latest",
            "update",
        )
        return any(marker in normalized for marker in search_markers)
    if _is_image_like_tool(normalized_tool):
        return bool(_IMAGE_MARKER_RE.search(text))
    if _is_tts_like_tool(normalized_tool):
        return bool(_TTS_MARKER_RE.search(text))
    return False


def _tool_call_intent_mismatch_reason(loop: Any, msg: InboundMessage, tool_name: str) -> str | None:
    normalized_tool = str(tool_name or "").strip().lower()
    query_text = _resolve_query_text_from_message(msg)
    metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
    session_meta = _session_metadata(loop, msg) if hasattr(loop, "sessions") else None

    if normalized_tool == "browser":
        if _query_has_explicit_payload_for_tool("web_fetch", query_text):
            return "expected 'web_fetch'"
        if (
            _looks_like_live_research_query(query_text)
            and not _looks_like_browser_interaction_request(query_text)
            and (_tools_has(loop, "web_search") or _tools_has(loop, "web_fetch"))
        ):
            return "prefer web_search/web_fetch for headless factual lookup"
        if _looks_like_web_source_selection_followup(query_text):
            return "prefer web_search then web_fetch for source follow-up"
        return None

    is_guarded = (
        normalized_tool in _GUARDED_TOOL_CALLS
        or _is_image_like_tool(normalized_tool)
        or _is_tts_like_tool(normalized_tool)
    )
    if not is_guarded:
        return None

    if normalized_tool == "web_search" and _looks_like_direct_page_fetch_request(query_text):
        return None

    if normalized_tool == "message":
        has_send_verb = bool(re.search(r"(?i)\b(send|share|attach|upload)\b", query_text))
        has_explicit_target = bool(_FILELIKE_QUERY_RE.search(query_text) or _PATHLIKE_QUERY_RE.search(query_text))
        if has_send_verb and not has_explicit_target:
            working_directory = str(metadata.get("working_directory") or "").strip()
            if not working_directory and isinstance(session_meta, dict):
                working_directory = str(session_meta.get("working_directory") or "").strip()
            delivery_route = metadata.get("delivery_route")
            if not isinstance(delivery_route, dict) and isinstance(session_meta, dict):
                candidate_route = session_meta.get("delivery_route")
                if isinstance(candidate_route, dict):
                    delivery_route = candidate_route
            if working_directory or isinstance(delivery_route, dict):
                return None
            last_delivery = ""
            last_nav = ""
            if isinstance(session_meta, dict):
                last_delivery = str(session_meta.get("last_delivery_path") or "").strip()
                last_nav = str(session_meta.get("last_navigated_path") or "").strip()
            if last_delivery or last_nav:
                return None

    allowed_workflow_tools: set[str] = set()
    if query_text:
        normalized_query = _normalize_text(query_text)
        delivery_required = bool(metadata.get("requires_message_delivery"))
        route_profile = str(metadata.get("route_profile") or "").strip().upper()
        continuity_source = str(metadata.get("continuity_source") or "").strip().lower()
        coding_execution_context = bool(
            route_profile == "CODING"
            or continuity_source in {"coding_request", "committed_coding_action"}
        )
        if delivery_required and _tools_has(loop, "message"):
            allowed_workflow_tools.add("message")
        if coding_execution_context:
            for workflow_tool in ("read_file", "list_dir", "write_file", "edit_file", "exec"):
                if _tools_has(loop, workflow_tool):
                    allowed_workflow_tools.add(workflow_tool)
        has_find_action = bool(_FIND_FILE_MARKER_RE.search(query_text))
        has_file_subject = bool(_FILELIKE_QUERY_RE.search(query_text) or _PATHLIKE_QUERY_RE.search(query_text))
        if not has_file_subject:
            has_file_subject = any(
                marker in normalized_query
                for marker in ("file", "folder", "directory", "dir", "document", "report", "pdf", "xlsx", "csv")
            )
        if delivery_required and has_find_action and has_file_subject and _tools_has(loop, "find_files"):
            allowed_workflow_tools.add("find_files")
        try:
            from kabot.agent.loop_core.tool_enforcement import infer_action_required_tool_for_loop

            action_tool, _action_query = infer_action_required_tool_for_loop(loop, query_text)
        except Exception:
            action_tool = None
        if action_tool:
            allowed_workflow_tools.add(str(action_tool).strip().lower())
    if normalized_tool in allowed_workflow_tools:
        return None

    if normalized_tool in {"stock", "stock_analysis", "crypto"}:
        if _should_defer_live_research_latch_to_skill(
            loop,
            query_text,
            profile="GENERAL",
            message_metadata=metadata if isinstance(metadata, dict) else None,
        ):
            return "prefer active or explicit external skill over legacy finance tool"

    expected_tool = _resolve_expected_tool_for_query(loop, msg)

    if expected_tool and expected_tool != normalized_tool:
        return f"expected '{expected_tool}'"
    if expected_tool and expected_tool == normalized_tool:
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
