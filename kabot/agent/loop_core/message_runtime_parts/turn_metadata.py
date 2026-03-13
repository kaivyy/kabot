"""Final turn metadata assembly extracted from process_flow."""

from __future__ import annotations

from typing import Any

from kabot.agent.loop_core.message_runtime_parts.helpers import (
    _channel_uses_mutable_status_lane,
    _is_short_context_followup,
    _looks_like_message_delivery_request,
    _looks_like_short_confirmation,
    _resolve_runtime_locale,
)
from kabot.agent.loop_core.message_runtime_parts.turn_helpers import (
    _resolve_turn_category,
)


def _finalize_turn_metadata(state: Any) -> None:
    state.runtime_locale = _resolve_runtime_locale(
        state.session,
        state.msg,
        state.effective_content,
    )
    state.observed_turn_category = _resolve_turn_category(
        decision=state.decision,
        continuity_source=str(state.continuity_source or ""),
        required_tool=str(state.required_tool or ""),
        is_short_confirmation=bool(state.is_short_confirmation),
        is_contextual_followup_request=bool(state.is_contextual_followup_request),
        is_answer_reference_followup=bool(state.is_answer_reference_followup),
        pending_followup_intent_kind=str(state.pending_followup_intent_kind or ""),
        skill_creation_intent=bool(state.skill_creation_intent),
        skill_install_intent=bool(state.skill_install_intent),
    )
    layered_context_sources: list[str] = []
    if state.conversation_history:
        layered_context_sources.append("recent_history")
    if state.recent_answer_target or state.continuity_source == "answer_reference":
        layered_context_sources.append("recent_answer_reference")
    elif state.continuity_source == "tool_execution" or state.last_tool_execution:
        layered_context_sources.append("recent_tool_execution")
    if (
        state.continuity_source in {"committed_action", "committed_coding_action"}
        or state.pending_followup_intent_kind == "assistant_committed_action"
    ):
        layered_context_sources.append("pending_committed_action")
    if state.relevant_memory_facts:
        layered_context_sources.append("memory_facts")
    if state.learned_execution_hints:
        layered_context_sources.append("learned_hints")
    state.layered_context_sources = layered_context_sources

    if isinstance(state.msg.metadata, dict):
        state.msg.metadata["route_profile"] = state.decision.profile
        state.msg.metadata["turn_category"] = state.observed_turn_category
        session_metadata = getattr(state.session, "metadata", None)
        if isinstance(session_metadata, dict):
            session_metadata["last_turn_category"] = state.observed_turn_category
        state.msg.metadata["layered_context_sources"] = list(layered_context_sources)
        state.msg.metadata["requires_message_delivery"] = bool(
            _looks_like_message_delivery_request(state.intent_source_for_followup)
            or _looks_like_message_delivery_request(state.effective_content)
            or state.continuity_source in {"committed_action", "committed_coding_action"}
            and _looks_like_message_delivery_request(state.committed_action_request_text)
        )
        state.msg.metadata["runtime_locale"] = state.runtime_locale
        state.msg.metadata["effective_content"] = state.effective_content
        if state.forced_skill_names:
            state.msg.metadata["forced_skill_names"] = list(state.forced_skill_names)
        else:
            state.msg.metadata.pop("forced_skill_names", None)
        state.msg.metadata["external_skill_lane"] = bool(
            getattr(state, "external_skill_lane", False)
        )
        if state.last_tool_context:
            state.msg.metadata["last_tool_context"] = state.last_tool_context
        else:
            state.msg.metadata.pop("last_tool_context", None)
        if state.last_tool_execution:
            state.msg.metadata["last_tool_execution"] = state.last_tool_execution
        else:
            state.msg.metadata.pop("last_tool_execution", None)
        if state.explicit_file_analysis_note and state.file_analysis_path:
            state.msg.metadata["file_analysis_mode"] = True
            state.msg.metadata["file_analysis_path"] = state.file_analysis_path
        else:
            state.msg.metadata.pop("file_analysis_mode", None)
            state.msg.metadata.pop("file_analysis_path", None)
        if state.mcp_context_note:
            state.msg.metadata["mcp_context_mode"] = True
        else:
            state.msg.metadata.pop("mcp_context_mode", None)
        if state.semantic_hint.kind != "none":
            state.msg.metadata["semantic_intent_hint"] = state.semantic_hint.kind
        else:
            state.msg.metadata.pop("semantic_intent_hint", None)
        if state.continuity_source:
            state.msg.metadata["continuity_source"] = state.continuity_source
        else:
            state.msg.metadata.pop("continuity_source", None)
        state.msg.metadata["suppress_required_tool_inference"] = bool(
            state.semantic_hint.kind
            in {"advice_turn", "meta_feedback", "weather_metric_interpretation"}
            or state.meta_skill_reference_turn
            or state.skill_creation_intent
            or state.skill_install_intent
            or bool(state.forced_skill_names)
            or bool(state.mcp_context_note)
            or state.continuity_source in {"committed_action", "action_request"}
        )
        if state.required_tool:
            state.msg.metadata["required_tool"] = state.required_tool
            state.msg.metadata["required_tool_query"] = str(
                state.required_tool_query or state.effective_content
            ).strip()
        else:
            state.msg.metadata.pop("required_tool", None)
            state.msg.metadata.pop("required_tool_query", None)
        state.msg.metadata["skip_critic_for_speed"] = bool(
            state.required_tool
            or _is_short_context_followup(state.msg.content)
            or _is_short_context_followup(state.effective_content)
            or _looks_like_short_confirmation(state.msg.content)
            or _looks_like_short_confirmation(state.effective_content)
        )
        state.msg.metadata["status_mutable_lane"] = bool(
            _channel_uses_mutable_status_lane(state.loop, state.msg.channel)
        )
        if state.skill_creation_intent or state.skill_install_intent:
            state.msg.metadata["skill_creation_guard"] = {
                "active": True,
                "stage": state.skill_creation_stage,
                "approved": state.skill_creation_approved,
                "kind": state.skill_workflow_kind,
                "request_text": state.skill_creation_request_text,
            }
        else:
            state.msg.metadata.pop("skill_creation_guard", None)

    state.observed_continuity_source = state.continuity_source or "none"
