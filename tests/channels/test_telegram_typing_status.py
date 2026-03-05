"""Tests for Telegram typing keepalive behavior with status updates."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.error import Conflict, NetworkError

import kabot.channels.telegram as telegram_module
from kabot.bus.events import OutboundMessage
from kabot.bus.queue import MessageBus
from kabot.channels.telegram import TelegramChannel
from kabot.config.schema import TelegramConfig


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
async def test_telegram_typing_loop_stops_after_repeated_failures(monkeypatch):
    monkeypatch.setattr(telegram_module, "_TELEGRAM_TYPING_RETRY_DELAY_SECONDS", 0.01)
    monkeypatch.setattr(telegram_module, "_TELEGRAM_TYPING_MAX_CONSECUTIVE_FAILURES", 2)

    async def _send_chat_action(*, chat_id: int, action: str) -> None:
        raise RuntimeError("temporary telegram timeout")

    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._app = SimpleNamespace(bot=SimpleNamespace(send_chat_action=_send_chat_action))

    task = asyncio.create_task(channel._typing_loop("123456"))
    channel._typing_tasks["123456"] = task
    await asyncio.wait_for(task, timeout=1.0)

    assert "123456" not in channel._typing_tasks


@pytest.mark.asyncio
async def test_telegram_typing_loop_stops_on_ttl(monkeypatch):
    monkeypatch.setattr(telegram_module, "_TELEGRAM_TYPING_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(telegram_module, "_TELEGRAM_TYPING_MAX_DURATION_SECONDS", 0.03)

    attempts: list[int] = []

    async def _send_chat_action(*, chat_id: int, action: str) -> None:
        attempts.append(chat_id)

    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._app = SimpleNamespace(bot=SimpleNamespace(send_chat_action=_send_chat_action))

    task = asyncio.create_task(channel._typing_loop("123456"))
    channel._typing_tasks["123456"] = task
    await asyncio.wait_for(task, timeout=1.0)

    assert attempts
    assert "123456" not in channel._typing_tasks


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


@pytest.mark.asyncio
async def test_telegram_final_message_cleans_stale_status_bubbles_after_edit_failure():
    send_calls = [
        SimpleNamespace(message_id=700),  # first status bubble
        SimpleNamespace(message_id=701),  # replacement status bubble
        SimpleNamespace(message_id=999),  # final assistant reply
    ]
    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._app = SimpleNamespace(
        bot=SimpleNamespace(
            send_message=AsyncMock(side_effect=send_calls),
            edit_message_text=AsyncMock(side_effect=Exception("Bad Request: message is too old to edit")),
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
    await channel.send(
        OutboundMessage(
            channel="telegram",
            chat_id="123456",
            content="Final answer",
        )
    )

    deleted_ids = {call.kwargs["message_id"] for call in channel._app.bot.delete_message.await_args_list}
    assert deleted_ids == {700, 701}


@pytest.mark.asyncio
async def test_telegram_concurrent_status_updates_use_single_status_message():
    class _Bot:
        def __init__(self) -> None:
            self.sent_calls = 0
            self.edit_calls = 0

        async def send_message(self, **kwargs):  # type: ignore[no-untyped-def]
            self.sent_calls += 1
            # Keep first send in-flight longer so concurrent update races are visible.
            await asyncio.sleep(0.02)
            return SimpleNamespace(message_id=900 + self.sent_calls)

        async def edit_message_text(self, **kwargs):  # type: ignore[no-untyped-def]
            self.edit_calls += 1
            return None

        async def delete_message(self, **kwargs):  # type: ignore[no-untyped-def]
            return None

    bot = _Bot()
    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._app = SimpleNamespace(bot=bot)

    status_1 = OutboundMessage(
        channel="telegram",
        chat_id="123456",
        content="Queued...",
        metadata={"type": "status_update", "phase": "queued"},
    )
    status_2 = OutboundMessage(
        channel="telegram",
        chat_id="123456",
        content="Thinking...",
        metadata={"type": "status_update", "phase": "thinking"},
    )

    await asyncio.gather(channel.send(status_1), channel.send(status_2))

    assert bot.sent_calls == 1
    assert bot.edit_calls >= 1
    assert channel._status_message_ids["123456"] >= 901
