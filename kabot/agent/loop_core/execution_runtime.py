"""Execution loop and tool-call runtime extracted from AgentLoop."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any

from loguru import logger

from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.core.failover_error import resolve_failover_reason
from kabot.utils.text_safety import ensure_utf8_text


def _sanitize_error(error_str: str) -> str:
    """Strip internal URLs, API keys, and verbose tracebacks from user-facing errors."""
    import re
    # Remove full URLs (internal API endpoints)
    sanitized = re.sub(r'https?://\S+', '[API endpoint]', error_str)
    # Remove anything that looks like an API key
    sanitized = re.sub(r'(sk-|key-|Bearer )[a-zA-Z0-9_-]{10,}', '[redacted]', sanitized)
    # Truncate excessively long messages
    if len(sanitized) > 200:
        sanitized = sanitized[:200] + "..."
    return ensure_utf8_text(sanitized)


def _runtime_resilience_cfg(loop: Any) -> Any:
    return getattr(loop, "runtime_resilience", None)


def _runtime_performance_cfg(loop: Any) -> Any:
    return getattr(loop, "runtime_performance", None)


def _extract_status_code(exc: Exception) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    text = str(exc)
    for token in (" 400 ", " 401 ", " 402 ", " 403 ", " 404 ", " 408 ", " 409 ", " 429 ", " 500 ", " 502 ", " 503 ", " 504 "):
        if token in text:
            try:
                return int(token.strip())
            except Exception:
                return None
    return None


def _classify_runtime_error(loop: Any, exc: Exception, status_code: int | None = None) -> str:
    """Classify errors for deterministic fallback decisions."""
    msg = str(exc or "")
    msg_lower = msg.lower()
    status = status_code if isinstance(status_code, int) else _extract_status_code(exc)

    if "no tool call found for function call output" in msg_lower:
        return "tool_protocol"

    strict = bool(getattr(_runtime_resilience_cfg(loop), "strict_error_classification", True))
    if not strict:
        if status == 401:
            return "auth"
        if status == 429 or "rate" in msg_lower:
            return "rate_limit"
        if status in {500, 502, 503, 504}:
            return "transient"
        if status == 400:
            return "tool_protocol"
        return "fatal"

    reason = resolve_failover_reason(status=status, message=msg)
    if reason == "auth":
        return "auth"
    if reason == "rate_limit":
        return "rate_limit"
    if reason in {"timeout", "unknown"}:
        return "transient"
    if reason == "format":
        return "tool_protocol"
    # billing/model_not_found are fatal for current model but fallback can still continue.
    return "fatal"


def _prune_expiring_cache(cache: dict[str, tuple[float, str]]) -> None:
    now = time.time()
    expired = [key for key, (expires_at, _) in cache.items() if expires_at <= now]
    for key in expired:
        cache.pop(key, None)


def _stable_tool_payload_hash(
    session_key: str,
    turn_id: str,
    tool_name: str,
    tool_args: dict[str, Any],
) -> str:
    normalized_args = json.dumps(tool_args, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    raw = f"{session_key}|{turn_id}|{tool_name}|{normalized_args}"
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def _should_defer_memory_write(loop: Any) -> bool:
    perf_cfg = _runtime_performance_cfg(loop)
    if not perf_cfg:
        return False
    return bool(getattr(perf_cfg, "fast_first_response", True))


def _schedule_memory_write(loop: Any, coro: Any, *, label: str) -> None:
    task = asyncio.create_task(coro)
    pending = getattr(loop, "_pending_memory_tasks", None)
    if not isinstance(pending, set):
        pending = set()
        setattr(loop, "_pending_memory_tasks", pending)
    pending.add(task)

    def _done_callback(done_task: asyncio.Task) -> None:
        pending.discard(done_task)
        try:
            done_task.result()
        except Exception as exc:
            logger.warning(f"Background memory write failed ({label}): {exc}")

    task.add_done_callback(_done_callback)


async def run_simple_response(loop: Any, msg: InboundMessage, messages: list) -> str | None:
    """Direct single-shot response for simple queries (no loop, no tools)."""
    try:
        models_to_try = loop._resolve_models_for_message(msg)
        model = models_to_try[0]

        if loop.context_guard.check_overflow(messages, model):
            logger.warning("Context overflow detected in simple response, compacting history")
            messages = await loop.compactor.compact(
                messages, loop.provider, model, keep_recent=10
            )
            if loop.context_guard.check_overflow(messages, model):
                logger.warning("Context still over limit after compaction")

        response, error = await loop._call_llm_with_fallback(messages, models_to_try)
        if not response:
            error_hint = _sanitize_error(str(error)) if error else "unknown error"
            return (
                "An error occurred while processing your message.\n"
                f"Error: {error_hint}\n\n"
                "Hint: use /switch <model> to change model, or try again in a moment."
            )

        return response.content or ""
    except Exception as e:
        logger.error(f"Simple response failed: {e}")
        error_hint = _sanitize_error(str(e))
        return (
            "An error occurred while processing your message.\n"
            f"Error: {error_hint}\n\n"
            "Hint: use /switch <model> to change model, or try again in a moment."
        )


async def run_agent_loop(loop: Any, msg: InboundMessage, messages: list, session: Any) -> str | None:
    """Full planner-executor-critic loop for complex tasks."""
    iteration = 0

    models_to_try = loop._resolve_models_for_message(msg)
    model = models_to_try[0]

    self_eval_retried = False
    critic_retried = 0
    max_tool_retry = max(0, int(getattr(_runtime_resilience_cfg(loop), "max_tool_retry_per_turn", 1)))
    tool_enforcement_retries = 0
    status_updates_sent: set[str] = set()
    required_tool = loop._required_tool_for_query(msg.content)
    # Synthetic/system callbacks (cron completion, heartbeat, etc.) should not
    # trigger hard tool-enforcement loops from reminder/weather keywords inside
    # system-generated text.
    if (msg.channel or "").lower() == "system" or (msg.sender_id or "").lower() == "system":
        required_tool = None
    tools_executed = False

    is_weak_model = loop._is_weak_model(model)
    max_critic_retries = 1 if is_weak_model else 2
    critic_threshold = 5 if is_weak_model else 7

    first_score = None

    plan = await loop._plan_task(msg.content)
    if plan:
        messages.append({"role": "user", "content": f"[SYSTEM PLAN]\n{plan}\n\nNow execute this plan step by step."})

    messages = loop._apply_think_mode(messages, session)

    # === FAST PATH: Execute deterministic tools directly, skip LLM tool-call step ===
    # This bypasses the broken tool-calling API (e.g. codex models returning 400),
    # but still uses the LLM to produce a nice natural-language summary of the result.
    _DIRECT_TOOLS = {"get_process_memory", "get_system_info", "cleanup_system", "weather", "speedtest", "stock", "crypto", "server_monitor"}
    if required_tool and required_tool in _DIRECT_TOOLS:
        direct_result = await loop._execute_required_tool_fallback(required_tool, msg)
        if direct_result is not None:
            logger.info(f"Direct tool execution (bypassed LLM tool-call): {required_tool}")
            # Now ask the LLM to format the result naturally
            summary_messages = messages + [
                {
                    "role": "user",
                    "content": (
                        f"[TOOL RESULT: {required_tool}]\n{direct_result}\n\n"
                        "Summarize this data in a clear, friendly response in the same language "
                        "the user used. Be concise and highlight the most important information."
                    ),
                }
            ]
            try:
                summary_response = await loop.provider.chat(
                    messages=summary_messages,
                    model=model,
                )
                if summary_response and summary_response.content:
                    return summary_response.content
            except Exception as e:
                logger.warning(f"LLM summary failed for {required_tool}, returning raw result: {e}")
            # Fallback: return raw result if LLM still fails
            return direct_result
    # === END FAST PATH ===

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
            return (
                f"WARNING: All available AI models failed to respond.\n"
                f"Error: {error_hint}\n\n"
                f"Tip: Try /switch <model> to change model, or try again in a moment."
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
                    return fallback_result
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
                return fallback_result

        if response.content:
            if not response.has_tool_calls and not self_eval_retried:
                passed, nudge = loop._self_evaluate(msg.content, response.content)
                if not passed and nudge:
                    self_eval_retried = True
                    logger.warning(f"Self-eval: refusal detected, retrying (iter {iteration})")
                    messages = loop.context.add_assistant_message(messages, response.content, reasoning_content=response.reasoning_content)
                    messages.append({"role": "user", "content": nudge})
                    continue

            if (
                not response.has_tool_calls
                and critic_retried < max_critic_retries
                and not is_weak_model
                and not tools_executed
            ):
                score, feedback = await loop._critic_evaluate(msg.content, response.content, model)
                if first_score is None:
                    first_score = score

                if score < critic_threshold and critic_retried < max_critic_retries:
                    critic_retried += 1
                    logger.warning(
                        f"Critic: score {score}/10 (threshold: {critic_threshold}), retrying ({critic_retried}/{max_critic_retries})"
                    )
                    messages = loop.context.add_assistant_message(messages, response.content, reasoning_content=response.reasoning_content)
                    messages.append({"role": "user", "content": (
                        f"[CRITIC FEEDBACK - Score: {score}/10]\n{feedback}\n\n"
                        f"Please improve your response based on this feedback."
                    )})
                    continue
                else:
                    if critic_retried > 0:
                        await loop._log_lesson(
                            question=msg.content,
                            feedback=feedback,
                            score_before=first_score or 0,
                            score_after=score,
                        )

            if response.has_tool_calls:
                # If the AI generated tool calls but forgot to say anything,
                # send a progressive status update to the user automatically.
                display_content = response.content or "Processing your request, please wait..."
                if display_content not in status_updates_sent:
                    status_updates_sent.add(display_content)
                    await loop.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id, content=display_content
                    ))

            messages = loop.context.add_assistant_message(messages, response.content, reasoning_content=response.reasoning_content)
            if not response.has_tool_calls:
                return response.content

        if response.has_tool_calls:
            messages = await loop._process_tool_calls(msg, messages, response, session)
        else:
            return response.content
    return "I've completed processing but have no response to give."


async def call_llm_with_fallback(loop: Any, messages: list, models: list) -> tuple[Any | None, Exception | None]:
    """Call provider with deterministic, bounded fallback state machine."""
    if not models:
        return None, RuntimeError("No models configured")

    resilience_cfg = _runtime_resilience_cfg(loop)
    max_attempts_cfg = int(getattr(resilience_cfg, "max_model_attempts_per_turn", 4))
    max_attempts = max(1, min(len(models), max_attempts_cfg))

    chain_snapshot = tuple(models)
    turn_id = str(getattr(loop, "_active_turn_id", "turn-unknown"))
    last_error: Exception | None = None

    for attempt_idx, current_model in enumerate(chain_snapshot[:max_attempts], start=1):
        state = "primary" if attempt_idx == 1 else "model_fallback"
        original_key = None

        if loop.auth_rotation and hasattr(loop.provider, "api_key"):
            current_key = loop.auth_rotation.current_key()
            original_key = loop.provider.api_key
            loop.provider.api_key = current_key

        try:
            response = await loop.provider.chat(
                messages=messages,
                tools=loop.tools.get_definitions(),
                model=current_model,
            )
            if original_key is not None:
                loop.provider.api_key = original_key

            loop.last_model_used = current_model
            loop.last_fallback_used = bool(current_model != chain_snapshot[0])
            loop.last_model_chain = list(chain_snapshot)
            if hasattr(loop, "resilience"):
                loop.resilience.on_success()
            logger.info(
                f"turn_id={turn_id} attempt={attempt_idx}/{max_attempts} state={state} "
                f"model={current_model} result=success"
            )
            return response, None
        except Exception as exc:
            if original_key is not None:
                loop.provider.api_key = original_key

            status_code = _extract_status_code(exc)
            error_class = _classify_runtime_error(loop, exc, status_code=status_code)
            last_error = exc
            logger.warning(
                f"turn_id={turn_id} attempt={attempt_idx}/{max_attempts} state={state} "
                f"model={current_model} class={error_class} error={exc}"
            )

            # State: auth_rotate (one attempt on same model with rotated key)
            if (
                loop.auth_rotation
                and hasattr(loop.provider, "api_key")
                and error_class in {"auth", "rate_limit"}
            ):
                current_key = loop.auth_rotation.current_key()
                reason = "rate_limit" if error_class == "rate_limit" else "auth_error"
                loop.auth_rotation.mark_failed(current_key, reason)
                next_key = loop.auth_rotation.rotate()
                if next_key and next_key != current_key:
                    try:
                        state = "auth_rotate"
                        original_key = loop.provider.api_key
                        loop.provider.api_key = next_key
                        logger.info(
                            f"turn_id={turn_id} attempt={attempt_idx}/{max_attempts} "
                            f"state={state} model={current_model} reason={reason}"
                        )
                        response = await loop.provider.chat(
                            messages=messages,
                            tools=loop.tools.get_definitions(),
                            model=current_model,
                        )
                        loop.provider.api_key = original_key
                        loop.last_model_used = current_model
                        loop.last_fallback_used = bool(current_model != chain_snapshot[0])
                        loop.last_model_chain = list(chain_snapshot)
                        if hasattr(loop, "resilience"):
                            loop.resilience.on_success()
                        return response, None
                    except Exception as rotate_exc:
                        if original_key is not None:
                            loop.provider.api_key = original_key
                        last_error = rotate_exc
                        status_code = _extract_status_code(rotate_exc)
                        error_class = _classify_runtime_error(loop, rotate_exc, status_code=status_code)
                        logger.warning(
                            f"turn_id={turn_id} attempt={attempt_idx}/{max_attempts} state=auth_rotate "
                            f"model={current_model} class={error_class} error={rotate_exc}"
                        )

            # State: text_only_retry (tool protocol mismatch only).
            if error_class == "tool_protocol":
                try:
                    logger.warning(
                        f"turn_id={turn_id} attempt={attempt_idx}/{max_attempts} "
                        f"state=text_only_retry model={current_model}"
                    )
                    response = await loop.provider.chat(
                        messages=messages,
                        model=current_model,
                    )
                    loop.last_model_used = current_model
                    loop.last_fallback_used = bool(current_model != chain_snapshot[0])
                    loop.last_model_chain = list(chain_snapshot)
                    if hasattr(loop, "resilience"):
                        loop.resilience.on_success()
                    return response, None
                except Exception as text_only_exc:
                    last_error = text_only_exc
                    logger.warning(
                        f"turn_id={turn_id} attempt={attempt_idx}/{max_attempts} state=text_only_retry "
                        f"model={current_model} class={_classify_runtime_error(loop, text_only_exc)} "
                        f"error={text_only_exc}"
                    )

            if hasattr(loop, "resilience"):
                try:
                    await loop.resilience.handle_error(exc, status_code=status_code)
                except Exception:
                    pass

            # Continue to next model in immutable snapshot.
            continue

    loop.last_model_chain = list(chain_snapshot)
    return None, last_error


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
            messages = loop.context.add_tool_result(messages, tc.id, tc.name, cached_result)
            continue

        # Check for tool loops before execution
        loop_result = loop.loop_detector.check(tc.name, tool_params)
        if loop_result.stuck:
            if loop_result.level == "critical":
                # Block execution and return error
                error_msg = f"WARNING: Tool loop detected: {loop_result.message}"
                logger.warning(f"Tool loop blocked: {tc.name} - {loop_result.message}")
                messages = loop.context.add_tool_result(messages, tc.id, tc.name, error_msg)
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
                channel=msg.channel, chat_id=msg.chat_id, content=f"_{status}_", metadata={"type": "status_update"}
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
        messages = loop.context.add_tool_result(messages, tc.id, tc.name, result_for_llm)
        if dedupe_enabled:
            expires_at = time.time() + ttl_seconds
            payload_cache[payload_key] = (expires_at, result_for_llm)
            call_id_cache[tc.id] = (expires_at, result_for_llm)

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


def format_tool_result(loop: Any, result: Any) -> str:
    """Format tool result for LLM context."""
    return str(result)

