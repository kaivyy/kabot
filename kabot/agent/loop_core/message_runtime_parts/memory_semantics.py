from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from kabot.agent.semantic_llm import call_semantic_llm_with_fallback

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _normalize_memory_intent(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"memory_recall", "memory_commit", "none"}:
        return normalized
    return "none"


def _parse_memory_intent_response(raw_response: Any) -> str:
    raw = _JSON_FENCE_RE.sub("", str(raw_response or "").strip()).strip()
    if not raw:
        return "none"
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        return _normalize_memory_intent(
            parsed.get("memory_intent") or parsed.get("intent") or parsed.get("kind")
        )
    match = re.search(r"\b(memory_recall|memory_commit|none)\b", raw, re.IGNORECASE)
    return _normalize_memory_intent(match.group(1) if match else "")


def _format_recent_history_excerpt(conversation_history: list[dict[str, Any]] | None) -> str:
    if not isinstance(conversation_history, list):
        return ""
    excerpt_lines: list[str] = []
    for item in conversation_history[-6:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if not role or not content:
            continue
        excerpt_lines.append(f"{role}: {content[:280]}")
    return "\n".join(excerpt_lines).strip()


async def classify_semantic_memory_intent(
    loop: Any,
    text: str,
    *,
    route_profile: str,
    turn_category: str,
    conversation_history: list[dict[str, Any]] | None = None,
    user_profile: dict[str, Any] | None = None,
) -> str:
    raw = str(text or "").strip()
    if not raw or raw.startswith("/"):
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

    profile_summary = ""
    if isinstance(user_profile, dict) and user_profile:
        summary_parts = [
            f"{key}={value}"
            for key, value in list(user_profile.items())[:6]
            if str(value or "").strip()
        ]
        profile_summary = ", ".join(summary_parts)

    history_excerpt = _format_recent_history_excerpt(conversation_history)
    prompt = f"""Classify the user's memory intent.

Return ONLY one JSON object:
{{"memory_intent":"memory_recall|memory_commit|none"}}

Use semantics, not keyword spotting.

Choose memory_recall when the user is asking you to recall something previously stored, remembered, decided, agreed, or learned about the user, project, or conversation.
Choose memory_commit when the user is asking you to store or remember current information for future use.
Choose none otherwise.

Route profile: {str(route_profile or '').strip().upper() or 'GENERAL'}
Turn category: {str(turn_category or '').strip().lower() or 'chat'}
Known user profile summary: {profile_summary or 'none'}
Recent conversation excerpt:
\"\"\"{history_excerpt[:1600]}\"\"\"

User message:
\"\"\"{raw[:2400]}\"\"\""""

    response = await call_semantic_llm_with_fallback(
        loop=loop,
        provider=provider,
        messages=[{"role": "user", "content": prompt}],
        primary_model=model,
        max_tokens=80,
        temperature=0.0,
    )
    if response is None:
        logger.debug("Semantic memory intent classification failed across fallback chain")
        return "none"
    return _parse_memory_intent_response(getattr(response, "content", ""))


__all__ = ["classify_semantic_memory_intent"]
