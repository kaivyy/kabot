"""Routing/model resolution helpers extracted from AgentLoop."""

from __future__ import annotations

from typing import Any

from kabot.bus.events import InboundMessage


def route_context_for_message(loop: Any, msg: InboundMessage) -> dict[str, Any]:
    """Build normalized routing context from message + channel instance metadata."""
    metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
    instance_meta = (
        metadata.get("channel_instance")
        if isinstance(metadata.get("channel_instance"), dict)
        else {}
    )

    account_id = msg.account_id
    instance_id = instance_meta.get("id")
    if not account_id and isinstance(instance_id, (str, int)):
        account_id = str(instance_id)

    peer_kind = msg.peer_kind
    peer_id = msg.peer_id
    if not peer_kind and metadata.get("is_group") is True:
        peer_kind = "group"
    elif not peer_kind and msg.chat_id:
        peer_kind = "direct"
    if not peer_id and msg.chat_id:
        peer_id = msg.chat_id

    peer = None
    if isinstance(peer_kind, str) and peer_kind and isinstance(peer_id, str) and peer_id:
        peer = {"kind": peer_kind, "id": peer_id}

    parent_peer = msg.parent_peer if isinstance(msg.parent_peer, dict) else None

    forced_agent_id = None
    if isinstance(instance_meta.get("agent_binding"), str) and instance_meta["agent_binding"].strip():
        forced_agent_id = instance_meta["agent_binding"].strip()

    return {
        "channel": msg.channel,
        "account_id": account_id,
        "forced_agent_id": forced_agent_id,
        "peer": peer,
        "parent_peer": parent_peer,
        "guild_id": msg.guild_id,
        "team_id": msg.team_id,
        "thread_id": msg.thread_id,
    }


def resolve_route_for_message(loop: Any, msg: InboundMessage) -> dict[str, str]:
    """Resolve OpenClaw-compatible route for a message with instance-aware context."""
    from kabot.routing.bindings import resolve_agent_route

    ctx = route_context_for_message(loop, msg)
    return resolve_agent_route(
        config=loop.config,
        channel=ctx["channel"],
        account_id=ctx["account_id"],
        forced_agent_id=ctx["forced_agent_id"],
        peer=ctx["peer"],
        parent_peer=ctx["parent_peer"],
        guild_id=ctx["guild_id"],
        team_id=ctx["team_id"],
        thread_id=ctx["thread_id"],
    )


def resolve_models_for_message(loop: Any, msg: InboundMessage) -> list[str]:
    """Resolve model chain for this message, including per-agent fallback overrides."""
    from kabot.agent.agent_scope import resolve_agent_model, resolve_agent_model_fallbacks

    route = resolve_route_for_message(loop, msg)
    agent_id = route["agent_id"]

    primary = loop.model
    fallback_models = list(loop.fallbacks)

    agent_model = resolve_agent_model(loop.config, agent_id)
    if agent_model:
        primary = loop.registry.resolve(agent_model)

        # OpenClaw-compatible behavior: per-agent fallbacks override global fallbacks.
        agent_fallbacks = resolve_agent_model_fallbacks(loop.config, agent_id)
        if agent_fallbacks:
            fallback_models = [loop.registry.resolve(m) for m in agent_fallbacks]

    chain: list[str] = []
    seen: set[str] = set()
    for model in [primary, *fallback_models]:
        resolved = loop.registry.resolve(model)
        if resolved in seen:
            continue
        seen.add(resolved)
        chain.append(resolved)
    return chain


def resolve_model_for_message(loop: Any, msg: InboundMessage) -> str:
    """Resolve primary model for this message based on agent routing."""
    return resolve_models_for_message(loop, msg)[0]


def resolve_agent_id_for_message(loop: Any, msg: InboundMessage) -> str:
    """Resolve routed agent id for this message."""
    route = resolve_route_for_message(loop, msg)
    return route["agent_id"]
