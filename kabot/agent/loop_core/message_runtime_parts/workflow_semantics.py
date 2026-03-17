from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger
from kabot.agent.semantic_llm import call_semantic_llm_with_fallback

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _normalize_workflow_intent(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"skill_creator", "skill_installer", "none"}:
        return normalized
    return "none"


def _parse_workflow_intent_response(raw_response: Any) -> str:
    raw = _JSON_FENCE_RE.sub("", str(raw_response or "").strip()).strip()
    if not raw:
        return "none"
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        return _normalize_workflow_intent(
            parsed.get("workflow_intent") or parsed.get("workflow") or parsed.get("intent")
        )
    match = re.search(r"\b(skill_creator|skill_installer|none)\b", raw, re.IGNORECASE)
    return _normalize_workflow_intent(match.group(1) if match else "")


def _workflow_skills_available(skills_loader: Any) -> set[str]:
    list_skills = getattr(skills_loader, "list_skills", None)
    if not callable(list_skills):
        return set()
    available: set[str] = set()
    try:
        skills = list_skills(filter_unavailable=False) or []
    except Exception:
        return set()
    for detail in skills:
        if not isinstance(detail, dict):
            continue
        if not bool(detail.get("eligible")):
            continue
        if bool(detail.get("disable_model_invocation")):
            continue
        if not bool(detail.get("user_invocable", True)):
            continue
        name = str(detail.get("name") or "").strip().lower()
        if name in {"skill-creator", "skill-installer"}:
            available.add(name)
    return available


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


async def classify_skill_workflow_intent(
    loop: Any,
    text: str,
    *,
    route_profile: str,
    turn_category: str,
    skills_loader: Any = None,
    conversation_history: list[dict[str, Any]] | None = None,
    current_workflow_request_text: str = "",
    current_workflow_stage: str = "",
    current_workflow_kind: str = "",
) -> str:
    raw = str(text or "").strip()
    if not raw or raw.startswith("/"):
        return "none"

    available_workflow_skills = _workflow_skills_available(skills_loader)
    if not available_workflow_skills:
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
    history_excerpt = _format_recent_history_excerpt(conversation_history)

    prompt = f"""Classify the user's primary workflow intent.

Return ONLY one JSON object:
{{"workflow_intent":"skill_creator|skill_installer|none"}}

Use semantics, not keyword spotting.

Choose skill_creator when the user is mainly asking to create or update a reusable skill/capability/workflow, especially if they provide API docs, endpoints, JSON examples, schemas, or trigger/output requirements.
Choose skill_installer when the user is mainly asking to install, list, update, or sync external skills.
Choose none otherwise.

Current active workflow kind: {str(current_workflow_kind or '').strip().lower() or 'none'}
Current active workflow stage: {str(current_workflow_stage or '').strip().lower() or 'none'}
Current active workflow request:
\"\"\"{str(current_workflow_request_text or '')[:900]}\"\"\"
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
        logger.debug("Semantic skill workflow classification failed across fallback chain")
        return "none"

    intent = _parse_workflow_intent_response(getattr(response, "content", ""))
    if intent == "skill_creator" and "skill-creator" not in available_workflow_skills:
        return "none"
    if intent == "skill_installer" and "skill-installer" not in available_workflow_skills:
        return "none"
    return intent


__all__ = [
    "classify_skill_workflow_intent",
]
