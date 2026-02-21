"""Tests for Telegram callback query handling."""

from types import SimpleNamespace

import pytest

from kabot.bus.queue import MessageBus
from kabot.channels.telegram import TelegramChannel
from kabot.config.schema import TelegramConfig


class _DummyCallbackQuery:
    def __init__(self):
        self.id = "cq-1"
        self.data = "approve"
        self.from_user = SimpleNamespace(id=123, username="alice", first_name="Alice")
        self.message = SimpleNamespace(
            chat_id=456,
            message_id=999,
            chat=SimpleNamespace(type="private"),
        )
        self.answered = False

    async def answer(self):
        self.answered = True


@pytest.mark.asyncio
async def test_callback_query_publishes_inbound_message():
    bus = MessageBus()
    channel = TelegramChannel(TelegramConfig(token="token", enabled=True), bus)
    callback_query = _DummyCallbackQuery()
    update = SimpleNamespace(callback_query=callback_query, effective_chat=None)

    await channel._on_callback_query(update, None)
    inbound = await bus.consume_inbound()

    assert inbound.channel == "telegram"
    assert inbound.chat_id == "456"
    assert inbound.sender_id == "123|alice"
    assert inbound.content == "approve"
    assert inbound.metadata["is_callback_query"] is True
    assert inbound.metadata["callback_data"] == "approve"
    assert callback_query.answered is True
    assert channel._chat_ids["123|alice"] == 456
