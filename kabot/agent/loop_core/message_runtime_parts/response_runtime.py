"""Extracted response/context execution tail for process_flow."""

from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from typing import Any

from loguru import logger

from kabot.agent.fallback_i18n import t
from kabot.agent.loop_core.message_runtime_parts.helpers import (
    _KEEPALIVE_INITIAL_DELAY_SECONDS,
    _KEEPALIVE_INTERVAL_SECONDS,
    _build_budget_hints,
    _build_untrusted_context_payload,
    _channel_supports_keepalive_passthrough,
    _channel_uses_mutable_status_lane,
    _classify_assistant_followup_intent_kind,
    _emit_runtime_event,
    _extract_assistant_followup_offer_text,
    _looks_like_memory_commit_turn,
    _looks_like_memory_recall_turn,
    _looks_like_side_effect_request,
    _looks_like_temporal_context_query,
    _message_needs_full_skill_context,
    _schedule_context_truncation_memory_fact,
    _set_pending_followup_intent,
    _update_skill_creation_flow_after_response,
)
from kabot.agent.loop_core.message_runtime_parts.bootstrap_onboarding import (
    update_bootstrap_onboarding_state,
)
from kabot.agent.loop_core.message_runtime_parts.temporal import build_temporal_fast_reply
from kabot.agent.loop_core.message_runtime_parts.turn_helpers import (
    _build_answer_reference_fast_reply,
)
from kabot.agent.loop_core.message_runtime_parts.user_profile import (
    resolve_self_identity_fast_reply,
)
from kabot.bus.events import OutboundMessage


async def _run_turn_response(state: Any) -> OutboundMessage | None:
    loop = state.loop
    msg = state.msg
    session = state.session
    decision = state.decision
    required_tool = state.required_tool
    effective_content = state.effective_content
    filesystem_location_context_note = state.filesystem_location_context_note
    explicit_file_analysis_note = state.explicit_file_analysis_note
    mcp_context_note = state.mcp_context_note
    runtime_locale = state.runtime_locale
    observed_continuity_source = state.observed_continuity_source
    recent_answer_target = state.recent_answer_target
    recent_answer_option_selection_reference = state.recent_answer_option_selection_reference
    recent_answer_referenced_item = state.recent_answer_referenced_item
    continuity_source = state.continuity_source
    perf_cfg = state.perf_cfg
    is_background_task = state.is_background_task
    skill_creation_approved = state.skill_creation_approved
    llm_current_message = state.llm_current_message
    history_limit = state.history_limit
    skip_history_for_speed = state.skip_history_for_speed
    token_mode = state.token_mode
    probe_mode = state.probe_mode
    conversation_history = state.conversation_history
    forced_skill_names = state.forced_skill_names
    turn_id = state.turn_id
    intent_source_for_followup = state.intent_source_for_followup
    pending_followup_intent_request_text = state.pending_followup_intent_request_text
    committed_action_request_text = state.committed_action_request_text
    fast_direct_context = state.fast_direct_context
    is_non_action_feedback = state.is_non_action_feedback
    is_contextual_followup_request = state.is_contextual_followup_request
    turn_started = state.turn_started

    accuracy_context_required = bool(
        is_non_action_feedback
        or _looks_like_temporal_context_query(effective_content)
        or _looks_like_memory_commit_turn(effective_content)
        or _looks_like_memory_recall_turn(effective_content)
        or is_contextual_followup_request
    )
    grounded_followup_fast_reply = None
    if (
        not decision.is_complex
        and not required_tool
        and continuity_source == "answer_reference"
        and recent_answer_target
    ):
        grounded_followup_fast_reply = _build_answer_reference_fast_reply(
            str(msg.content or ""),
            locale=runtime_locale,
            answer_target=recent_answer_target,
            option_selection_reference=recent_answer_option_selection_reference,
            referenced_item=recent_answer_referenced_item,
        )
    temporal_fast_reply = None
    profile_fast_reply = None
    if (
        not decision.is_complex
        and not required_tool
        and not filesystem_location_context_note
        and not explicit_file_analysis_note
        and not mcp_context_note
    ):
        profile_fast_reply = resolve_self_identity_fast_reply(session, effective_content)
        temporal_fast_reply = grounded_followup_fast_reply or build_temporal_fast_reply(
            effective_content,
            locale=runtime_locale,
        )
        if profile_fast_reply:
            temporal_fast_reply = profile_fast_reply

    fast_simple_context = bool(
        perf_cfg
        and bool(getattr(perf_cfg, "fast_first_response", True))
        and not decision.is_complex
        and not required_tool
        and not filesystem_location_context_note
        and not explicit_file_analysis_note
        and not mcp_context_note
        and not accuracy_context_required
        and not _looks_like_memory_commit_turn(effective_content)
    )
    if forced_skill_names:
        fast_direct_context = False
        fast_simple_context = False

    queue_meta = msg.metadata if isinstance(msg.metadata, dict) else {}
    queue_info = queue_meta.get("queue") if isinstance(queue_meta.get("queue"), dict) else {}
    dropped_count = int(queue_info.get("dropped_count", 0) or 0)
    dropped_preview = queue_info.get("dropped_preview", [])
    preview_items = [str(item).strip() for item in dropped_preview if str(item).strip()]
    untrusted_context = _build_untrusted_context_payload(
        msg,
        dropped_count=dropped_count,
        dropped_preview=preview_items,
    )

    queued_status = t("runtime.status.queued", locale=runtime_locale, text=effective_content)
    if dropped_count > 0:
        queued_status += " " + t(
            "runtime.status.queued_merged",
            locale=runtime_locale,
            text=effective_content,
            count=dropped_count,
        )
        merge_note = f"[Queue Merge] {dropped_count} pending message(s) were merged before processing."
        if preview_items:
            merge_note += " Earlier snippets: " + " | ".join(preview_items[:2])
        effective_content = f"{effective_content}\n\n{merge_note}"
    thinking_status = t("runtime.status.thinking", locale=runtime_locale, text=effective_content)
    approved_status = t("runtime.status.approved", locale=runtime_locale, text=effective_content)
    done_status = t("runtime.status.done", locale=runtime_locale, text=effective_content)
    error_status = t("runtime.status.error", locale=runtime_locale, text=effective_content)

    async def _publish_status(text: str, phase: str, *, keepalive: bool = False) -> None:
        bus = getattr(loop, "bus", None)
        publish = getattr(bus, "publish_outbound", None)
        if not callable(publish):
            return
        try:
            metadata = {"type": "status_update", "phase": phase}
            metadata["lane"] = "status"
            if keepalive:
                metadata["keepalive"] = True
            await publish(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=text,
                    metadata=metadata,
                )
            )
        except Exception:
            return

    keepalive_stop = asyncio.Event()
    keepalive_task: asyncio.Task | None = None

    async def _keepalive_loop() -> None:
        try:
            try:
                await asyncio.wait_for(
                    keepalive_stop.wait(),
                    timeout=float(_KEEPALIVE_INITIAL_DELAY_SECONDS),
                )
                return
            except asyncio.TimeoutError:
                pass

            while not keepalive_stop.is_set():
                await _publish_status(thinking_status, "thinking", keepalive=True)
                try:
                    await asyncio.wait_for(
                        keepalive_stop.wait(),
                        timeout=float(_KEEPALIVE_INTERVAL_SECONDS),
                    )
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            return

    mutable_status_lane = bool(_channel_uses_mutable_status_lane(loop, msg.channel))
    keepalive_enabled = bool(
        not is_background_task and _channel_supports_keepalive_passthrough(loop, msg.channel)
    )
    if not is_background_task:
        await _publish_status(queued_status, "queued")
        if skill_creation_approved and mutable_status_lane:
            await _publish_status(approved_status, "approved")
        if keepalive_enabled and isinstance(msg.metadata, dict):
            msg.metadata["suppress_initial_thinking_status"] = True
        if temporal_fast_reply is None and keepalive_enabled:
            keepalive_task = asyncio.create_task(_keepalive_loop())

    if temporal_fast_reply is not None:
        context_build_ms = 0
        logger.info(f"turn_id={turn_id} context_build_ms={context_build_ms}")
        _emit_runtime_event(
            loop,
            "context_built",
            turn_id=turn_id,
            context_build_ms=context_build_ms,
            continuity_source=observed_continuity_source,
        )
        if not is_background_task and mutable_status_lane:
            await _publish_status(done_status, "done")
        final_content = temporal_fast_reply
    else:
        try:
            context_builder = loop.context
            resolve_context = getattr(loop, "_resolve_context_for_message", None)
            if callable(resolve_context):
                try:
                    resolved_context = resolve_context(msg)
                    if resolved_context is not None:
                        context_builder = resolved_context
                except Exception as exc:
                    logger.warning(f"Failed to resolve routed context builder: {exc}")

            if fast_simple_context and _message_needs_full_skill_context(
                context_builder,
                llm_current_message,
                str(decision.profile),
            ):
                fast_simple_context = False

            if fast_direct_context or fast_simple_context:
                messages = [{"role": "user", "content": effective_content}]
                context_build_ms = 0
            else:
                context_started = time.perf_counter()
                budget_hints = _build_budget_hints(
                    history_limit=history_limit,
                    dropped_count=dropped_count,
                    fast_path=bool(fast_direct_context or fast_simple_context),
                    skip_history_for_speed=skip_history_for_speed,
                    token_mode=token_mode,
                    probe_mode=probe_mode,
                )
                if mcp_context_note:
                    budget_hints["mcp_context_mode"] = True
                    budget_hints["compact_system_prompt"] = True
                if accuracy_context_required and not decision.is_complex and not required_tool:
                    budget_hints["compact_system_prompt"] = True
                messages = await asyncio.to_thread(
                    context_builder.build_messages,
                    history=conversation_history,
                    current_message=llm_current_message,
                    skill_names=forced_skill_names,
                    media=msg.media if hasattr(msg, "media") else None,
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    profile=decision.profile,
                    tool_names=loop.tools.tool_names,
                    untrusted_context=untrusted_context,
                    budget_hints=budget_hints,
                )
                truncation_summary = None
                consume_summary = getattr(context_builder, "consume_last_truncation_summary", None)
                if callable(consume_summary):
                    try:
                        truncation_summary = consume_summary()
                    except Exception as exc:
                        logger.debug(f"Failed reading context truncation summary: {exc}")
                await _schedule_context_truncation_memory_fact(
                    loop,
                    session_key=msg.session_key,
                    summary_meta=truncation_summary,
                )
                context_build_ms = int((time.perf_counter() - context_started) * 1000)
            max_context_build_ms = int(getattr(perf_cfg, "max_context_build_ms", 500)) if perf_cfg else 500
            logger.info(f"turn_id={turn_id} context_build_ms={context_build_ms}")
            _emit_runtime_event(
                loop,
                "context_built",
                turn_id=turn_id,
                context_build_ms=context_build_ms,
                continuity_source=observed_continuity_source,
            )
            if context_build_ms > max_context_build_ms:
                logger.warning(
                    f"turn_id={turn_id} context_build_ms={context_build_ms} exceeded budget={max_context_build_ms}"
                )

            if decision.is_complex or required_tool:
                if required_tool and not decision.is_complex:
                    logger.info(f"Route override: simple -> complex (required_tool={required_tool})")
                final_content = await loop._run_agent_loop(msg, messages, session)
            else:
                if not is_background_task and mutable_status_lane:
                    await _publish_status(thinking_status, "thinking")
                final_content = await loop._run_simple_response(msg, messages)
                if not is_background_task and mutable_status_lane:
                    await _publish_status(
                        done_status if final_content else error_status,
                        "done" if final_content else "error",
                    )

        finally:
            keepalive_stop.set()
            if keepalive_task is not None:
                keepalive_task.cancel()
                with suppress(asyncio.CancelledError):
                    await keepalive_task
        _update_skill_creation_flow_after_response(
            session,
            msg,
            final_content,
            now_ts=time.time(),
        )
        update_bootstrap_onboarding_state(
            loop,
            session,
            msg,
            final_content,
            now_ts=time.time(),
        )
        followup_offer_text = _extract_assistant_followup_offer_text(final_content or "")
        if followup_offer_text:
            followup_intent_kind = _classify_assistant_followup_intent_kind(followup_offer_text)
            followup_request_text = None
            if followup_intent_kind == "assistant_committed_action":
                followup_request_text = (
                    committed_action_request_text
                    or pending_followup_intent_request_text
                    or (
                        intent_source_for_followup
                        if _looks_like_side_effect_request(intent_source_for_followup)
                        else ""
                    )
                    or intent_source_for_followup
                )
            elif intent_source_for_followup:
                followup_request_text = (
                    pending_followup_intent_request_text
                    or committed_action_request_text
                    or intent_source_for_followup
                )
            _set_pending_followup_intent(
                session,
                followup_offer_text,
                str(decision.profile),
                time.time(),
                kind=followup_intent_kind,
                request_text=followup_request_text,
            )

    first_response_ms = int((time.perf_counter() - turn_started) * 1000)
    logger.info(f"turn_id={turn_id} first_response_ms={first_response_ms}")
    warmup_ms: int | None = None
    started_at = getattr(loop, "_memory_warmup_started_at", None)
    completed_at = getattr(loop, "_memory_warmup_completed_at", None)
    if isinstance(started_at, (int, float)) and isinstance(completed_at, (int, float)) and completed_at >= started_at:
        warmup_ms = int((completed_at - started_at) * 1000)
    _emit_runtime_event(
        loop,
        "turn_end",
        turn_id=turn_id,
        first_response_ms=first_response_ms,
        memory_warmup_ms=warmup_ms if warmup_ms is not None else -1,
        continuity_source=observed_continuity_source,
    )
    max_first_response_soft = int(getattr(perf_cfg, "max_first_response_ms_soft", 4000)) if perf_cfg else 4000
    if first_response_ms > max_first_response_soft:
        logger.warning(
            f"turn_id={turn_id} first_response_ms={first_response_ms} exceeded soft_target={max_first_response_soft}"
        )

    suppress_post_response_warmup = bool(
        isinstance(getattr(msg, "metadata", None), dict)
        and msg.metadata.get("suppress_post_response_warmup")
    )
    if (
        perf_cfg
        and bool(getattr(perf_cfg, "defer_memory_warmup", True))
        and not suppress_post_response_warmup
    ):
        ensure_warmup = getattr(loop, "_ensure_memory_warmup_task", None)
        if callable(ensure_warmup):
            ensure_warmup()

    return await loop._finalize_session(msg, session, final_content)
