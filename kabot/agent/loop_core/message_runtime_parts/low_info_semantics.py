from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from kabot.agent.loop_core.message_runtime_parts.helpers import _is_low_information_turn
from kabot.agent.semantic_llm import call_semantic_llm_with_fallback

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _normalize_turn_intent(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"closing_ack", "greeting_smalltalk", "meta_feedback", "none"}:
        return normalized
    return "none"


def _parse_turn_intent_response(raw_response: Any) -> str:
    raw = _JSON_FENCE_RE.sub("", str(raw_response or "").strip()).strip()
    if not raw:
        return "none"
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        return _normalize_turn_intent(
            parsed.get("turn_intent") or parsed.get("intent") or parsed.get("kind")
        )
    match = re.search(r"\b(closing_ack|greeting_smalltalk|meta_feedback|none)\b", raw, re.IGNORECASE)
    return _normalize_turn_intent(match.group(1) if match else "")


async def classify_low_information_turn_intent(
    loop: Any,
    text: str,
    *,
    route_profile: str,
    turn_category: str,
) -> str:
    raw = str(text or "").strip()
    if not raw or raw.startswith("/"):
        return "none"
    if not _is_low_information_turn(raw, max_tokens=10, max_chars=120):
        return "none"
    if str(turn_category or "").strip().lower() not in {"chat", "contextual_action", "action"}:
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

    prompt = f"""Classify this short user turn.

Return ONLY one JSON object:
{{"turn_intent":"closing_ack|greeting_smalltalk|meta_feedback|none"}}

Use semantics, not keyword spotting.

- closing_ack: short gratitude, closure, or polite wrap-up with no new task.
- greeting_smalltalk: short greeting/opening with no task.
- meta_feedback: short reaction about the assistant's prior answer, but still not a new task.
- none: anything else.

Understand the user's actual language.

Route profile: {str(route_profile or '').strip().upper() or 'GENERAL'}
Turn category: {str(turn_category or '').strip().lower() or 'chat'}
User message:
\"\"\"{raw[:600]}\"\"\""""

    response = await call_semantic_llm_with_fallback(
        loop=loop,
        provider=provider,
        messages=[{"role": "user", "content": prompt}],
        primary_model=model,
        max_tokens=80,
        temperature=0.0,
    )
    if response is None:
        logger.debug("Low-info turn semantic classification failed across fallback chain")
        return "none"

    return _parse_turn_intent_response(getattr(response, "content", ""))


__all__ = ["classify_low_information_turn_intent"]
