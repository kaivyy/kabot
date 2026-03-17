"""Extracted turn helper logic for process_flow."""

from __future__ import annotations

from typing import Any

from kabot.agent.loop_core.message_runtime_parts.helpers import (
    _is_low_information_turn,
    _normalize_text,
    _tool_registry_has,
)
from kabot.agent.loop_core.tool_enforcement import required_tool_for_query_for_loop

_BRIEF_ANSWER_REQUEST_MARKERS = (
    "singkat",
    "pendek",
    "short",
    "brief",
    "one line",
    "one sentence",
    "satu baris",
    "satu kalimat",
    "简短",
    "短一点",
    "一行",
    "短く",
    "一文",
    "ตอบสั้น",
    "สั้นๆ",
)

_MEANING_FOLLOWUP_MARKERS = (
    "maksudnya",
    "what does that mean",
    "what does it mean",
    "what do you mean",
    "这是什么意思",
    "這是什麼意思",
    "什么意思",
    "什麼意思",
    "どういう意味",
    "それどういう意味",
    "หมายความว่าไง",
    "หมายความว่าอะไร",
)


def _looks_like_brief_answer_request(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    return any(marker in normalized for marker in _BRIEF_ANSWER_REQUEST_MARKERS)


def _select_answer_reference_target(
    answer_text: str,
    referenced_item: str | None,
) -> str | None:
    exact_item = str(referenced_item or "").strip()
    if exact_item:
        return exact_item

    raw_answer = str(answer_text or "").strip()
    if not raw_answer:
        return None

    lines = [line.strip() for line in raw_answer.splitlines() if line.strip()]
    if len(lines) <= 6 and len(raw_answer) <= 280:
        return raw_answer
    return None


def _looks_like_meaning_followup(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    return any(marker in normalized for marker in _MEANING_FOLLOWUP_MARKERS)


def _format_grounded_target_reply(target: str, *, locale: str, meaning: bool) -> str:
    normalized_locale = str(locale or "").strip().lower()
    target_text = str(target or "").strip()
    if not target_text:
        return ""
    if not meaning:
        return target_text
    if normalized_locale == "ja":
        return f"「{target_text}」という文字列です。"
    if normalized_locale == "zh":
        return f"指的是「{target_text}」。"
    if normalized_locale == "th":
        return f"หมายถึง \"{target_text}\""
    if normalized_locale == "id":
        return f"Maksudnya \"{target_text}\"."
    return f"It refers to \"{target_text}\"."


def _build_answer_reference_fast_reply(
    followup_text: str,
    *,
    locale: str,
    answer_target: str | None,
    option_selection_reference: str | None,
    referenced_item: str | None,
) -> str | None:
    target_text = str(answer_target or "").strip()
    if not target_text:
        return None

    if option_selection_reference and str(referenced_item or "").strip():
        return _format_grounded_target_reply(target_text, locale=locale, meaning=False)

    if _looks_like_meaning_followup(followup_text) and len(target_text) <= 160:
        return _format_grounded_target_reply(target_text, locale=locale, meaning=True)

    return None


def _resolve_turn_category(
    *,
    decision: Any,
    continuity_source: str,
    required_tool: str,
    is_short_confirmation: bool,
    is_contextual_followup_request: bool,
    is_answer_reference_followup: bool,
    pending_followup_intent_kind: str,
    skill_creation_intent: bool,
    skill_install_intent: bool,
) -> str:
    continuity = str(continuity_source or "").strip().lower()
    required = str(required_tool or "").strip()
    router_category = str(getattr(decision, "turn_category", "") or "").strip().lower()
    route_profile = str(getattr(decision, "profile", "") or "").strip().upper()
    complex_route = bool(getattr(decision, "is_complex", False))
    contextual_followup = bool(
        is_short_confirmation
        or is_contextual_followup_request
        or is_answer_reference_followup
    )

    if continuity in {"committed_action", "committed_coding_action"}:
        return "contextual_action"
    if continuity in {"action_request", "coding_request"}:
        if contextual_followup or pending_followup_intent_kind in {
            "assistant_offer",
            "assistant_committed_action",
        }:
            return "contextual_action"
        return "action"
    if pending_followup_intent_kind in {"assistant_offer", "assistant_committed_action"} and contextual_followup:
        return "contextual_action"
    if skill_creation_intent or skill_install_intent or required:
        return "action"
    if router_category in {"chat", "action", "contextual_action", "command"}:
        if router_category == "action" and contextual_followup:
            return "contextual_action"
        return router_category
    if route_profile in {"CODING", "RESEARCH"} or complex_route:
        return "contextual_action" if contextual_followup else "action"
    return "chat"


def _infer_required_tool_from_recent_user_intent(
    loop: Any,
    followup_text: str,
    conversation_history: list[dict[str, Any]] | None,
) -> tuple[str | None, str | None]:
    """Recover the most recent actionable user tool intent for a vague follow-up."""
    inferred_tool = None
    inferred_source = None
    infer_from_history = getattr(loop, "_infer_required_tool_from_history", None)
    if callable(infer_from_history):
        try:
            inferred_tool, inferred_source = infer_from_history(
                followup_text,
                conversation_history,
            )
        except Exception:
            inferred_tool, inferred_source = None, None
    else:
        normalized_followup = _normalize_text(followup_text)
        for item in reversed((conversation_history or [])[-8:]):
            role = str(item.get("role", "") or "").strip().lower()
            candidate = str(item.get("content", "") or "").strip()
            if not candidate:
                continue
            if role != "user":
                continue
            candidate_norm = _normalize_text(candidate)
            if not candidate_norm or candidate_norm == normalized_followup:
                continue
            if _is_low_information_turn(candidate, max_tokens=3, max_chars=24):
                continue
            inferred = _resolve_grounded_required_tool(loop, candidate)
            if inferred:
                inferred_tool = inferred
                inferred_source = candidate
                break
    return inferred_tool, inferred_source


def _resolve_grounded_required_tool(loop: Any, text: str) -> str | None:
    candidate = str(text or "").strip()
    if not candidate:
        return None
    try:
        return required_tool_for_query_for_loop(loop, candidate)
    except Exception:
        return None


def _extract_reusable_last_tool_execution(
    loop: Any,
    last_tool_execution: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    """Return a reusable execution tool/source pair when continuity can safely reuse it."""
    execution_tool = str((last_tool_execution or {}).get("tool") or "").strip()
    execution_source = str((last_tool_execution or {}).get("source") or "").strip()
    if not execution_tool or not execution_source:
        return None, None

    # Finance quote tools are high-risk for stale follow-up reuse (e.g. generic
    # "why?" turns accidentally re-trigger stock prompts). Require fresh
    # intent/payload instead of blindly inheriting prior execution context.
    if execution_tool in {"stock", "stock_analysis", "crypto"}:
        return None, None

    can_reuse_execution_tool = bool(
        execution_tool.startswith("mcp__")
        or _tool_registry_has(loop, execution_tool)
    )
    if not can_reuse_execution_tool:
        return None, None
    return execution_tool, execution_source
