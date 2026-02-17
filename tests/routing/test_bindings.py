"""Tests for agent binding resolution."""

import pytest
from kabot.routing.bindings import resolve_agent_route
from kabot.config.schema import Config, AgentsConfig, AgentConfig, AgentBinding


def test_resolve_agent_by_channel():
    """Test that channel-only bindings route to the correct agent."""
    config = Config(
        agents=AgentsConfig(
            agents=[AgentConfig(id="work"), AgentConfig(id="personal", default=True)],
            bindings=[AgentBinding(agent_id="work", channel="telegram")]
        )
    )

    agent_id = resolve_agent_route(config, "telegram", "123456")
    assert agent_id == "work"

    agent_id = resolve_agent_route(config, "whatsapp", "789")
    assert agent_id == "personal"  # fallback to default


def test_resolve_agent_by_exact_match():
    """Test that exact channel+chat_id bindings have highest priority."""
    config = Config(
        agents=AgentsConfig(
            agents=[
                AgentConfig(id="work"),
                AgentConfig(id="personal", default=True),
                AgentConfig(id="vip")
            ],
            bindings=[
                AgentBinding(agent_id="work", channel="telegram"),
                AgentBinding(agent_id="vip", channel="telegram", chat_id="999")
            ]
        )
    )

    # Exact match should take priority over channel-only
    agent_id = resolve_agent_route(config, "telegram", "999")
    assert agent_id == "vip"

    # Channel-only match
    agent_id = resolve_agent_route(config, "telegram", "123")
    assert agent_id == "work"

    # Default fallback
    agent_id = resolve_agent_route(config, "whatsapp", "456")
    assert agent_id == "personal"


def test_resolve_agent_priority_order():
    """Test the priority order: exact > channel > default."""
    config = Config(
        agents=AgentsConfig(
            agents=[
                AgentConfig(id="default_agent", default=True),
                AgentConfig(id="telegram_agent"),
                AgentConfig(id="special_chat_agent")
            ],
            bindings=[
                AgentBinding(agent_id="telegram_agent", channel="telegram"),
                AgentBinding(agent_id="special_chat_agent", channel="telegram", chat_id="special123")
            ]
        )
    )

    # Priority 1: Exact match
    assert resolve_agent_route(config, "telegram", "special123") == "special_chat_agent"

    # Priority 2: Channel-only
    assert resolve_agent_route(config, "telegram", "other456") == "telegram_agent"

    # Priority 3: Default
    assert resolve_agent_route(config, "discord", "789") == "default_agent"


def test_resolve_agent_no_bindings():
    """Test that default agent is used when no bindings exist."""
    config = Config(
        agents=AgentsConfig(
            agents=[AgentConfig(id="only_agent", default=True)],
            bindings=[]
        )
    )

    agent_id = resolve_agent_route(config, "telegram", "123")
    assert agent_id == "only_agent"
