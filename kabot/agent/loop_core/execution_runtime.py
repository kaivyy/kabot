"""Execution loop and tool-call runtime extracted from AgentLoop."""

from __future__ import annotations

import json
import time
from typing import Any

from loguru import logger

from kabot.agent.fallback_i18n import t
from kabot.agent.loop_core.execution_runtime_parts.helpers import (
    _apply_channel_tool_result_hard_cap,
    _apply_response_quota_usage,
    _emit_runtime_event,
    _looks_like_live_research_query,
    _looks_like_short_confirmation,
    _prune_expiring_cache,
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
    _tool_call_intent_mismatch_reason,
)
from kabot.agent.loop_core.execution_runtime_parts.llm import (
    call_llm_with_fallback,
    format_tool_result,
    run_simple_response,
)
from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.utils.text_safety import ensure_utf8_text

__all__ = [
    "format_tool_result",
    "call_llm_with_fallback",
    "run_agent_loop",
    "run_simple_response",
    "_apply_response_quota_usage",
    "_resolve_expected_tool_for_query",
    "_sanitize_error",
]


async def run_agent_loop(loop: Any, msg: InboundMessage, messages: list, session: Any) -> str | None:
    """Full planner-executor-critic loop for complex tasks."""
    iteration = 0

    message_metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
    models_to_try = loop._resolve_models_for_message(msg)
    model = models_to_try[0]

    self_eval_retried = False
    critic_retried = 0
    max_tool_retry = max(0, int(getattr(_runtime_resilience_cfg(loop), "max_tool_retry_per_turn", 1)))
    tool_enforcement_retries = 0
    status_updates_sent: set[str] = set()
    draft_updates_sent: set[str] = set()
    reasoning_updates_sent: set[str] = set()
    suppress_required_tool_inference = bool(message_metadata.get("suppress_required_tool_inference", False))
    required_tool = None if suppress_required_tool_inference else loop._required_tool_for_query(msg.content)
    raw_user_text = str(msg.content or "").strip()
    raw_user_word_count = len([part for part in raw_user_text.split() if part])
    effective_content = str(message_metadata.get("effective_content") or "").strip()
    question_text = effective_content or raw_user_text
    question_word_count = len([part for part in question_text.split() if part])
    route_profile = str(message_metadata.get("route_profile", "")).strip().upper()
    runtime_locale = str(message_metadata.get("runtime_locale") or "").strip() or None
    tools_registry = getattr(loop, "tools", None)
    has_tool = getattr(tools_registry, "has", None)
    resolved_required_tool = str(message_metadata.get("required_tool") or "").strip()
    if resolved_required_tool:
        if callable(has_tool):
            try:
                if has_tool(resolved_required_tool):
                    required_tool = resolved_required_tool
            except Exception:
                required_tool = resolved_required_tool
        else:
            required_tool = resolved_required_tool
    elif suppress_required_tool_inference:
        required_tool = None
    has_web_search_tool = False
    if callable(has_tool):
        try:
            has_web_search_tool = bool(has_tool("web_search"))
        except Exception:
            has_web_search_tool = False
    if (
        not suppress_required_tool_inference
        and not required_tool
        and has_web_search_tool
        and _looks_like_live_research_query(raw_user_text)
    ):
        required_tool = "web_search"
        logger.info("Live-research safety latch: forcing required_tool=web_search")
    if (
        not suppress_required_tool_inference
        and
        not required_tool
        and route_profile == "RESEARCH"
        and has_web_search_tool
        and _looks_like_live_research_query(question_text)
    ):
        required_tool = "web_search"
        logger.info("Research route safety latch: forcing required_tool=web_search")
    # OpenClaw-like responsiveness: skip expensive critic retries for short/chat/required-tool turns.
    skip_critic_for_speed = (
        bool(message_metadata.get("skip_critic_for_speed", False))
        or
        bool(required_tool)
        or raw_user_word_count <= 12
        or question_word_count <= 10
        or _looks_like_short_confirmation(raw_user_text)
        or _looks_like_short_confirmation(question_text)
        or _looks_like_live_research_query(raw_user_text)
        or "[follow-up context]" in question_text.lower()
        or route_profile in {"CHAT", "RESEARCH"}
    )
    is_background_task = (
        (msg.channel or "").lower() == "system"
        or (msg.sender_id or "").lower() == "system"
        or (
            isinstance(msg.content, str)
            and msg.content.strip().lower().startswith("heartbeat task:")
        )
    )
    # Synthetic/system callbacks (cron completion, heartbeat, etc.) should not
    # trigger hard tool-enforcement loops from reminder/weather keywords inside
    # system-generated text.
    if is_background_task:
        required_tool = None
    tools_executed = False

    is_weak_model = loop._is_weak_model(model)
    max_critic_retries = 1 if is_weak_model else 2
    critic_threshold = 5 if is_weak_model else 7

    first_score = None
    skill_creation_phase = _skill_creation_status_phase(message_metadata)

    def _phase_text(phase: str) -> str:
        key = f"runtime.status.{phase}"
        fallback_map = {
            "thinking": "runtime.status.thinking",
            "discovery": "runtime.status.thinking",
            "planning": "runtime.status.thinking",
            "executing": "runtime.status.thinking",
            "verified": "runtime.status.done",
        }
        fallback = fallback_map.get(phase, key)
        translated = t(key, locale=runtime_locale, text=question_text)
        if translated == key and fallback != key:
            return t(fallback, locale=runtime_locale, text=question_text)
        return translated

    async def _publish_phase(phase: str) -> None:
        if is_background_task:
            return
        mutable_status_lane = message_metadata.get("status_mutable_lane")
        if (
            isinstance(mutable_status_lane, bool)
            and not mutable_status_lane
            and phase in {"thinking", "done", "error"}
        ):
            return
        if phase == "thinking" and bool(message_metadata.get("suppress_initial_thinking_status", False)):
            message_metadata["suppress_initial_thinking_status"] = False
            return
        bus = getattr(loop, "bus", None)
        publish = getattr(bus, "publish_outbound", None)
        if not callable(publish):
            return
        text = _phase_text(phase)
        dedupe_key = f"{phase}:{text}"
        if dedupe_key in status_updates_sent:
            return
        status_updates_sent.add(dedupe_key)
        try:
            await publish(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=text,
                    metadata={"type": "status_update", "phase": phase, "lane": "status"},
                )
            )
        except Exception:
            return

    async def _publish_draft(text: str, *, phase: str = "thinking") -> None:
        if is_background_task:
            return
        bus = getattr(loop, "bus", None)
        publish = getattr(bus, "publish_outbound", None)
        if not callable(publish):
            return
        normalized = ensure_utf8_text(text or "").strip()
        if not normalized:
            return
        # Keep draft previews short to avoid progress-message flooding.
        if len(normalized) > 600:
            normalized = normalized[:597].rstrip() + "..."
        dedupe_key = f"{phase}:{normalized}"
        if dedupe_key in draft_updates_sent:
            return
        draft_updates_sent.add(dedupe_key)
        try:
            await publish(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=normalized,
                    metadata={"type": "draft_update", "phase": phase, "lane": "partial"},
                )
            )
        except Exception:
            return

    async def _publish_reasoning(reasoning_text: str) -> None:
        if is_background_task:
            return
        bus = getattr(loop, "bus", None)
        publish = getattr(bus, "publish_outbound", None)
        if not callable(publish):
            return
        normalized = ensure_utf8_text(reasoning_text or "").strip()
        if not normalized:
            return
        if len(normalized) > 600:
            normalized = normalized[:597].rstrip() + "..."
        dedupe_key = normalized
        if dedupe_key in reasoning_updates_sent:
            return
        reasoning_updates_sent.add(dedupe_key)
        try:
            await publish(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=normalized,
                    metadata={"type": "reasoning_update", "phase": "thinking", "lane": "reasoning"},
                )
            )
        except Exception:
            return

    async def _return_with_phase(content: str, *, phase: str = "done") -> str:
        if phase == "done" and skill_creation_phase == "executing":
            phase = "verified"
        await _publish_phase(phase)
        return content

    await _publish_phase(skill_creation_phase or "thinking")

    # === FAST PATH: Execute deterministic tools directly, skip LLM tool-call step ===
    # This bypasses fragile tool-call protocols for deterministic intents.
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
        "crypto",
        "server_monitor",
        "check_update",
        "system_update",
    }
    raw_direct_tools = {
        "read_file",
        "list_dir",
        "cleanup_system",
        "get_process_memory",
        "web_search",
        "check_update",
        "system_update",
        "weather",
        "stock",
        "crypto",
    }
    if required_tool and required_tool in direct_tools:
        await _publish_phase("tool")
        direct_result = await loop._execute_required_tool_fallback(required_tool, msg)
        if direct_result is not None:
            logger.info(f"Direct tool execution (bypassed LLM tool-call): {required_tool}")
            metadata = getattr(msg, "metadata", None)
            summarize_file_analysis = bool(
                required_tool == "read_file"
                and isinstance(metadata, dict)
                and metadata.get("file_analysis_mode")
            )
            if required_tool in raw_direct_tools and not summarize_file_analysis:
                return await _return_with_phase(direct_result)
            # Read-only direct tools still get an LLM-formatted summary.
            summary_messages = messages + [
                {
                    "role": "user",
                    "content": (
                        f"[TOOL RESULT: {required_tool}]\n{direct_result}\n\n"
                        "Use this tool result to answer the user's actual request in a clear, friendly "
                        "response in the same language the user used. Do not ask the user to resend a "
                        "path or repeat the same file reference. Be concise and highlight the most "
                        "important information."
                    ),
                }
            ]
            try:
                summary_response = await loop.provider.chat(
                    messages=summary_messages,
                    model=model,
                )
                if summary_response and summary_response.content:
                    return await _return_with_phase(summary_response.content)
            except Exception as e:
                logger.warning(f"LLM summary failed for {required_tool}, returning raw result: {e}")
            # Fallback: return raw result if LLM still fails
            return await _return_with_phase(direct_result)
    # === END FAST PATH ===

    skip_plan_for_speed = (
        not is_background_task
        and (
        bool(required_tool)
        or raw_user_word_count <= 12
        or _looks_like_short_confirmation(raw_user_text)
        or route_profile in {"CHAT", "RESEARCH"}
        )
    )
    plan = None
    if not required_tool and not skip_plan_for_speed:
        plan = await loop._plan_task(question_text)
        if plan:
            messages.append({"role": "user", "content": f"[SYSTEM PLAN]\n{plan}\n\nNow execute this plan step by step."})
    else:
        if required_tool:
            logger.info(f"Skipping plan for immediate-action task: required_tool={required_tool}")
        else:
            logger.info("Skipping plan for speed: short/follow-up/research route")

    messages = loop._apply_think_mode(messages, session)

    while iteration < loop.max_iterations:
        iteration += 1

        if loop.context_guard.check_overflow(messages, model):
            logger.warning("Context overflow detected, compacting history")
            messages = await loop.compactor.compact(
                messages, loop.provider, model, keep_recent=10
            )
            if loop.context_guard.check_overflow(messages, model):
                logger.warning("Context still over limit after compaction")

        response, error = await loop._call_llm_with_fallback(messages, models_to_try)
        if not response:
            # User-friendly error: never expose raw exception / internal URLs
            error_hint = _sanitize_error(str(error)) if error else "unknown error"
            return await _return_with_phase(
                f"WARNING: All available AI models failed to respond.\n"
                f"Error: {error_hint}\n\n"
                f"Tip: Try /switch <model> to change model, or try again in a moment."
                ,
                phase="error",
            )

        if required_tool and response.has_tool_calls:
            if any(tc.name == required_tool for tc in response.tool_calls):
                required_tool = None
                tool_enforcement_retries = 0
            else:
                wrong_tools = ", ".join(tc.name for tc in response.tool_calls)
                if tool_enforcement_retries < max_tool_retry:
                    tool_enforcement_retries += 1
                    logger.warning(
                        f"Tool enforcement: expected '{required_tool}' but got other tools ({wrong_tools}) (iter {iteration})"
                    )
                    if response.content:
                        messages = loop.context.add_assistant_message(
                            messages, response.content, reasoning_content=response.reasoning_content
                        )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"SYSTEM: This request REQUIRES the '{required_tool}' tool. "
                                f"You called [{wrong_tools}] which is incorrect for this task. "
                                "Call the required tool now."
                            ),
                        }
                    )
                    continue

                fallback_result = await loop._execute_required_tool_fallback(required_tool, msg)
                if fallback_result is not None:
                    logger.warning(
                        f"Tool enforcement fallback executed for '{required_tool}' after wrong tool calls"
                    )
                    return await _return_with_phase(fallback_result)
        if response.has_tool_calls:
            tools_executed = True

        if required_tool and not response.has_tool_calls:
            if tool_enforcement_retries < max_tool_retry:
                tool_enforcement_retries += 1
                logger.warning(
                    f"Tool enforcement: expected '{required_tool}' but got text-only response (iter {iteration})"
                )
                if response.content:
                    messages = loop.context.add_assistant_message(
                        messages, response.content, reasoning_content=response.reasoning_content
                    )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"SYSTEM: For this request, you MUST call the '{required_tool}' tool now. "
                            "Do not answer from memory or estimation. Return a tool call."
                        ),
                    }
                )
                continue

            fallback_result = await loop._execute_required_tool_fallback(required_tool, msg)
            if fallback_result is not None:
                logger.warning(f"Tool enforcement fallback executed for '{required_tool}'")
                return await _return_with_phase(fallback_result)

        if response.has_tool_calls:
            await _publish_phase("tool")

        if response.content:
            if response.reasoning_content:
                await _publish_reasoning(response.reasoning_content)
            if not response.has_tool_calls and not self_eval_retried and not is_background_task:
                passed, nudge = loop._self_evaluate(question_text, response.content)
                if not passed and nudge:
                    self_eval_retried = True
                    logger.warning(f"Self-eval: refusal detected, retrying (iter {iteration})")
                    await _publish_draft(response.content, phase="thinking")
                    messages = loop.context.add_assistant_message(messages, response.content, reasoning_content=response.reasoning_content)
                    messages.append({"role": "user", "content": nudge})
                    continue

            if (
                not response.has_tool_calls
                and critic_retried < max_critic_retries
                and not is_weak_model
                and not tools_executed
                and not is_background_task
                and not skip_critic_for_speed
            ):
                score, feedback = await loop._critic_evaluate(question_text, response.content, model)
                if first_score is None:
                    first_score = score

                if score < critic_threshold and critic_retried < max_critic_retries:
                    critic_retried += 1
                    logger.warning(
                        f"Critic: score {score}/10 (threshold: {critic_threshold}), retrying ({critic_retried}/{max_critic_retries})"
                    )
                    await _publish_draft(response.content, phase="thinking")
                    messages = loop.context.add_assistant_message(messages, response.content, reasoning_content=response.reasoning_content)
                    messages.append({"role": "user", "content": (
                        f"[CRITIC FEEDBACK - Score: {score}/10]\n{feedback}\n\n"
                        f"Please improve your response based on this feedback."
                    )})
                    continue
                else:
                    if critic_retried > 0:
                        await loop._log_lesson(
                            question=question_text,
                            feedback=feedback,
                            score_before=first_score or 0,
                            score_after=score,
                        )

            messages = loop.context.add_assistant_message(messages, response.content, reasoning_content=response.reasoning_content)
            if not response.has_tool_calls:
                return await _return_with_phase(response.content)

        if response.has_tool_calls:
            messages = await loop._process_tool_calls(msg, messages, response, session)
        else:
            return await _return_with_phase(response.content)
    return await _return_with_phase("I've completed processing but have no response to give.")


async def process_tool_calls(loop: Any, msg: InboundMessage, messages: list, response: Any, session: Any) -> list:
    """Execute tool calls and append results to conversation context."""
    resilience_cfg = _runtime_resilience_cfg(loop)
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

        result = await loop.tools.execute(tc.name, tool_params)

        # Record tool call for loop detection
        loop.loop_detector.record(tc.name, tool_params, tc.id)
        result_str = str(result)
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


