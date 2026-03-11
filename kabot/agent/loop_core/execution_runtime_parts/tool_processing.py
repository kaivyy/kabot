"""Tool-call processing extracted from agent loop runtime."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from loguru import logger

from kabot.agent.fallback_i18n import t
from kabot.agent.loop_core.execution_runtime_parts.helpers import (
    _apply_channel_tool_result_hard_cap,
    _extract_single_result_path,
    _apply_response_quota_usage,
    _build_pending_interrupt_note,
    _emit_runtime_event,
    _looks_like_live_research_query,
    _looks_like_short_confirmation,
    _prune_expiring_cache,
    _query_has_explicit_payload_for_tool,
    _resolve_query_text_from_message,
    _resolve_expected_tool_for_query,
    _resolve_token_mode,
    _runtime_performance_cfg,
    _runtime_resilience_cfg,
    _sanitize_error,
    _schedule_memory_write,
    _should_defer_memory_write,
    _should_skip_memory_persistence,
    _skill_creation_guard_reason,
    _skill_creation_status_phase,
    _stable_tool_payload_hash,
    _take_pending_interrupt_messages,
    _tool_call_intent_mismatch_reason,
    _update_completion_evidence,
    _update_followup_context_from_tool_execution,
    _verify_completion_artifact_path,
)
from kabot.agent.loop_core.execution_runtime_parts.llm import (
    call_llm_with_fallback,
    format_tool_result,
    run_simple_response,
)
from kabot.agent.loop_core.tool_enforcement import (
    _extract_list_dir_limit,
    _extract_list_dir_path,
    _extract_message_delivery_path,
    _extract_read_file_path,
    _looks_like_write_file_request,
    _resolve_delivery_path,
    infer_action_required_tool_for_loop,
)
from kabot.bus.events import InboundMessage, OutboundMessage

async def process_tool_calls(loop: Any, msg: InboundMessage, messages: list, response: Any, session: Any) -> list:
    """Execute tool calls and append results to conversation context."""
    resilience_cfg = _runtime_resilience_cfg(loop)
    message_metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
    dedupe_enabled = bool(getattr(resilience_cfg, "dedupe_tool_calls", True))
    ttl_seconds = max(30, int(getattr(resilience_cfg, "idempotency_ttl_seconds", 600)))
    turn_id = str(getattr(loop, "_active_turn_id", f"{msg.session_key}:{int(msg.timestamp.timestamp() * 1000)}"))

    payload_cache = getattr(loop, "_tool_payload_cache", None)
    if not isinstance(payload_cache, dict):
        payload_cache = {}
        setattr(loop, "_tool_payload_cache", payload_cache)

    call_id_cache = getattr(loop, "_tool_call_id_cache", None)
    if not isinstance(call_id_cache, dict):
        call_id_cache = {}
        setattr(loop, "_tool_call_id_cache", call_id_cache)

    if dedupe_enabled:
        _prune_expiring_cache(payload_cache)
        _prune_expiring_cache(call_id_cache)

    tool_call_dicts = [
        {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
        for tc in response.tool_calls
    ]
    if response.content:
        # Keep tool_calls attached to assistant messages even when content exists.
        # Without this, tool outputs can become orphaned in history and codex
        # backend may reject the request with "No tool call found ...".
        attached_to_last = False
        if messages and isinstance(messages[-1], dict):
            last = messages[-1]
            last_tool_ids = {
                str(tc.get("id"))
                for tc in (last.get("tool_calls") or [])
                if isinstance(tc, dict) and tc.get("id")
            }
            current_ids = {str(tc.get("id")) for tc in tool_call_dicts if tc.get("id")}
            if (
                last.get("role") == "assistant"
                and str(last.get("content", "")) == str(response.content or "")
                and current_ids
                and current_ids.issubset(last_tool_ids)
            ):
                attached_to_last = True
            elif (
                last.get("role") == "assistant"
                and "tool_calls" not in last
                and str(last.get("content", "")) == str(response.content or "")
            ):
                last["tool_calls"] = tool_call_dicts
                if response.reasoning_content and not last.get("reasoning_content"):
                    last["reasoning_content"] = response.reasoning_content
                attached_to_last = True

        if not attached_to_last:
            messages = loop.context.add_assistant_message(
                messages,
                response.content,
                tool_call_dicts,
                reasoning_content=response.reasoning_content,
            )
    else:
        messages = loop.context.add_assistant_message(
            messages, None, tool_call_dicts, reasoning_content=response.reasoning_content
        )

    tc_data = [{"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in response.tool_calls]
    if not _should_skip_memory_persistence(msg):
        if _should_defer_memory_write(loop):
            _schedule_memory_write(
                loop,
                loop.memory.add_message(msg.session_key, "assistant", response.content or "", tool_calls=tc_data),
                label="tool-assistant-envelope",
            )
        else:
            await loop.memory.add_message(msg.session_key, "assistant", response.content or "", tool_calls=tc_data)

    permissions = loop._get_tool_permissions(session)
    if permissions.get("auto_approve") or loop.exec_auto_approve:
        logger.debug("Elevated mode active: auto_approve=True, restrict_to_workspace=False")

    exec_tool = loop.tools.get("exec")
    if exec_tool and hasattr(exec_tool, "auto_approve"):
        exec_tool.auto_approve = bool(
            loop.exec_auto_approve or permissions.get("auto_approve", False)
        )

    sent_status_updates: set[str] = set()
    token_mode = _resolve_token_mode(_runtime_performance_cfg(loop))
    execute_tool = getattr(loop, "_execute_tool", None)
    expected_tool_for_guard = _resolve_expected_tool_for_query(loop, msg)
    for tc in response.tool_calls:
        args_raw = tc.arguments
        tool_params = args_raw if isinstance(args_raw, dict) else {}

        payload_key = _stable_tool_payload_hash(
            session_key=msg.session_key,
            turn_id=turn_id,
            tool_name=tc.name,
            tool_args=tool_params,
        )
        if dedupe_enabled and tc.id in call_id_cache:
            _, cached_result = call_id_cache[tc.id]
            logger.warning(
                f"tool_idempotency_hit=1 reason=tool_call_id_replay tool={tc.name} "
                f"tool_call_id={tc.id} turn_id={turn_id}"
            )
            _emit_runtime_event(
                loop,
                "tool_idempotency_hit",
                turn_id=turn_id,
                tool_name=tc.name,
                tool_call_id=tc.id,
                reason="tool_call_id_replay",
                tool_idempotency_hit=1,
            )
            # Prevent duplicate function_call_output entries for the same call_id.
            # Duplicate outputs can trigger backend validation errors in strict
            # tool-call protocols ("No tool call found ..." for replayed output).
            has_existing_output = any(
                isinstance(existing, dict)
                and existing.get("role") == "tool"
                and str(existing.get("tool_call_id", "")) == str(tc.id)
                for existing in messages
            )
            if not has_existing_output:
                messages = loop.context.add_tool_result(messages, tc.id, tc.name, cached_result)
            continue
        if dedupe_enabled and payload_key in payload_cache:
            _, cached_result = payload_cache[payload_key]
            expires_at = time.time() + ttl_seconds
            call_id_cache[tc.id] = (expires_at, cached_result)
            logger.warning(
                f"tool_idempotency_hit=1 reason=payload_duplicate tool={tc.name} "
                f"tool_call_id={tc.id} turn_id={turn_id}"
            )
            _emit_runtime_event(
                loop,
                "tool_idempotency_hit",
                turn_id=turn_id,
                tool_name=tc.name,
                tool_call_id=tc.id,
                reason="payload_duplicate",
                tool_idempotency_hit=1,
            )
            messages = loop.context.add_tool_result(messages, tc.id, tc.name, cached_result)
            continue

        skill_creation_guard_reason = _skill_creation_guard_reason(msg, tc.name)
        if skill_creation_guard_reason:
            blocked_result = (
                "TOOL_CALL_BLOCKED_SKILL_CREATION_APPROVAL: "
                f"'{tc.name}' blocked ({skill_creation_guard_reason}). "
                "Stay in discovery/planning mode, present a short implementation plan, and wait for explicit approval before writing files or running code."
            )
            if loop._should_log_verbose(session):
                token_count = loop.truncator._count_tokens(blocked_result)
                blocked_result = loop._format_verbose_output(
                    tc.name,
                    blocked_result,
                    token_count,
                )
            logger.warning(
                f"tool_call_blocked=1 tool={tc.name} reason={skill_creation_guard_reason} "
                f"turn_id={turn_id} chat_id={msg.chat_id}"
            )
            result_for_llm = loop._format_tool_result(blocked_result)
            result_for_llm = _apply_channel_tool_result_hard_cap(
                result_for_llm,
                channel=msg.channel,
                tool_name=tc.name,
                token_mode=token_mode,
            )
            messages = loop.context.add_tool_result(messages, tc.id, tc.name, result_for_llm)
            if dedupe_enabled:
                expires_at = time.time() + ttl_seconds
                payload_cache[payload_key] = (expires_at, result_for_llm)
                call_id_cache[tc.id] = (expires_at, result_for_llm)
            if not _should_skip_memory_persistence(msg):
                if _should_defer_memory_write(loop):
                    _schedule_memory_write(
                        loop,
                        loop.memory.add_message(
                            msg.session_key,
                            "tool",
                            blocked_result,
                            tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": blocked_result[:1000]}],
                        ),
                        label="tool-blocked-skill-creation",
                    )
                else:
                    await loop.memory.add_message(
                        msg.session_key,
                        "tool",
                        blocked_result,
                        tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": blocked_result[:1000]}],
                    )
            continue

        mismatch_reason = _tool_call_intent_mismatch_reason(loop, msg, tc.name)
        if mismatch_reason:
            blocked_result = (
                "TOOL_CALL_BLOCKED_INTENT_MISMATCH: "
                f"'{tc.name}' blocked ({mismatch_reason}). "
                "Re-evaluate current user intent and choose the correct tool or respond without tool calls."
            )
            if loop._should_log_verbose(session):
                token_count = loop.truncator._count_tokens(blocked_result)
                blocked_result = loop._format_verbose_output(
                    tc.name,
                    blocked_result,
                    token_count,
                )
            logger.warning(
                f"tool_call_blocked=1 tool={tc.name} reason={mismatch_reason} "
                f"turn_id={turn_id} chat_id={msg.chat_id}"
            )
            result_for_llm = loop._format_tool_result(blocked_result)
            result_for_llm = _apply_channel_tool_result_hard_cap(
                result_for_llm,
                channel=msg.channel,
                tool_name=tc.name,
                token_mode=token_mode,
            )
            messages = loop.context.add_tool_result(messages, tc.id, tc.name, result_for_llm)
            if dedupe_enabled:
                expires_at = time.time() + ttl_seconds
                payload_cache[payload_key] = (expires_at, result_for_llm)
                call_id_cache[tc.id] = (expires_at, result_for_llm)
            if not _should_skip_memory_persistence(msg):
                if _should_defer_memory_write(loop):
                    _schedule_memory_write(
                        loop,
                        loop.memory.add_message(
                            msg.session_key,
                            "tool",
                            blocked_result,
                            tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": blocked_result[:1000]}],
                        ),
                        label="tool-blocked",
                    )
                else:
                    await loop.memory.add_message(
                        msg.session_key,
                        "tool",
                        blocked_result,
                        tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": blocked_result[:1000]}],
                    )
            continue

        # Check for tool loops before execution
        loop_result = loop.loop_detector.check(tc.name, tool_params)
        if loop_result.stuck:
            if loop_result.level == "critical":
                # Block execution and return error
                error_msg = f"WARNING: Tool loop detected: {loop_result.message}"
                logger.warning(f"Tool loop blocked: {tc.name} - {loop_result.message}")
                messages = loop.context.add_tool_result(messages, tc.id, tc.name, error_msg)
                if not _should_skip_memory_persistence(msg):
                    if _should_defer_memory_write(loop):
                        _schedule_memory_write(
                            loop,
                            loop.memory.add_message(
                                msg.session_key,
                                "tool",
                                error_msg,
                                tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": error_msg}],
                            ),
                            label="tool-loop-block",
                        )
                    else:
                        await loop.memory.add_message(
                            msg.session_key, "tool", error_msg,
                            tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": error_msg}],
                        )
                continue
            else:
                # Warning level - log but allow execution
                logger.warning(f"Tool loop warning: {tc.name} - {loop_result.message}")

        status = loop._get_tool_status_message(tc.name, tool_params)
        if status and status not in sent_status_updates:
            sent_status_updates.add(status)
            await loop.bus.publish_outbound(OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=f"_{status}_",
                metadata={"type": "status_update", "phase": "tool", "lane": "status"},
            ))

        if tc.name == "weather":
            tool_params.setdefault("context_text", msg.content)
        if tc.name == "cron":
            tool_params.setdefault("context_text", msg.content)
        if tc.name == "exec":
            tool_params["_session_key"] = msg.session_key
            tool_params["_channel"] = msg.channel
            tool_params["_chat_id"] = msg.chat_id
            tool_params["_agent_id"] = loop._resolve_agent_id_for_message(msg)
            tool_params["_account_id"] = msg.account_id or ""
            tool_params["_thread_id"] = msg.thread_id or ""
            tool_params["_peer_kind"] = msg.peer_kind or ""
            tool_params["_peer_id"] = msg.peer_id or ""

        if callable(execute_tool):
            result = await execute_tool(tc.name, tool_params, session_key=msg.session_key)
        else:
            result = await loop.tools.execute(tc.name, tool_params)

        # Record tool call for loop detection
        loop.loop_detector.record(tc.name, tool_params, tc.id)
        result_str = str(result)
        if isinstance(message_metadata, dict):
            executed_tools = message_metadata.get("executed_tools")
            if not isinstance(executed_tools, list):
                executed_tools = []
            if tc.name not in executed_tools:
                executed_tools.append(tc.name)
            message_metadata["executed_tools"] = executed_tools
            if tc.name == "message":
                files_arg = tool_params.get("files")
                if isinstance(files_arg, list) and any(str(item or "").strip() for item in files_arg):
                    message_metadata["message_delivery_verified"] = True
        if (
            expected_tool_for_guard
            and tc.name == expected_tool_for_guard
            and result_str.startswith(f"Error: Invalid parameters for tool '{tc.name}'")
        ):
            fallback_result = await loop._execute_required_tool_fallback(tc.name, msg)
            fallback_text = str(fallback_result or "").strip()
            if fallback_text and fallback_text != result_str:
                logger.warning(
                    f"Tool parameter recovery fallback executed for '{tc.name}' after invalid args"
                )
                result_str = fallback_text
        source_hint = _resolve_query_text_from_message(msg)
        _update_followup_context_from_tool_execution(
            session,
            tool_name=tc.name,
            tool_args=tool_params,
            fallback_source=source_hint,
            tool_result=result_str,
        )
        evidence_artifact_paths: list[str] | None = None
        evidence_artifact_verified: bool | None = None
        evidence_delivery_paths: list[str] | None = None
        evidence_delivery_verified: bool | None = None
        extracted_result_path = _extract_single_result_path(tc.name, tool_params, result_str)
        if tc.name == "message":
            if extracted_result_path:
                evidence_artifact_paths = [extracted_result_path]
                evidence_delivery_paths = [extracted_result_path]
                evidence_artifact_verified = True
            evidence_delivery_verified = bool(message_metadata.get("message_delivery_verified"))
        elif extracted_result_path:
            verified_path, exists = _verify_completion_artifact_path(loop, extracted_result_path)
            evidence_artifact_paths = [verified_path or extracted_result_path]
            evidence_artifact_verified = exists
        _update_completion_evidence(
            message_metadata,
            session,
            artifact_paths=evidence_artifact_paths,
            artifact_verified=evidence_artifact_verified,
            delivery_paths=evidence_delivery_paths,
            delivery_verified=evidence_delivery_verified,
        )
        truncated_result = loop.truncator.truncate(result_str, tc.name)

        if loop._should_log_verbose(session):
            token_count = loop.truncator._count_tokens(result_str)
            verbose_output = loop._format_verbose_output(tc.name, result_str, token_count)
            truncated_result += verbose_output

        result_for_llm = loop._format_tool_result(truncated_result)
        result_for_llm = _apply_channel_tool_result_hard_cap(
            result_for_llm,
            channel=msg.channel,
            tool_name=tc.name,
            token_mode=token_mode,
        )
        messages = loop.context.add_tool_result(messages, tc.id, tc.name, result_for_llm)
        if dedupe_enabled:
            expires_at = time.time() + ttl_seconds
            payload_cache[payload_key] = (expires_at, result_for_llm)
            call_id_cache[tc.id] = (expires_at, result_for_llm)

        if not _should_skip_memory_persistence(msg):
            if _should_defer_memory_write(loop):
                _schedule_memory_write(
                    loop,
                    loop.memory.add_message(
                        msg.session_key, "tool", str(result),
                        tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": str(result)[:1000]}],
                    ),
                    label="tool-result",
                )
            else:
                await loop.memory.add_message(
                    msg.session_key, "tool", str(result),
                    tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": str(result)[:1000]}],
                )
    return messages


