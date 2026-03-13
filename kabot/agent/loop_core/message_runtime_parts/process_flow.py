"""Message/session runtime helpers extracted from AgentLoop."""

from __future__ import annotations

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
    _build_filesystem_location_context_note,
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
)
from kabot.agent.loop_core.execution_runtime_parts.intent import (
    _should_defer_live_research_latch_to_skill,
)
from kabot.agent.loop_core.tool_enforcement import (
    _extract_list_dir_path,
    _extract_read_file_path,
    infer_action_required_tool_for_loop,
    _query_has_tool_payload,
)
from kabot.agent.loop_core.quality_runtime import get_learned_execution_hints
from kabot.agent.semantic_intent import arbitrate_semantic_intent
from kabot.agent.skills import (
    looks_like_skill_creation_request,
    looks_like_skill_install_request,
    normalize_skill_reference_name,
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

    # OpenClaw-style abort shortcut: standalone stop/cancel intent should
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
    clean_body, directives = loop.directive_parser.parse(msg.content)
    effective_content = clean_body or msg.content
    intent_source_for_followup = effective_content
    persist_user_profile(loop, session, effective_content, now_ts=time.time())

    # Store directives in session metadata
    if directives.raw_directives:
        active = loop.directive_parser.format_active_directives(directives)
        logger.info(f"Directives active: {active}")

        session.metadata["directives"] = {
            "think": directives.think,
            "verbose": directives.verbose,
            "elevated": directives.elevated,
        }
        # Ensure metadata persists
        loop.sessions.save(session)

    # Phase 9: Model override via directive
    if directives.model:
        logger.info(f"Directive override: model -> {directives.model}")
        if isinstance(msg.metadata, dict):
            override = str(directives.model).strip()
            if override:
                msg.metadata["model_override"] = override
                msg.metadata["model_override_source"] = "directive"

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
    is_side_effect_request = _looks_like_side_effect_request(effective_content)
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
    semantic_hint = arbitrate_semantic_intent(
        effective_content,
        parser_tool=required_tool,
        pending_followup_tool=pending_followup_tool,
        pending_followup_source=pending_followup_source,
        last_tool_context=last_tool_context,
        payload_checker=_query_has_tool_payload,
    )
    meta_skill_reference_turn = looks_like_meta_skill_or_workflow_prompt(effective_content)
    if semantic_hint.kind in {"advice_turn", "meta_feedback", "weather_metric_interpretation", "memory_recall"}:
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

    if is_closing_ack or is_short_greeting or is_non_action_feedback or semantic_hint.clear_pending:
        _clear_pending_followup_tool(session)
        _clear_pending_followup_intent(session)
    elif is_explicit_new_request or clear_stale_followup_for_new_tool_request:
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
        if list_dir_followup_path:
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

    if (
        not required_tool
        and str(decision.profile).upper() == "RESEARCH"
        and _tool_registry_has(loop, "web_search")
        and _looks_like_live_research_query(effective_content)
        and not _should_defer_live_research_latch_to_skill(
            loop,
            effective_content,
            profile=str(decision.profile).upper() or "RESEARCH",
        )
        and not is_non_action_feedback
    ):
        required_tool = "web_search"
        required_tool_query = effective_content
        decision.is_complex = True
        logger.info(
            f"Research safety latch: '{_normalize_text(effective_content)[:120]}' -> required_tool=web_search"
        )
        fast_direct_context = bool(
            perf_cfg
            and bool(getattr(perf_cfg, "fast_first_response", True))
            and required_tool in direct_tools
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
                "Answer directly from existing knowledge in the user's requested language or style. "
                "Do not call web search again unless the user explicitly asks for live, latest, or verified external information."
            ).strip()
        continuity_source = "knowledge_followup"
        decision.is_complex = True
        fast_direct_context = False
        _clear_pending_followup_tool(session)
        pending_followup_tool = None
        pending_followup_source = ""
        logger.info(
            "Web-search follow-up demotion: "
            f"'{_normalize_text(effective_content)[:120]}' -> complex knowledge route"
        )

    if (
        pending_followup_tool
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
        and not is_explicit_new_request
    )
    skill_creation_followup = bool(
        current_skill_flow
        and current_skill_flow_kind != "install"
        and (
            is_short_confirmation
            or _looks_like_skill_creation_approval(msg.content)
            or skill_workflow_detail_followup
        )
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not is_explicit_new_request
    )
    skill_install_followup = bool(
        current_skill_flow
        and current_skill_flow_kind == "install"
        and (
            is_short_confirmation
            or _looks_like_skill_creation_approval(msg.content)
            or skill_workflow_detail_followup
        )
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not is_explicit_new_request
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
            "user's language."
        )
    filesystem_location_context_note = ""
    explicit_file_analysis_note = ""
    mcp_context_note = ""
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
    elif current_skill_flow and is_explicit_new_request:
        _clear_skill_creation_flow(session)

    if (
        not forced_skill_names
        and not skill_creation_intent
        and not skill_install_intent
        and not meta_skill_reference_turn
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
    ):
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
        matched_skill_details: list[dict[str, Any]] = []
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

        format_skill_unavailability = getattr(skills_loader, "_format_skill_unavailability", None)
        eligible_external_matches: list[dict[str, str]] = []
        unavailable_external_matches: list[dict[str, str]] = []
        for detail in matched_skill_details:
            if not isinstance(detail, dict):
                continue
            skill_name = normalize_skill_reference_name(str(detail.get("name") or ""))
            source = str(detail.get("source") or "").strip().lower()
            if not skill_name or not source or source == "builtin":
                continue
            if bool(detail.get("eligible")):
                eligible_external_matches.append(
                    {
                        "name": skill_name,
                        "source": source,
                        "description": str(detail.get("description") or "").strip(),
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

        if len(eligible_external_matches) == 1:
            primary_skill = eligible_external_matches[0]
            forced_skill_names = [primary_skill["name"]]
            external_skill_lane = True
            llm_current_message = (
                f"{llm_current_message}\n\n"
                "[External Skill Note]\n"
                f"- The installed external skill `{primary_skill['name']}` is the best match for this request.\n"
                "- Load and follow that skill first.\n"
                "- Prefer the skill workflow over generic fallback behavior.\n"
                "- If the skill still needs credentials or setup, explain that briefly and ask only for the missing requirement."
            ).strip()
            if not decision.is_complex:
                decision.is_complex = True
            logger.info(
                "External skill execution latch: "
                f"'{_normalize_text(effective_content)[:120]}' -> skill={primary_skill['name']}"
            )
        elif len(unavailable_external_matches) == 1:
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
        and not required_tool
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
            required_tool = action_required_tool
            required_tool_query = str(action_required_tool_query or effective_content).strip()
            continuity_source = continuity_source or "action_request"
            if not decision.is_complex:
                decision.is_complex = True
            logger.info(
                "Action-request tool inference: "
                f"'{_normalize_text(effective_content)[:120]}' -> required_tool={required_tool}"
            )

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
        _set_pending_followup_intent(session, intent_source_for_followup, str(decision.profile), now_ts)
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

