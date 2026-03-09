"""LLM/simple-response helpers extracted from execution_runtime."""

from __future__ import annotations

from typing import Any

from loguru import logger

from kabot.agent.loop_core.execution_runtime_parts.helpers import (
    _apply_response_quota_usage,
    _check_quota_guard,
    _classify_runtime_error,
    _emit_runtime_event,
    _extract_status_code,
    _runtime_resilience_cfg,
    _sanitize_error,
)
from kabot.bus.events import InboundMessage


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

        response, error = await loop._call_llm_with_fallback(
            messages,
            models_to_try,
            include_tools_initial=False,
        )
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

async def call_llm_with_fallback(
    loop: Any,
    messages: list,
    models: list,
    include_tools_initial: bool = True,
) -> tuple[Any | None, Exception | None]:
    """Call provider with deterministic, bounded fallback state machine."""
    if not models:
        return None, RuntimeError("No models configured")

    resilience_cfg = _runtime_resilience_cfg(loop)
    max_attempts_cfg = int(getattr(resilience_cfg, "max_model_attempts_per_turn", 4))
    max_attempts = max(1, min(len(models), max_attempts_cfg))

    chain_snapshot = tuple(models)
    turn_id = str(getattr(loop, "_active_turn_id", "turn-unknown"))
    last_error: Exception | None = None

    def _provider_response_is_error(response: Any) -> bool:
        """Detect provider-level synthetic error payloads that should trigger model fallback."""
        finish_reason = str(getattr(response, "finish_reason", "") or "").lower()
        if finish_reason == "error":
            return True
        content = str(getattr(response, "content", "") or "")
        return content.startswith("All models failed. Last error:")

    async def _chat_single_model(model_name: str, *, include_tools: bool) -> Any:
        """
        Execute provider call for one explicit model only.

        Runtime already owns model fallback order; provider-level fallback chain
        is temporarily disabled to avoid double-fallback ambiguity and misleading
        observability (e.g., primary logs "success" while fallback actually answered).
        """
        provider = loop.provider
        restore_fallbacks: list[str] | None = None
        current_fallbacks = getattr(provider, "fallbacks", None)
        if isinstance(current_fallbacks, list):
            restore_fallbacks = list(current_fallbacks)
            provider.fallbacks = []
        try:
            kwargs: dict[str, Any] = {
                "messages": messages,
                "model": model_name,
            }
            if include_tools:
                kwargs["tools"] = loop.tools.get_definitions()
            return await provider.chat(**kwargs)
        finally:
            if restore_fallbacks is not None:
                provider.fallbacks = restore_fallbacks

    for attempt_idx, current_model in enumerate(chain_snapshot[:max_attempts], start=1):
        state = "primary" if attempt_idx == 1 else "model_fallback"
        original_key = None
        _emit_runtime_event(
            loop,
            "llm_attempt",
            turn_id=turn_id,
            model_chain=list(chain_snapshot),
            attempt_index=attempt_idx,
            model=current_model,
            state=state,
        )

        allowed_by_quota, quota_message = _check_quota_guard(
            loop,
            messages,
            current_model,
            turn_id=turn_id,
            attempt_index=attempt_idx,
        )
        if quota_message:
            logger.warning(quota_message)
        if not allowed_by_quota:
            return None, RuntimeError(f"Quota exceeded: {quota_message}")

        if loop.auth_rotation and hasattr(loop.provider, "api_key"):
            current_key = loop.auth_rotation.current_key()
            original_key = loop.provider.api_key
            loop.provider.api_key = current_key

        try:
            response = await _chat_single_model(current_model, include_tools=include_tools_initial)
            if _provider_response_is_error(response):
                raise RuntimeError(str(getattr(response, "content", "Provider returned error response")))
            if original_key is not None:
                loop.provider.api_key = original_key

            loop.last_model_used = current_model
            loop.last_fallback_used = bool(current_model != chain_snapshot[0])
            loop.last_model_chain = list(chain_snapshot)
            _apply_response_quota_usage(loop, response)
            if hasattr(loop, "resilience"):
                loop.resilience.on_success()
            logger.info(
                f"turn_id={turn_id} attempt={attempt_idx}/{max_attempts} state={state} "
                f"model={current_model} result=success"
            )
            _emit_runtime_event(
                loop,
                "llm_attempt_result",
                turn_id=turn_id,
                model_chain=list(chain_snapshot),
                attempt_index=attempt_idx,
                model=current_model,
                state=state,
                result="success",
                error_class="",
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
            _emit_runtime_event(
                loop,
                "llm_attempt_result",
                turn_id=turn_id,
                model_chain=list(chain_snapshot),
                attempt_index=attempt_idx,
                model=current_model,
                state=state,
                result="error",
                error_class=error_class,
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
                        response = await _chat_single_model(current_model, include_tools=True)
                        if _provider_response_is_error(response):
                            raise RuntimeError(str(getattr(response, "content", "Provider returned error response")))
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
                    response = await _chat_single_model(current_model, include_tools=False)
                    if _provider_response_is_error(response):
                        raise RuntimeError(str(getattr(response, "content", "Provider returned error response")))
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

def format_tool_result(loop: Any, result: Any) -> str:
    """Format tool result for LLM context."""
    return str(result)
