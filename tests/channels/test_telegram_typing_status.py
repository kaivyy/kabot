"""Tests for Telegram typing keepalive behavior with status updates."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.bus.events import OutboundMessage
from kabot.bus.queue import MessageBus
from kabot.channels.telegram import TelegramChannel
from kabot.config.schema import TelegramConfig
from telegram.error import Conflict, NetworkError


@pytest.mark.asyncio
async def test_telegram_send_keeps_typing_for_status_updates():
    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._app = SimpleNamespace(
        bot=SimpleNamespace(
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=111)),
            edit_message_text=AsyncMock(),
            delete_message=AsyncMock(),
        )
    )
    channel._stop_typing = MagicMock()

    msg = OutboundMessage(
        channel="telegram",
        chat_id="123456",
        content="Queued. Preparing your request...",
        metadata={"type": "status_update", "phase": "queued"},
    )
    await channel.send(msg)

    channel._stop_typing.assert_not_called()
    channel._app.bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_telegram_send_stops_typing_for_regular_messages():
    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._app = SimpleNamespace(
        bot=SimpleNamespace(
            send_message=AsyncMock(),
            edit_message_text=AsyncMock(),
            delete_message=AsyncMock(),
        )
    )
    channel._stop_typing = MagicMock()

    msg = OutboundMessage(
        channel="telegram",
        chat_id="123456",
        content="Final answer",
    )
    await channel.send(msg)

    channel._stop_typing.assert_called_once_with("123456")
    channel._app.bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_telegram_status_update_edits_existing_status_message():
    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._app = SimpleNamespace(
        bot=SimpleNamespace(
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=777)),
            edit_message_text=AsyncMock(),
            delete_message=AsyncMock(),
        )
    )
    channel._stop_typing = MagicMock()

    await channel.send(
        OutboundMessage(
            channel="telegram",
            chat_id="123456",
            content="Queued...",
            metadata={"type": "status_update", "phase": "queued"},
        )
    )
    await channel.send(
        OutboundMessage(
            channel="telegram",
            chat_id="123456",
            content="Thinking...",
            metadata={"type": "status_update", "phase": "thinking"},
        )
    )

    channel._app.bot.send_message.assert_awaited_once()
    channel._app.bot.edit_message_text.assert_awaited_once_with(
        chat_id=123456,
        message_id=777,
        text="Thinking...",
    )
    channel._stop_typing.assert_not_called()


@pytest.mark.asyncio
async def test_telegram_draft_update_edits_existing_progress_message():
    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._app = SimpleNamespace(
        bot=SimpleNamespace(
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=888)),
            edit_message_text=AsyncMock(),
            delete_message=AsyncMock(),
        )
    )
    channel._stop_typing = MagicMock()

    await channel.send(
        OutboundMessage(
            channel="telegram",
            chat_id="123456",
            content="Draft awal",
            metadata={"type": "draft_update", "phase": "thinking"},
        )
    )
    await channel.send(
        OutboundMessage(
            channel="telegram",
            chat_id="123456",
            content="Draft awal",
            metadata={"type": "draft_update", "phase": "thinking"},
        )
    )
    await channel.send(
        OutboundMessage(
            channel="telegram",
            chat_id="123456",
            content="Draft revisi",
            metadata={"type": "draft_update", "phase": "thinking"},
        )
    )

    channel._app.bot.send_message.assert_awaited_once()
    channel._app.bot.edit_message_text.assert_awaited_once_with(
        chat_id=123456,
        message_id=888,
        text="Draft revisi",
    )
    channel._stop_typing.assert_not_called()


@pytest.mark.asyncio
async def test_telegram_regular_message_clears_status_message():
    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._app = SimpleNamespace(
        bot=SimpleNamespace(
            send_message=AsyncMock(),
            edit_message_text=AsyncMock(),
            delete_message=AsyncMock(),
        )
    )
    channel._stop_typing = MagicMock()
    channel._status_message_ids["123456"] = 42

    await channel.send(
        OutboundMessage(
            channel="telegram",
            chat_id="123456",
            content="Final answer",
        )
    )

    channel._app.bot.delete_message.assert_awaited_once_with(chat_id=123456, message_id=42)
    channel._stop_typing.assert_called_once_with("123456")


@pytest.mark.asyncio
async def test_telegram_status_update_restarts_typing_when_missing():
    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._app = SimpleNamespace(
        bot=SimpleNamespace(
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=321)),
            edit_message_text=AsyncMock(),
            delete_message=AsyncMock(),
        )
    )
    channel._typing_tasks.clear()
    channel._ensure_typing = MagicMock()

    await channel.send(
        OutboundMessage(
            channel="telegram",
            chat_id="123456",
            content="Thinking...",
            metadata={"type": "status_update", "phase": "thinking"},
        )
    )

    channel._ensure_typing.assert_called_once_with("123456")


@pytest.mark.asyncio
async def test_telegram_typing_loop_recovers_after_transient_failure():
    attempts: list[int] = []
    recovered = asyncio.Event()

    async def _send_chat_action(*, chat_id: int, action: str) -> None:  # pragma: no cover - async callback
        attempts.append(chat_id)
        if len(attempts) == 1:
            raise RuntimeError("temporary telegram timeout")
        recovered.set()

    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._app = SimpleNamespace(bot=SimpleNamespace(send_chat_action=_send_chat_action))

    task = asyncio.create_task(channel._typing_loop("123456"))
    await asyncio.wait_for(recovered.wait(), timeout=3.0)
    task.cancel()
    await task

    assert len(attempts) >= 2


@pytest.mark.asyncio
async def test_telegram_polling_conflict_triggers_single_shutdown():
    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._running = True
    channel.stop = AsyncMock()  # type: ignore[method-assign]

    channel._on_polling_error(Conflict("another getUpdates request is active"))
    channel._on_polling_error(Conflict("another getUpdates request is active"))
    await asyncio.sleep(0)

    assert channel._running is False
    assert channel._polling_conflict_handled is True
    channel.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_telegram_polling_non_conflict_does_not_shutdown():
    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._running = True
    channel.stop = AsyncMock()  # type: ignore[method-assign]

    channel._on_polling_error(NetworkError("temporary timeout"))
    await asyncio.sleep(0)

    assert channel._running is True
    assert channel._polling_conflict_handled is False
    channel.stop.assert_not_awaited()


@pytest.mark.asyncio
async def test_telegram_status_keepalive_does_not_create_duplicate_messages_on_not_modified():
    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._app = SimpleNamespace(
        bot=SimpleNamespace(
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=700)),
            edit_message_text=AsyncMock(side_effect=Exception("Message is not modified")),
            delete_message=AsyncMock(),
        )
    )
    channel._status_message_ids["123456"] = 700

    # Simulate keepalive pulse with identical status text.
    await channel.send(
        OutboundMessage(
            channel="telegram",
            chat_id="123456",
            content="Processing your request, please wait...",
            metadata={"type": "status_update", "phase": "thinking", "keepalive": True},
        )
    )

    # Must not post a second status bubble when Telegram says "not modified".
    channel._app.bot.send_message.assert_not_awaited()
    assert channel._status_message_ids["123456"] == 700


@pytest.mark.asyncio
async def test_telegram_status_keepalive_transient_edit_error_keeps_existing_status_message():
    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._app = SimpleNamespace(
        bot=SimpleNamespace(
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=701)),
            edit_message_text=AsyncMock(side_effect=Exception("Timed out")),
            delete_message=AsyncMock(),
        )
    )
    channel._status_message_ids["123456"] = 700

    await channel.send(
        OutboundMessage(
            channel="telegram",
            chat_id="123456",
            content="Processing your request, please wait...",
            metadata={"type": "status_update", "phase": "thinking", "keepalive": True},
        )
    )

    channel._app.bot.send_message.assert_not_awaited()
    assert channel._status_message_ids["123456"] == 700


@pytest.mark.asyncio
async def test_telegram_regular_message_transient_delete_keeps_status_message_for_retry():
    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._app = SimpleNamespace(
        bot=SimpleNamespace(
            send_message=AsyncMock(),
            edit_message_text=AsyncMock(),
            delete_message=AsyncMock(side_effect=Exception("Timed out")),
        )
    )
    channel._stop_typing = MagicMock()
    channel._status_message_ids["123456"] = 42

    await channel.send(
        OutboundMessage(
            channel="telegram",
            chat_id="123456",
            content="Final answer",
        )
    )

    channel._app.bot.delete_message.assert_awaited_once_with(chat_id=123456, message_id=42)
    channel._app.bot.send_message.assert_awaited_once()
    assert channel._status_message_ids["123456"] == 42
