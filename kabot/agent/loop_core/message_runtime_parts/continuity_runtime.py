"""Continuity follow-up runtime helpers extracted from process_flow."""

from __future__ import annotations

from typing import Any

from loguru import logger

from kabot.agent.loop_core.message_runtime_parts.helpers import (
    _clear_pending_followup_intent,
    _clear_pending_followup_tool,
    _extract_option_selection_reference,
    _extract_referenced_answer_item,
    _looks_like_coding_build_request,
    _looks_like_side_effect_request,
    _normalize_text,
)
from kabot.agent.loop_core.message_runtime_parts.turn_helpers import (
    _infer_required_tool_from_recent_user_intent,
    _looks_like_brief_answer_request,
    _resolve_grounded_required_tool,
    _select_answer_reference_target,
)
from kabot.agent.loop_core.tool_enforcement import infer_action_required_tool_for_loop


def _apply_continuity_runtime(state: Any) -> None:
    """Mutate the provided turn state with answer-reference and follow-up context."""

    allow_explicit_path_hint_for_committed_delivery = bool(
        state.pending_followup_intent_kind == "assistant_committed_action"
        and state.required_tool == "list_dir"
    )
    recent_answer_context_candidate = bool(
        state.recent_assistant_answer
        and (
            state.raw_is_answer_reference_followup
            or state.raw_is_contextual_followup_request
        )
    )
    recent_answer_option_selection_reference = (
        _extract_option_selection_reference(state.effective_content)
        if recent_answer_context_candidate
        else None
    )
    state.recent_answer_option_selection_reference = recent_answer_option_selection_reference
    recent_answer_referenced_item = (
        _extract_referenced_answer_item(
            state.recent_assistant_answer,
            recent_answer_option_selection_reference,
        )
        if recent_answer_context_candidate and recent_answer_option_selection_reference
        else None
    )
    state.recent_answer_referenced_item = recent_answer_referenced_item
    state.recent_answer_target = (
        _select_answer_reference_target(
            state.recent_assistant_answer,
            recent_answer_referenced_item,
        )
        if recent_answer_context_candidate
        else None
    )
    if (
        not state.required_tool
        and not (
            state.pending_followup_intent
            and state.pending_followup_intent_kind in {
                "assistant_offer",
                "assistant_committed_action",
            }
        )
        and recent_answer_context_candidate
        and not state.is_closing_ack
        and not state.is_short_greeting
        and not state.is_non_action_feedback
        and not state.is_explicit_new_request
    ):
        brief_answer_requested = _looks_like_brief_answer_request(state.effective_content)
        sections = [state.effective_content]
        if state.recent_answer_target:
            grounded_note = (
                "The user's follow-up refers to the target above. Resolve words like "
                "'that', 'it', or 'what does it mean' against that target instead of "
                "explaining the literal wording of the user's follow-up itself."
            )
            if recent_answer_referenced_item:
                grounded_note += (
                    " Answer about that target item only, and do not repeat the whole list "
                    "or nearby sibling items."
                )
            else:
                grounded_note += (
                    " Explain or continue that target directly, and do not ask the user to "
                    "resend context."
                )
            if brief_answer_requested:
                grounded_note += " Keep the reply to one short sentence."
            sections.append(
                "[Answer Reference Target]\n"
                f"{state.recent_answer_target}\n\n"
                "[Grounded Answer Note]\n"
                f"{grounded_note}"
            )
        sections.append(
            "[Answer Reference Context]\n"
            f"{state.recent_assistant_answer}\n\n"
            "[Answer Reference Note]\n"
            "The user appears to be referring to the assistant response above. "
            "Assume that response is the target unless the user explicitly points "
            "to different text. If they ask to continue, clarify, simplify, shorten, "
            "restate, or explain it, operate on the response above directly instead "
            "of asking them to resend it. Stay on the same topic and do not reset "
            "the conversation."
        )
        if recent_answer_option_selection_reference:
            sections.append(
                "[Selection Note]\n"
                f"The user appears to be referring to option {recent_answer_option_selection_reference} "
                "from the answer-reference context above. Interpret their reply as asking about "
                "that specific item and answer directly instead of repeating the whole list."
            )
        if recent_answer_referenced_item:
            sections.append(
                "[Referenced Item Context]\n"
                f"{recent_answer_referenced_item}\n\n"
                "[Referenced Item Note]\n"
                "The user's reference resolves to the exact item above from the assistant answer. "
                "Prefer answering from that item directly instead of repeating the whole list."
            )
        state.effective_content = "\n\n".join(section for section in sections if section).strip()
        state.continuity_source = "answer_reference"
        logger.info(
            f"Recent assistant answer context continued: '{_normalize_text(state.effective_content)[:120]}'"
        )
    if (
        state.continuity_source == "answer_reference"
        and state.pending_followup_intent_kind != "assistant_offer"
    ):
        _clear_pending_followup_intent(state.session)
        state.pending_followup_intent = None
        state.pending_followup_intent_text = ""
        state.pending_followup_intent_kind = ""
        state.pending_followup_intent_request_text = ""
        state.committed_action_request_text = ""

    ignore_stale_pending_intent_for_answer_reference = bool(
        state.continuity_source == "answer_reference"
        and state.pending_followup_intent_kind != "assistant_offer"
    )
    pending_intent_kind = str(
        ((state.pending_followup_intent or {}).get("kind") if state.pending_followup_intent else "") or ""
    ).strip().lower()
    generic_pending_intent_followup = bool(
        pending_intent_kind not in {"assistant_offer", "assistant_committed_action"}
        and state.is_short_confirmation
    )
    skill_managed_pending_intent_followup = bool(
        pending_intent_kind in {"assistant_offer", "assistant_committed_action"}
        and (
            state.is_short_confirmation
            or state.is_assistant_offer_context_followup
            or state.is_assistant_committed_action_followup
            or allow_explicit_path_hint_for_committed_delivery
            or state.is_contextual_followup_request
            or (
                pending_intent_kind == "assistant_offer"
                and state.is_answer_reference_followup
            )
        )
    )

    if (
        state.pending_followup_intent
        and (
            not state.required_tool
            or (
                state.pending_followup_intent_kind == "assistant_committed_action"
                and state.required_tool == "list_dir"
            )
        )
        and not ignore_stale_pending_intent_for_answer_reference
        and (
            generic_pending_intent_followup
            or skill_managed_pending_intent_followup
        )
        and not state.is_closing_ack
        and not state.is_short_greeting
        and not state.is_non_action_feedback
        and (
            not state.is_explicit_new_request
            or allow_explicit_path_hint_for_committed_delivery
        )
    ):
        intent_text = str(state.pending_followup_intent.get("text") or "").strip()
        intent_profile = (
            str(state.pending_followup_intent.get("profile") or "GENERAL").strip().upper()
        )
        intent_kind = str(state.pending_followup_intent.get("kind") or "").strip().lower()
        intent_request_text = (
            str(state.pending_followup_intent.get("request_text") or "").strip()
        )
        option_selection_reference = (
            _extract_option_selection_reference(state.effective_content)
            if intent_kind == "assistant_offer"
            else None
        )
        answer_reference_followup = bool(
            intent_kind not in {"assistant_offer", "assistant_committed_action"}
            and state.is_answer_reference_followup
        )
        inferred_tool = None
        if (
            intent_text
            and intent_kind not in {"assistant_offer", "assistant_committed_action"}
            and not answer_reference_followup
        ):
            inferred_tool = _resolve_grounded_required_tool(state.loop, intent_text)
        if intent_kind == "assistant_committed_action":
            committed_task_text = intent_request_text or intent_text
            state.committed_action_request_text = (
                committed_task_text or state.committed_action_request_text
            )
            committed_coding_request = _looks_like_coding_build_request(
                committed_task_text or intent_text,
                route_profile=intent_profile,
            )
            sections = [state.effective_content]
            if committed_task_text:
                sections.extend(["[Committed Action Context]", committed_task_text])
            if intent_text and intent_text != committed_task_text:
                sections.extend(["[Assistant Promise]", intent_text])
            sections.extend(
                [
                    "[Committed Action Note]",
                    "The user is asking you to follow through on the promised action now. "
                    "Use the committed action context above as the operative request, "
                    "perform the work with the appropriate tools or skills, and stay on "
                    "that exact task. Do not switch topics, do not ask the user to repeat "
                    "the request unless essential details are truly missing, and do not "
                    "claim the work is done or sent unless you have actual tool evidence.",
                ]
            )
            state.effective_content = "\n\n".join(section for section in sections if section).strip()
            state.continuity_source = (
                "committed_coding_action" if committed_coding_request else "committed_action"
            )
            state.decision.is_complex = True
            if committed_coding_request:
                state.decision.profile = "CODING"
            elif intent_profile:
                state.decision.profile = intent_profile
            if committed_task_text and (
                not state.required_tool or state.required_tool == "list_dir"
            ):
                inferred_committed_tool = _resolve_grounded_required_tool(
                    state.loop,
                    committed_task_text,
                )
                inferred_committed_query = committed_task_text
                if not inferred_committed_tool:
                    (
                        inferred_committed_tool,
                        inferred_committed_query,
                    ) = infer_action_required_tool_for_loop(
                        state.loop,
                        committed_task_text,
                    )
                if inferred_committed_tool:
                    override_list_dir_with_committed_delivery = bool(
                        state.required_tool == "list_dir"
                        and inferred_committed_tool == "message"
                    )
                    state.required_tool = inferred_committed_tool
                    if override_list_dir_with_committed_delivery:
                        state.required_tool_query = (
                            "\n".join(
                                part
                                for part in [committed_task_text, state.effective_content]
                                if part and str(part).strip()
                            )
                        ).strip()
                        state.continuity_source = "committed_action"
                    else:
                        state.required_tool_query = str(
                            inferred_committed_query or committed_task_text
                        ).strip()
                    state.fast_direct_context = bool(
                        state.perf_cfg
                        and bool(getattr(state.perf_cfg, "fast_first_response", True))
                        and state.required_tool in state.direct_tools
                    )
            logger.info(
                f"Committed action continued: '{_normalize_text(state.effective_content)[:120]}' profile={state.decision.profile} complex={state.decision.is_complex}"
            )
            _clear_pending_followup_tool(state.session)
            state.pending_followup_tool = None
            state.pending_followup_source = ""
        elif inferred_tool:
            state.required_tool = inferred_tool
            state.required_tool_query = intent_text
            state.continuity_source = "pending_followup_intent"
            state.decision.is_complex = True
            logger.info(
                f"Session intent follow-up inference: '{_normalize_text(state.effective_content)}' -> required_tool={inferred_tool}"
            )
            state.fast_direct_context = bool(
                state.perf_cfg
                and bool(getattr(state.perf_cfg, "fast_first_response", True))
                and state.required_tool in state.direct_tools
            )
        else:
            state.effective_content = (
                f"{state.effective_content}\n\n[Follow-up Context]\n{intent_text}"
                if intent_text
                else state.effective_content
            )
            if intent_kind == "assistant_offer" and intent_text:
                offer_request_text = intent_request_text
                offer_request_is_coding = False
                offer_request_is_side_effect = False
                offer_action_context_text = ""
                if offer_request_text:
                    state.effective_content = (
                        f"{state.effective_content}\n\n"
                        "[Offer Request Context]\n"
                        f"{offer_request_text}\n\n"
                        "[Offer Request Note]\n"
                        "Use the request context above as the concrete task the assistant offer "
                        "was referring to. If the user is accepting the offer with a short reply, "
                        "continue from that concrete request instead of treating the offer sentence "
                        "as the only available context."
                    )
                    (
                        offer_request_action_tool,
                        offer_request_action_query,
                    ) = infer_action_required_tool_for_loop(
                        state.loop,
                        offer_request_text,
                    )
                    offer_request_is_coding = _looks_like_coding_build_request(
                        offer_request_text,
                        route_profile=intent_profile,
                    )
                    offer_request_is_side_effect = _looks_like_side_effect_request(
                        offer_request_text
                    )
                    if offer_request_action_tool and not state.required_tool:
                        state.required_tool = offer_request_action_tool
                        state.required_tool_query = str(
                            offer_request_action_query or offer_request_text
                        ).strip()
                        state.continuity_source = "action_request"
                        state.decision.is_complex = True
                    elif offer_request_is_coding:
                        state.continuity_source = state.continuity_source or "coding_request"
                        state.decision.profile = "CODING"
                        state.decision.is_complex = True
                    elif offer_request_is_side_effect:
                        state.continuity_source = state.continuity_source or "action_request"
                        state.decision.is_complex = True
                    offer_action_context_text = offer_request_text
                if intent_text:
                    merged_offer_action_context = "\n".join(
                        part
                        for part in [offer_action_context_text, intent_text]
                        if part and part.strip()
                    ).strip()
                    if (
                        merged_offer_action_context
                        and not state.required_tool
                    ):
                        offer_intent_action_tool = (
                            _resolve_grounded_required_tool(
                                state.loop,
                                merged_offer_action_context,
                            )
                            if offer_request_text
                            else None
                        )
                        offer_intent_action_query = (
                            merged_offer_action_context if offer_intent_action_tool else None
                        )
                        if not offer_intent_action_tool:
                            (
                                offer_intent_action_tool,
                                offer_intent_action_query,
                            ) = infer_action_required_tool_for_loop(
                                state.loop,
                                merged_offer_action_context,
                            )
                        if offer_intent_action_tool:
                            state.required_tool = offer_intent_action_tool
                            state.required_tool_query = str(
                                offer_intent_action_query or merged_offer_action_context
                            ).strip()
                            state.continuity_source = "action_request"
                            state.decision.is_complex = True
                        elif (
                            offer_request_text
                            and (
                            not offer_request_is_coding
                            and _looks_like_coding_build_request(
                                merged_offer_action_context,
                                route_profile=intent_profile,
                            )
                            )
                        ):
                            state.continuity_source = state.continuity_source or "coding_request"
                            state.decision.profile = "CODING"
                            state.decision.is_complex = True
                        elif (
                            offer_request_text
                            and (
                            not offer_request_is_side_effect
                            and _looks_like_side_effect_request(merged_offer_action_context)
                            )
                        ):
                            state.continuity_source = state.continuity_source or "action_request"
                            state.decision.is_complex = True
                if (
                    not state.required_tool
                    and not offer_request_text
                    and getattr(state, "conversation_history", None)
                ):
                    inferred_offer_tool, inferred_offer_source = _infer_required_tool_from_recent_user_intent(
                        state.loop,
                        state.effective_content,
                        state.conversation_history,
                    )
                    if inferred_offer_tool:
                        state.required_tool = inferred_offer_tool
                        state.required_tool_query = str(
                            inferred_offer_source or state.effective_content
                        ).strip()
                        state.continuity_source = "user_intent"
                        state.decision.is_complex = True
                state.effective_content = (
                    f"{state.effective_content}\n\n"
                    "[Offer Acceptance Note]\n"
                    "The user appears to be accepting the assistant offer from the "
                    "follow-up context above and wants the promised continuation. "
                    "Continue that exact topic naturally. Do not switch topics, "
                    "restart the conversation, or fetch unrelated tools/data unless "
                    "the offer itself explicitly required it."
                )
                if state.recent_assistant_answer and state.is_answer_reference_followup:
                    state.effective_content = (
                        f"{state.effective_content}\n\n"
                        "[Answer Reference Context]\n"
                        f"{state.recent_assistant_answer}\n\n"
                        "[Answer Reference Note]\n"
                        "The user appears to be referring to the assistant response above "
                        "while continuing the accepted offer. Operate directly on that "
                        "response instead of asking them to resend it, and keep the same "
                        "topic without resetting the conversation."
                    )
                    state.continuity_source = "answer_reference"
            if option_selection_reference:
                state.effective_content = (
                    f"{state.effective_content}\n\n"
                    "[Selection Note]\n"
                    f"The user appears to be referring to option {option_selection_reference} "
                    "from the follow-up context above. Interpret their reply as selecting or "
                    "asking about that option. Continue naturally and do not simply repeat "
                    "the option number back."
                )
            if not state.decision.is_complex and str(state.decision.profile).upper() == "CHAT":
                state.decision.profile = intent_profile if intent_profile else state.decision.profile
                if intent_profile in {"CODING", "RESEARCH", "GENERAL"}:
                    state.decision.is_complex = True
            logger.info(
                f"Session intent context continued: '{_normalize_text(state.effective_content)[:120]}' profile={state.decision.profile} complex={state.decision.is_complex}"
            )
            if intent_kind == "assistant_offer":
                _clear_pending_followup_tool(state.session)
                state.pending_followup_tool = None
                state.pending_followup_source = ""
