"""Structured delivery-route helpers for session continuity."""

from __future__ import annotations

from typing import Any

from kabot.bus.events import InboundMessage


_DELIVERY_ROUTE_FIELDS = (
    "channel",
    "chat_id",
    "account_id",
    "peer_kind",
    "peer_id",
    "guild_id",
    "team_id",
    "thread_id",
)


def _normalize_scalar(value: Any) -> str | None:
    if not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    return text or None


def normalize_delivery_route(value: Any) -> dict[str, Any] | None:
    """Normalize arbitrary route metadata into a compact structured dict."""
    if not isinstance(value, dict):
        return None
    result: dict[str, Any] = {}
    for key in _DELIVERY_ROUTE_FIELDS:
        normalized = _normalize_scalar(value.get(key))
        if normalized:
            result[key] = normalized
    parent_peer = value.get("parent_peer")
    if isinstance(parent_peer, dict):
        kind = _normalize_scalar(parent_peer.get("kind"))
        peer_id = _normalize_scalar(parent_peer.get("id"))
        if kind and peer_id:
            result["parent_peer"] = {"kind": kind, "id": peer_id}
    return result or None


def merge_delivery_route(primary: Any, fallback: Any) -> dict[str, Any] | None:
    """Merge two route payloads, preferring the primary values when present."""
    primary_norm = normalize_delivery_route(primary) or {}
    fallback_norm = normalize_delivery_route(fallback) or {}
    if not primary_norm and not fallback_norm:
        return None
    merged = dict(fallback_norm)
    merged.update(primary_norm)
    return merged or None


def delivery_route_from_message(msg: InboundMessage) -> dict[str, Any] | None:
    """Build a normalized delivery route from an inbound message."""
    payload: dict[str, Any] = {
        "channel": msg.channel,
        "chat_id": msg.chat_id,
        "account_id": msg.account_id,
        "peer_kind": msg.peer_kind,
        "peer_id": msg.peer_id,
        "guild_id": msg.guild_id,
        "team_id": msg.team_id,
        "thread_id": msg.thread_id,
        "parent_peer": msg.parent_peer,
    }
    return normalize_delivery_route(payload)
