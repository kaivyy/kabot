from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from kabot.agent.semantic_llm import call_semantic_llm_with_fallback
from kabot.agent.loop_core.message_runtime_parts.helpers import _is_low_information_turn

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)

_TEMPORAL_INTENTS = {
    "day_today",
    "day_tomorrow",
    "day_yesterday",
    "day_next_week",
    "time_now",
    "date_today",
    "timezone",
    "none",
}


def _normalize_temporal_intent(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in _TEMPORAL_INTENTS:
        return normalized
    return "none"


def _parse_temporal_intent_response(raw_response: Any) -> str:
    raw = _JSON_FENCE_RE.sub("", str(raw_response or "").strip()).strip()
    if not raw:
        return "none"
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        return _normalize_temporal_intent(
            parsed.get("temporal_intent") or parsed.get("intent") or parsed.get("kind")
        )
    match = re.search(
        r"\b(day_today|day_tomorrow|day_yesterday|day_next_week|time_now|date_today|timezone|none)\b",
        raw,
        re.IGNORECASE,
    )
    return _normalize_temporal_intent(match.group(1) if match else "")


async def classify_temporal_fast_intent(
    loop: Any,
    text: str,
    *,
    locale_hint: str = "",
) -> str:
    raw = str(text or "").strip()
    if not raw or raw.startswith("/"):
        return "none"
    if not _is_low_information_turn(raw, max_tokens=14, max_chars=180):
        return "none"

    provider = getattr(loop, "provider", None)
    chat = getattr(provider, "chat", None)
    if not callable(chat):
        return "none"

    model = (
        str(getattr(getattr(loop, "router", None), "model", "") or "").strip()
        or str(getattr(loop, "model", "") or "").strip()
    )
    if not model and hasattr(provider, "get_default_model"):
        try:
            model = str(provider.get_default_model() or "").strip()
        except Exception:
            model = ""

    prompt = f"""Classify whether this user turn is a narrow temporal/day-time query.

Return ONLY one JSON object:
{{"temporal_intent":"day_today|day_tomorrow|day_yesterday|day_next_week|time_now|date_today|timezone|none"}}

Use semantics, not keyword spotting.

Labels:
- day_today: asks what day it is now.
- day_tomorrow: asks what day tomorrow is.
- day_yesterday: asks what day yesterday was.
- day_next_week: asks what day it will be in one week / next-week day relation.
- time_now: asks current local time.
- date_today: asks current local date.
- timezone: asks current local timezone or UTC offset.
- none: not a narrow temporal query.

Locale hint: {str(locale_hint or '').strip().lower() or 'none'}
User message:
\"\"\"{raw[:1200]}\"\"\""""

    response = await call_semantic_llm_with_fallback(
        loop=loop,
        provider=provider,
        messages=[{"role": "user", "content": prompt}],
        primary_model=model,
        max_tokens=80,
        temperature=0.0,
    )
    if response is None:
        logger.debug("Temporal semantic classification failed across fallback chain")
        return "none"
    return _parse_temporal_intent_response(getattr(response, "content", ""))


__all__ = ["classify_temporal_fast_intent"]

