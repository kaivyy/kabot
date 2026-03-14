from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from kabot.agent.cron_fallback_nlp import extract_weather_location

_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_META_FEEDBACK_RE = re.compile(
    r"(?i)\b("
    r"kok|kenapa|why|wrong|ngaco|aneh|lama|slow|bug|error|"
    r"bukan (?:itu|saham|stock|cuaca|weather|web\s*search|websearch|brows(?:e|ing))|"
    r"no web\s*search|not web\s*search|"
    r"koreksi (?:chat|percakapan)|correct(?:ing|ion)? (?:the )?(?:chat|conversation)|"
    r"stop bahas|jangan bahas|not about|that's not what i asked"
    r")\b"
)
_ADVICE_RE = re.compile(
    r"(?i)\b("
    r"saran(?:mu)?|advice|recommend(?:ation)?|recommend|bagus|bagusan|"
    r"which one|mana yang|apa ya|what should i use|should i use"
    r")\b"
)
_WEATHER_MARKER_RE = re.compile(
    r"(?i)\b("
    r"weather|cuaca|suhu|temperature|temperatur|forecast|angin|wind|"
    r"humid|kelembapan|rain|hujan|berawan|cloudy|sunny"
    r")\b|[風风]|ลม|天気|天气|อากาศ"
)
_WEATHER_METRIC_VALUE_RE = re.compile(
    r"(?i)\b\d+(?:[.,]\d+)?\s*(?:km/?h|kph|m/?s|mph|kt|kts|knots?)\b"
)
_WEATHER_METRIC_QUERY_RE = re.compile(
    r"(?i)\b("
    r"berapa|kenapa|gimana|bagaimana|maksudnya|artinya|normal|"
    r"how|what|why|is that|too fast|too slow|strong|weak"
    r")\b"
)
_IDR_CONVERSION_RE = re.compile(
    r"(?i)\b("
    r"idr|rupiah|dirupiahkan|rupiahkan|konversi|convert(?:ed|ion)?|"
    r"dirupiahkan|indonesian rupiah"
    r")\b"
)
_CURRENCY_RE = re.compile(r"(?i)\b(usd|dollar|idr|rupiah|yen|eur|euro|gbp)\b")
_STOCK_TREND_RE = re.compile(
    r"(?i)\b("
    r"trend(?:nya)?|naik|turun|bullish|bearish|support|resistance|"
    r"analisis|analysis|breakout|pullback|entry|exit|stop\s*loss|take\s*profit|tp|sl"
    r")\b"
)
_HR_ZONE_RE = re.compile(
    r"(?i)\b("
    r"hr|heart rate|detak jantung|zona hr|hr zona|hr zone|heart rate zone|"
    r"karvonen|max hr|hr max|resting hr"
    r")\b"
)
_HR_ZONE_ACTION_RE = re.compile(
    r"(?i)\b("
    r"hitung|calculate|calc|tolong|please|berapa|zona|zone|umur|usia|age"
    r")\b"
)
_MEMORY_RECALL_RE = re.compile(
    r"(?i)\b("
    r"what do you remember|what did you save|what do you know about me|"
    r"what was my preference code|what is my preference code|my preference code|"
    r"what was the code you just remembered|"
    r"who am i"
    r"|saved code|memory code"
    r")\b"
)
_MEMORY_COMMIT_RE = re.compile(
    r"(?i)\b("
    r"save to memory|save this to memory|save that to memory|save this memory|commit to memory|"
    r"save in memory|remember this|remember that"
    r")\b"
)


@dataclass(slots=True)
class SemanticIntentHint:
    kind: str = "none"
    required_tool: str | None = None
    required_tool_query: str | None = None
    clear_pending: bool = False
    reason: str = ""


def _normalize_text(text: str) -> str:
    raw = str(text or "").strip().lower()
    if not raw:
        return ""
    compact = _NON_WORD_RE.sub(" ", raw)
    return _SPACE_RE.sub(" ", compact).strip()


def _is_cjk_or_unspaced_substantive(raw: str) -> bool:
    if any(ch.isspace() for ch in raw):
        return False
    return bool(
        re.search(r"[\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF\u0E00-\u0E7F]", raw)
        and len(raw) >= 5
    )


def _is_low_information_turn(text: str, *, max_tokens: int, max_chars: int) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if raw.startswith("/"):
        return False
    if _is_cjk_or_unspaced_substantive(raw):
        return False
    if len(normalized) > max_chars:
        return False
    tokens = [token for token in normalized.split(" ") if token]
    return 0 < len(tokens) <= max_tokens


def _looks_like_meta_feedback(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if not _is_low_information_turn(raw, max_tokens=12, max_chars=96):
        return False
    return bool(_META_FEEDBACK_RE.search(normalized))


def _looks_like_advice_request(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if len(normalized) > 180:
        return False
    if not ("?" in raw or normalized.startswith(("apa ", "what ", "which ", "mana ", "should "))) and not _ADVICE_RE.search(normalized):
        return False
    return bool(_ADVICE_RE.search(normalized))


def _looks_like_weather_followup(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized or raw.startswith("/"):
        return False
    if len(normalized) > 96:
        return False
    return bool(_WEATHER_MARKER_RE.search(normalized))


def _looks_like_weather_metric_interpretation_followup(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized or raw.startswith("/"):
        return False
    if len(normalized) > 120:
        return False
    if not _WEATHER_MARKER_RE.search(normalized):
        return False
    if not _WEATHER_METRIC_VALUE_RE.search(raw):
        return False
    if extract_weather_location(raw):
        return False
    if "?" in raw:
        return True
    return bool(_WEATHER_METRIC_QUERY_RE.search(normalized))


def _looks_like_quote_conversion_followup(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if not _IDR_CONVERSION_RE.search(normalized):
        return False
    if _is_low_information_turn(raw, max_tokens=8, max_chars=96):
        return True
    return bool(
        _CURRENCY_RE.search(normalized)
        or "jadikan" in normalized
        or "roughly in" in normalized
        or "berapa kalau" in normalized
        or "ubah jadi" in normalized
    )


def _looks_like_stock_trend_followup(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if raw.startswith("/"):
        return False
    if len(normalized) > 120:
        return False
    return bool(_STOCK_TREND_RE.search(normalized))


def _looks_like_hr_zone_or_fitness_calculation(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if len(normalized) > 320 and "dari sini" not in normalized and "from this" not in normalized:
        return False
    return bool(_HR_ZONE_RE.search(normalized) and _HR_ZONE_ACTION_RE.search(normalized))


def _looks_like_memory_recall(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if len(normalized) > 240:
        return False
    if _MEMORY_COMMIT_RE.search(normalized) and not re.search(
        r"(?i)\b(who am i|what do you remember)\b",
        normalized,
    ):
        return False
    return bool(_MEMORY_RECALL_RE.search(raw) or _MEMORY_RECALL_RE.search(normalized))


def arbitrate_semantic_intent(
    text: str,
    *,
    parser_tool: str | None,
    pending_followup_tool: str | None = None,
    pending_followup_source: str = "",
    last_tool_context: dict[str, Any] | None = None,
    payload_checker: Callable[[str, str], bool] | None = None,
) -> SemanticIntentHint:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return SemanticIntentHint()

    payload_present = False
    if parser_tool and callable(payload_checker):
        try:
            payload_present = bool(payload_checker(parser_tool, raw))
        except Exception:
            payload_present = False

    if _looks_like_meta_feedback(raw) and not payload_present:
        return SemanticIntentHint(
            kind="meta_feedback",
            clear_pending=True,
            reason="meta_feedback_turn",
        )

    if parser_tool and _looks_like_memory_recall(raw) and not payload_present:
        return SemanticIntentHint(
            kind="memory_recall",
            reason="memory_recall_not_tool",
        )

    if parser_tool == "weather" and _looks_like_hr_zone_or_fitness_calculation(raw):
        return SemanticIntentHint(
            kind="advice_turn",
            reason="hr_zone_not_weather",
        )

    stock_context = last_tool_context if isinstance(last_tool_context, dict) else {}
    stock_tool_active = str((stock_context or {}).get("tool") or "").strip() == "stock"
    if (
        _looks_like_stock_trend_followup(raw)
        and (pending_followup_tool == "stock" or stock_tool_active)
    ):
        base_source = str(pending_followup_source or stock_context.get("source") or stock_context.get("symbol") or "").strip()
        if base_source:
            return SemanticIntentHint(
                kind="stock_context_followup",
                required_tool="stock_analysis",
                required_tool_query=f"{base_source} {raw}".strip(),
                reason="stock_context_followup",
            )

    if parser_tool and _looks_like_advice_request(raw):
        return SemanticIntentHint(
            kind="advice_turn",
            reason="advice_without_tool_payload",
        )

    context = last_tool_context if isinstance(last_tool_context, dict) else {}
    context_tool = str(context.get("tool") or pending_followup_tool or "").strip().lower()
    if context_tool == "weather":
        context_source = str(
            context.get("location")
            or context.get("source")
            or pending_followup_source
            or ""
        ).strip()
    elif context_tool == "stock":
        context_source = str(
            context.get("symbol")
            or context.get("source")
            or context.get("location")
            or pending_followup_source
            or ""
        ).strip()
    else:
        context_source = str(
            context.get("source")
            or context.get("symbol")
            or context.get("location")
            or pending_followup_source
            or ""
        ).strip()

    if context_tool == "weather" and context_source and _looks_like_weather_followup(raw):
        if _looks_like_weather_metric_interpretation_followup(raw):
            return SemanticIntentHint(
                kind="weather_metric_interpretation",
                reason="weather_metric_interpretation",
            )
        return SemanticIntentHint(
            kind="weather_followup",
            required_tool="weather",
            required_tool_query=f"{context_source} {raw}".strip(),
            reason="weather_context_followup",
        )

    if not parser_tool and _looks_like_weather_followup(raw):
        location = extract_weather_location(raw)
        if location:
            return SemanticIntentHint(
                kind="weather_query",
                required_tool="weather",
                required_tool_query=raw,
                reason="weather_question_with_location",
            )

    if context_tool == "stock" and context_source and _looks_like_quote_conversion_followup(raw):
        return SemanticIntentHint(
            kind="stock_quote_followup",
            required_tool="stock",
            required_tool_query=f"{context_source} {raw}".strip(),
            reason="stock_quote_followup",
        )

    if parser_tool in {"check_update", "system_update"} and context_tool == "weather" and context_source:
        if _looks_like_weather_followup(raw):
            return SemanticIntentHint(
                kind="weather_update_conflict",
                required_tool="weather",
                required_tool_query=f"{context_source} {raw}".strip(),
                reason="weather_context_beats_update_keyword",
            )

    return SemanticIntentHint()
