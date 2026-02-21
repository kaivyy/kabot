"""Tests for Discord interaction event handling."""

import pytest

from kabot.bus.queue import MessageBus
from kabot.channels.discord import DiscordChannel
from kabot.config.schema import DiscordConfig


@pytest.mark.asyncio
async def test_interaction_create_publishes_inbound_message():
    bus = MessageBus()
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), bus)
    payload = {
        "id": "interaction-1",
        "type": 3,
        "channel_id": "123456",
        "guild_id": "999",
        "member": {
            "user": {
                "id": "555",
                "username": "tester",
            }
        },
        "data": {
            "component_type": 2,
            "custom_id": "approve_task",
        },
    }

    await channel._handle_interaction_create(payload)
    inbound = await bus.consume_inbound()

    assert inbound.channel == "discord"
    assert inbound.chat_id == "123456"
    assert inbound.sender_id == "555"
    assert inbound.content == "approve_task"
    assert inbound.metadata["is_interaction"] is True
    assert inbound.metadata["interaction_id"] == "interaction-1"
    assert inbound.metadata["custom_id"] == "approve_task"
