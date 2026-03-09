"""Message/session runtime helpers extracted from AgentLoop."""

from __future__ import annotations

import asyncio
import time
from contextlib import suppress
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
    _channel_supports_keepalive_passthrough,
    _channel_uses_mutable_status_lane,
    _clear_pending_followup_intent,
    _clear_pending_followup_tool,
    _clear_skill_creation_flow,
    _emit_runtime_event,
    _get_last_tool_context,
    _get_pending_followup_intent,
    _get_pending_followup_tool,
    _get_skill_creation_flow,
    _infer_recent_file_path_from_history,
    _is_abort_request_text,
    _is_low_information_turn,
    _is_probe_mode_message,
    _is_short_context_followup,
    _looks_like_closing_acknowledgement,
    _looks_like_explicit_new_request,
    _looks_like_file_context_followup,
    _looks_like_filesystem_location_query,
    _looks_like_live_research_query,
    _looks_like_memory_commit_turn,
    _looks_like_non_action_meta_feedback,
    _looks_like_short_confirmation,
    _looks_like_short_greeting_smalltalk,
    _looks_like_skill_creation_approval,
    _looks_like_temporal_context_query,
    _looks_like_weather_context_followup,
    _message_needs_full_skill_context,
    _normalize_text,
    _resolve_runtime_locale,
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
from kabot.agent.loop_core.message_runtime_parts.temporal import (
    build_temporal_fast_reply,
)
from kabot.agent.loop_core.tool_enforcement import (
    _extract_list_dir_path,
    _extract_read_file_path,
    _query_has_tool_payload,
)
from kabot.agent.semantic_intent import arbitrate_semantic_intent
from kabot.agent.skills import (
    looks_like_skill_creation_request,
    looks_like_skill_install_request,
)
from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.core.command_router import CommandContext

__all__ = [
    "_is_low_information_turn",
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

    approval_action = loop._parse_approval_command(msg.content)
    if approval_action:
        action, approval_id = approval_action
        return await process_pending_exec_approval(
            loop,
            msg,
            action=action,
            approval_id=approval_id,
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
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=result,
            )

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

    required_tool = loop._required_tool_for_query(effective_content)
    required_tool_query = effective_content
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
        "read_file",
        "list_dir",
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
        "read_file",
        "list_dir",
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
    if (not probe_mode or persist_probe_history) and not fast_direct_context and not skip_history_for_speed:
        conversation_history = loop.memory.get_conversation_context(msg.session_key, max_messages=history_limit)
        if conversation_history:
            conversation_history = [m for m in conversation_history if isinstance(m, dict)]

    # Router triase: SIMPLE vs COMPLEX
    if fast_direct_context and required_tool in route_bypass_direct_tools:
        decision = SimpleNamespace(profile="GENERAL", is_complex=True)
    else:
        decision = await loop.router.route(effective_content)
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
    pending_followup_intent = _get_pending_followup_intent(session, now_ts)
    is_short_confirmation = bool(not required_tool and _looks_like_short_confirmation(effective_content))
    is_closing_ack = _looks_like_closing_acknowledgement(effective_content)
    is_short_greeting = _looks_like_short_greeting_smalltalk(effective_content)
    is_non_action_feedback = _looks_like_non_action_meta_feedback(effective_content)
    raw_is_explicit_new_request = _looks_like_explicit_new_request(effective_content)
    is_weather_context_followup = bool(
        pending_followup_tool == "weather"
        and _looks_like_weather_context_followup(effective_content)
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
    semantic_hint = arbitrate_semantic_intent(
        effective_content,
        parser_tool=required_tool,
        pending_followup_tool=pending_followup_tool,
        pending_followup_source=pending_followup_source,
        last_tool_context=last_tool_context,
        payload_checker=_query_has_tool_payload,
    )
    meta_skill_reference_turn = looks_like_meta_skill_or_workflow_prompt(effective_content)
    if semantic_hint.kind in {"advice_turn", "meta_feedback"}:
        required_tool = None
        required_tool_query = effective_content
    elif semantic_hint.required_tool:
        required_tool = semantic_hint.required_tool
        required_tool_query = str(semantic_hint.required_tool_query or effective_content).strip()
    if meta_skill_reference_turn:
        required_tool = None
        required_tool_query = effective_content
    is_non_action_feedback = bool(is_non_action_feedback or semantic_hint.kind == "meta_feedback")

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

    if is_closing_ack or is_short_greeting or is_non_action_feedback or semantic_hint.clear_pending:
        _clear_pending_followup_tool(session)
        _clear_pending_followup_intent(session)
    elif is_explicit_new_request and not required_tool:
        # Fresh explicit asks (file/config/path/URL/command-like payload) should
        # not inherit stale pending follow-up state from previous turns.
        _clear_pending_followup_tool(session)
        _clear_pending_followup_intent(session)
        pending_followup_tool = None
        pending_followup_source = ""
        pending_followup_intent = None

    if (
        not required_tool
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
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

    if (
        pending_followup_tool
        and not decision.is_complex
        and not required_tool
        and (is_short_confirmation or is_weather_context_followup)
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not is_explicit_new_request
    ):
        required_tool = pending_followup_tool
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

    # Infer required tool for short follow-ups before context building, so
    # confirmations like "gas"/"ambil sekarang" can take the direct fast path.
    if (
        not decision.is_complex
        and not required_tool
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not is_explicit_new_request
    ):
        normalized_followup = _normalize_text(effective_content)
        if _looks_like_short_confirmation(normalized_followup):
            inferred_tool = None
            inferred_source = None
            infer_from_history = getattr(loop, "_infer_required_tool_from_history", None)
            if callable(infer_from_history):
                try:
                    inferred_tool, inferred_source = infer_from_history(
                        effective_content,
                        conversation_history,
                    )
                except Exception:
                    inferred_tool, inferred_source = None, None
            else:
                # Backward-compatible fallback for lightweight test doubles
                # that don't expose the loop facade helper yet.
                for item in reversed(conversation_history[-8:]):
                    role = str(item.get("role", "") or "").strip().lower()
                    candidate = str(item.get("content", "") or "").strip()
                    if not candidate:
                        continue
                    # Never infer required tools from assistant text. Assistant
                    # summaries/offers can contain rich keywords/tickers that are
                    # not fresh user intent and can cause rigid/hallucinated routing.
                    if role != "user":
                        continue
                    candidate_norm = _normalize_text(candidate)
                    if not candidate_norm or candidate_norm == normalized_followup:
                        continue
                    if _looks_like_short_confirmation(candidate):
                        continue
                    inferred = loop._required_tool_for_query(candidate)
                    if inferred:
                        inferred_tool = inferred
                        inferred_source = candidate
                        break
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

    if (
        pending_followup_intent
        and not required_tool
        and is_short_confirmation
        and not is_closing_ack
        and not is_short_greeting
        and not is_non_action_feedback
        and not is_explicit_new_request
    ):
        intent_text = str(pending_followup_intent.get("text") or "").strip()
        intent_profile = str(pending_followup_intent.get("profile") or "GENERAL").strip().upper()
        inferred_tool = loop._required_tool_for_query(intent_text) if intent_text else None
        if inferred_tool:
            required_tool = inferred_tool
            required_tool_query = intent_text
            decision.is_complex = True
            logger.info(
                f"Session intent follow-up inference: '{_normalize_text(effective_content)}' -> required_tool={inferred_tool}"
            )
            fast_direct_context = bool(
                perf_cfg
                and bool(getattr(perf_cfg, "fast_first_response", True))
                and required_tool in direct_tools
            )
        else:
            # Preserve non-tool intent context so short confirms like
            # "ya/lanjut/gas" still continue the previous actionable flow.
            effective_content = (
                f"{effective_content}\n\n[Follow-up Context]\n{intent_text}"
                if intent_text
                else effective_content
            )
            if not decision.is_complex and str(decision.profile).upper() == "CHAT":
                decision.profile = intent_profile if intent_profile else decision.profile
                if intent_profile in {"CODING", "RESEARCH", "GENERAL"}:
                    decision.is_complex = True
            logger.info(
                f"Session intent context continued: '{_normalize_text(effective_content)[:120]}' profile={decision.profile} complex={decision.is_complex}"
            )

    current_skill_flow = _get_skill_creation_flow(session, now_ts)
    current_skill_flow_kind = str((current_skill_flow or {}).get("kind") or "create").strip().lower() or "create"
    skill_creation_followup = bool(
        current_skill_flow
        and current_skill_flow_kind != "install"
        and (
            is_short_confirmation
            or _looks_like_skill_creation_approval(msg.content)
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
    llm_current_message = effective_content
    filesystem_location_context_note = ""
    explicit_file_analysis_note = ""
    file_analysis_path = ""
    skill_creation_stage = str((current_skill_flow or {}).get("stage") or "discovery").strip().lower() or "discovery"
    skill_workflow_kind = "install" if skill_install_intent else current_skill_flow_kind
    skill_creation_request_text = str((current_skill_flow or {}).get("request_text") or effective_content).strip()
    skill_creation_approved = False
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
        explicit_file_path = _extract_read_file_path(effective_content)
        if explicit_file_path:
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

    runtime_locale = _resolve_runtime_locale(session, msg, effective_content)
    if isinstance(msg.metadata, dict):
        msg.metadata["runtime_locale"] = runtime_locale
        msg.metadata["effective_content"] = effective_content
        if forced_skill_names:
            msg.metadata["forced_skill_names"] = list(forced_skill_names)
        else:
            msg.metadata.pop("forced_skill_names", None)
        if last_tool_context:
            msg.metadata["last_tool_context"] = last_tool_context
        else:
            msg.metadata.pop("last_tool_context", None)
        if explicit_file_analysis_note and file_analysis_path:
            msg.metadata["file_analysis_mode"] = True
            msg.metadata["file_analysis_path"] = file_analysis_path
        else:
            msg.metadata.pop("file_analysis_mode", None)
            msg.metadata.pop("file_analysis_path", None)
        if semantic_hint.kind != "none":
            msg.metadata["semantic_intent_hint"] = semantic_hint.kind
        else:
            msg.metadata.pop("semantic_intent_hint", None)
        msg.metadata["suppress_required_tool_inference"] = bool(
            semantic_hint.kind in {"advice_turn", "meta_feedback"}
            or meta_skill_reference_turn
            or skill_creation_intent
            or skill_install_intent
        )
        if required_tool:
            msg.metadata["required_tool"] = required_tool
            msg.metadata["required_tool_query"] = str(required_tool_query or effective_content).strip()
        else:
            msg.metadata.pop("required_tool", None)
            msg.metadata.pop("required_tool_query", None)
        msg.metadata["skip_critic_for_speed"] = bool(
            required_tool
            or _is_short_context_followup(msg.content)
            or _is_short_context_followup(effective_content)
            or _looks_like_short_confirmation(msg.content)
            or _looks_like_short_confirmation(effective_content)
        )
        msg.metadata["status_mutable_lane"] = bool(
            _channel_uses_mutable_status_lane(loop, msg.channel)
        )
        if skill_creation_intent or skill_install_intent:
            msg.metadata["skill_creation_guard"] = {
                "active": True,
                "stage": skill_creation_stage,
                "approved": skill_creation_approved,
                "kind": skill_workflow_kind,
                "request_text": skill_creation_request_text,
            }
        else:
            msg.metadata.pop("skill_creation_guard", None)

    accuracy_context_required = bool(
        is_non_action_feedback
        or _looks_like_temporal_context_query(effective_content)
        or _looks_like_memory_commit_turn(effective_content)
    )
    temporal_fast_reply = None
    if (
        not decision.is_complex
        and not required_tool
        and not filesystem_location_context_note
        and not explicit_file_analysis_note
    ):
        temporal_fast_reply = build_temporal_fast_reply(
            effective_content,
            locale=runtime_locale,
        )

    fast_simple_context = bool(
        perf_cfg
        and bool(getattr(perf_cfg, "fast_first_response", True))
        and not decision.is_complex
        and not required_tool
        and not filesystem_location_context_note
        and not explicit_file_analysis_note
        and not accuracy_context_required
    )

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
                    await _publish_status(done_status if final_content else error_status, "done" if final_content else "error")

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
    )
    max_first_response_soft = int(getattr(perf_cfg, "max_first_response_ms_soft", 4000)) if perf_cfg else 4000
    if first_response_ms > max_first_response_soft:
        logger.warning(
            f"turn_id={turn_id} first_response_ms={first_response_ms} exceeded soft_target={max_first_response_soft}"
        )

    # Start memory warmup after first response path when defer mode is active.
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


from kabot.agent.loop_core.message_runtime_parts.tail import (  # noqa: E402,I001
    process_isolated,
    process_pending_exec_approval,
    process_system_message,
)

