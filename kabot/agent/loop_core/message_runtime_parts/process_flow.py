"""Message/session runtime helpers extracted from AgentLoop."""

from __future__ import annotations

import re
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from loguru import logger

from kabot.agent.cron_fallback_nlp import (
    extract_weather_location,
    looks_like_meta_skill_or_workflow_prompt,
)
from kabot.agent.fallback_i18n import t
from kabot.agent.loop_core.message_runtime_parts.helpers import (
    _KEEPALIVE_INITIAL_DELAY_SECONDS,
    _KEEPALIVE_INTERVAL_SECONDS,
    _build_budget_hints,
    _build_explicit_file_analysis_note,
    _build_grounded_filesystem_inspection_note,
    _build_filesystem_location_context_note,
    _build_session_continuity_action_note,
    _build_skill_creation_workflow_note,
    _build_temporal_context_note,
    _build_untrusted_context_payload,
    _classify_assistant_followup_intent_kind,
    _channel_supports_keepalive_passthrough,
    _clear_pending_followup_intent,
    _clear_pending_followup_tool,
    _clear_skill_creation_flow,
    _emit_runtime_event,
    _extract_assistant_followup_offer_text,
    _extract_explicit_mcp_tool_name,
    _extract_option_selection_reference,
    _extract_user_supplied_option_prompt_text,
    _get_last_tool_context,
    _get_last_tool_execution,
    _get_pending_followup_intent,
    _get_pending_followup_tool,
    _get_skill_creation_flow,
    _infer_recent_created_skill_name_from_path,
    _infer_recent_assistant_answer_from_history,
    _infer_recent_assistant_option_prompt_from_history,
    _infer_recent_file_path_from_history,
    _is_abort_request_text,
    _is_low_information_turn,
    _is_probe_mode_message,
    _is_short_context_followup,
    _looks_like_answer_reference_followup,
    _looks_like_assistant_offer_context_followup,
    _looks_like_closing_acknowledgement,
    _looks_like_coding_build_request,
    _looks_like_contextual_followup_request,
    _looks_like_explicit_new_request,
    _looks_like_explicit_tool_use_request,
    _looks_like_existing_skill_use_followup,
    _looks_like_file_context_followup,
    _looks_like_filesystem_location_query,
    _looks_like_live_research_query,
    _looks_like_message_delivery_request,
    _looks_like_memory_commit_turn,
    _looks_like_memory_recall_turn,
    _looks_like_non_action_meta_feedback,
    _looks_like_side_effect_request,
    _looks_like_short_confirmation,
    _looks_like_short_greeting_smalltalk,
    _looks_like_skill_creation_approval,
    _looks_like_skill_workflow_followup_detail,
    _looks_like_temporal_context_query,
    _looks_like_web_search_demotion_followup,
    _looks_like_weather_context_followup,
    _message_needs_full_skill_context,
    _normalize_text,
    _resolve_runtime_locale,
    _resolve_relevant_memory_facts,
    _resolve_token_mode,
    _schedule_context_truncation_memory_fact,
    _set_last_tool_context,
    _set_pending_followup_intent,
    _set_pending_followup_tool,
    _set_skill_creation_flow,
    _should_persist_probe_history,
    _should_store_followup_intent,
    _tool_registry_has,
    _update_skill_creation_flow_after_response,
)
from kabot.agent.loop_core.message_runtime_parts.mcp_context import (
    _extract_explicit_mcp_prompt_reference,
    _extract_explicit_mcp_resource_reference,
)
from kabot.agent.loop_core.message_runtime_parts.continuity_runtime import (
    _apply_continuity_runtime,
)
from kabot.agent.loop_core.directive_pipeline import (
    apply_directive_overrides,
    format_active_directives,
    parse_directives,
    persist_directives,
)
from kabot.agent.loop_core.message_runtime_parts.response_runtime import (
    _run_turn_response,
)
from kabot.agent.loop_core.message_runtime_parts.temporal import (
    build_temporal_fast_reply,
)
from kabot.agent.loop_core.message_runtime_parts.turn_metadata import (
    _finalize_turn_metadata,
)
from kabot.agent.loop_core.message_runtime_parts.turn_helpers import (
    _build_answer_reference_fast_reply,
    _extract_reusable_last_tool_execution,
    _format_grounded_target_reply,
    _infer_required_tool_from_recent_user_intent,
    _looks_like_brief_answer_request,
    _looks_like_meaning_followup,
    _resolve_turn_category,
    _select_answer_reference_target,
)
from kabot.agent.loop_core.message_runtime_parts.user_profile import (
    persist_user_profile,
    sync_user_profile_memory,
)
from kabot.agent.loop_core.execution_runtime_parts.intent import (
    _build_source_constrained_web_search_query,
    _extract_direct_fetch_url_candidate,
    _looks_like_live_data_refresh_followup,
    _looks_like_live_finance_lookup,
    _looks_like_web_source_selection_followup,
    _should_defer_live_research_latch_to_skill,
)
from kabot.agent.loop_core.tool_enforcement import (
    _extract_list_dir_path,
    _extract_read_file_path,
    infer_action_required_tool_for_loop,
    _query_has_tool_payload,
)
from kabot.agent.loop_core.tool_enforcement_parts.action_requests import (
    _looks_like_message_send_file_request,
)
from kabot.agent.loop_core.quality_runtime import get_learned_execution_hints
from kabot.agent.semantic_intent import arbitrate_semantic_intent
from kabot.agent.skills import (
    looks_like_skill_creation_request,
    looks_like_skill_install_request,
    normalize_skill_reference_name,
)
from kabot.agent.skills_matching import (
    looks_like_explicit_skill_use_request,
)
from kabot.agent.tools.stock import (
    extract_crypto_ids,
    extract_stock_symbols,
)
from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.core.command_router import CommandContext

__all__ = [
    "_extract_assistant_followup_offer_text",
    "_extract_option_selection_reference",
    "_infer_recent_assistant_answer_from_history",
    "_infer_recent_assistant_option_prompt_from_history",
    "_extract_user_supplied_option_prompt_text",
    "_is_low_information_turn",
    "_looks_like_answer_reference_followup",
    "_normalize_text",
    "_resolve_runtime_locale",
    "build_temporal_fast_reply",
    "extract_weather_location",
    "process_isolated",
    "process_message",
    "process_pending_exec_approval",
    "process_system_message",
]





async def process_message(loop: Any, msg: InboundMessage) -> OutboundMessage | None:
    """Process a regular inbound message."""
    if msg.channel == "system":
        return await process_system_message(loop, msg)

    turn_started = time.perf_counter()
    turn_id = f"{msg.channel}:{msg.chat_id}:{int(msg.timestamp.timestamp() * 1000)}"
    setattr(loop, "_active_turn_id", turn_id)
    _emit_runtime_event(
        loop,
        "turn_start",
        turn_id=turn_id,
        channel=msg.channel,
        chat_id=msg.chat_id,
    )
    perf_cfg = getattr(loop, "runtime_performance", None)
    token_mode = _resolve_token_mode(perf_cfg)

    drain_pending_memory = getattr(loop, "_drain_pending_memory_writes", None)
    if callable(drain_pending_memory):
        try:
            await drain_pending_memory(max_wait_ms=250)
        except Exception as exc:
            logger.debug(f"Pending memory drain skipped: {exc}")

    tools_obj = getattr(loop, "tools", None)
    tool_get = getattr(tools_obj, "get", None)
    exec_tool = tool_get("exec") if callable(tool_get) else None
    pending_exec = None
    if exec_tool and hasattr(exec_tool, "get_pending_approval"):
        try:
            pending_exec = exec_tool.get_pending_approval(msg.session_key)
        except Exception:
            pending_exec = None
    if pending_exec:
        parse_exec_approval_turn = getattr(loop, "_parse_exec_approval_turn", None)
        resolved_action = parse_exec_approval_turn(msg.content) if callable(parse_exec_approval_turn) else None
        if resolved_action in {"approve", "deny"}:
            approval_id = pending_exec.get("id") if isinstance(pending_exec, dict) else None
            return await process_pending_exec_approval(
                loop,
                msg,
                action=resolved_action,
                approval_id=approval_id if isinstance(approval_id, str) else None,
            )

    # Fast abort shortcut: standalone stop/cancel intent should
    # immediately halt follow-up continuation and clear pending intent state.
    if _is_abort_request_text(msg.content):
        session = await loop._init_session(msg)
        _clear_pending_followup_tool(session)
        _clear_pending_followup_intent(session)
        runtime_locale = _resolve_runtime_locale(session, msg, msg.content)
        stop_text = t("runtime.abort.ack", locale=runtime_locale, text=msg.content)
        _emit_runtime_event(loop, "turn_abort_shortcut", turn_id=turn_id)
        return await loop._finalize_session(msg, session, stop_text)

    # Phase 8: Intercept slash commands BEFORE routing to LLM
    if loop.command_router.is_command(msg.content):
        ctx = CommandContext(
            message=msg.content,
            args=[],
            sender_id=msg.sender_id,
            channel=msg.channel,
            chat_id=msg.chat_id,
            session_key=msg.session_key,
            agent_loop=loop,
        )
        result = await loop.command_router.route(msg.content, ctx)
        if result:
            session = await loop._init_session(msg)
            return await loop._finalize_session(msg, session, result)

    session = await loop._init_session(msg)
    if isinstance(msg.metadata, dict):
        setattr(loop, "_active_message_metadata", msg.metadata)
    else:
        setattr(loop, "_active_message_metadata", {})
    if not bool(getattr(loop, "_cold_start_reported", False)):
        boot_started = getattr(loop, "_boot_started_at", None)
        startup_ready = getattr(loop, "_startup_ready_at", None)
        if isinstance(boot_started, (int, float)) and isinstance(startup_ready, (int, float)):
            cold_start_ms = int((startup_ready - boot_started) * 1000)
            logger.info(f"cold_start_ms={max(0, cold_start_ms)}")
        elif isinstance(boot_started, (int, float)):
            cold_start_ms = int((time.perf_counter() - boot_started) * 1000)
            logger.info(f"cold_start_ms={cold_start_ms}")
        loop._cold_start_reported = True

    # Phase 9: Parse directives from message body
    clean_body, directives = parse_directives(loop, msg.content)
    effective_content = clean_body or msg.content
    intent_source_for_followup = effective_content
    persist_user_profile(loop, session, effective_content, now_ts=time.time())
    try:
        await sync_user_profile_memory(loop, session, session_key=msg.session_key)
    except Exception as exc:
        logger.debug(f"user profile memory sync skipped: {exc}")

    # Store directives in session metadata
    if directives.raw_directives:
        active = format_active_directives(loop, directives)
        logger.info(f"Directives active: {active}")
        persist_directives(loop, session, directives)

    # Phase 9: Model override via directive
    if directives.model:
        logger.info(f"Directive override: model -> {directives.model}")
    apply_directive_overrides(msg, directives)

    # Phase 13: Detect document uploads and inject hint for KnowledgeLearnTool
    if hasattr(msg, "media") and msg.media:
        document_paths = []
        for path in msg.media:
            ext = Path(path).suffix.lower()
            if ext in [".pdf", ".txt", ".md", ".csv"]:
                document_paths.append(path)

        if document_paths:
            hint = "\n\n[System Note: Document(s) detected: " + ", ".join(document_paths) + ". If the user wants you to 'learn' or 'memorize' these permanently, use the 'knowledge_learn' tool.]"
            effective_content += hint
            logger.info(f"Document hint injected: {len(document_paths)} files")

    incoming_metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
    preseeded_required_tool = str(incoming_metadata.get("required_tool") or "").strip()
    preseeded_required_tool_query = str(
        incoming_metadata.get("required_tool_query") or effective_content
    ).strip()
    if preseeded_required_tool:
        required_tool = preseeded_required_tool
        required_tool_query = preseeded_required_tool_query
        parser_required_tool = preseeded_required_tool
        continuity_source = str(incoming_metadata.get("continuity_source") or "action_request").strip() or "action_request"
    else:
        required_tool = loop._required_tool_for_query(effective_content)
        required_tool_query = effective_content
        parser_required_tool = required_tool
        continuity_source = "parser" if parser_required_tool else None
    explicit_mcp_prompt_ref = _extract_explicit_mcp_prompt_reference(effective_content)
    explicit_mcp_resource_ref = _extract_explicit_mcp_resource_reference(effective_content)
    now_ts = time.time()
    is_background_task = (
        (msg.channel or "").lower() == "system"
        or (msg.sender_id or "").lower() == "system"
        or (
            isinstance(msg.content, str)
            and msg.content.strip().lower().startswith("heartbeat task:")
        )
    )

    direct_tools = {
        "find_files",
        "read_file",
        "list_dir",
        "message",
        "save_memory",
        "get_process_memory",
        "get_system_info",
        "cleanup_system",
        "web_search",
        "weather",
        "speedtest",
        "stock",
        "stock_analysis",
        "crypto",
        "server_monitor",
        "check_update",
        "system_update",
    }
    route_bypass_direct_tools = {
        "find_files",
        "read_file",
        "list_dir",
        "message",
        "save_memory",
        "get_process_memory",
        "get_system_info",
        "cleanup_system",
        "speedtest",
        "server_monitor",
        "check_update",
        "system_update",
    }
    fast_direct_context = bool(
        perf_cfg
        and bool(getattr(perf_cfg, "fast_first_response", True))
        and required_tool in direct_tools
    )
    requires_live_data_honesty_note = False
    should_load_history_for_continuity = bool(
        not _looks_like_explicit_new_request(effective_content)
        and not _looks_like_closing_acknowledgement(effective_content)
        and not _looks_like_short_greeting_smalltalk(effective_content)
        and not _looks_like_non_action_meta_feedback(effective_content)
        and (
            _looks_like_answer_reference_followup(effective_content)
            or _looks_like_short_confirmation(effective_content)
            or _looks_like_contextual_followup_request(effective_content)
        )
    )

    history_limit = 30
    if perf_cfg and bool(getattr(perf_cfg, "fast_first_response", True)):
        warmup_task = getattr(loop, "_memory_warmup_task", None)
        if warmup_task is not None and not warmup_task.done():
            history_limit = 12
    if fast_direct_context:
        history_limit = min(history_limit, 6)

    probe_mode = _is_probe_mode_message(msg)
    persist_probe_history = _should_persist_probe_history(msg)
    conversation_history: list[dict[str, Any]] = []
    skip_history_for_speed = bool(
        perf_cfg
        and bool(getattr(perf_cfg, "fast_first_response", True))
        and _looks_like_live_research_query(effective_content)
    )
    if (
        (not probe_mode or persist_probe_history)
        and (not fast_direct_context or should_load_history_for_continuity)
        and not skip_history_for_speed
    ):
        conversation_history = loop.memory.get_conversation_context(msg.session_key, max_messages=history_limit)
        if conversation_history:
            conversation_history = [m for m in conversation_history if isinstance(m, dict)]
        if not conversation_history:
            get_session_history = getattr(session, "get_history", None)
            if callable(get_session_history):
                try:
                    hydrated_history = get_session_history(max_messages=history_limit)
                except Exception as exc:
                    logger.debug(f"Session snapshot hydration skipped: {exc}")
                    hydrated_history = []
                if hydrated_history:
                    conversation_history = [m for m in hydrated_history if isinstance(m, dict)]
                    try:
                        msg.metadata["history_hydration_source"] = "session_snapshot"
                    except Exception:
                        pass

    # Router triase: SIMPLE vs COMPLEX
    if fast_direct_context and required_tool in route_bypass_direct_tools:
        decision = SimpleNamespace(profile="GENERAL", is_complex=True)
    else:
        decision = await loop.router.route(effective_content)
    if (
        not required_tool
        and not bool(decision.is_complex)
        and _looks_like_explicit_tool_use_request(effective_content)
    ):
        decision.is_complex = True
    semantic_tool_override = False
    explicit_mcp_tool_routing = False
    explicit_mcp_tool = _extract_explicit_mcp_tool_name(effective_content)
    if not required_tool and explicit_mcp_tool:
        required_tool = explicit_mcp_tool
        required_tool_query = effective_content
        explicit_mcp_tool_routing = True
        continuity_source = "explicit_mcp_alias"
        decision.is_complex = True
        logger.info(
            "Explicit MCP tool alias detected: "
            f"'{_normalize_text(effective_content)[:120]}' -> required_tool={required_tool}"
        )
    elif explicit_mcp_prompt_ref or explicit_mcp_resource_ref:
        if required_tool:
            logger.info(
                "Explicit MCP prompt/resource reference detected: "
                f"clearing parser tool '{required_tool}' for '{_normalize_text(effective_content)[:120]}'"
            )
        required_tool = None
        required_tool_query = effective_content
        fast_direct_context = False
        continuity_source = None
    logger.info(f"Route: profile={decision.profile}, complex={decision.is_complex}")
    try:
        msg.metadata["route_profile"] = decision.profile
        msg.metadata["route_complex"] = bool(decision.is_complex)
    except Exception:
        pass
    route_turn_category = str(getattr(decision, "turn_category", "") or "").strip().lower()
    route_grounding_mode = str(getattr(decision, "grounding_mode", "") or "").strip().lower()
    if route_grounding_mode == "filesystem_inspection" and not bool(getattr(decision, "is_complex", False)):
        decision.is_complex = True

    pending_followup_tool_payload = _get_pending_followup_tool(session, now_ts)
    pending_followup_tool = (
        str(pending_followup_tool_payload.get("tool") or "").strip()
        if isinstance(pending_followup_tool_payload, dict)
        else None
    )
    pending_followup_source = (
        str(pending_followup_tool_payload.get("source") or "").strip()
        if isinstance(pending_followup_tool_payload, dict)
        else ""
    )
    recent_history_file_path = _infer_recent_file_path_from_history(conversation_history)
    last_tool_context = _get_last_tool_context(session, now_ts)
    last_tool_execution = _get_last_tool_execution(session, now_ts)
    pending_followup_intent = _get_pending_followup_intent(session, now_ts)
    pending_followup_intent_text = (
        str(pending_followup_intent.get("text") or "").strip()
        if isinstance(pending_followup_intent, dict)
        else ""
    )
    pending_followup_intent_kind = (
        str(pending_followup_intent.get("kind") or "").strip().lower()
        if isinstance(pending_followup_intent, dict)
        else ""
    )
    pending_followup_intent_request_text = (
        str(pending_followup_intent.get("request_text") or "").strip()
        if isinstance(pending_followup_intent, dict)
        else ""
    )
    committed_action_request_text = pending_followup_intent_request_text
    recent_assistant_option_prompt = _infer_recent_assistant_option_prompt_from_history(
        conversation_history
    )
    recent_assistant_answer = _infer_recent_assistant_answer_from_history(conversation_history)
    raw_is_answer_reference_followup = _looks_like_answer_reference_followup(effective_content)
    raw_is_short_confirmation = _looks_like_short_confirmation(effective_content)
    raw_is_contextual_followup_request = _looks_like_contextual_followup_request(effective_content)
    is_answer_reference_followup = bool(not required_tool and raw_is_answer_reference_followup)
    is_short_confirmation = bool(not required_tool and raw_is_short_confirmation)
    is_closing_ack = _looks_like_closing_acknowledgement(effective_content)
    is_short_greeting = _looks_like_short_greeting_smalltalk(effective_content)
    is_non_action_feedback = _looks_like_non_action_meta_feedback(effective_content)
    raw_is_explicit_new_request = _looks_like_explicit_new_request(effective_content)
    is_side_effect_request = bool(
        _looks_like_side_effect_request(effective_content)
        or route_turn_category in {"action", "contextual_action"}
    )
    is_weather_context_followup = bool(
        _looks_like_weather_context_followup(effective_content)
        and (
            pending_followup_tool == "weather"
            or (
                isinstance(last_tool_context, dict)
                and str(last_tool_context.get("tool") or "").strip() == "weather"
            )
        )
    )
    is_file_context_followup = bool(
        (
            (
                isinstance(last_tool_context, dict)
                and str(last_tool_context.get("tool") or "").strip() == "read_file"
            )
            or recent_history_file_path
        )
        and _looks_like_file_context_followup(effective_content)
    )
    is_explicit_new_request = bool(raw_is_explicit_new_request and not is_weather_context_followup)
    is_assistant_offer_context_followup = bool(
        pending_followup_intent_kind == "assistant_offer"
        and _looks_like_assistant_offer_context_followup(
            effective_content,
            pending_followup_intent_text,
        )
    )
    is_assistant_committed_action_followup = bool(
        pending_followup_intent_kind == "assistant_committed_action"
        and (
            raw_is_short_confirmation
            or raw_is_contextual_followup_request
            or _looks_like_assistant_offer_context_followup(
                effective_content,
                pending_followup_intent_request_text or pending_followup_intent_text,
            )
        )
    )
    is_contextual_followup_request = bool(
        not required_tool and raw_is_contextual_followup_request and not is_weather_context_followup
    )
    parser_required_tool_has_payload = False
    if required_tool and required_tool == parser_required_tool:
        try:
            parser_required_tool_has_payload = _query_has_tool_payload(required_tool, effective_content)
        except Exception:
            parser_required_tool_has_payload = False
    if (
        not pending_followup_intent_text
        and recent_assistant_option_prompt
        and (raw_is_short_confirmation or raw_is_contextual_followup_request)
    ):
        pending_followup_intent = {
            "text": recent_assistant_option_prompt,
            "profile": "CHAT",
            "kind": "assistant_offer",
        }
        pending_followup_intent_text = recent_assistant_option_prompt
        pending_followup_intent_kind = "assistant_offer"
    explicit_skill_use_request = looks_like_explicit_skill_use_request(effective_content)
    semantic_hint = arbitrate_semantic_intent(
        effective_content,
        parser_tool=required_tool,
        pending_followup_tool=pending_followup_tool,
        pending_followup_source=pending_followup_source,
        last_tool_context=last_tool_context,
        payload_checker=_query_has_tool_payload,
    )
    meta_skill_reference_turn = (
        looks_like_meta_skill_or_workflow_prompt(effective_content)
        and not explicit_skill_use_request
    )
    if semantic_hint.kind in {
        "advice_turn",
        "meta_feedback",
        "weather_metric_interpretation",
        "weather_commentary",
        "weather_source_followup",
        "memory_recall",
    }:
        required_tool = None
        required_tool_query = effective_content
        continuity_source = None
    elif semantic_hint.required_tool:
        required_tool = semantic_hint.required_tool
        required_tool_query = str(semantic_hint.required_tool_query or effective_content).strip()
        semantic_tool_override = True
        continuity_source = "semantic_hint"
    if meta_skill_reference_turn:
        required_tool = None
        required_tool_query = effective_content
        continuity_source = None
    if (
        is_weather_context_followup
        and _tool_registry_has(loop, "weather")
        and required_tool != "weather"
    ):
        grounded_weather_location = ""
        if isinstance(last_tool_context, dict):
            grounded_weather_location = str(last_tool_context.get("location") or "").strip()
        if not grounded_weather_location and pending_followup_source:
            grounded_weather_location = extract_weather_location(pending_followup_source) or ""
        required_tool = "weather"
        required_tool_query = (
            f"{grounded_weather_location} {effective_content}".strip()
            if grounded_weather_location
            else effective_content
        )
        continuity_source = "weather_context"
        semantic_tool_override = True
        logger.info(
            "Weather context follow-up overrode parser tool "
            f"for '{_normalize_text(effective_content)[:120]}'"
        )
    is_non_action_feedback = bool(is_non_action_feedback or semantic_hint.kind == "meta_feedback")
    if (
        is_side_effect_request
        and required_tool
        and required_tool != "save_memory"
        and required_tool == parser_required_tool
        and not parser_required_tool_has_payload
        and not semantic_tool_override
        and not explicit_mcp_tool_routing
        and not meta_skill_reference_turn
        and not is_non_action_feedback
    ):
        logger.info(
            "Side-effect request outranked weak parser tool "
            f"required_tool={required_tool} for '{_normalize_text(effective_content)[:120]}'"
        )
        required_tool = None
        required_tool_query = effective_content
        continuity_source = None
        fast_direct_context = False

    if (
        required_tool
        and pending_followup_tool
        and required_tool == pending_followup_tool
        and pending_followup_source
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
    ):
        enrich_from_pending = bool(
            is_weather_context_followup
            or _is_short_context_followup(effective_content)
            or is_short_confirmation
        )
        if enrich_from_pending:
            try:
                raw_has_payload = _query_has_tool_payload(required_tool, effective_content)
                pending_has_payload = _query_has_tool_payload(required_tool, pending_followup_source)
            except Exception:
                raw_has_payload = False
                pending_has_payload = False
            if pending_has_payload and not raw_has_payload:
                required_tool_query = f"{pending_followup_source} {effective_content}".strip()

    clear_stale_followup_for_new_tool_request = bool(
        required_tool
        and required_tool == parser_required_tool
        and not semantic_tool_override
        and not explicit_mcp_tool_routing
        and pending_followup_tool
        and required_tool != pending_followup_tool
        and not is_short_confirmation
        and not raw_is_short_confirmation
        and not raw_is_contextual_followup_request
        and not is_assistant_offer_context_followup
        and not is_assistant_committed_action_followup
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
    )
    preserve_committed_action_path_hint = bool(
        pending_followup_intent_kind == "assistant_committed_action"
        and required_tool == parser_required_tool == "list_dir"
        and is_explicit_new_request
        and not semantic_tool_override
    )

    if is_closing_ack or is_short_greeting or is_non_action_feedback or semantic_hint.clear_pending:
        _clear_pending_followup_tool(session)
        _clear_pending_followup_intent(session)
    elif (
        (is_explicit_new_request and not preserve_committed_action_path_hint)
        or (
            clear_stale_followup_for_new_tool_request
            and not preserve_committed_action_path_hint
        )
    ):
        # Fresh explicit asks (file/config/path/URL/command-like payload) should
        # not inherit stale pending follow-up state from previous turns, even
        # when the new turn already resolved to a concrete tool.
        _clear_pending_followup_tool(session)
        _clear_pending_followup_intent(session)
        pending_followup_tool = None
        pending_followup_source = ""
        pending_followup_intent = None
        pending_followup_intent_text = ""
        pending_followup_intent_kind = ""
        pending_followup_intent_request_text = ""
        committed_action_request_text = ""

    continuity_candidate_turn = bool(
        not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not is_explicit_new_request
        and (
            raw_is_answer_reference_followup
            or raw_is_short_confirmation
            or raw_is_contextual_followup_request
        )
    )
    parser_required_tool_active = bool(
        required_tool
        and required_tool == parser_required_tool
        and not semantic_tool_override
        and not explicit_mcp_tool_routing
    )
    parser_required_tool_has_payload = False
    if parser_required_tool_active:
        try:
            parser_required_tool_has_payload = _query_has_tool_payload(required_tool, effective_content)
        except Exception:
            parser_required_tool_has_payload = False

    if continuity_candidate_turn:
        continuity_overrode_routing = False
        if (
            raw_is_answer_reference_followup
            and recent_assistant_answer
            and not is_weather_context_followup
            and (not required_tool or (parser_required_tool_active and not parser_required_tool_has_payload))
        ):
            if required_tool:
                logger.info(
                    "Continuity resolver: recent assistant answer outranked weak parser tool "
                    f"for '{_normalize_text(effective_content)[:120]}'"
                )
            required_tool = None
            required_tool_query = effective_content
            continuity_source = "answer_reference"
            continuity_overrode_routing = True
        elif not pending_followup_tool and not pending_followup_intent:
            execution_tool, execution_source = _extract_reusable_last_tool_execution(
                loop,
                last_tool_execution,
            )
            if execution_tool and execution_source:
                required_tool = execution_tool
                required_tool_query = execution_source
                continuity_source = "tool_execution"
                decision.is_complex = True
                continuity_overrode_routing = True
                logger.info(
                    "Continuity resolver: recent tool execution selected "
                    f"required_tool={execution_tool} for '{_normalize_text(effective_content)[:120]}'"
                )
                fast_direct_context = bool(
                    perf_cfg
                    and bool(getattr(perf_cfg, "fast_first_response", True))
                    and required_tool in direct_tools
                )
            elif not required_tool or (parser_required_tool_active and not parser_required_tool_has_payload):
                inferred_tool, inferred_source = _infer_required_tool_from_recent_user_intent(
                    loop,
                    effective_content,
                    conversation_history,
                )
                if inferred_tool:
                    required_tool = inferred_tool
                    required_tool_query = str(inferred_source or required_tool_query or effective_content).strip()
                    continuity_source = "user_intent"
                    decision.is_complex = True
                    continuity_overrode_routing = True
                    logger.info(
                        "Continuity resolver: recent user intent selected "
                        f"required_tool={inferred_tool} for '{_normalize_text(effective_content)[:120]}'"
                    )
                    fast_direct_context = bool(
                        perf_cfg
                        and bool(getattr(perf_cfg, "fast_first_response", True))
                        and required_tool in direct_tools
                    )
        if continuity_overrode_routing:
            is_answer_reference_followup = bool(not required_tool and raw_is_answer_reference_followup)
            is_short_confirmation = bool(not required_tool and raw_is_short_confirmation)
            is_contextual_followup_request = bool(
                not required_tool and raw_is_contextual_followup_request
            )

    user_supplied_option_prompt_text = ""
    if (
        not required_tool
        and not pending_followup_intent
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
    ):
        user_supplied_option_prompt_text = (
            _extract_user_supplied_option_prompt_text(effective_content) or ""
        )
        if user_supplied_option_prompt_text:
            effective_content = (
                "[User-Provided Option Prompt]\n"
                f"{user_supplied_option_prompt_text}\n\n"
                "[Context Note]\n"
                "The text above was written by the user and should be treated as a quoted "
                "option list or draft, not as an assistant message to continue in-character. "
                "Do not choose an option on the user's behalf, and do not auto-pick "
                "the 'best' or most natural-sounding option. Only ask them to choose, "
                "help clarify the options, or explicitly recommend one if they clearly "
                "ask for your recommendation."
            ).strip()

    if (
        not required_tool
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not (
            recent_assistant_answer
            and (raw_is_answer_reference_followup or raw_is_contextual_followup_request)
        )
        and not _looks_like_filesystem_location_query(effective_content)
        and _tool_registry_has(loop, "list_dir")
        and isinstance(last_tool_context, dict)
        and str(last_tool_context.get("tool") or "").strip() == "list_dir"
    ):
        list_dir_followup_path = _extract_list_dir_path(
            effective_content,
            last_tool_context=last_tool_context,
        )
        action_tool_hint, _ = infer_action_required_tool_for_loop(loop, effective_content)
        action_tool_conflict = str(action_tool_hint or "").strip() in {
            "message",
            "read_file",
            "write_file",
            "find_files",
        }
        if list_dir_followup_path and not action_tool_conflict:
            required_tool = "list_dir"
            required_tool_query = effective_content
            decision.is_complex = True
            logger.info(
                f"Filesystem follow-up context: '{_normalize_text(effective_content)}' -> required_tool=list_dir"
            )
            fast_direct_context = bool(
                perf_cfg
                and bool(getattr(perf_cfg, "fast_first_response", True))
                and required_tool in direct_tools
            )

    pure_temporal_context_query = bool(
        _looks_like_temporal_context_query(effective_content)
        and not _looks_like_live_finance_lookup(effective_content)
        and not re.search(
            r"\b(latest|breaking|headline|headlines|news|update)\b",
            _normalize_text(effective_content),
        )
    )
    live_research_latch_active = bool(
        not required_tool
        and _looks_like_live_research_query(effective_content)
        and not pure_temporal_context_query
        and not _should_defer_live_research_latch_to_skill(
            loop,
            effective_content,
            profile=str(decision.profile).upper() or "GENERAL",
            session_metadata=session.metadata if isinstance(getattr(session, "metadata", None), dict) else None,
        )
        and not is_non_action_feedback
    )
    if live_research_latch_active:
        if _tool_registry_has(loop, "web_search"):
            required_tool = "web_search"
            required_tool_query = effective_content
            decision.is_complex = True
            continuity_source = continuity_source or "action_request"
            logger.info(
                f"Live research safety latch: '{_normalize_text(effective_content)[:120]}' -> required_tool=web_search"
            )
            fast_direct_context = bool(
                perf_cfg
                and bool(getattr(perf_cfg, "fast_first_response", True))
                and required_tool in direct_tools
            )
        elif _looks_like_live_finance_lookup(effective_content):
            stock_symbols: list[str] = []
            crypto_ids: list[str] = []
            try:
                stock_symbols = list(extract_stock_symbols(effective_content) or [])
            except Exception:
                stock_symbols = []
            try:
                crypto_ids = list(extract_crypto_ids(effective_content) or [])
            except Exception:
                crypto_ids = []

            if stock_symbols and _tool_registry_has(loop, "stock"):
                required_tool = "stock"
                required_tool_query = effective_content
                decision.is_complex = True
                continuity_source = continuity_source or "action_request"
                logger.info(
                    f"Live finance fallback latch: '{_normalize_text(effective_content)[:120]}' -> required_tool=stock"
                )
                fast_direct_context = bool(
                    perf_cfg
                    and bool(getattr(perf_cfg, "fast_first_response", True))
                    and required_tool in direct_tools
                )
            elif crypto_ids and _tool_registry_has(loop, "crypto"):
                required_tool = "crypto"
                required_tool_query = effective_content
                decision.is_complex = True
                continuity_source = continuity_source or "action_request"
                logger.info(
                    f"Live finance fallback latch: '{_normalize_text(effective_content)[:120]}' -> required_tool=crypto"
                )
                fast_direct_context = bool(
                    perf_cfg
                    and bool(getattr(perf_cfg, "fast_first_response", True))
                    and required_tool in direct_tools
                )
            else:
                decision.is_complex = True
                requires_live_data_honesty_note = True
                logger.info(
                    "Live data honesty latch: "
                    f"'{_normalize_text(effective_content)[:120]}' -> no live tool available"
                )

    web_search_demotion_followup = bool(
        pending_followup_tool == "web_search"
        and _looks_like_web_search_demotion_followup(effective_content)
        and not is_assistant_offer_context_followup
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not is_explicit_new_request
    )
    if web_search_demotion_followup:
        grounded_search_source = str(
            pending_followup_source
            or (last_tool_context.get("source") if isinstance(last_tool_context, dict) else "")
            or effective_content
        ).strip()
        required_tool = None
        required_tool_query = ""
        if grounded_search_source:
            effective_content = (
                f"{effective_content}\n\n"
                "[Follow-up Context]\n"
                f"{grounded_search_source}\n\n"
                "[Knowledge-First Note]\n"
                "The earlier web search path was unavailable or unnecessary for this request. "
                "Answer directly from existing knowledge in the user's language unless they explicitly ask for a different language or style. "
                "Do not call web search again unless the user explicitly asks for live, latest, or verified external information."
            ).strip()
        continuity_source = "knowledge_followup"
        fast_direct_context = bool(
            perf_cfg and bool(getattr(perf_cfg, "fast_first_response", True))
        )
        _clear_pending_followup_tool(session)
        pending_followup_tool = None
        pending_followup_source = ""
        logger.info(
            "Web-search follow-up demotion: "
            f"'{_normalize_text(effective_content)[:120]}' -> complex knowledge route"
        )

    web_source_selection_followup = bool(
        pending_followup_tool == "web_search"
        and _looks_like_web_source_selection_followup(effective_content)
        and not is_assistant_offer_context_followup
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not is_explicit_new_request
        and (_tool_registry_has(loop, "web_search") or _tool_registry_has(loop, "web_fetch"))
    )
    if web_source_selection_followup:
        grounded_search_source = str(
            pending_followup_source
            or (last_tool_context.get("source") if isinstance(last_tool_context, dict) else "")
            or effective_content
        ).strip()
        preferred_fetch_url = _extract_direct_fetch_url_candidate(effective_content)
        constrained_query = _build_source_constrained_web_search_query(
            grounded_search_source,
            effective_content,
        )
        if preferred_fetch_url and _tool_registry_has(loop, "web_fetch"):
            required_tool = "web_fetch"
            required_tool_query = preferred_fetch_url
            continuity_source = "web_source_direct_fetch"
        elif constrained_query and _tool_registry_has(loop, "web_search"):
            required_tool = "web_search"
            required_tool_query = constrained_query
            continuity_source = "web_source_followup"
        if required_tool:
            decision.is_complex = True
            logger.info(
                "Web source follow-up: "
                f"'{_normalize_text(effective_content)[:120]}' -> required_tool={required_tool}"
            )
            fast_direct_context = bool(
                perf_cfg
                and bool(getattr(perf_cfg, "fast_first_response", True))
                and required_tool in direct_tools
            )

    grounded_live_followup_source = str(
        pending_followup_source
        or pending_followup_intent_request_text
        or pending_followup_intent_text
        or (last_tool_context.get("source") if isinstance(last_tool_context, dict) else "")
        or effective_content
    ).strip()
    live_data_refresh_followup = bool(
        not required_tool
        and _looks_like_live_data_refresh_followup(effective_content)
        and not is_assistant_offer_context_followup
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not is_explicit_new_request
        and (
            pending_followup_tool in {"web_search", "stock", "crypto"}
            or (
                grounded_live_followup_source
                and _looks_like_live_research_query(grounded_live_followup_source)
                and (
                    pending_followup_intent is not None
                    or isinstance(last_tool_context, dict)
                )
            )
        )
    )
    if live_data_refresh_followup:
        refresh_query = grounded_live_followup_source
        if refresh_query and effective_content:
            refresh_query = f"{refresh_query} {effective_content}".strip()
        elif effective_content:
            refresh_query = effective_content

        finance_source = grounded_live_followup_source or effective_content
        finance_stock_ids = extract_stock_symbols(finance_source)
        finance_crypto_ids = extract_crypto_ids(finance_source)

        preferred_live_tool = str(pending_followup_tool or "").strip().lower()
        if preferred_live_tool == "web_search" and _tool_registry_has(loop, "web_search"):
            required_tool = "web_search"
            required_tool_query = refresh_query
        elif preferred_live_tool == "stock" and _tool_registry_has(loop, "stock"):
            required_tool = "stock"
            required_tool_query = finance_source
        elif preferred_live_tool == "crypto" and _tool_registry_has(loop, "crypto"):
            required_tool = "crypto"
            required_tool_query = finance_source
        elif _tool_registry_has(loop, "web_search"):
            required_tool = "web_search"
            required_tool_query = refresh_query
        elif finance_stock_ids and _tool_registry_has(loop, "stock"):
            required_tool = "stock"
            required_tool_query = finance_source
        elif finance_crypto_ids and _tool_registry_has(loop, "crypto"):
            required_tool = "crypto"
            required_tool_query = finance_source
        else:
            requires_live_data_honesty_note = True
            if grounded_live_followup_source:
                effective_content = (
                    f"{effective_content}\n\n"
                    "[Live Follow-up Context]\n"
                    f"{grounded_live_followup_source}\n\n"
                    "[Live Data Continuity]\n"
                    "The user is asking for fresher or latest data for the same topic. "
                    "Keep the reply grounded in that earlier live-data request and do not answer from stale memory."
                ).strip()

        decision.is_complex = True
        continuity_source = "live_data_refresh_followup"
        if required_tool:
            logger.info(
                "Live-data refresh follow-up: "
                f"'{_normalize_text(effective_content)[:120]}' -> required_tool={required_tool}"
            )
            fast_direct_context = bool(
                perf_cfg
                and bool(getattr(perf_cfg, "fast_first_response", True))
                and required_tool in direct_tools
            )
        else:
            logger.info(
                "Live-data refresh follow-up: "
                f"'{_normalize_text(effective_content)[:120]}' -> no live tool available"
            )

    if (
        pending_followup_tool
        and _tool_registry_has(loop, pending_followup_tool)
        and not decision.is_complex
        and not required_tool
        and (is_short_confirmation or is_weather_context_followup)
        and not is_assistant_offer_context_followup
        and not is_contextual_followup_request
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not is_explicit_new_request
    ):
        required_tool = pending_followup_tool
        continuity_source = "pending_followup_tool"
        if pending_followup_source:
            if is_weather_context_followup:
                required_tool_query = f"{pending_followup_source} {effective_content}".strip()
            else:
                required_tool_query = pending_followup_source
        decision.is_complex = True
        logger.info(
            f"Session follow-up inference: '{_normalize_text(effective_content)}' -> required_tool={required_tool}"
        )
        fast_direct_context = bool(
            perf_cfg
            and bool(getattr(perf_cfg, "fast_first_response", True))
            and required_tool in direct_tools
        )

    if (
        required_tool == "weather"
        and is_weather_context_followup
        and isinstance(last_tool_context, dict)
    ):
        grounded_weather_location = str(last_tool_context.get("location") or "").strip()
        if grounded_weather_location and not extract_weather_location(str(required_tool_query or "")):
            required_tool_query = f"{grounded_weather_location} {effective_content}".strip()

    # Infer required tool for short follow-ups before context building, so
    # confirmations like "gas"/"ambil sekarang" can take the direct fast path.
    if (
        not decision.is_complex
        and not required_tool
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not is_explicit_new_request
        and not is_assistant_offer_context_followup
        and not is_contextual_followup_request
    ):
        normalized_followup = _normalize_text(effective_content)
        if _looks_like_short_confirmation(normalized_followup):
            inferred_tool = None
            inferred_source = None
            if not pending_followup_tool and not pending_followup_intent:
                inferred_tool, inferred_source = _extract_reusable_last_tool_execution(
                    loop,
                    last_tool_execution,
                )
                if inferred_tool:
                    continuity_source = "tool_execution"
            if not inferred_tool:
                inferred_tool, inferred_source = _infer_required_tool_from_recent_user_intent(
                    loop,
                    effective_content,
                    conversation_history,
                )
                if inferred_tool:
                    continuity_source = "user_intent"
            if inferred_tool:
                required_tool = inferred_tool
                required_tool_query = str(inferred_source or required_tool_query or effective_content).strip()
                decision.is_complex = True
                logger.info(
                    f"Pre-context follow-up inference: '{normalized_followup}' -> required_tool={inferred_tool}"
                )
                fast_direct_context = bool(
                    perf_cfg
                    and bool(getattr(perf_cfg, "fast_first_response", True))
                    and required_tool in direct_tools
                )

    continuity_state = SimpleNamespace(
        loop=loop,
        session=session,
        effective_content=effective_content,
        required_tool=required_tool,
        required_tool_query=required_tool_query,
        continuity_source=continuity_source,
        pending_followup_intent=pending_followup_intent,
        pending_followup_intent_text=pending_followup_intent_text,
        pending_followup_intent_kind=pending_followup_intent_kind,
        pending_followup_intent_request_text=pending_followup_intent_request_text,
        pending_followup_tool=pending_followup_tool,
        pending_followup_source=pending_followup_source,
        committed_action_request_text=committed_action_request_text,
        recent_assistant_answer=recent_assistant_answer,
        raw_is_contextual_followup_request=raw_is_contextual_followup_request,
        raw_is_answer_reference_followup=raw_is_answer_reference_followup,
        is_answer_reference_followup=is_answer_reference_followup,
        is_short_confirmation=is_short_confirmation,
        is_assistant_offer_context_followup=is_assistant_offer_context_followup,
        is_assistant_committed_action_followup=is_assistant_committed_action_followup,
        is_contextual_followup_request=is_contextual_followup_request,
        is_closing_ack=is_closing_ack,
        is_short_greeting=is_short_greeting,
        is_non_action_feedback=is_non_action_feedback,
        is_explicit_new_request=is_explicit_new_request,
        decision=decision,
        perf_cfg=perf_cfg,
        direct_tools=direct_tools,
        fast_direct_context=fast_direct_context,
        recent_answer_target=None,
        recent_answer_option_selection_reference=None,
        recent_answer_referenced_item=None,
    )
    _apply_continuity_runtime(continuity_state)
    effective_content = continuity_state.effective_content
    required_tool = continuity_state.required_tool
    required_tool_query = continuity_state.required_tool_query
    continuity_source = continuity_state.continuity_source
    pending_followup_intent = continuity_state.pending_followup_intent
    pending_followup_intent_text = continuity_state.pending_followup_intent_text
    pending_followup_intent_kind = continuity_state.pending_followup_intent_kind
    pending_followup_intent_request_text = continuity_state.pending_followup_intent_request_text
    pending_followup_tool = continuity_state.pending_followup_tool
    pending_followup_source = continuity_state.pending_followup_source
    committed_action_request_text = continuity_state.committed_action_request_text
    decision = continuity_state.decision
    fast_direct_context = continuity_state.fast_direct_context
    recent_answer_target = continuity_state.recent_answer_target
    recent_answer_option_selection_reference = (
        continuity_state.recent_answer_option_selection_reference
    )
    recent_answer_referenced_item = continuity_state.recent_answer_referenced_item

    current_skill_flow = _get_skill_creation_flow(session, now_ts)
    current_skill_flow_kind = str((current_skill_flow or {}).get("kind") or "create").strip().lower() or "create"
    recent_created_skill_name = _infer_recent_created_skill_name_from_path(
        recent_history_file_path
    )
    existing_created_skill_followup = bool(
        current_skill_flow
        and str((current_skill_flow or {}).get("stage") or "").strip().lower() == "approved"
        and recent_created_skill_name
        and _looks_like_existing_skill_use_followup(
            msg.content,
            assistant_offer_text=pending_followup_intent_text,
        )
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not is_explicit_new_request
    )
    skill_workflow_detail_followup = bool(
        current_skill_flow
        and _looks_like_skill_workflow_followup_detail(msg.content)
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
    )
    skill_creation_followup = bool(
        current_skill_flow
        and current_skill_flow_kind != "install"
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and (
            skill_workflow_detail_followup
            or (
                not is_explicit_new_request
                and (
                    is_short_confirmation
                    or _looks_like_skill_creation_approval(msg.content)
                )
            )
        )
    )
    skill_install_followup = bool(
        current_skill_flow
        and current_skill_flow_kind == "install"
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and (
            skill_workflow_detail_followup
            or (
                not is_explicit_new_request
                and (
                    is_short_confirmation
                    or _looks_like_skill_creation_approval(msg.content)
                )
            )
        )
    )
    skill_creation_intent = bool(
        looks_like_skill_creation_request(effective_content) or skill_creation_followup
    )
    skill_install_intent = bool(
        looks_like_skill_install_request(effective_content) or skill_install_followup
    )
    if skill_install_intent:
        skill_creation_intent = False
    forced_skill_names: list[str] | None = None
    external_skill_lane = False
    llm_current_message = effective_content
    if is_non_action_feedback:
        llm_current_message = (
            f"{llm_current_message}\n\n"
            "[Feedback Note]\n"
            "The user appears frustrated with the previous answer. Acknowledge "
            "that briefly, do not joke or restart the conversation, and then "
            "clarify or restate the most recent answer more directly in the "
            "same factual style, in the user's language unless they explicitly ask for a different language."
        )
    if requires_live_data_honesty_note:
        llm_current_message = (
            f"{llm_current_message}\n\n"
            "[Live Data Constraint Note]\n"
            "- The user is asking for fresh or current information.\n"
            "- Do not guess a latest price, quote, date, headline, or live value from memory.\n"
            "- If a live web or finance tool is unavailable, blocked, or rate-limited, say that plainly.\n"
            "- Offer the next best grounded path: exact URL for web_fetch, screenshot, pasted number, or enabling web search."
        )
    filesystem_location_context_note = ""
    session_continuity_action_note = ""
    grounded_filesystem_inspection_note = ""
    explicit_file_analysis_note = ""
    mcp_context_note = ""
    requires_grounded_filesystem_inspection = False
    file_analysis_path = ""
    coding_build_request = False
    skill_creation_stage = str((current_skill_flow or {}).get("stage") or "discovery").strip().lower() or "discovery"
    skill_workflow_kind = "install" if skill_install_intent else current_skill_flow_kind
    skill_creation_request_text = str((current_skill_flow or {}).get("request_text") or effective_content).strip()
    skill_creation_approved = skill_creation_stage == "approved"
    if existing_created_skill_followup:
        existing_skill_required_tool_query = (
            str(pending_followup_intent_text or "").strip()
            or str(pending_followup_intent_request_text or "").strip()
            or str(effective_content or "").strip()
        )
        inferred_existing_skill_tool = None
        if existing_skill_required_tool_query:
            try:
                inferred_existing_skill_tool = loop._required_tool_for_query(
                    existing_skill_required_tool_query
                )
            except Exception:
                inferred_existing_skill_tool = None
        required_tool = None
        required_tool_query = ""
        skill_creation_intent = False
        skill_install_intent = False
        forced_skill_names = [recent_created_skill_name]
        if inferred_existing_skill_tool:
            required_tool = str(inferred_existing_skill_tool).strip() or None
            required_tool_query = existing_skill_required_tool_query
        if existing_skill_required_tool_query:
            intent_source_for_followup = existing_skill_required_tool_query
            pending_followup_intent_request_text = existing_skill_required_tool_query
            committed_action_request_text = existing_skill_required_tool_query
        continuity_source = "existing_skill_followup"
        llm_current_message = (
            f"{effective_content}\n\n"
            "[Existing Skill Note]\n"
            f"- The skill `{recent_created_skill_name}` was already created earlier in this conversation.\n"
            "- Do not restart the skill-creator workflow.\n"
            "- Load and follow that existing skill now.\n"
            "- Use that existing skill now for the user's current request and recent follow-up context."
        ).strip()
        if not decision.is_complex:
            decision.is_complex = True
            logger.info(
                "Existing skill follow-up latch: "
                f"'{_normalize_text(effective_content)[:120]}' -> complex route via skill={recent_created_skill_name}"
            )
        _clear_skill_creation_flow(session)
    if skill_creation_intent or skill_install_intent:
        # Skill workflows must outrank deterministic tool routing; otherwise
        # ordinary domain words like "weather" or repo-like text can hijack
        # create/update/install requests into stock/weather direct tools.
        required_tool = None
        required_tool_query = ""
        if (skill_creation_followup or skill_install_followup) and current_skill_flow:
            skill_creation_request_text = str(current_skill_flow.get("request_text") or skill_creation_request_text).strip()
            effective_content = (
                f"{effective_content}\n\n[Follow-up Context]\n{skill_creation_request_text}"
                if skill_creation_request_text and "[Follow-up Context]" not in effective_content
                else effective_content
            )
        if skill_creation_stage == "planning" and _looks_like_skill_creation_approval(msg.content):
            skill_creation_stage = "approved"
            skill_creation_approved = True
        if not decision.is_complex:
            decision.is_complex = True
            logger.info(
                f"Skill workflow latch: '{_normalize_text(effective_content)[:120]}' -> complex route"
            )
        forced_skill_names = ["skill-installer"] if skill_install_intent else ["skill-creator"]
        first_turn = "[Follow-up Context]" not in effective_content
        llm_current_message = (
            f"{effective_content}\n\n{_build_skill_creation_workflow_note(first_turn=first_turn, approved=skill_creation_approved, kind=skill_workflow_kind)}"
        ).strip()
        _set_skill_creation_flow(
            session,
            skill_creation_request_text,
            now_ts,
            stage=skill_creation_stage,
            kind=skill_workflow_kind,
        )
    elif current_skill_flow and is_explicit_new_request and not skill_workflow_detail_followup:
        _clear_skill_creation_flow(session)

    unavailable_required_tool = str(required_tool or "").strip()
    tool_registry_known = False
    unavailable_by_registry = False
    if unavailable_required_tool and not unavailable_required_tool.startswith("mcp__"):
        tools_obj = getattr(loop, "tools", None)
        has_callable = getattr(tools_obj, "has", None)
        if callable(has_callable):
            try:
                tool_registry_known = True
                unavailable_by_registry = not bool(has_callable(unavailable_required_tool))
            except Exception:
                tool_registry_known = False
                unavailable_by_registry = False
        else:
            tool_names = getattr(tools_obj, "tool_names", None)
            if isinstance(tool_names, list) and len(tool_names) > 0:
                tool_registry_known = True
                unavailable_by_registry = unavailable_required_tool not in {
                    str(name).strip() for name in tool_names if str(name or "").strip()
                }

    if unavailable_required_tool and tool_registry_known and unavailable_by_registry:
        logger.info(
            "Dropping unavailable required tool route "
            f"required_tool={unavailable_required_tool} for '{_normalize_text(effective_content)[:120]}'"
        )
        required_tool = None
        required_tool_query = effective_content
        continuity_source = None
        if pending_followup_tool == unavailable_required_tool:
            _clear_pending_followup_tool(session)
            pending_followup_tool = None
            pending_followup_source = ""

    session_metadata = getattr(session, "metadata", None)
    persisted_external_skills: list[str] = []
    if isinstance(session_metadata, dict):
        raw_persisted_skills = session_metadata.get("forced_skill_names")
        if isinstance(raw_persisted_skills, (list, tuple, set)):
            persisted_external_skills = [
                normalized
                for normalized in (
                    normalize_skill_reference_name(str(skill_name or ""))
                    for skill_name in raw_persisted_skills
                )
                if normalized
            ]
    context_builder = None
    skills_loader = None
    match_skill_details = None
    matched_skill_details: list[dict[str, Any]] = []
    should_probe_external_skills = bool(
        not skill_creation_intent
        and not skill_install_intent
        and not meta_skill_reference_turn
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and (
            not forced_skill_names
            or (
                isinstance(session_metadata, dict)
                and bool(session_metadata.get("external_skill_lane"))
                and persisted_external_skills
            )
        )
    )
    if should_probe_external_skills:
        context_builder = getattr(loop, "context", None)
        resolve_context = getattr(loop, "_resolve_context_for_message", None)
        if callable(resolve_context):
            try:
                resolved_context = resolve_context(msg)
                if resolved_context is not None:
                    context_builder = resolved_context
            except Exception as exc:
                logger.debug(f"Failed resolving context builder for skill execution latch: {exc}")
        skills_loader = getattr(context_builder, "skills", None)
        match_skill_details = getattr(skills_loader, "match_skill_details", None)
        if callable(match_skill_details):
            try:
                matched_skill_details = list(
                    match_skill_details(
                        effective_content,
                        profile=str(decision.profile or "GENERAL"),
                        max_results=3,
                        filter_unavailable=False,
                    )
                    or []
                )
            except TypeError:
                try:
                    matched_skill_details = list(
                        match_skill_details(effective_content) or []
                    )
                except Exception as exc:
                    logger.debug(f"External skill execution latch failed: {exc}")
            except Exception as exc:
                logger.debug(f"External skill execution latch failed: {exc}")

    persisted_external_skill_matches_current_turn = False
    if persisted_external_skills and matched_skill_details:
        persisted_skill_names = set(persisted_external_skills)
        for detail in matched_skill_details:
            if not isinstance(detail, dict):
                continue
            source = str(detail.get("source") or "").strip().lower()
            skill_name = normalize_skill_reference_name(str(detail.get("name") or ""))
            if not skill_name or not source or source == "builtin":
                continue
            if skill_name in persisted_skill_names:
                persisted_external_skill_matches_current_turn = True
                break

    should_rehydrate_external_skill_lane = bool(
        not forced_skill_names
        and isinstance(session_metadata, dict)
        and bool(session_metadata.get("external_skill_lane"))
        and persisted_external_skills
        and not skill_creation_intent
        and not skill_install_intent
        and not meta_skill_reference_turn
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and (
            (
                not is_explicit_new_request
                and (
                    raw_is_contextual_followup_request
                    or _is_short_context_followup(effective_content)
                    or pending_followup_tool == "web_search"
                    or _looks_like_web_source_selection_followup(effective_content)
                    or _looks_like_web_search_demotion_followup(effective_content)
                )
            )
            or persisted_external_skill_matches_current_turn
        )
    )
    if should_rehydrate_external_skill_lane:
        forced_skill_names = list(dict.fromkeys(persisted_external_skills))
        external_skill_lane = True
        llm_current_message = (
            f"{llm_current_message}\n\n"
            "[External Skill Continuity Note]\n"
            f"- Continue using the active external skill lane: {', '.join(forced_skill_names)}.\n"
            "- Treat this turn as a follow-up to the same skill workflow unless the user clearly changes topic.\n"
            "- Load/follow that skill now and keep its `references/` and bundled `scripts/` as the source of truth."
        ).strip()
        continuity_source = continuity_source or "external_skill_followup"
        if not decision.is_complex:
            decision.is_complex = True
        logger.info(
            "External skill continuity latch: "
            f"'{_normalize_text(effective_content)[:120]}' -> skills={','.join(forced_skill_names)}"
        )

    if (
        not forced_skill_names
        and not skill_creation_intent
        and not skill_install_intent
        and not meta_skill_reference_turn
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
    ):
        format_skill_unavailability = getattr(skills_loader, "_format_skill_unavailability", None)
        eligible_skill_matches: list[dict[str, str]] = []
        eligible_external_matches: list[dict[str, str]] = []
        unavailable_external_matches: list[dict[str, str]] = []
        for detail in matched_skill_details:
            if not isinstance(detail, dict):
                continue
            skill_name = normalize_skill_reference_name(str(detail.get("name") or ""))
            source = str(detail.get("source") or "").strip().lower()
            if not skill_name or not source or source == "builtin":
                if skill_name and source and bool(detail.get("eligible")):
                    eligible_skill_matches.append(
                        {
                            "name": skill_name,
                            "source": source,
                            "description": str(detail.get("description") or "").strip(),
                            "adapt_grounded_diagnostics": bool(
                                detail.get("adapt_grounded_diagnostics")
                            ),
                        }
                    )
                continue
            if bool(detail.get("eligible")):
                skill_summary = {
                    "name": skill_name,
                    "source": source,
                    "description": str(detail.get("description") or "").strip(),
                    "adapt_grounded_diagnostics": bool(
                        detail.get("adapt_grounded_diagnostics")
                    ),
                }
                eligible_skill_matches.append(skill_summary)
                eligible_external_matches.append(
                    {
                        "name": skill_summary["name"],
                        "source": skill_summary["source"],
                        "description": skill_summary["description"],
                    }
                )
                continue

            missing_reason = ""
            if callable(format_skill_unavailability):
                try:
                    missing_reason = str(format_skill_unavailability(detail) or "").strip()
                except Exception:
                    missing_reason = ""
            if not missing_reason:
                missing_reason = "requirements not met"
            install_hint = ""
            install_options = detail.get("install", [])
            if isinstance(install_options, list) and install_options:
                first_option = install_options[0] if isinstance(install_options[0], dict) else {}
                install_hint = (
                    str(first_option.get("label", "")).strip()
                    or str(first_option.get("cmd", "")).strip()
                )
            unavailable_external_matches.append(
                {
                    "name": skill_name,
                    "source": source,
                    "description": str(detail.get("description") or "").strip(),
                    "missing_reason": missing_reason,
                    "install_hint": install_hint,
                }
            )

        if len(eligible_external_matches) == 1 and explicit_skill_use_request:
            primary_skill = eligible_external_matches[0]
            forced_skill_names = [primary_skill["name"]]
            external_skill_lane = True
            llm_current_message = (
                f"{llm_current_message}\n\n"
                "[External Skill Note]\n"
                f"- The installed external skill `{primary_skill['name']}` is the best match for this request.\n"
                "- Load and follow that skill first.\n"
                "- Prefer the skill workflow over generic fallback behavior.\n"
                "- Treat the skill's `references/` docs and bundled `scripts/` as the primary source of truth for endpoint and execution details.\n"
                "- Read only the relevant reference files, and prefer running bundled scripts over improvising generic endpoint guesses.\n"
                "- If `web_search` is unavailable, keep going with the skill's `references/`, bundled `scripts/`, direct `web_fetch`, or grounded `exec` workflow instead of stopping on missing search credentials.\n"
                "- If the skill still needs credentials or setup, explain that briefly and ask only for the missing requirement."
            ).strip()
            if not decision.is_complex:
                decision.is_complex = True
            logger.info(
                "External skill execution latch: "
                f"'{_normalize_text(effective_content)[:120]}' -> skill={primary_skill['name']}"
            )
        elif len(unavailable_external_matches) == 1 and explicit_skill_use_request:
            primary_skill = unavailable_external_matches[0]
            forced_skill_names = [primary_skill["name"]]
            external_skill_lane = True
            setup_note_lines = [
                "[External Skill Setup Note]",
                f"- The installed external skill `{primary_skill['name']}` is the best match for this request, but it is not executable yet.",
                f"- Missing requirements: {primary_skill['missing_reason']}.",
                "- Stay on this skill lane first instead of silently falling back to generic legacy behavior.",
                "- Explain the missing setup briefly and ask only for the next concrete requirement the user can provide or fix now.",
            ]
            if primary_skill["install_hint"]:
                setup_note_lines.append(f"- Helpful install/setup hint: {primary_skill['install_hint']}")
            llm_current_message = f"{llm_current_message}\n\n" + "\n".join(setup_note_lines)
            llm_current_message = llm_current_message.strip()
            if not decision.is_complex:
                decision.is_complex = True
            continuity_source = continuity_source or "external_skill_setup"
            logger.info(
                "External skill setup latch: "
                f"'{_normalize_text(effective_content)[:120]}' -> skill={primary_skill['name']} "
                f"missing={primary_skill['missing_reason']}"
            )

        primary_unavailable_skill = (
            unavailable_external_matches[0] if len(unavailable_external_matches) == 1 else None
        )
        single_unavailable_skill_prefers_grounded_diagnostics = bool(
            primary_unavailable_skill
            and bool(primary_unavailable_skill.get("adapt_grounded_diagnostics"))
            and bool(getattr(decision, "is_complex", False))
            and str(getattr(decision, "turn_category", "") or "").strip().lower()
            in {"action", "contextual_action", "command"}
        )
        single_unavailable_external_action_workflow = bool(
            primary_unavailable_skill
            and str(primary_unavailable_skill.get("source") or "").strip().lower() != "builtin"
            and str(getattr(decision, "turn_category", "") or "").strip().lower()
            in {"action", "contextual_action", "command"}
            and not looks_like_meta_skill_or_workflow_prompt(effective_content)
        )
        auto_external_setup_turn = bool(
            not forced_skill_names
            and not required_tool
            and not explicit_skill_use_request
            and primary_unavailable_skill is not None
            and str(primary_unavailable_skill.get("source") or "").strip().lower() != "builtin"
            and not looks_like_meta_skill_or_workflow_prompt(effective_content)
            and (
                _looks_like_live_research_query(effective_content)
                or route_grounding_mode == "filesystem_inspection"
                or str(decision.profile or "").strip().upper() in {"CODING", "RESEARCH"}
                or single_unavailable_skill_prefers_grounded_diagnostics
                or single_unavailable_external_action_workflow
            )
        )
        if auto_external_setup_turn:
            forced_skill_names = [str(primary_unavailable_skill["name"])]
            external_skill_lane = True
            setup_note_lines = [
                "[External Skill Setup Note]",
                f"- The installed external skill `{primary_unavailable_skill['name']}` is the clearest workflow match for this request, but it is not executable yet.",
                f"- Missing requirements: {primary_unavailable_skill['missing_reason']}.",
                "- Stay on this skill lane first instead of silently falling back to generic legacy behavior.",
                "- Explain the missing setup briefly and continue from the next grounded requirement, script, credential, or binary the user needs for this skill.",
            ]
            if primary_unavailable_skill["install_hint"]:
                setup_note_lines.append(
                    f"- Helpful install/setup hint: {primary_unavailable_skill['install_hint']}"
                )
            llm_current_message = f"{llm_current_message}\n\n" + "\n".join(setup_note_lines)
            llm_current_message = llm_current_message.strip()
            if not decision.is_complex:
                decision.is_complex = True
            continuity_source = continuity_source or "external_skill_setup"
            logger.info(
                "External skill auto-setup latch: "
                f"'{_normalize_text(effective_content)[:120]}' -> skill={primary_unavailable_skill['name']} "
                f"missing={primary_unavailable_skill['missing_reason']}"
            )

        primary_skill = eligible_skill_matches[0] if len(eligible_skill_matches) == 1 else None
        single_skill_is_grounded_weather = bool(
            primary_skill
            and str(primary_skill.get("name") or "").strip().lower() == "weather"
            and not raw_is_contextual_followup_request
            and not is_answer_reference_followup
        )
        single_skill_is_creator_workflow = bool(
            primary_skill
            and str(primary_skill.get("name") or "").strip().lower() == "skill-creator"
            and str(getattr(decision, "turn_category", "") or "").strip().lower()
            in {"action", "contextual_action", "command"}
            and not looks_like_meta_skill_or_workflow_prompt(effective_content)
        )
        single_skill_prefers_grounded_diagnostics = bool(
            primary_skill
            and bool(primary_skill.get("adapt_grounded_diagnostics"))
            and bool(getattr(decision, "is_complex", False))
            and str(getattr(decision, "turn_category", "") or "").strip().lower()
            in {"action", "contextual_action", "command"}
        )
        if single_skill_is_creator_workflow:
            required_tool = None
            required_tool_query = ""
            skill_creation_intent = True
            skill_install_intent = False
            forced_skill_names = ["skill-creator"]
            llm_current_message = (
                f"{effective_content}\n\n"
                f"{_build_skill_creation_workflow_note(first_turn=True, approved=False, kind='create')}"
            ).strip()
            _set_skill_creation_flow(
                session,
                skill_creation_request_text,
                now_ts,
                stage=skill_creation_stage,
                kind="create",
            )
            continuity_source = continuity_source or "skill_creator_adaptation"
            if not decision.is_complex:
                decision.is_complex = True
            logger.info(
                "Skill-creator adaptation latch: "
                f"'{_normalize_text(effective_content)[:120]}' -> workflow=skill-creator"
            )
        single_external_action_workflow = bool(
            primary_skill
            and str(primary_skill.get("source") or "").strip().lower() != "builtin"
            and str(getattr(decision, "turn_category", "") or "").strip().lower()
            in {"action", "contextual_action", "command"}
            and not looks_like_meta_skill_or_workflow_prompt(effective_content)
        )
        auto_skill_adaptation_turn = bool(
            not forced_skill_names
            and not skill_creation_intent
            and not skill_install_intent
            and not required_tool
            and not explicit_skill_use_request
            and primary_skill is not None
            and (
                _looks_like_live_research_query(effective_content)
                or route_grounding_mode == "filesystem_inspection"
                or str(decision.profile or "").strip().upper() in {"CODING", "RESEARCH"}
                or single_skill_is_grounded_weather
                or single_skill_prefers_grounded_diagnostics
                or single_external_action_workflow
            )
        )
        if auto_skill_adaptation_turn:
            diagnostics_note = ""
            if single_skill_prefers_grounded_diagnostics:
                diagnostics_note = (
                    "- This is a grounded diagnostics/config turn: inspect the real config, "
                    "status output, logs, and other local evidence before suggesting changes.\n"
                )
            forced_skill_names = [primary_skill["name"]]
            external_skill_lane = primary_skill["source"] != "builtin"
            llm_current_message = (
                f"{llm_current_message}\n\n"
                "[Skill Adaptation Note]\n"
                f"- The installed skill `{primary_skill['name']}` is the clearest workflow match for this request.\n"
                "- Adapt to that skill before answering normally.\n"
                "- Read its SKILL.md first, then follow its workflow.\n"
                f"{diagnostics_note}"
                "- Use the skill's `references/`, bundled `scripts/`, grounded tools, or live-web steps before giving a generic text answer.\n"
                "- If the skill still requires a concrete tool, URL, or credential after reading it, say that briefly and continue from the grounded next step."
            ).strip()
            continuity_source = continuity_source or (
                "external_skill_adaptation" if external_skill_lane else "skill_adaptation"
            )
            if not decision.is_complex:
                decision.is_complex = True
            logger.info(
                "Skill adaptation latch: "
                f"'{_normalize_text(effective_content)[:120]}' -> skill={primary_skill['name']}"
            )

    if (
        required_tool == "weather"
        and not skill_creation_intent
        and not skill_install_intent
        and _tool_registry_has(loop, "weather")
    ):
        forced_skill_names = list(dict.fromkeys([*(forced_skill_names or []), "weather"]))
        grounded_weather_text = str(
            required_tool_query
            or pending_followup_source
            or pending_followup_intent_text
            or effective_content
        ).strip()
        grounded_weather_location = (
            extract_weather_location(grounded_weather_text)
            or extract_weather_location(pending_followup_source)
            or extract_weather_location(effective_content)
        )
        weather_skill_note = (
            "[Weather Skill Note]\n"
            "- Treat this turn as a grounded weather or forecast request.\n"
            "- Reuse the last grounded weather location when the user follow-up omits it.\n"
            "- Never invent a new city or region. If no location can be grounded, ask briefly for one."
        )
        if grounded_weather_location:
            weather_skill_note += f"\n- Grounded weather location: {grounded_weather_location}"
        if "[Weather Skill Note]" not in llm_current_message:
            llm_current_message = f"{llm_current_message}\n\n{weather_skill_note}".strip()

    if (
        is_side_effect_request
        and not skill_creation_intent
        and not skill_install_intent
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
    ):
        action_required_tool, action_required_tool_query = infer_action_required_tool_for_loop(
            loop,
            effective_content,
        )
        if action_required_tool:
            find_then_send_workflow = bool(
                action_required_tool == "find_files"
                and _tool_registry_has(loop, "find_files")
                and _tool_registry_has(loop, "message")
                and (
                    _looks_like_message_delivery_request(effective_content)
                    or _looks_like_message_delivery_request(intent_source_for_followup)
                )
            )
            weak_parser_action_override = bool(
                required_tool
                and required_tool == parser_required_tool
                and action_required_tool != required_tool
                and required_tool in {"read_file", "list_dir", "web_search"}
                and not semantic_tool_override
                and not explicit_mcp_tool_routing
                and not meta_skill_reference_turn
            )
            if find_then_send_workflow:
                continuity_source = continuity_source or "action_request"
                if not decision.is_complex:
                    decision.is_complex = True
                logger.info(
                    "Action-request workflow inference: "
                    f"'{_normalize_text(effective_content)[:120]}' -> workflow=find_files->message"
                )
            elif not required_tool or weak_parser_action_override:
                required_tool = action_required_tool
                required_tool_query = str(action_required_tool_query or effective_content).strip()
                continuity_source = "action_request" if weak_parser_action_override else (continuity_source or "action_request")
                if not decision.is_complex:
                    decision.is_complex = True
                logger.info(
                    "Action-request tool inference: "
                    f"'{_normalize_text(effective_content)[:120]}' -> required_tool={required_tool}"
                )
            elif (
                action_required_tool == required_tool
                and required_tool == parser_required_tool
                and continuity_source in {None, "parser"}
            ):
                continuity_source = "action_request"

    if (
        not required_tool
        and not skill_creation_intent
        and not skill_install_intent
        and is_side_effect_request
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and _looks_like_coding_build_request(
            effective_content,
            route_profile=str(decision.profile),
        )
    ):
        coding_build_request = True
        decision.profile = "CODING"
        decision.is_complex = True
        committed_action_request_text = committed_action_request_text or intent_source_for_followup
        continuity_source = continuity_source or "coding_request"
        logger.info(
            "Coding-build request latch: "
            f"'{_normalize_text(effective_content)[:120]}' -> profile=CODING"
        )

    if (
        not required_tool
        and not skill_creation_intent
        and not skill_install_intent
        and is_side_effect_request
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not coding_build_request
    ):
        if not decision.is_complex:
            decision.is_complex = True
            logger.info(
                "Side-effect request latch: "
                f"'{_normalize_text(effective_content)[:120]}' -> complex route"
            )
        committed_action_request_text = committed_action_request_text or intent_source_for_followup
        continuity_source = continuity_source or "action_request"

    if not skill_creation_intent and not skill_install_intent:
        if continuity_source == "action_request" and "[Immediate Action Note]" not in llm_current_message:
            llm_current_message = (
                f"{effective_content}\n\n"
                "[Immediate Action Note]\n"
                "The user is asking for a concrete artifact, side effect, or generated output now. "
                "Use the appropriate tools or skills immediately, verify the result before claiming "
                "success, and do not stop at a plan, placeholder, or guessed completion message."
            )
        elif (
            continuity_source in {"coding_request", "committed_coding_action"}
            and "[Coding Build Note]" not in llm_current_message
        ):
            llm_current_message = (
                f"{effective_content}\n\n"
                "[Coding Build Note]\n"
                "The user is asking for real software build work now. Treat this as a coding task: "
                "understand the existing chat context, plan briefly when needed, then execute with "
                "real tools or approved skills. If the request already gives a concrete brand/theme/"
                "deliverable, do not bounce back into a separate discovery or approval round unless "
                "a real blocker remains. Do not stop at a mockup, placeholder, or guessed completion "
                "message, and do not claim delivery unless the result was actually sent."
            )

    relevant_memory_facts = await _resolve_relevant_memory_facts(
        loop,
        session=session,
        session_key=msg.session_key,
        text=effective_content,
        limit=3,
    )
    if relevant_memory_facts and not required_tool:
        memory_note_lines = "\n".join(f"- {fact}" for fact in relevant_memory_facts)
        llm_current_message = (
            f"{llm_current_message}\n\n"
            "[Relevant Memory Facts]\n"
            f"{memory_note_lines}\n\n"
            "[Memory Recall Note]\n"
            "The user is explicitly asking to recall stored information. Prefer the "
            "memory facts above over stale parser guesses or leftover tool context unless "
            "the user clearly asks for a fresh tool action."
        )

    learned_execution_hints = get_learned_execution_hints(
        loop,
        effective_content,
        required_tool=required_tool,
        limit=3,
    )
    if learned_execution_hints and (required_tool or decision.is_complex):
        learned_hint_lines = "\n".join(f"- {hint}" for hint in learned_execution_hints)
        llm_current_message = (
            f"{llm_current_message}\n\n"
            "[Learned Execution Hints]\n"
            f"{learned_hint_lines}\n\n"
            "[Learned Hint Note]\n"
            "These hints come from previous verified fixes or retries. Use them as bounded "
            "execution guidance, but explicit user intent and real tool evidence always win."
        )

    if (
        not required_tool
        and not skill_creation_intent
        and not skill_install_intent
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
    ):
        continuity_note_candidate = _build_session_continuity_action_note(
            loop,
            session,
            last_tool_context=last_tool_context,
            pending_followup_tool=pending_followup_tool,
            pending_followup_source=pending_followup_source,
            recent_file_path=recent_history_file_path,
        )
        should_apply_continuity_note = bool(
            continuity_note_candidate
            and (
                route_turn_category in {"action", "contextual_action"}
                or raw_is_contextual_followup_request
                or raw_is_short_confirmation
                or is_file_context_followup
                or bool(pending_followup_tool)
                or pending_followup_intent_kind in {"assistant_offer", "assistant_committed_action"}
            )
        )
        if should_apply_continuity_note:
            session_continuity_action_note = continuity_note_candidate
            llm_current_message = (
                f"{llm_current_message}\n\n{session_continuity_action_note}"
            ).strip()

        should_apply_grounded_filesystem_inspection = bool(
            route_grounding_mode == "filesystem_inspection"
            and route_turn_category in {"action", "contextual_action"}
        )
        if should_apply_grounded_filesystem_inspection:
            inspection_note_candidate = _build_grounded_filesystem_inspection_note(
                loop,
                session,
                last_tool_context=last_tool_context,
                recent_file_path=recent_history_file_path,
            )
            if inspection_note_candidate:
                grounded_filesystem_inspection_note = inspection_note_candidate
                llm_current_message = (
                    f"{llm_current_message}\n\n{grounded_filesystem_inspection_note}"
                ).strip()
                requires_grounded_filesystem_inspection = True

    if (
        not required_tool
        and not skill_creation_intent
        and not skill_install_intent
        and _looks_like_temporal_context_query(effective_content)
    ):
        temporal_context_note = _build_temporal_context_note()
        llm_current_message = f"{effective_content}\n\n{temporal_context_note}".strip()
    elif (
        not required_tool
        and not skill_creation_intent
        and not skill_install_intent
        and _looks_like_filesystem_location_query(effective_content)
    ):
        filesystem_location_context_note = _build_filesystem_location_context_note(loop, session, last_tool_context)
        if filesystem_location_context_note:
            llm_current_message = f"{effective_content}\n\n{filesystem_location_context_note}".strip()
    elif not required_tool and not skill_creation_intent and not skill_install_intent:
        explicit_mcp_prompt_ref = _extract_explicit_mcp_prompt_reference(effective_content)
        explicit_mcp_resource_ref = _extract_explicit_mcp_resource_reference(effective_content)
        if explicit_mcp_prompt_ref or explicit_mcp_resource_ref:
            build_mcp_context = getattr(loop, "_build_explicit_mcp_context_note", None)
            if callable(build_mcp_context):
                try:
                    mcp_context_note = (
                        await build_mcp_context(
                            msg.session_key,
                            prompt_ref=explicit_mcp_prompt_ref,
                            resource_ref=explicit_mcp_resource_ref,
                        )
                        or ""
                    )
                except Exception as exc:
                    logger.warning(f"Failed to build explicit MCP context note: {exc}")
            if mcp_context_note:
                llm_current_message = f"{effective_content}\n\n{mcp_context_note}".strip()

        if not mcp_context_note:
            explicit_file_path = _extract_read_file_path(intent_source_for_followup)
            if explicit_file_path and not is_side_effect_request:
                file_analysis_path = explicit_file_path
                explicit_file_analysis_note = _build_explicit_file_analysis_note(explicit_file_path)
                if explicit_file_analysis_note:
                    llm_current_message = f"{effective_content}\n\n{explicit_file_analysis_note}".strip()
            elif is_file_context_followup:
                last_file_path = str((last_tool_context or {}).get("path") or "").strip()
                if not last_file_path:
                    last_file_path = recent_history_file_path
                if last_file_path:
                    file_analysis_path = last_file_path
                    explicit_file_analysis_note = _build_explicit_file_analysis_note(last_file_path)
                    if explicit_file_analysis_note:
                        llm_current_message = f"{effective_content}\n\n{explicit_file_analysis_note}".strip()

        if (
            explicit_file_analysis_note
            and file_analysis_path
            and _tool_registry_has(loop, "read_file")
        ):
            required_tool = "read_file"
            required_tool_query = file_analysis_path
            decision.is_complex = True
            requires_grounded_filesystem_inspection = False

    if required_tool:
        _set_pending_followup_tool(session, required_tool, now_ts, str(required_tool_query or effective_content))
        _set_last_tool_context(session, required_tool, now_ts, str(required_tool_query or effective_content))
    elif explicit_file_analysis_note and _extract_read_file_path(llm_current_message):
        _set_last_tool_context(session, "read_file", now_ts, llm_current_message)
    elif explicit_file_analysis_note and is_file_context_followup:
        history_file_path = recent_history_file_path
        if history_file_path:
            _set_last_tool_context(session, "read_file", now_ts, history_file_path)
    elif not is_short_confirmation:
        _clear_pending_followup_tool(session)

    if _should_store_followup_intent(
        intent_source_for_followup,
        required_tool=required_tool,
        decision_profile=str(decision.profile),
        decision_is_complex=bool(decision.is_complex),
    ):
        existing_pending_intent = (
            session.metadata.get("pending_followup_intent")
            if isinstance(getattr(session, "metadata", None), dict)
            else None
        )
        existing_pending_kind = (
            str((existing_pending_intent or {}).get("kind") or "").strip().lower()
        )
        existing_pending_request_text = str(
            (existing_pending_intent or {}).get("request_text") or ""
        ).strip()
        followup_intent_text = str(intent_source_for_followup or "").strip()
        followup_request_hint = str(required_tool_query or followup_intent_text or effective_content).strip()
        followup_explicit_path = _extract_read_file_path(followup_request_hint)
        message_send_request_followup = bool(
            required_tool == "message"
            and _looks_like_message_send_file_request(
                followup_request_hint,
                explicit_path=followup_explicit_path,
            )
        )
        preserved_pending_kind = (
            existing_pending_kind if existing_pending_kind == "assistant_committed_action" else None
        )
        preserved_pending_request_text = (
            existing_pending_request_text if preserved_pending_kind else None
        )
        if message_send_request_followup:
            preserved_pending_kind = "assistant_committed_action"
            preserved_pending_request_text = followup_request_hint
        _set_pending_followup_intent(
            session,
            intent_source_for_followup,
            str(decision.profile),
            now_ts,
            kind=preserved_pending_kind,
            request_text=preserved_pending_request_text,
        )
    elif not _looks_like_short_confirmation(intent_source_for_followup):
        _clear_pending_followup_intent(session)

    metadata_state = SimpleNamespace(
        loop=loop,
        session=session,
        msg=msg,
        decision=decision,
        continuity_source=continuity_source,
        required_tool=required_tool,
        required_tool_query=required_tool_query,
        is_short_confirmation=is_short_confirmation,
        is_contextual_followup_request=is_contextual_followup_request,
        is_answer_reference_followup=is_answer_reference_followup,
        pending_followup_intent_kind=pending_followup_intent_kind,
        skill_creation_intent=skill_creation_intent,
        skill_install_intent=skill_install_intent,
        conversation_history=conversation_history,
        recent_answer_target=recent_answer_target,
        last_tool_execution=last_tool_execution,
        relevant_memory_facts=relevant_memory_facts,
        learned_execution_hints=learned_execution_hints,
        intent_source_for_followup=intent_source_for_followup,
        effective_content=effective_content,
        committed_action_request_text=committed_action_request_text,
        forced_skill_names=forced_skill_names,
        external_skill_lane=external_skill_lane,
        last_tool_context=last_tool_context,
        explicit_file_analysis_note=explicit_file_analysis_note,
        file_analysis_path=file_analysis_path,
        route_grounding_mode=route_grounding_mode,
        requires_grounded_filesystem_inspection=requires_grounded_filesystem_inspection,
        mcp_context_note=mcp_context_note,
        semantic_hint=semantic_hint,
        meta_skill_reference_turn=meta_skill_reference_turn,
        skill_creation_stage=skill_creation_stage,
        skill_creation_approved=skill_creation_approved,
        skill_workflow_kind=skill_workflow_kind,
        skill_creation_request_text=skill_creation_request_text,
        observed_turn_category=None,
        observed_continuity_source=None,
        runtime_locale=None,
        layered_context_sources=None,
    )
    _finalize_turn_metadata(metadata_state)
    runtime_locale = metadata_state.runtime_locale
    observed_turn_category = metadata_state.observed_turn_category
    observed_continuity_source = metadata_state.observed_continuity_source
    route_decision_snapshot = {}
    if isinstance(msg.metadata, dict):
        snapshot_candidate = msg.metadata.get("route_decision_snapshot")
        if isinstance(snapshot_candidate, dict):
            route_decision_snapshot = dict(snapshot_candidate)
    if route_decision_snapshot:
        _emit_runtime_event(loop, "route_decision", **route_decision_snapshot)
    logger.info(
        f"turn_id={turn_id} continuity_source={observed_continuity_source} "
        f"turn_category={observed_turn_category}"
    )

    return await _run_turn_response(
        SimpleNamespace(
            loop=loop,
            msg=msg,
            session=session,
            decision=decision,
            required_tool=required_tool,
            effective_content=effective_content,
            filesystem_location_context_note=filesystem_location_context_note,
            explicit_file_analysis_note=explicit_file_analysis_note,
            route_grounding_mode=route_grounding_mode,
            mcp_context_note=mcp_context_note,
            runtime_locale=runtime_locale,
            observed_continuity_source=observed_continuity_source,
            recent_answer_target=recent_answer_target,
            recent_answer_option_selection_reference=recent_answer_option_selection_reference,
            recent_answer_referenced_item=recent_answer_referenced_item,
            continuity_source=continuity_source,
            perf_cfg=perf_cfg,
            is_background_task=is_background_task,
            skill_creation_approved=skill_creation_approved,
            llm_current_message=llm_current_message,
            history_limit=history_limit,
            skip_history_for_speed=skip_history_for_speed,
            token_mode=token_mode,
            probe_mode=probe_mode,
            conversation_history=conversation_history,
            forced_skill_names=forced_skill_names,
            external_skill_lane=external_skill_lane,
            turn_id=turn_id,
            intent_source_for_followup=intent_source_for_followup,
            pending_followup_intent_request_text=pending_followup_intent_request_text,
            committed_action_request_text=committed_action_request_text,
            fast_direct_context=fast_direct_context,
            is_non_action_feedback=is_non_action_feedback,
            is_contextual_followup_request=is_contextual_followup_request,
            turn_started=turn_started,
        )
    )


from kabot.agent.loop_core.message_runtime_parts.tail import (  # noqa: E402,I001
    process_isolated,
    process_pending_exec_approval,
    process_system_message,
)
