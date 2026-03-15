from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from kabot.agent.cron_fallback_nlp import extract_weather_location

_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_WEATHER_METRIC_VALUE_RE = re.compile(
    r"(?i)\b\d+(?:[.,]\d+)?\s*(?:km/?h|kph|m/?s|mph|kt|kts|knots?)\b"
)
_WEATHER_METRIC_QUERY_RE = re.compile(
    r"(?i)\b("
    r"normal|"
    r"how|what|why|is that|too fast|too slow|strong|weak"
    r")\b"
)
_IDR_CONVERSION_RE = re.compile(
    r"(?i)\b("
    r"idr|convert(?:ed|ion)?"
    r")\b"
)
_CURRENCY_RE = re.compile(r"(?i)\b(usd|dollar|idr|yen|eur|euro|gbp)\b")
_STOCK_TREND_RE = re.compile(
    r"(?i)\b("
    r"bullish|bearish|support|resistance|"
    r"analysis|breakout|pullback|entry|exit|stop\s*loss|take\s*profit|tp|sl"
    r")\b"
)
_WEATHER_KEYWORDS = frozenset({
    "weather", "temperature", "forecast",
    "wind", "humid", "rain",
    "cloudy", "sunny",
})
_WEATHER_FRAGMENTS = ("風", "风", "ลม", "天気", "天气", "อากาศ")
_WEATHER_COMMENTARY_KEYWORDS = frozenset({
    "pretty", "quite", "kind", "feels", "feel", "seems",
})
_WEATHER_TEMPERATURE_FEEL_KEYWORDS = frozenset({
    "humid", "warm", "hot", "cold", "cool", "chilly",
})
_WEATHER_FRESH_QUERY_KEYWORDS = frozenset({
    "forecast", "tomorrow", "later", "next", "rain", "wind",
    "humidity", "degree", "degrees", "why", "how", "what", "when",
})
_WEATHER_SOURCE_REQUEST_RE = re.compile(
    r"(?i)\b(?:source|provider)\b|source[- ]?name|where\s+from"
)
_WEATHER_PROVIDER_DOMAIN_RE = re.compile(
    r"(?i)(?:^|[\s(])(?:https?://)?(?:www\.)?"
    r"(?:wttr\.in|wttrin|open-meteo|open\s+meteo|openweather|weatherapi|weather\.com|accuweather)"
    r"(?:/|\b)"
)
_DOMAIN_LIKE_RE = re.compile(r"(?i)^(?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+/?$")


@dataclass(slots=True)
class ContextualFollowupHint:
    kind: str = "none"
    required_tool: str | None = None
    required_tool_query: str | None = None
    reason: str = ""


def _normalize_text(text: str) -> str:
    raw = str(text or "").strip().lower()
    if not raw:
        return ""
    compact = _NON_WORD_RE.sub(" ", raw)
    return _SPACE_RE.sub(" ", compact).strip()


def _normalized_keywords(normalized: str) -> set[str]:
    if not normalized:
        return set()
    return {token for token in normalized.split(" ") if token}


def _contains_any_keyword(normalized: str, keywords: frozenset[str]) -> bool:
    return bool(_normalized_keywords(normalized) & keywords)


def _contains_any_fragment(raw: str, fragments: tuple[str, ...]) -> bool:
    lowered = str(raw or "").lower()
    return any(fragment.lower() in lowered for fragment in fragments)


def _has_weather_signal(raw: str, normalized: str) -> bool:
    return _contains_any_keyword(normalized, _WEATHER_KEYWORDS) or _contains_any_fragment(
        raw, _WEATHER_FRAGMENTS
    )


def _looks_like_weather_followup(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized or raw.startswith("/"):
        return False
    if len(normalized) > 96:
        return False
    return _has_weather_signal(raw, normalized)


def _looks_like_weather_metric_interpretation_followup(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized or raw.startswith("/"):
        return False
    if len(normalized) > 120:
        return False
    if not _has_weather_signal(raw, normalized):
        return False
    if not _WEATHER_METRIC_VALUE_RE.search(raw):
        return False
    if extract_weather_location(raw):
        return False
    if "?" in raw:
        return True
    return bool(_WEATHER_METRIC_QUERY_RE.search(normalized))


def _looks_like_weather_commentary_followup(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized or raw.startswith("/"):
        return False
    if len(normalized) > 140:
        return False
    if _WEATHER_METRIC_VALUE_RE.search(raw) or "?" in raw:
        return False
    if _contains_any_keyword(normalized, _WEATHER_FRESH_QUERY_KEYWORDS):
        return False
    if not _contains_any_keyword(normalized, _WEATHER_TEMPERATURE_FEEL_KEYWORDS):
        return False
    has_commentary_marker = bool(
        _contains_any_keyword(normalized, _WEATHER_COMMENTARY_KEYWORDS)
        or normalized.startswith(("pretty ", "quite "))
    )
    has_weather_anchor = bool(
        _has_weather_signal(raw, normalized)
        or extract_weather_location(raw)
    )
    return bool(has_commentary_marker or has_weather_anchor)


def _looks_like_weather_source_followup(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized or raw.startswith("/"):
        return False
    if len(normalized) > 140 or _WEATHER_METRIC_VALUE_RE.search(raw):
        return False
    has_source_marker = bool(_WEATHER_SOURCE_REQUEST_RE.search(normalized))
    has_provider_marker = bool(
        _WEATHER_PROVIDER_DOMAIN_RE.search(raw)
        or _WEATHER_PROVIDER_DOMAIN_RE.search(normalized)
        or _DOMAIN_LIKE_RE.fullmatch(raw)
    )
    if not has_source_marker and not has_provider_marker:
        return False
    if extract_weather_location(raw):
        return False
    return True


def _looks_like_quote_conversion_followup(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized or not _IDR_CONVERSION_RE.search(normalized):
        return False
    if len(normalized.split()) <= 8 and len(normalized) <= 96:
        return True
    return bool(
        _CURRENCY_RE.search(normalized)
        or "roughly in" in normalized
    )


def _looks_like_stock_trend_followup(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized or raw.startswith("/") or len(normalized) > 120:
        return False
    return bool(_STOCK_TREND_RE.search(normalized))


def _resolve_context_source(
    *,
    context_tool: str,
    last_tool_context: dict[str, Any],
    pending_followup_source: str,
) -> str:
    if context_tool == "weather":
        return str(
            last_tool_context.get("location")
            or last_tool_context.get("source")
            or pending_followup_source
            or ""
        ).strip()
    if context_tool == "stock":
        return str(
            last_tool_context.get("symbol")
            or last_tool_context.get("source")
            or last_tool_context.get("location")
            or pending_followup_source
            or ""
        ).strip()
    return str(
        last_tool_context.get("source")
        or last_tool_context.get("symbol")
        or last_tool_context.get("location")
        or pending_followup_source
        or ""
    ).strip()


def arbitrate_contextual_followup(
    text: str,
    *,
    parser_tool: str | None,
    pending_followup_tool: str | None = None,
    pending_followup_source: str = "",
    last_tool_context: dict[str, Any] | None = None,
) -> ContextualFollowupHint:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return ContextualFollowupHint()

    context = last_tool_context if isinstance(last_tool_context, dict) else {}
    context_tool = str(context.get("tool") or pending_followup_tool or "").strip().lower()
    context_source = _resolve_context_source(
        context_tool=context_tool,
        last_tool_context=context,
        pending_followup_source=pending_followup_source,
    )

    if _looks_like_stock_trend_followup(raw) and context_tool == "stock":
        base_source = str(
            pending_followup_source
            or context.get("source")
            or context.get("symbol")
            or ""
        ).strip()
        if base_source:
            return ContextualFollowupHint(
                kind="stock_context_followup",
                required_tool="stock_analysis",
                required_tool_query=f"{base_source} {raw}".strip(),
                reason="stock_context_followup",
            )

    if context_tool == "weather" and _looks_like_weather_commentary_followup(raw):
        return ContextualFollowupHint(
            kind="weather_commentary",
            reason="weather_commentary_followup",
        )

    if context_tool == "weather" and _looks_like_weather_source_followup(raw):
        return ContextualFollowupHint(
            kind="weather_source_followup",
            reason="weather_source_followup",
        )

    if context_tool == "weather" and context_source and _looks_like_weather_followup(raw):
        if _looks_like_weather_metric_interpretation_followup(raw):
            return ContextualFollowupHint(
                kind="weather_metric_interpretation",
                reason="weather_metric_interpretation",
            )
        return ContextualFollowupHint(
            kind="weather_followup",
            required_tool="weather",
            required_tool_query=f"{context_source} {raw}".strip(),
            reason="weather_context_followup",
        )

    if context_tool == "stock" and context_source and _looks_like_quote_conversion_followup(raw):
        return ContextualFollowupHint(
            kind="stock_quote_followup",
            required_tool="stock",
            required_tool_query=f"{context_source} {raw}".strip(),
            reason="stock_quote_followup",
        )

    if parser_tool in {"check_update", "system_update"} and context_tool == "weather" and context_source:
        if _looks_like_weather_followup(raw):
            return ContextualFollowupHint(
                kind="weather_update_conflict",
                required_tool="weather",
                required_tool_query=f"{context_source} {raw}".strip(),
                reason="weather_context_beats_update_keyword",
            )

    return ContextualFollowupHint()
