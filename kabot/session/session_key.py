"""Session key utilities with OpenClaw-compatible format.

Session key format: agent:{agentId}:{channel}:{peerKind}:{peerId}
Examples:
- agent:main:main (main session)
- agent:work:telegram:direct:123456789 (DM)
- agent:work:discord:group:987654321 (group chat)
- agent:work:telegram:direct:123:thread:456 (thread)
"""

from typing import TypedDict

DEFAULT_AGENT_ID = "main"
DEFAULT_MAIN_KEY = "main"
DEFAULT_ACCOUNT_ID = "default"


class ParsedSessionKey(TypedDict, total=False):
    """Parsed session key components."""
    agent_id: str
    channel: str
    peer_kind: str
    peer_id: str
    thread_id: str | None


def normalize_agent_id(value: str | None) -> str:
    """Normalize agent ID to lowercase alphanumeric."""
    if not value:
        return DEFAULT_AGENT_ID
    trimmed = value.strip().lower()
    if not trimmed:
        return DEFAULT_AGENT_ID
    # Keep path-safe and shell-friendly
    import re
    sanitized = re.sub(r'[^a-z0-9_-]+', '-', trimmed)
    sanitized = sanitized.strip('-')[:64]
    return sanitized or DEFAULT_AGENT_ID


def normalize_account_id(value: str | None) -> str:
    """Normalize account ID."""
    if not value:
        return DEFAULT_ACCOUNT_ID
    trimmed = value.strip()
    return trimmed if trimmed else DEFAULT_ACCOUNT_ID


def build_agent_main_session_key(agent_id: str, main_key: str | None = None) -> str:
    """Build main session key for an agent.

    Args:
        agent_id: The agent identifier
        main_key: Optional main key (defaults to "main")

    Returns:
        Session key in format: agent:{agentId}:{mainKey}
    """
    normalized_agent = normalize_agent_id(agent_id)
    normalized_main = (main_key or DEFAULT_MAIN_KEY).strip().lower()
    return f"agent:{normalized_agent}:{normalized_main}"


def build_agent_session_key(
    agent_id: str,
    channel: str,
    account_id: str | None = None,
    peer_kind: str | None = None,
    peer_id: str | None = None,
    dm_scope: str = "main",
    identity_links: dict[str, list[str]] | None = None,
) -> str:
    """Build session key for an agent with full routing context.

    Args:
        agent_id: The agent identifier
        channel: Channel name (telegram, discord, etc.)
        account_id: Account/user identifier
        peer_kind: Type of peer (direct, group, channel)
        peer_id: Peer identifier
        dm_scope: DM session scope mode
        identity_links: Identity linking configuration

    Returns:
        Session key in appropriate format based on peer_kind and dm_scope
    """
    normalized_agent = normalize_agent_id(agent_id)
    normalized_channel = (channel or "unknown").strip().lower()
    normalized_peer_kind = (peer_kind or "direct").strip().lower()

    # Direct messages - apply DM scope
    if normalized_peer_kind == "direct":
        normalized_peer_id = (peer_id or "").strip().lower()

        # Apply identity linking if configured
        if dm_scope != "main" and identity_links and normalized_peer_id:
            linked_id = _resolve_linked_peer_id(
                identity_links, normalized_channel, normalized_peer_id
            )
            if linked_id:
                normalized_peer_id = linked_id

        # DM scope: per-account-channel-peer
        if dm_scope == "per-account-channel-peer" and normalized_peer_id:
            normalized_account = normalize_account_id(account_id)
            return f"agent:{normalized_agent}:{normalized_channel}:{normalized_account}:direct:{normalized_peer_id}"

        # DM scope: per-channel-peer
        if dm_scope == "per-channel-peer" and normalized_peer_id:
            return f"agent:{normalized_agent}:{normalized_channel}:direct:{normalized_peer_id}"

        # DM scope: per-peer
        if dm_scope == "per-peer" and normalized_peer_id:
            return f"agent:{normalized_agent}:direct:{normalized_peer_id}"

        # DM scope: main (collapse all DMs to main session)
        return build_agent_main_session_key(normalized_agent)

    # Group/channel chats - always use full format
    normalized_peer_id = (peer_id or "unknown").strip().lower()
    return f"agent:{normalized_agent}:{normalized_channel}:{normalized_peer_kind}:{normalized_peer_id}"


def _resolve_linked_peer_id(
    identity_links: dict[str, list[str]],
    channel: str,
    peer_id: str,
) -> str | None:
    """Resolve linked peer ID from identity links configuration.

    Args:
        identity_links: Mapping of canonical IDs to linked IDs
        channel: Channel name
        peer_id: Peer identifier to resolve

    Returns:
        Canonical peer ID if found, None otherwise
    """
    # Build candidate keys
    candidates = {peer_id.lower()}
    scoped_candidate = f"{channel}:{peer_id}".lower()
    candidates.add(scoped_candidate)

    # Search for matching canonical ID
    for canonical, linked_ids in identity_links.items():
        canonical_name = canonical.strip()
        if not canonical_name or not isinstance(linked_ids, list):
            continue

        for linked_id in linked_ids:
            normalized = (linked_id or "").strip().lower()
            if normalized in candidates:
                return canonical_name

    return None


def build_thread_session_key(
    base_session_key: str,
    thread_id: str,
) -> str:
    """Build thread session key from base session key.

    Args:
        base_session_key: Base session key
        thread_id: Thread identifier

    Returns:
        Thread session key: {base}:thread:{threadId}
    """
    normalized_thread = (thread_id or "").strip().lower()
    if not normalized_thread:
        return base_session_key
    return f"{base_session_key}:thread:{normalized_thread}"


def build_subagent_session_key(
    parent_session_key: str,
    subagent_id: str,
) -> str:
    """Build subagent session key from parent session key.

    Args:
        parent_session_key: Parent session key
        subagent_id: Subagent identifier

    Returns:
        Subagent session key: {parent}:subagent:{subagentId}
    """
    normalized_subagent = (subagent_id or "").strip().lower()
    if not normalized_subagent:
        return parent_session_key
    return f"{parent_session_key}:subagent:{normalized_subagent}"


def parse_agent_session_key(session_key: str) -> ParsedSessionKey | None:
    """Parse agent session key into components.

    Args:
        session_key: Session key to parse

    Returns:
        Parsed components or None if invalid format
    """
    if not session_key:
        return None

    parts = session_key.split(":")
    if len(parts) < 3 or parts[0] != "agent":
        return None

    result: ParsedSessionKey = {
        "agent_id": parts[1],
    }

    # Main session: agent:{agentId}:{mainKey}
    if len(parts) == 3:
        result["channel"] = parts[2]
        result["peer_kind"] = "direct"
        result["peer_id"] = ""
        return result

    # Check for thread suffix
    for i, part in enumerate(parts):
        if part == "thread" and i + 1 < len(parts):
            result["thread_id"] = parts[i + 1]
            parts = parts[:i]  # Remove thread suffix
            break

    # Full format: agent:{agentId}:{channel}:{peerKind}:{peerId}
    if len(parts) >= 5:
        result["channel"] = parts[2]
        result["peer_kind"] = parts[3]
        result["peer_id"] = ":".join(parts[4:])
        return result

    # Per-channel-peer: agent:{agentId}:{channel}:direct:{peerId}
    if len(parts) == 5:
        result["channel"] = parts[2]
        result["peer_kind"] = parts[3]
        result["peer_id"] = parts[4]
        return result

    # Per-peer: agent:{agentId}:direct:{peerId}
    if len(parts) == 4 and parts[2] == "direct":
        result["channel"] = ""
        result["peer_kind"] = "direct"
        result["peer_id"] = parts[3]
        return result

    return None


def resolve_agent_id_from_session_key(session_key: str) -> str:
    """Extract agent ID from session key.

    Args:
        session_key: Session key to parse

    Returns:
        Agent ID or default if parsing fails
    """
    parsed = parse_agent_session_key(session_key)
    if parsed:
        return normalize_agent_id(parsed.get("agent_id"))
    return DEFAULT_AGENT_ID
