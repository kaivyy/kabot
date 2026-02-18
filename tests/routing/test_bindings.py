"""Tests for agent binding resolution."""

import pytest
from kabot.routing.bindings import resolve_agent_route
from kabot.config.schema import Config, AgentsConfig, AgentConfig, AgentBinding, AgentBindingMatch, PeerMatch


def test_resolve_agent_by_channel():
    """Test that channel-only bindings route to the correct agent."""
    config = Config(
        agents=AgentsConfig(
            agents=[AgentConfig(id="work"), AgentConfig(id="personal", default=True)],
            bindings=[
                AgentBinding(
                    agent_id="work",
                    match=AgentBindingMatch(
                        channel="telegram",
                        account_id="*"
                    )
                )
            ]
        )
    )

    route = resolve_agent_route(config, "telegram", "123456")
    assert route["agent_id"] == "work"

    route = resolve_agent_route(config, "whatsapp", "789")
    assert route["agent_id"] == "personal"  # fallback to default


def test_resolve_agent_by_exact_match():
    """Test that exact channel+peer bindings have highest priority."""
    config = Config(
        agents=AgentsConfig(
            agents=[
                AgentConfig(id="work"),
                AgentConfig(id="personal", default=True),
                AgentConfig(id="vip")
            ],
            bindings=[
                AgentBinding(
                    agent_id="work",
                    match=AgentBindingMatch(
                        channel="telegram",
                        account_id="*"
                    )
                ),
                AgentBinding(
                    agent_id="vip",
                    match=AgentBindingMatch(
                        channel="telegram",
                        peer=PeerMatch(kind="direct", id="999")
                    )
                )
            ]
        )
    )

    # Exact peer match should take priority over channel-only
    route = resolve_agent_route(config, "telegram", peer={"kind": "direct", "id": "999"})
    assert route["agent_id"] == "vip"

    # Channel-only match
    route = resolve_agent_route(config, "telegram", peer={"kind": "direct", "id": "123"})
    assert route["agent_id"] == "work"

    # Default fallback
    route = resolve_agent_route(config, "whatsapp", peer={"kind": "direct", "id": "456"})
    assert route["agent_id"] == "personal"


def test_resolve_agent_priority_order():
    """Test the priority order: peer > channel > default."""
    config = Config(
        agents=AgentsConfig(
            agents=[
                AgentConfig(id="default_agent", default=True),
                AgentConfig(id="telegram_agent"),
                AgentConfig(id="special_chat_agent")
            ],
            bindings=[
                AgentBinding(
                    agent_id="telegram_agent",
                    match=AgentBindingMatch(
                        channel="telegram",
                        account_id="*"
                    )
                ),
                AgentBinding(
                    agent_id="special_chat_agent",
                    match=AgentBindingMatch(
                        channel="telegram",
                        peer=PeerMatch(kind="direct", id="special123")
                    )
                )
            ]
        )
    )

    # Priority 1: Peer match
    route = resolve_agent_route(config, "telegram", peer={"kind": "direct", "id": "special123"})
    assert route["agent_id"] == "special_chat_agent"

    # Priority 2: Channel-only
    route = resolve_agent_route(config, "telegram", peer={"kind": "direct", "id": "other456"})
    assert route["agent_id"] == "telegram_agent"

    # Priority 3: Default
    route = resolve_agent_route(config, "discord", peer={"kind": "direct", "id": "789"})
    assert route["agent_id"] == "default_agent"


def test_resolve_agent_no_bindings():
    """Test that default agent is used when no bindings exist."""
    config = Config(
        agents=AgentsConfig(
            agents=[AgentConfig(id="only_agent", default=True)],
            bindings=[]
        )
    )

    route = resolve_agent_route(config, "telegram", peer={"kind": "direct", "id": "123"})
    assert route["agent_id"] == "only_agent"
