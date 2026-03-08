"""Tool-enforcement and deterministic fallback logic for AgentLoop."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kabot.agent.cron_fallback_nlp import (
    CRON_MANAGEMENT_OPS,
    CRON_MANAGEMENT_TERMS,
    extract_cycle_schedule,
    extract_explicit_schedule_title,
    extract_new_schedule_title,
    extract_recurring_schedule,
    extract_reminder_message,
    extract_weather_location,
    required_tool_for_query,
)
from kabot.agent.cron_fallback_nlp import (
    build_cycle_title as nlp_build_cycle_title,
)
from kabot.agent.cron_fallback_nlp import (
    build_group_id as nlp_build_group_id,
)
from kabot.agent.cron_fallback_nlp import (
    make_unique_schedule_title as nlp_make_unique_schedule_title,
)
from kabot.agent.fallback_i18n import t as i18n_t
from kabot.agent.tools.stock import (
    extract_crypto_ids,
    extract_stock_name_candidates,
    extract_stock_symbols,
)
from kabot.bus.events import InboundMessage

_FILELIKE_QUERY_RE = re.compile(
    r"\b[\w\-]+\.(json|ya?ml|toml|ini|cfg|conf|env|md|txt|csv|log|pdf|docx?|xlsx?|py|js|ts|tsx|jsx|html|css|xml)\b",
    re.IGNORECASE,
)
_PATHLIKE_QUERY_RE = re.compile(
    r"([a-zA-Z]:[\\/][^\n\r\"']+|\\\\[^\n\r\"']+|(?<![\w])/[^\"'\s]+|(?<![\w])~[\\/][^\s\"']+|[\w.\-]+\\[\w .\\/-]+)"
)
_STOCK_TRACKING_MARKER_RE = re.compile(
    r"(?i)\b("
    r"track(?:ing)?|trend|movement|history|historical|chart|grafik|"
    r"pergerakan|riwayat|naik turun|kinerja|performance|"
    r"bulan terakhir|hari terakhir|minggu terakhir|"
    r"\d+\s*(?:day|days|hari|week|weeks|minggu|month|months|bulan)|"
    r"1m|3m|6m|1y"
    r")\b"
)
_STOCK_DAYS_DAY_RE = re.compile(r"(?i)\b(\d{1,3})\s*(day|days|hari)\b")
_STOCK_DAYS_WEEK_RE = re.compile(r"(?i)\b(\d{1,3})\s*(week|weeks|minggu)\b")
_STOCK_DAYS_MONTH_RE = re.compile(r"(?i)\b(\d{1,2})\s*(month|months|bulan)\b")
_STOCK_IDR_CONVERSION_MARKER_RE = re.compile(
    r"(?i)\b(idr|rupiah|dirupiahkan|rupiahkan|konversi|convert(?:ed|ion)?)\b"
)
_GENERIC_STOCK_NAME_NOISE_WORDS = {
    "harga",
    "price",
    "sekarang",
    "today",
    "now",
    "berapa",
    "how",
    "much",
    "dengan",
    "dalam",
    "untuk",
    "kalau",
    "jika",
    "pakai",
    "gunakan",
    "dirupiahkan",
    "rupiah",
    "rupiahkan",
    "kurs",
    "konversi",
    "convert",
    "usd",
    "idr",
    "dollar",
    "ke",
    "to",
}
_WEB_SEARCH_TAIL_INSTRUCTION_RE = re.compile(
    r"(?i)(?:[,:;.!?]\s*|\s+)(?:tolong|please)\s+(?:jawab|answer|respond)\b.*$"
)
_WEB_SEARCH_STYLE_CLAUSE_RE = re.compile(
    r"(?i)\b(?:jawab|answer|respond)\s+(?:seperti|like|as)\b.*$"
)
_WEB_SEARCH_EXTRA_SPACE_RE = re.compile(r"\s+")
_FILESYSTEM_TARGET_MARKERS = (
    "desktop",
    "downloads",
    "download",
    "documents",
    "document",
    "docs",
    "pictures",
    "photos",
    "music",
    "videos",
    "home",
    "桌面",
    "下载",
    "下載",
    "文档",
    "文件档案",
    "文件檔案",
    "デスクトップ",
    "ダウンロード",
    "書類",
    "ドキュメント",
    "เดสก์ท็อป",
    "ดาวน์โหลด",
    "เอกสาร",
)
_FILESYSTEM_TRAILING_TAIL_RE = re.compile(
    r"(?i)\s+(?:sekarang|now|please|tolong|tampilkan|tampilin|show|display|list|lihat|lihatkan|"
    r"buka|open|masuk|enter|read|baca|dong|ya|lagi|again|pc)$"
)
_RELATIVE_DIRECTORY_QUERY_RE = re.compile(
    r"(?i)(?:\b(?:subfolder|folder|direktori|directory|dir)\b|文件夹|文件夾|资料夹|資料夾|目录|目錄|フォルダ|ディレクトリ|โฟลเดอร์|ไดเรกทอรี)\s+(.+)$"
)


def _filesystem_home_dir() -> Path:
    return Path.home()


def _normalize_filesystem_candidate(value: str) -> str:
    cleaned = str(value or "").strip().strip("\"'`").rstrip(".,;:!?)]}")
    while cleaned:
        next_cleaned = _FILESYSTEM_TRAILING_TAIL_RE.sub("", cleaned).strip().rstrip(".,;:!?)]}")
        if next_cleaned == cleaned:
            break
        cleaned = next_cleaned
    return cleaned


def _trim_candidate_after_filelike(candidate: str) -> str:
    raw = str(candidate or "").strip()
    if not raw:
        return ""
    matches = list(_FILELIKE_QUERY_RE.finditer(raw))
    if not matches:
        return raw
    last_match = matches[-1]
    trailing = raw[last_match.end() :].strip()
    if trailing:
        return raw[: last_match.end()]
    return raw


def _extract_explicit_path_candidate(text: str) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None

    quoted = re.findall(r"[\"'`]+([^\"'`]+)[\"'`]+", raw)
    for candidate in quoted:
        cleaned = _trim_candidate_after_filelike(_normalize_filesystem_candidate(candidate))
        if cleaned and (_FILELIKE_QUERY_RE.search(cleaned) or _PATHLIKE_QUERY_RE.search(cleaned)):
            return cleaned

    path_match = _PATHLIKE_QUERY_RE.search(raw)
    if path_match:
        cleaned = _trim_candidate_after_filelike(_normalize_filesystem_candidate(path_match.group(1)))
        if cleaned:
            return cleaned
    return None


def _resolve_special_directory_path(text: str) -> str | None:
    normalized = _normalize_text(text)
    if not normalized:
        return None
    home = _filesystem_home_dir()
    if re.search(r"(?i)\bdesktop\b|桌面|デスクトップ|เดสก์ท็อป", normalized):
        return str(home / "Desktop")
    if re.search(r"(?i)\bdownloads?\b|下载|下載|ダウンロード|ดาวน์โหลด", normalized):
        return str(home / "Downloads")
    if re.search(r"(?i)\bdocuments?\b|\bdocs\b|文档|文件档案|文件檔案|書類|ドキュメント|เอกสาร", normalized):
        return str(home / "Documents")
    if re.search(r"(?i)\bpictures?\b|\bphotos?\b", normalized):
        return str(home / "Pictures")
    if re.search(r"(?i)\bmusic\b", normalized):
        return str(home / "Music")
    if re.search(r"(?i)\bvideos?\b", normalized):
        return str(home / "Videos")
    if re.search(r"(?i)\bhome\b", normalized):
        return str(home)
    return None


def _extract_relative_directory_candidate(text: str) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    match = _RELATIVE_DIRECTORY_QUERY_RE.search(raw)
    if not match:
        return None
    candidate = _normalize_filesystem_candidate(match.group(1))
    if not candidate:
        return None
    if any(sep in candidate for sep in ("/", "\\")):
        return None
    normalized = _normalize_text(candidate)
    if normalized in _FILESYSTEM_TARGET_MARKERS:
        return None
    return candidate


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
    return required_tool_for_query(
        question=question,
        has_weather_tool=loop.tools.has("weather"),
        has_cron_tool=loop.tools.has("cron"),
        has_system_info_tool=loop.tools.has("get_system_info"),
        has_cleanup_tool=loop.tools.has("cleanup_system"),
        has_speedtest_tool=loop.tools.has("speedtest"),
        has_process_memory_tool=loop.tools.has("get_process_memory"),
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


def make_unique_schedule_title_for_loop(loop: Any, base_title: str) -> str:
    return nlp_make_unique_schedule_title(base_title, existing_schedule_titles(loop))


def build_group_id_for_loop(loop: Any, title: str) -> str:
    stamp = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    return nlp_build_group_id(title, now_ms=stamp)


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _is_low_information_followup(value: str, *, max_tokens: int = 6, max_chars: int = 64) -> bool:
    """
    Detect short confirmation/follow-up turns without language-specific keywords.

    This keeps behavior multilingual and avoids parsing stale assistant metadata
    as fresh user intent.
    """
    normalized = _normalize_text(value)
    if not normalized:
        return False
    if len(normalized) > max_chars:
        return False
    tokens = [part for part in normalized.split(" ") if part]
    if len(tokens) == 0 or len(tokens) > max_tokens:
        return False
    if any(mark in value for mark in ("?", "？", "¿", "؟")):
        return False
    if re.search(r"(https?://|www\.)", normalized):
        return False
    if re.search(r"[@#]\w+", normalized):
        return False
    if re.search(r"\d{4,}", normalized):
        return False
    return True


def _looks_like_verbose_non_query_text(value: str) -> bool:
    """
    Detect assistant-style/stale metadata blobs that are unlikely to be direct user queries.

    This intentionally uses structural signals (length + sentence/list formatting)
    to stay language-agnostic.
    """
    raw = str(value or "").strip()
    if not raw:
        return False
    normalized = _normalize_text(raw)
    if len(normalized) < 80:
        return False
    tokens = [part for part in normalized.split(" ") if part]
    if len(tokens) < 14:
        return False
    sentence_like = raw.count(".") + raw.count("!") + raw.count("?") >= 2
    structured = any(marker in raw for marker in ("\n", "•", "|"))
    return sentence_like or structured


def _query_has_tool_payload(tool_name: str, text: str) -> bool:
    """Check whether raw user text carries explicit payload for a required tool."""
    raw = str(text or "").strip()
    if not raw:
        return False
    tool = str(tool_name or "").strip().lower()
    if tool in {"stock", "stock_analysis"}:
        symbols = extract_stock_symbols(raw)
        if symbols:
            return True
        if _FILELIKE_QUERY_RE.search(raw) or _PATHLIKE_QUERY_RE.search(raw):
            return False
        names = extract_stock_name_candidates(raw)
        if not names:
            return False
        for candidate in names:
            tokens = [token for token in _normalize_text(candidate).split(" ") if token]
            if not tokens:
                continue
            if any(token not in _GENERIC_STOCK_NAME_NOISE_WORDS for token in tokens):
                return True
        return False
    if tool == "crypto":
        return bool(extract_crypto_ids(raw))
    if tool == "weather":
        return bool(extract_weather_location(raw))
    if tool == "read_file":
        return bool(_extract_read_file_path(raw))
    if tool == "list_dir":
        return bool(_extract_list_dir_path(raw) or _extract_relative_directory_candidate(raw))
    return False


def _extract_read_file_path(text: str) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None

    explicit_path = _extract_explicit_path_candidate(raw)
    if explicit_path:
        return explicit_path

    # Finally, plain filename.ext tokens.
    file_match = _FILELIKE_QUERY_RE.search(raw)
    if file_match:
        cleaned = _normalize_filesystem_candidate(file_match.group(0))
        if cleaned:
            return cleaned
    return None


def _extract_list_dir_path(text: str, *, last_tool_context: dict[str, Any] | None = None) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None

    fallback_path = ""
    if isinstance(last_tool_context, dict):
        fallback_path = str(last_tool_context.get("path") or "").strip()

    explicit_path = _extract_explicit_path_candidate(raw)
    if explicit_path:
        return explicit_path

    special_dir = _resolve_special_directory_path(raw)
    if special_dir:
        return special_dir

    relative_dir = _extract_relative_directory_candidate(raw)
    if relative_dir and fallback_path:
        return str(Path(fallback_path) / relative_dir)

    if fallback_path and _is_low_information_followup(raw):
        return fallback_path

    return None


def _looks_like_stock_tracking_query(text: str) -> bool:
    return bool(_STOCK_TRACKING_MARKER_RE.search(str(text or "")))


def _looks_like_stock_idr_conversion_query(text: str) -> bool:
    return bool(_STOCK_IDR_CONVERSION_MARKER_RE.search(str(text or "")))


def _extract_stock_analysis_days(text: str, *, default_days: int = 30) -> int:
    raw = str(text or "")
    match_day = _STOCK_DAYS_DAY_RE.search(raw)
    if match_day:
        return max(5, min(365, int(match_day.group(1))))

    match_week = _STOCK_DAYS_WEEK_RE.search(raw)
    if match_week:
        days = int(match_week.group(1)) * 7
        return max(5, min(365, days))

    match_month = _STOCK_DAYS_MONTH_RE.search(raw)
    if match_month:
        days = int(match_month.group(1)) * 30
        return max(5, min(365, days))

    return max(5, min(365, int(default_days)))


def _format_update_tool_output(required_tool: str, raw_result: Any, source_text: str) -> str:
    """Convert JSON tool payload to localized user-facing update message."""
    text_result = str(raw_result or "").strip()
    if not text_result:
        return text_result
    try:
        payload = json.loads(text_result)
    except Exception:
        return text_result

    if required_tool == "check_update":
        error = str(payload.get("error") or "").strip()
        if error:
            return i18n_t("update.check.error", source_text, error=error)

        latest_version = str(payload.get("latest_version") or "unknown")
        current_version = str(payload.get("current_version") or "unknown")
        update_available = bool(payload.get("update_available"))

        lines: list[str] = []
        if update_available:
            lines.append(
                i18n_t(
                    "update.check.available",
                    source_text,
                    latest_version=latest_version,
                    current_version=current_version,
                )
            )
            commits_behind = int(payload.get("commits_behind") or 0)
            if commits_behind > 0:
                lines.append(
                    i18n_t(
                        "update.check.commits_behind",
                        source_text,
                        commits_behind=commits_behind,
                    )
                )
        else:
            lines.append(
                i18n_t(
                    "update.check.up_to_date",
                    source_text,
                    current_version=current_version,
                )
            )

        release_url = str(payload.get("release_url") or "").strip()
        if release_url:
            lines.append(f"Release: {release_url}")
        return "\n".join(lines)

    if required_tool == "system_update":
        if not bool(payload.get("success")):
            reason = str(payload.get("reason") or "").strip()
            if reason == "dirty_working_tree":
                return i18n_t("update.install.dirty_tree", source_text)
            error = str(payload.get("message") or reason or "unknown error")
            return i18n_t("update.install.failed", source_text, error=error)

        old_version = str(payload.get("updated_from") or "unknown")
        new_version = str(payload.get("updated_to") or "unknown")
        lines = [
            i18n_t(
                "update.install.success",
                source_text,
                old_version=old_version,
                new_version=new_version,
            )
        ]
        if bool(payload.get("restart_required")):
            lines.append(i18n_t("update.install.restart_confirm", source_text))
        release_url = str(payload.get("release_url") or "").strip()
        if release_url:
            lines.append(f"Release: {release_url}")
        return "\n".join(lines)

    return text_result


def _compact_web_search_query(source_text: str) -> str:
    """
    Trim conversational answer-style tails from live-search queries.

    Keep the original user text in `context_text`; only compact the actual
    outbound search string so news prompts remain natural but searchable.
    """
    raw = str(source_text or "").strip()
    if not raw:
        return raw
    compact = _WEB_SEARCH_TAIL_INSTRUCTION_RE.sub("", raw).strip(" ,;:.!?")
    compact = _WEB_SEARCH_STYLE_CLAUSE_RE.sub("", compact).strip(" ,;:.!?")
    compact = _WEB_SEARCH_EXTRA_SPACE_RE.sub(" ", compact).strip()
    return compact or raw


async def execute_required_tool_fallback(loop: Any, required_tool: str, msg: InboundMessage) -> str | None:
    """Deterministic fallback when model skips required tools repeatedly."""
    metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
    resolved_query = str(metadata.get("required_tool_query") or "").strip()
    raw_text = str(msg.content or "").strip()
    source_text = resolved_query or raw_text
    stale_metadata_dropped = False

    # Prefer fresh raw user intent when it clearly maps to the same required tool.
    # This protects against stale carried metadata when users switch tasks quickly.
    if resolved_query and raw_text:
        try:
            raw_required_tool = required_tool_for_query_for_loop(loop, raw_text)
        except Exception:
            raw_required_tool = None
        if raw_required_tool == required_tool:
            raw_has_payload = _query_has_tool_payload(required_tool, raw_text)
            resolved_has_payload = _query_has_tool_payload(required_tool, source_text)
            if raw_has_payload or not resolved_has_payload:
                source_text = raw_text

    # Generic stale-metadata guard for short follow-up turns.
    # Example: user sends "iya/ok/gas", but metadata accidentally carries a long
    # assistant paragraph from the previous turn.
    if (
        resolved_query
        and raw_text
        and _is_low_information_followup(raw_text)
        and _looks_like_verbose_non_query_text(resolved_query)
    ):
        source_text = raw_text
        stale_metadata_dropped = True

    # If user sends a short follow-up that contains a concrete tool payload
    # (e.g., "adaro mana", "ethereum berapa", "cuaca di 東京"), prefer it over
    # stale carried query metadata.
    if resolved_query and raw_text and _query_has_tool_payload(required_tool, raw_text):
        source_text = raw_text

    if required_tool == "web_search":
        query = _compact_web_search_query(source_text)
        if not query:
            return i18n_t("web_search.need_query", source_text)
        if stale_metadata_dropped:
            return i18n_t("web_search.need_topic", source_text)
        result = await loop.tools.execute(
            "web_search",
            {"query": query, "count": 5, "context_text": source_text},
        )
        return str(result)

    if required_tool == "list_dir":
        last_tool_context = metadata.get("last_tool_context") if isinstance(metadata.get("last_tool_context"), dict) else {}
        path = _extract_list_dir_path(source_text, last_tool_context=last_tool_context)
        if not path:
            return i18n_t("filesystem.need_path", source_text)
        result = await loop.tools.execute("list_dir", {"path": path})
        return str(result)

    if required_tool == "read_file":
        path = _extract_read_file_path(source_text)
        if not path:
            path = str(metadata.get("file_analysis_path") or "").strip()
        if not path:
            last_tool_context = (
                metadata.get("last_tool_context")
                if isinstance(metadata.get("last_tool_context"), dict)
                else {}
            )
            path = str(last_tool_context.get("path") or "").strip()
        if not path:
            return i18n_t("filesystem.need_path", source_text)
        result = await loop.tools.execute("read_file", {"path": path})
        return str(result)

    if required_tool == "check_update":
        result = await loop.tools.execute("check_update", {})
        return _format_update_tool_output(required_tool, result, source_text)

    if required_tool == "system_update":
        result = await loop.tools.execute("system_update", {"confirm_restart": False})
        return _format_update_tool_output(required_tool, result, source_text)

    if required_tool == "weather":
        last_tool_context = metadata.get("last_tool_context") if isinstance(metadata.get("last_tool_context"), dict) else {}
        fallback_location = str(last_tool_context.get("location") or "").strip()
        short_weather_followup = bool(
            raw_text
            and len(str(raw_text).strip()) <= 24
            and re.search(r"(?i)(wind|angin|weather|cuaca|[風风]|ลม)", str(raw_text))
        )
        if raw_text and (_is_low_information_followup(raw_text) or short_weather_followup) and fallback_location:
            location = fallback_location
        else:
            location = extract_weather_location(source_text)
            if not location and fallback_location:
                location = fallback_location
        if not location:
            return i18n_t("weather.need_location", source_text)
        result = await loop.tools.execute(
            "weather",
            {"location": location, "context_text": source_text},
        )
        return str(result)

    if required_tool == "get_system_info":
        result = await loop.tools.execute("get_system_info", {})
        return str(result)

    if required_tool == "server_monitor":
        result = await loop.tools.execute("server_monitor", {})
        return str(result)

    if required_tool == "get_process_memory":
        q_lower = source_text.lower()
        limit = 15
        match = re.search(r"\b(\d{1,3})\b", q_lower)
        if match:
            try:
                limit = int(match.group(1))
            except Exception:
                limit = 15
        if limit < 1:
            limit = 1
        if limit > 200:
            limit = 200
        result = await loop.tools.execute("get_process_memory", {"limit": limit})
        return str(result)

    if required_tool == "speedtest":
        result = await loop.tools.execute("speedtest", {})
        return str(result)

    if required_tool == "stock_analysis":
        symbols = extract_stock_symbols(source_text)
        days = _extract_stock_analysis_days(source_text, default_days=30)
        if symbols:
            result = await loop.tools.execute(
                "stock_analysis",
                {"symbol": symbols[0], "days": days},
            )
            return str(result)
        name_candidates = extract_stock_name_candidates(source_text)
        if not name_candidates:
            return i18n_t("stock.need_symbol", source_text)
        result = await loop.tools.execute(
            "stock_analysis",
            {"symbol": source_text, "days": days},
        )
        return str(result)

    if required_tool == "stock":
        # Guard against stale assistant-style metadata being reused as ticker query
        # when user only sends a short confirmation like "iya/ok/gas".
        raw_text_norm = _normalize_text(raw_text)
        if (
            resolved_query
            and raw_text_norm
            and _is_low_information_followup(raw_text)
            and len(resolved_query) > 80
        ):
            source_text = raw_text

        tracking_signal = _looks_like_stock_tracking_query(raw_text) or _looks_like_stock_tracking_query(source_text)
        if tracking_signal and loop.tools.has("stock_analysis"):
            combined_text = " ".join(part for part in (source_text, raw_text) if part).strip()
            analysis_symbols = extract_stock_symbols(combined_text)
            analysis_days = _extract_stock_analysis_days(raw_text or source_text, default_days=30)
            if analysis_symbols:
                result = await loop.tools.execute(
                    "stock_analysis",
                    {"symbol": analysis_symbols[0], "days": analysis_days},
                )
                return str(result)
            analysis_name_candidates = extract_stock_name_candidates(combined_text)
            if analysis_name_candidates:
                result = await loop.tools.execute(
                    "stock_analysis",
                    {"symbol": combined_text, "days": analysis_days},
                )
                return str(result)

        combined_parts: list[str] = []
        seen_parts: set[str] = set()
        for part in (source_text, raw_text):
            normalized_part = str(part or "").strip()
            if not normalized_part:
                continue
            dedupe_key = normalized_part.lower()
            if dedupe_key in seen_parts:
                continue
            seen_parts.add(dedupe_key)
            combined_parts.append(normalized_part)
        combined_text = " ".join(combined_parts).strip()
        if (
            combined_text
            and raw_text
            and _looks_like_stock_idr_conversion_query(raw_text)
            and combined_text != source_text
        ):
            result = await loop.tools.execute("stock", {"symbol": combined_text})
            return str(result)

        q_lower = source_text.lower()
        tickers = extract_stock_symbols(source_text)
        if tickers:
            result = await loop.tools.execute("stock", {"symbol": ",".join(tickers)})
            return str(result)

        if "crypto" in q_lower or "btc" in q_lower or "eth" in q_lower:
            required_tool = "crypto"
        else:
            # For ranking/list-style requests without explicit ticker, use web search directly.
            stock_research_markers = ("top", "best", "teratas", "unggulan", "rekomendasi", "list", "daftar")
            if loop.tools.has("web_search") and any(marker in q_lower for marker in stock_research_markers):
                result = await loop.tools.execute(
                    "web_search",
                    {"query": source_text.strip(), "count": 5, "context_text": source_text},
                )
                return str(result)
            name_candidates = extract_stock_name_candidates(source_text)
            if not name_candidates:
                return i18n_t("stock.need_symbol", source_text)
            stock_result = await loop.tools.execute("stock", {"symbol": source_text})
            stock_text = str(stock_result)
            if (
                stock_text == i18n_t("stock.need_symbol", source_text)
                or "No valid stock ticker found" in stock_text
            ):
                return i18n_t("stock.need_symbol", source_text)
            return stock_text

    if required_tool == "crypto":
        coins = extract_crypto_ids(source_text)
        coin_arg = ",".join(coins) if coins else "bitcoin"
        result = await loop.tools.execute("crypto", {"coin": coin_arg})
        return str(result)

    if required_tool == "cleanup_system":
        # Detect cleanup level from user message
        q_lower = source_text.lower()
        level = "standard"
        if any(k in q_lower for k in ("deep", "dalam", "mendalam", "full", "lengkap")):
            level = "deep"
        elif any(k in q_lower for k in ("quick", "cepat", "ringan", "light")):
            level = "quick"
        result = await loop.tools.execute("cleanup_system", {"level": level})
        return str(result)

    if required_tool != "cron":
        return None

    from kabot.cron.parse import parse_absolute_time_ms, parse_relative_time_ms

    async def _exec_cron(payload: dict[str, Any]) -> Any:
        enriched = dict(payload)
        enriched.setdefault("context_text", source_text)
        return await loop.tools.execute("cron", enriched)

    q_lower = source_text.lower()
    is_management = any(op in q_lower for op in CRON_MANAGEMENT_OPS) and any(
        term in q_lower for term in CRON_MANAGEMENT_TERMS
    )

    if is_management and any(k in q_lower for k in ("list", "lihat", "show")):
        result = await _exec_cron({"action": "list_groups"})
        return str(result)

    if is_management and any(k in q_lower for k in ("hapus", "delete", "remove")):
        group_id_match = re.search(r"\bgrp_[a-z0-9_-]+\b", q_lower)
        if group_id_match:
            result = await _exec_cron({"action": "remove_group", "group_id": group_id_match.group(0)})
            return str(result)

        title = extract_explicit_schedule_title(source_text)
        if title:
            result = await _exec_cron({"action": "remove_group", "title": title})
            return str(result)

        job_id_match = re.search(r"\b[a-f0-9]{8}\b", q_lower)
        if job_id_match:
            result = await _exec_cron({"action": "remove", "job_id": job_id_match.group(0)})
            return str(result)

        return i18n_t("cron.remove.need_selector", source_text)

    if is_management and any(k in q_lower for k in ("edit", "ubah", "update")):
        selector_payload: dict[str, Any] = {}
        group_id_match = re.search(r"\bgrp_[a-z0-9_-]+\b", q_lower)
        if group_id_match:
            selector_payload["group_id"] = group_id_match.group(0)
        else:
            title = extract_explicit_schedule_title(source_text)
            if title:
                selector_payload["title"] = title

        if not selector_payload:
            return i18n_t("cron.update.need_selector", source_text)

        update_payload: dict[str, Any] = {"action": "update_group", **selector_payload}
        recurring_update = extract_recurring_schedule(source_text)
        if recurring_update:
            update_payload.update(recurring_update)

        new_title = extract_new_schedule_title(source_text)
        if new_title:
            update_payload["new_title"] = make_unique_schedule_title_for_loop(loop, new_title)

        if len(update_payload) <= 2:
            return i18n_t("cron.update.incomplete", source_text)

        result = await _exec_cron(update_payload)
        return str(result)

    cycle_schedule = extract_cycle_schedule(source_text)
    if cycle_schedule:
        every_seconds = int(cycle_schedule["period_days"]) * 86400
        group_title = nlp_build_cycle_title(
            source_text,
            int(cycle_schedule["period_days"]),
            existing_schedule_titles(loop),
        )
        group_id = build_group_id_for_loop(loop, group_title)
        created_jobs = 0
        for event in cycle_schedule["events"]:
            payload = {
                "action": "add",
                "message": event["message"],
                "title": group_title,
                "group_id": group_id,
                "every_seconds": every_seconds,
                "start_at": event["start_at"],
                "one_shot": False,
            }
            await _exec_cron(payload)
            created_jobs += 1
        return i18n_t(
            "cron.cycle_created",
            source_text,
            title=group_title,
            group_id=group_id,
            job_count=created_jobs,
            period_days=int(cycle_schedule["period_days"]),
        )

    reminder_text = extract_reminder_message(source_text)
    recurring_schedule = extract_recurring_schedule(source_text)
    if recurring_schedule:
        default_title = f"Recurring: {reminder_text[:40]}".strip()
        group_title = make_unique_schedule_title_for_loop(loop, default_title)
        recurring_payload = {
            "action": "add",
            "message": reminder_text,
            "title": group_title,
            "group_id": build_group_id_for_loop(loop, group_title),
            **recurring_schedule,
        }
        result = await _exec_cron(recurring_payload)
        return str(result)

    target_ms: int | None = None
    relative_ms = parse_relative_time_ms(source_text)
    if relative_ms is not None:
        now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        target_ms = now_ms + relative_ms
    else:
        absolute_match = re.search(
            r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)",
            source_text or "",
        )
        if absolute_match:
            target_ms = parse_absolute_time_ms(absolute_match.group(1))

    if target_ms is None:
        return i18n_t("cron.time_unclear", source_text)

    at_time = datetime.fromtimestamp(target_ms / 1000, tz=timezone.utc).astimezone().isoformat(timespec="seconds")
    result = await _exec_cron(
        {
            "action": "add",
            "message": reminder_text,
            "at_time": at_time,
            "one_shot": True,
        }
    )
    return str(result)
