from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from kabot.agent.semantic_llm import call_semantic_llm_with_fallback
from kabot.agent.loop_core.message_runtime_parts.helpers import _is_low_information_turn

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _normalize_language_intent(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"language_switch", "none"}:
        return normalized
    return "none"


def _parse_language_intent_response(raw_response: Any) -> str:
    raw = _JSON_FENCE_RE.sub("", str(raw_response or "").strip()).strip()
    if not raw:
        return "none"
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        return _normalize_language_intent(
            parsed.get("language_intent") or parsed.get("intent") or parsed.get("kind")
        )
    match = re.search(r"\b(language_switch|none)\b", raw, re.IGNORECASE)
    return _normalize_language_intent(match.group(1) if match else "")


async def classify_language_followup_intent(
    loop: Any,
    text: str,
    *,
    context_label: str = "",
) -> str:
    raw = str(text or "").strip()
    if not raw or raw.startswith("/"):
        return "none"
    if not _is_low_information_turn(raw, max_tokens=12, max_chars=160):
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

    prompt = f"""Classify whether the user's short follow-up is mainly asking to change reply language.

Return ONLY one JSON object:
{{"language_intent":"language_switch|none"}}

Use semantics, not keyword spotting.

Choose language_switch only when the user is primarily asking for the same answer/context in a different language.
Choose none for ordinary content follow-ups or new topic requests.

Follow-up context label: {str(context_label or '').strip() or 'none'}
User message:
\"\"\"{raw[:1200]}\"\"\""""

    response = await call_semantic_llm_with_fallback(
        loop=loop,
        provider=provider,
        messages=[{"role": "user", "content": prompt}],
        primary_model=model,
        max_tokens=50,
        temperature=0.0,
    )
    if response is None:
        logger.debug("Language follow-up semantic classification failed across fallback chain")
        return "none"
    return _parse_language_intent_response(getattr(response, "content", ""))


__all__ = ["classify_language_followup_intent"]

