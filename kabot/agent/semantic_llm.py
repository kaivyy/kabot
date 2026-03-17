from __future__ import annotations

from typing import Any

from loguru import logger

from kabot.bus.events import InboundMessage


def _dedupe_models(models: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw_model in models:
        model = str(raw_model or "").strip()
        if not model or model in seen:
            continue
        seen.add(model)
        ordered.append(model)
    return ordered


def _build_provider_model_chain(provider: Any, *, primary_model: str = "") -> list[str]:
    models: list[str] = []
    if primary_model:
        models.append(primary_model)

    get_default_model = getattr(provider, "get_default_model", None)
    if callable(get_default_model):
        try:
            default_model = str(get_default_model() or "").strip()
        except Exception:
            default_model = ""
        if default_model:
            models.append(default_model)

    fallbacks = getattr(provider, "fallbacks", None)
    if isinstance(fallbacks, list):
        models.extend(str(item or "").strip() for item in fallbacks)
    return _dedupe_models(models)


def _build_loop_model_chain(loop: Any, *, primary_model: str = "") -> list[str]:
    provider = getattr(loop, "provider", None)
    models: list[str] = []
    if primary_model:
        models.append(primary_model)

    resolve_models = getattr(loop, "_resolve_models_for_message", None)
    if callable(resolve_models):
        try:
            probe_msg = InboundMessage(
                channel="semantic",
                sender_id="system",
                chat_id="semantic",
                content="semantic-classifier",
                metadata={},
            )
            resolved = resolve_models(probe_msg) or []
        except Exception:
            resolved = []
        if isinstance(resolved, list):
            models.extend(str(item or "").strip() for item in resolved)

    router_model = str(getattr(getattr(loop, "router", None), "model", "") or "").strip()
    loop_model = str(getattr(loop, "model", "") or "").strip()
    if router_model:
        models.append(router_model)
    if loop_model:
        models.append(loop_model)
    if provider is not None:
        models.extend(_build_provider_model_chain(provider, primary_model=""))
    return _dedupe_models(models)


async def call_semantic_llm_with_fallback(
    *,
    loop: Any | None = None,
    provider: Any | None = None,
    messages: list[dict[str, Any]],
    primary_model: str = "",
    max_tokens: int = 120,
    temperature: float = 0.0,
) -> Any | None:
    resolved_provider = provider or getattr(loop, "provider", None)
    chat = getattr(resolved_provider, "chat", None)
    if not callable(chat):
        return None

    model_chain = (
        _build_loop_model_chain(loop, primary_model=primary_model)
        if loop is not None
        else _build_provider_model_chain(resolved_provider, primary_model=primary_model)
    )
    if not model_chain and primary_model:
        model_chain = [primary_model]

    call_with_fallback = getattr(loop, "_call_llm_with_fallback", None) if loop is not None else None
    if callable(call_with_fallback) and model_chain:
        previous_metadata = getattr(loop, "_active_message_metadata", None)
        try:
            setattr(
                loop,
                "_active_message_metadata",
                {
                    "directive_max_tokens": max(1, int(max_tokens or 120)),
                    "directive_temperature": float(temperature),
                    "directive_no_tools": True,
                },
            )
            response, error = await call_with_fallback(
                messages,
                model_chain,
                include_tools_initial=False,
            )
        except Exception as exc:
            logger.debug(f"Semantic fallback chain failed: {exc}")
            response = None
            error = exc
        finally:
            setattr(loop, "_active_message_metadata", previous_metadata)

        if response is not None:
            return response
        if error is not None:
            logger.debug(f"Semantic fallback chain exhausted: {error}")
        return None

    last_error: Exception | None = None
    manual_chain = _dedupe_models(
        [str(item or "").strip() for item in (model_chain or [primary_model])]
    )
    if not manual_chain:
        manual_chain = [""]
    for candidate in manual_chain:
        kwargs: dict[str, Any] = {
            "messages": messages,
            "model": candidate or None,
            "max_tokens": max(1, int(max_tokens or 120)),
            "temperature": float(temperature),
        }
        try:
            return await chat(**kwargs)
        except Exception as exc:
            last_error = exc
            logger.debug(
                "Semantic single-provider attempt failed: "
                f"model={candidate or 'default'} error={exc}"
            )
            continue
    if last_error is not None:
        logger.debug(f"Semantic fallback chain exhausted: {last_error}")
    return None


__all__ = ["call_semantic_llm_with_fallback"]
