"""Intent and required-tool routing helpers for execution runtime."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from kabot.agent.cron_fallback_nlp import required_tool_for_query
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
    if _PERSONAL_HR_CALC_RE.search(normalized):
        return False
    if _MEMORY_COMMIT_INTENT_RE.search(normalized):
        return False

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
) -> bool:
    """Return True when a matched external skill should outrank web-search forcing."""
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
            return bool(external_match(text, profile=profile))
        except Exception:
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
_FIND_FILE_MARKER_RE = re.compile(
    r"(?i)\b(cari|carikan|find|search|locate|look for|temukan|telusuri)\b"
)
_SEND_FILE_MARKER_RE = re.compile(
    r"(?i)\b(kirim|send|share|attach|lampirkan|upload)\b"
)
_WEATHER_MARKER_RE = re.compile(
    r"(?i)\b(weather|temperature|forecast|cuaca|suhu|temperatur|prakiraan|ramalan)\b"
)
_IMAGE_MARKER_RE = re.compile(
    r"(?i)\b(image|gambar|photo|foto|picture|draw|sketch|illustrat(?:e|ion)|render|generate\s+image|buat(?:kan)?\s+gambar)\b"
)
_TTS_MARKER_RE = re.compile(
    r"(?i)\b(tts|text\s*to\s*speech|voice|suara|audio|narrat(?:e|ion)|bacakan|read\s+aloud|speak|ucapkan)\b"
)
_DIRECT_FETCH_VERB_RE = re.compile(
    r"(?i)\b(fetch|open|visit|read|scrape|crawl|ambil|buka|baca|ringkas|summari[sz]e|isi website|isi halaman|konten website|konten halaman)\b"
)
_DIRECT_FETCH_URL_RE = re.compile(r"(?i)\bhttps?://[^\s]+")
_DIRECT_FETCH_DOMAIN_RE = re.compile(
    r"(?i)\b(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s]*)?\b"
)
_NON_ACTION_MARKER_RE = re.compile(
    r"(?i)\b(stop|hentikan|berhenti|jangan|bukan|dont|don't|do not|cancel|batalkan|ga usah|gak usah|nggak usah|tidak usah|no need)\b"
)
_NON_ACTION_STOCK_TOPIC_RE = re.compile(
    r"(?i)\b(stock|saham|ticker|market|harga|price|idx|ihsg)\b"
)
_SKILL_CREATION_GUARDED_TOOLS = {"write_file", "edit_file", "exec"}


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

    expected = required_tool_for_query(
        question=query_text,
        has_weather_tool=_tools_has(loop, "weather"),
        has_cron_tool=_tools_has(loop, "cron"),
        has_system_info_tool=_tools_has(loop, "get_system_info"),
        has_cleanup_tool=_tools_has(loop, "cleanup_system"),
        has_speedtest_tool=_tools_has(loop, "speedtest"),
        has_process_memory_tool=_tools_has(loop, "get_process_memory"),
        has_save_memory_tool=_tools_has(loop, "save_memory"),
        has_stock_tool=_tools_has(loop, "stock"),
        has_stock_analysis_tool=_tools_has(loop, "stock_analysis"),
        has_crypto_tool=_tools_has(loop, "crypto"),
        has_server_monitor_tool=_tools_has(loop, "server_monitor"),
        has_web_search_tool=_tools_has(loop, "web_search"),
        has_read_file_tool=_tools_has(loop, "read_file"),
        has_check_update_tool=_tools_has(loop, "check_update"),
        has_system_update_tool=_tools_has(loop, "system_update"),
    )
    if expected in {"stock", "stock_analysis", "crypto"}:
        return None
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
        normalized = _normalize_text(text)
        has_subject = bool(_FILELIKE_QUERY_RE.search(text)) or any(
            marker in normalized for marker in ("file", "folder", "berkas", "dokumen", "document", "report", "pdf", "xlsx", "csv")
        )
        return bool(_FIND_FILE_MARKER_RE.search(text) and has_subject)
    if normalized_tool == "message":
        normalized = _normalize_text(text)
        has_target = bool(_FILELIKE_QUERY_RE.search(text) or _PATHLIKE_QUERY_RE.search(text))
        has_delivery_target = any(
            marker in normalized for marker in ("chat ini", "chat here", "kirim ke chat", "send it here", "channel ini", "channel")
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
    metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
    session_meta = _session_metadata(loop, msg) if hasattr(loop, "sessions") else None

    if normalized_tool == "web_search" and _looks_like_direct_page_fetch_request(query_text):
        return None

    if normalized_tool == "message":
        has_send_verb = bool(re.search(r"(?i)\b(kirim|send|share|attach|lampirkan|upload)\b", query_text))
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
                for marker in ("file", "folder", "directory", "dir", "berkas", "dokumen", "document", "report", "pdf", "xlsx", "csv")
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
        context_builder = getattr(loop, "context", None)
        skills_loader = getattr(context_builder, "skills", None)
        external_finance = getattr(skills_loader, "has_external_finance_skill_available", None)
        try:
            if callable(external_finance) and external_finance():
                return "prefer external finance skill over legacy finance tool"
        except Exception:
            pass
        if _should_defer_live_research_latch_to_skill(loop, query_text, profile="GENERAL"):
            return "prefer matched external skill over legacy finance tool"

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
