from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
async def test_agent_loop_routes_to_correct_agent(tmp_path):
    from kabot.agent.loop import AgentLoop
    from kabot.bus.events import InboundMessage
    from kabot.bus.queue import MessageBus
    from kabot.config.schema import (
        AgentBinding,
        AgentBindingMatch,
        AgentConfig,
        AgentsConfig,
        Config,
    )

    config = Config(
        agents=AgentsConfig(
            agents=[
                AgentConfig(id="work", model="openai/gpt-4o", workspace=str(tmp_path / "work")),
                AgentConfig(id="personal", model="anthropic/claude-sonnet-4-5", default=True)
            ],
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

    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="openai/gpt-4o")

    loop = AgentLoop(bus, provider, tmp_path, config=config)

    msg = InboundMessage(
        channel="telegram",
        sender_id="user1",
        chat_id="123",
        content="Hello",
        timestamp=None
    )

    # Should route to work agent
    session_key = loop._get_session_key(msg)
    assert "work" in session_key
