"""Test per-agent model switching functionality."""
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_agent_uses_override_model(tmp_path):
    """Test that agent with model override uses the correct model."""
    from datetime import datetime

    from kabot.agent.loop import AgentLoop
    from kabot.bus.events import InboundMessage
    from kabot.bus.queue import MessageBus
    from kabot.config.schema import (
        AgentBinding,
        AgentBindingMatch,
        AgentConfig,
        AgentsConfig,
        Config,
        PeerMatch,
    )

    # Setup config with two agents: one with model override, one without
    config = Config()
    config.agents = AgentsConfig(
        agents=[
            AgentConfig(id="default", name="Default Agent", model=None, default=True),
            AgentConfig(id="work", name="Work Agent", model="openai/gpt-4o", default=False),
        ],
        bindings=[
            AgentBinding(
                agent_id="work",
                match=AgentBindingMatch(
                    channel="telegram",
                    peer=PeerMatch(kind="direct", id="work_chat")
                )
            ),
        ]
    )

    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="anthropic/claude-3-5-sonnet-20241022")
    provider.chat = AsyncMock(return_value=MagicMock(content="Response", has_tool_calls=False))

    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        config=config,
        model="anthropic/claude-3-5-sonnet-20241022"  # Default model
    )

    # Create message routed to "work" agent (should use gpt-4o)
    msg = InboundMessage(
        channel="telegram",
        chat_id="work_chat",
        sender_id="user123",
        content="Test message",
        timestamp=datetime.now()
    )

    # Get the resolved model for this message
    resolved_model = loop._resolve_model_for_message(msg)

    # Should use work agent's model override
    assert resolved_model == "openai/gpt-4o"


@pytest.mark.asyncio
async def test_agent_uses_default_model_when_no_override(tmp_path):
    """Test that agent without model override uses default model."""
    from datetime import datetime

    from kabot.agent.loop import AgentLoop
    from kabot.bus.events import InboundMessage
    from kabot.bus.queue import MessageBus
    from kabot.config.schema import AgentConfig, AgentsConfig, Config

    # Setup config with agent without model override
    config = Config()
    config.agents = AgentsConfig(
        agents=[
            AgentConfig(id="default", name="Default Agent", model=None, default=True),
        ]
    )

    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="anthropic/claude-3-5-sonnet-20241022")
    provider.chat = AsyncMock(return_value=MagicMock(content="Response", has_tool_calls=False))

    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        config=config,
        model="anthropic/claude-3-5-sonnet-20241022"
    )

    # Create message routed to default agent
    msg = InboundMessage(
        channel="telegram",
        chat_id="default_chat",
        sender_id="user123",
        content="Test message",
        timestamp=datetime.now()
    )

    # Get the resolved model for this message
    resolved_model = loop._resolve_model_for_message(msg)

    # Should use default model
    assert resolved_model == "anthropic/claude-3-5-sonnet-20241022"


@pytest.mark.asyncio
async def test_instance_agent_binding_forces_agent_model_and_fallbacks(tmp_path):
    """Instance agent_binding should route to bound agent and use agent fallbacks."""
    from datetime import datetime

    from kabot.agent.loop import AgentLoop
    from kabot.bus.events import InboundMessage
    from kabot.bus.queue import MessageBus
    from kabot.config.schema import AgentConfig, AgentModelConfig, AgentsConfig, Config

    config = Config()
    config.agents = AgentsConfig(
        agents=[
            AgentConfig(id="main", default=True),
            AgentConfig(
                id="work",
                model=AgentModelConfig(
                    primary="openai/gpt-4o",
                    fallbacks=["openai/gpt-4o-mini", "openai/gpt-4.1-mini"],
                ),
            ),
        ]
    )

    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="anthropic/claude-3-5-sonnet-20241022")
    provider.chat = AsyncMock(return_value=MagicMock(content="Response", has_tool_calls=False))

    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        config=config,
        model="anthropic/claude-3-5-sonnet-20241022",
        fallbacks=["openai/gpt-4.1", "anthropic/claude-3-5-haiku-20241022"],
    )

    msg = InboundMessage(
        channel="telegram:work_bot",
        chat_id="work_chat",
        sender_id="user123",
        content="Test message",
        timestamp=datetime.now(),
        metadata={
            "channel_instance": {
                "id": "work_bot",
                "type": "telegram",
                "agent_binding": "work",
            }
        },
    )

    assert loop._resolve_agent_id_for_message(msg) == "work"
    assert "work" in loop._get_session_key(msg)

    # New behavior: per-agent fallbacks override global runtime fallbacks.
    models = loop._resolve_models_for_message(msg)
    assert models == ["openai/gpt-4o", "openai/gpt-4o-mini", "openai/gpt-4.1-mini"]
