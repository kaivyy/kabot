"""Fallback-support helpers for tool enforcement."""

from __future__ import annotations

import json
import re
from typing import Any

from kabot.agent.fallback_i18n import t as i18n_t

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

def _parse_mcp_argument_value(raw_value: str, schema: dict[str, Any] | None) -> Any:
    value = str(raw_value or "").strip()
    if not value:
        return ""
    if value[:1] == value[-1:] and value[:1] in {"'", '"', "`"}:
        return value[1:-1]

    expected_type = str((schema or {}).get("type") or "").strip().lower()
    lowered = value.lower()
    if expected_type == "boolean":
        if lowered in {"true", "yes", "on"}:
            return True
        if lowered in {"false", "no", "off"}:
            return False
    if expected_type == "integer":
        try:
            return int(value)
        except Exception:
            return value
    if expected_type == "number":
        try:
            return float(value)
        except Exception:
            return value
    if expected_type in {"object", "array"} and value[:1] in {"{", "["}:
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _extract_explicit_mcp_tool_arguments(loop: Any, tool_name: str, text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    tool = loop.tools.get(tool_name)
    if tool is None:
        return {}
    schema = tool.parameters if isinstance(getattr(tool, "parameters", None), dict) else {}
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    if not isinstance(properties, dict) or not properties:
        return {}

    payload: dict[str, Any] = {}
    for prop_name, prop_schema in properties.items():
        pattern = re.compile(
            rf"(?i)\b{re.escape(str(prop_name))}\s*=\s*"
            r"("
            r"'[^']*'"
            r'|"[^"]*"'
            r"|`[^`]*`"
            r"|\{.*?\}"
            r"|\[.*?\]"
            r"|[^\s,;]+"
            r")"
        )
        match = pattern.search(raw)
        if not match:
            continue
        payload[str(prop_name)] = _parse_mcp_argument_value(match.group(1), prop_schema)
    return payload


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
