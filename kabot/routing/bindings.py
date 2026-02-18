"""Agent binding resolution for message routing.

This module implements OpenClaw-compatible routing with priority-based matching:
1. Peer matching (specific user/chat)
2. Parent peer matching (thread inheritance)
3. Guild matching (Discord servers)
4. Team matching (Slack workspaces)
5. Account matching (specific account)
6. Channel matching (wildcard)
7. Default agent
"""

from typing import TypedDict
from kabot.config.schema import Config, AgentBinding, PeerMatch
from kabot.agent.agent_scope import resolve_default_agent_id
from kabot.session.session_key import (
    build_agent_session_key,
    build_agent_main_session_key,
    normalize_agent_id,
    normalize_account_id,
    DEFAULT_ACCOUNT_ID,
)


class RoutePeer(TypedDict):
    """Peer information for routing."""
    kind: str  # "direct", "group", "channel"
    id: str


class ResolvedRoute(TypedDict):
    """Resolved routing information."""
    agent_id: str
    session_key: str
    main_session_key: str
    matched_by: str


def _normalize_token(value: str | None) -> str:
    """Normalize token to lowercase."""
    return (value or "").strip().lower()


def _normalize_id(value: str | None) -> str:
    """Normalize ID (preserve case)."""
    return (value or "").strip()


def _matches_channel(binding: AgentBinding, channel: str) -> bool:
    """Check if binding matches channel."""
    if not binding.match.channel:
        return False
    return _normalize_token(binding.match.channel) == _normalize_token(channel)


def _matches_account_id(binding: AgentBinding, account_id: str) -> bool:
    """Check if binding matches account ID (supports wildcard)."""
    match_account = (binding.match.account_id or "").strip()

    # No account_id in binding = match default account only
    if not match_account:
        return account_id == DEFAULT_ACCOUNT_ID

    # Wildcard matches any account
    if match_account == "*":
        return True

    # Exact match
    return match_account == account_id


def _matches_peer(binding: AgentBinding, peer: RoutePeer) -> bool:
    """Check if binding matches peer."""
    if not binding.match.peer:
        return False

    match_peer = binding.match.peer
    peer_kind = _normalize_token(match_peer.kind)
    peer_id = _normalize_id(match_peer.id)

    if not peer_kind or not peer_id:
        return False

    return (
        peer_kind == _normalize_token(peer["kind"]) and
        peer_id == _normalize_id(peer["id"])
    )


def _matches_guild(binding: AgentBinding, guild_id: str) -> bool:
    """Check if binding matches guild ID."""
    if not binding.match.guild_id:
        return False
    return _normalize_id(binding.match.guild_id) == _normalize_id(guild_id)


def _matches_team(binding: AgentBinding, team_id: str) -> bool:
    """Check if binding matches team ID."""
    if not binding.match.team_id:
        return False
    return _normalize_id(binding.match.team_id) == _normalize_id(team_id)


def resolve_agent_route(
    config: Config,
    channel: str,
    account_id: str | None = None,
    peer: RoutePeer | None = None,
    parent_peer: RoutePeer | None = None,
    guild_id: str | None = None,
    team_id: str | None = None,
    thread_id: str | None = None,
) -> ResolvedRoute:
    """Resolve which agent should handle a message based on bindings.

    Priority order (OpenClaw-compatible):
    1. Peer matching (specific user/chat)
    2. Parent peer matching (thread inheritance)
    3. Guild matching (Discord servers)
    4. Team matching (Slack workspaces)
    5. Account matching (specific account)
    6. Channel matching (wildcard)
    7. Default agent

    Args:
        config: The application configuration
        channel: Channel name (telegram, discord, etc.)
        account_id: Account/user identifier
        peer: Peer information (kind + id)
        parent_peer: Parent peer for thread inheritance
        guild_id: Discord guild identifier
        team_id: Slack team identifier
        thread_id: Thread identifier (optional)

    Returns:
        Resolved routing information with agent_id and session_key
    """
    normalized_channel = _normalize_token(channel)
    normalized_account = normalize_account_id(account_id)

    # Get session config
    dm_scope = config.agents.session.dm_scope
    identity_links = config.agents.session.identity_links

    # Filter bindings by channel and account
    candidate_bindings = [
        b for b in config.agents.bindings
        if _matches_channel(b, normalized_channel) and
           _matches_account_id(b, normalized_account)
    ]

    def _build_route(agent_id: str, matched_by: str) -> ResolvedRoute:
        """Build resolved route with session keys."""
        normalized_agent = normalize_agent_id(agent_id)

        # Build session key
        session_key = build_agent_session_key(
            agent_id=normalized_agent,
            channel=normalized_channel,
            account_id=normalized_account,
            peer_kind=peer["kind"] if peer else None,
            peer_id=peer["id"] if peer else None,
            dm_scope=dm_scope,
            identity_links=identity_links,
        )

        # Apply thread suffix if provided
        if thread_id:
            from kabot.session.session_key import build_thread_session_key
            session_key = build_thread_session_key(session_key, thread_id)

        # Build main session key
        main_session_key = build_agent_main_session_key(normalized_agent)

        return {
            "agent_id": normalized_agent,
            "session_key": session_key.lower(),
            "main_session_key": main_session_key.lower(),
            "matched_by": matched_by,
        }

    # Priority 1: Peer matching
    if peer:
        for binding in candidate_bindings:
            if _matches_peer(binding, peer):
                return _build_route(binding.agent_id, "binding.peer")

    # Priority 2: Parent peer matching (thread inheritance)
    if parent_peer:
        for binding in candidate_bindings:
            if _matches_peer(binding, parent_peer):
                return _build_route(binding.agent_id, "binding.peer.parent")

    # Priority 3: Guild matching
    if guild_id:
        for binding in candidate_bindings:
            if _matches_guild(binding, guild_id):
                return _build_route(binding.agent_id, "binding.guild")

    # Priority 4: Team matching
    if team_id:
        for binding in candidate_bindings:
            if _matches_team(binding, team_id):
                return _build_route(binding.agent_id, "binding.team")

    # Priority 5: Account matching (specific account, no peer/guild/team)
    for binding in candidate_bindings:
        if (binding.match.account_id and
            binding.match.account_id != "*" and
            not binding.match.peer and
            not binding.match.guild_id and
            not binding.match.team_id):
            return _build_route(binding.agent_id, "binding.account")

    # Priority 6: Channel matching (wildcard account)
    for binding in candidate_bindings:
        if (binding.match.account_id == "*" and
            not binding.match.peer and
            not binding.match.guild_id and
            not binding.match.team_id):
            return _build_route(binding.agent_id, "binding.channel")

    # Priority 7: Default agent
    default_agent = resolve_default_agent_id(config)
    return _build_route(default_agent, "default")
