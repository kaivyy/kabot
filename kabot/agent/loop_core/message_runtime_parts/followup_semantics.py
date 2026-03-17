from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger
from kabot.agent.semantic_llm import call_semantic_llm_with_fallback

from kabot.agent.loop_core.message_runtime_parts.helpers import _is_low_information_turn

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)

_FOLLOWUP_INTENTS = {
    "assistant_offer_accept",
    "assistant_committed_action_followup",
    "answer_reference",
    "option_selection",
    "file_context",
    "directory_context",
    "delivery_request",
    "weather_context",
    "contextual_followup",
    "none",
}


def _normalize_followup_intent(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in _FOLLOWUP_INTENTS:
        return normalized
    return "none"


def _parse_followup_intent_response(raw_response: Any) -> str:
    raw = _JSON_FENCE_RE.sub("", str(raw_response or "").strip()).strip()
    if not raw:
        return "none"
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        return _normalize_followup_intent(
            parsed.get("followup_intent") or parsed.get("turn_intent") or parsed.get("intent")
        )
    match = re.search(
        r"\b("
        r"assistant_offer_accept|assistant_committed_action_followup|answer_reference|"
        r"option_selection|file_context|directory_context|delivery_request|"
        r"weather_context|contextual_followup|none"
        r")\b",
        raw,
        re.IGNORECASE,
    )
    return _normalize_followup_intent(match.group(1) if match else "")


async def classify_stateful_followup_intent(
    loop: Any,
    text: str,
    *,
    route_profile: str,
    turn_category: str,
    pending_followup_kind: str = "",
    pending_followup_text: str = "",
    pending_followup_request_text: str = "",
    pending_followup_tool: str = "",
    pending_followup_source: str = "",
    last_tool_context: dict[str, Any] | None = None,
    last_tool_execution: dict[str, Any] | None = None,
    recent_assistant_answer: str = "",
    recent_history_file_path: str = "",
    current_workflow_kind: str = "",
    current_workflow_stage: str = "",
    current_workflow_request_text: str = "",
) -> str:
    raw = str(text or "").strip()
    if not raw or raw.startswith("/"):
        return "none"

    last_tool_name = str((last_tool_context or {}).get("tool") or "").strip()
    last_tool_path = str((last_tool_context or {}).get("path") or "").strip()
    last_execution_tool = str((last_tool_execution or {}).get("tool") or "").strip()
    last_execution_source = str((last_tool_execution or {}).get("source") or "").strip()
    has_anchor = any(
        [
            str(pending_followup_kind or "").strip(),
            str(pending_followup_text or "").strip(),
            str(pending_followup_request_text or "").strip(),
            str(pending_followup_tool or "").strip(),
            str(pending_followup_source or "").strip(),
            last_tool_name,
            last_tool_path,
            last_execution_tool,
            last_execution_source,
            str(recent_assistant_answer or "").strip(),
            str(recent_history_file_path or "").strip(),
            str(current_workflow_kind or "").strip(),
            str(current_workflow_stage or "").strip(),
            str(current_workflow_request_text or "").strip(),
        ]
    )
    if not has_anchor:
        return "none"

    if not _is_low_information_turn(raw, max_tokens=18, max_chars=220):
        if len(raw) > 420 or len([token for token in raw.split() if token]) > 32:
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

    prompt = f"""Classify whether the user's turn is continuing existing context.

Return ONLY one JSON object:
{{"followup_intent":"assistant_offer_accept|assistant_committed_action_followup|answer_reference|option_selection|file_context|directory_context|delivery_request|weather_context|contextual_followup|none"}}

Use semantics, not keyword spotting.

Labels:
- assistant_offer_accept: the user is accepting or continuing a pending assistant offer.
- assistant_committed_action_followup: the user is asking you to proceed with a previously committed action or is giving a small missing detail for it.
- answer_reference: the user is referring to the assistant's recent answer and wants that answer continued, clarified, simplified, expanded, or interpreted.
- option_selection: the user is selecting or asking about one option from a recent assistant-provided option list.
- file_context: the user is referring to the current file/page/artifact context and expects follow-up inspection or continuation on that same file.
- directory_context: the user is continuing directory/folder navigation or asking about contents relative to the active directory context.
- delivery_request: the user is asking to send/share/attach the active file/artifact context to the current destination.
- weather_context: the user is asking a follow-up about the same weather/location context.
- contextual_followup: the user is continuing the same active context, but none of the more specific labels fit.
- none: this is mainly a fresh request or there is not enough evidence of continuation.

Route profile: {str(route_profile or '').strip().upper() or 'GENERAL'}
Turn category: {str(turn_category or '').strip().lower() or 'chat'}
Pending follow-up kind: {str(pending_followup_kind or '').strip().lower() or 'none'}
Pending follow-up text:
\"\"\"{str(pending_followup_text or '')[:900]}\"\"\"
Pending follow-up request text:
\"\"\"{str(pending_followup_request_text or '')[:900]}\"\"\"
Pending follow-up tool: {str(pending_followup_tool or '').strip().lower() or 'none'}
Pending follow-up source:
\"\"\"{str(pending_followup_source or '')[:900]}\"\"\"
Last tool name: {last_tool_name or 'none'}
Last tool path: {last_tool_path or 'none'}
Last execution tool: {last_execution_tool or 'none'}
Last execution source: {last_execution_source or 'none'}
Recent history file path: {str(recent_history_file_path or '').strip() or 'none'}
Current workflow kind: {str(current_workflow_kind or '').strip().lower() or 'none'}
Current workflow stage: {str(current_workflow_stage or '').strip().lower() or 'none'}
Current workflow request:
\"\"\"{str(current_workflow_request_text or '')[:900]}\"\"\"
Recent assistant answer excerpt:
\"\"\"{str(recent_assistant_answer or '')[:1200]}\"\"\"
User message:
\"\"\"{raw[:1200]}\"\"\""""

    response = await call_semantic_llm_with_fallback(
        loop=loop,
        provider=provider,
        messages=[{"role": "user", "content": prompt}],
        primary_model=model,
        max_tokens=120,
        temperature=0.0,
    )
    if response is None:
        logger.debug("Stateful follow-up semantic classification failed across fallback chain")
        return "none"

    return _parse_followup_intent_response(getattr(response, "content", ""))


__all__ = ["classify_stateful_followup_intent"]
