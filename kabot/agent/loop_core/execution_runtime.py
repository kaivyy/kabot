"""Execution loop and tool-call runtime extracted from AgentLoop."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from kabot.bus.events import InboundMessage, OutboundMessage


async def run_simple_response(loop: Any, msg: InboundMessage, messages: list) -> str | None:
    """Direct single-shot response for simple queries (no loop, no tools)."""
    try:
        model = loop._resolve_model_for_message(msg)

        if loop.context_guard.check_overflow(messages, model):
            logger.warning("Context overflow detected in simple response, compacting history")
            messages = await loop.compactor.compact(
                messages, loop.provider, model, keep_recent=10
            )
            if loop.context_guard.check_overflow(messages, model):
                logger.warning("Context still over limit after compaction")

        response = await loop.provider.chat(
            messages=messages,
            model=model,
        )
        return response.content or ""
    except Exception as e:
        logger.error(f"Simple response failed: {e}")
        return f"Sorry, an error occurred: {str(e)}"


async def run_agent_loop(loop: Any, msg: InboundMessage, messages: list, session: Any) -> str | None:
    """Full planner-executor-critic loop for complex tasks."""
    iteration = 0

    models_to_try = loop._resolve_models_for_message(msg)
    model = models_to_try[0]

    self_eval_retried = False
    critic_retried = 0
    tool_enforcement_retried = False
    required_tool = loop._required_tool_for_query(msg.content)
    tools_executed = False

    is_weak_model = loop._is_weak_model(model)
    max_critic_retries = 1 if is_weak_model else 2
    critic_threshold = 5 if is_weak_model else 7

    first_score = None

    plan = await loop._plan_task(msg.content)
    if plan:
        messages.append({"role": "user", "content": f"[SYSTEM PLAN]\n{plan}\n\nNow execute this plan step by step."})

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
            return f"Sorry, all available models failed. Last error: {str(error)}"

        if required_tool and response.has_tool_calls:
            if any(tc.name == required_tool for tc in response.tool_calls):
                required_tool = None
                tool_enforcement_retried = False
            else:
                wrong_tools = ", ".join(tc.name for tc in response.tool_calls)
                if not tool_enforcement_retried:
                    tool_enforcement_retried = True
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
            if not tool_enforcement_retried:
                tool_enforcement_retried = True
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
                await loop.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id, content=response.content
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
    """Call provider with model fallback and auth rotation handling."""
    last_error = None
    for current_model in models:
        try:
            original_key = None
            if loop.auth_rotation:
                current_key = loop.auth_rotation.current_key()
                if hasattr(loop.provider, "api_key"):
                    original_key = loop.provider.api_key
                    loop.provider.api_key = current_key

            response = await loop.provider.chat(
                messages=messages,
                tools=loop.tools.get_definitions(),
                model=current_model,
            )

            if loop.auth_rotation and original_key is not None:
                loop.provider.api_key = original_key

            loop.resilience.on_success()
            return response, None
        except Exception as e:
            error_str = str(e).lower()

            if loop.auth_rotation and hasattr(loop.provider, "api_key"):
                if "401" in error_str or "429" in error_str or "rate" in error_str:
                    reason = "rate_limit" if "429" in error_str or "rate" in error_str else "auth_error"
                    current_key = loop.auth_rotation.current_key()
                    loop.auth_rotation.mark_failed(current_key, reason)

                    next_key = loop.auth_rotation.rotate()
                    if next_key != current_key:
                        logger.info(f"Retrying with rotated key due to {reason}")
                        if original_key is not None:
                            loop.provider.api_key = original_key
                        continue

            if loop.auth_rotation and original_key is not None:
                loop.provider.api_key = original_key

            logger.warning(f"Model {current_model} failed: {e}")
            last_error = e
            status_code = getattr(e, "status_code", None)
            recovery = await loop.resilience.handle_error(e, status_code=status_code)
            if recovery["action"] == "model_fallback" and recovery["new_model"]:
                models.append(recovery["new_model"])
    return None, last_error


async def process_tool_calls(loop: Any, msg: InboundMessage, messages: list, response: Any, session: Any) -> list:
    """Execute tool calls and append results to conversation context."""
    tool_call_dicts = [
        {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
        for tc in response.tool_calls
    ]
    if not response.content:
        messages = loop.context.add_assistant_message(messages, None, tool_call_dicts, reasoning_content=response.reasoning_content)

    tc_data = [{"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in response.tool_calls]
    await loop.memory.add_message(msg.session_key, "assistant", response.content or "", tool_calls=tc_data)

    permissions = loop._get_tool_permissions(session)
    if permissions.get("auto_approve") or loop.exec_auto_approve:
        logger.debug("Elevated mode active: auto_approve=True, restrict_to_workspace=False")

    exec_tool = loop.tools.get("exec")
    if exec_tool and hasattr(exec_tool, "auto_approve"):
        exec_tool.auto_approve = bool(
            loop.exec_auto_approve or permissions.get("auto_approve", False)
        )

    for tc in response.tool_calls:
        status = loop._get_tool_status_message(tc.name, tc.arguments)
        if status:
            await loop.bus.publish_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=f"_{status}_", metadata={"type": "status_update"}
            ))
        tool_params = dict(tc.arguments)
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
        result_str = str(result)
        truncated_result = loop.truncator.truncate(result_str, tc.name)

        if loop._should_log_verbose(session):
            token_count = loop.truncator._count_tokens(result_str)
            verbose_output = loop._format_verbose_output(tc.name, result_str, token_count)
            truncated_result += verbose_output

        result_for_llm = loop._format_tool_result(truncated_result)
        messages = loop.context.add_tool_result(messages, tc.id, tc.name, result_for_llm)
        await loop.memory.add_message(
            msg.session_key, "tool", str(result),
            tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": str(result)[:1000]}],
        )
    return messages


def format_tool_result(loop: Any, result: Any) -> str:
    """Format tool result for LLM context."""
    return str(result)
