from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.bus.events import OutboundMessage
from kabot.bus.queue import MessageBus
from kabot.channels.telegram import TelegramChannel
from kabot.config.schema import TelegramConfig


@pytest.mark.asyncio
async def test_telegram_start_routes_to_agent_when_bootstrap_exists(tmp_path):
    (tmp_path / "BOOTSTRAP.md").write_text(
        "# Bootstrap\n\nAsk onboarding questions for first-run setup.",
        encoding="utf-8",
    )
    channel = TelegramChannel(
        TelegramConfig(token="test-token", enabled=True),
        MessageBus(),
        workspace=tmp_path,
    )
    channel._handle_message = AsyncMock()
    reply_text = AsyncMock()
    update = SimpleNamespace(
        message=SimpleNamespace(
            chat_id=123456,
            message_id=99,
            reply_text=reply_text,
        ),
        effective_user=SimpleNamespace(
            id=777,
            username="maharaja",
            first_name="Maha Raja",
        ),
    )

    await channel._on_start(update, None)

    channel._handle_message.assert_awaited_once()
    reply_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_telegram_start_uses_generic_reply_without_bootstrap(tmp_path):
    channel = TelegramChannel(
        TelegramConfig(token="test-token", enabled=True),
        MessageBus(),
        workspace=tmp_path,
    )
    channel._handle_message = AsyncMock()
    reply_text = AsyncMock()
    update = SimpleNamespace(
        message=SimpleNamespace(
            chat_id=123456,
            message_id=100,
            reply_text=reply_text,
        ),
        effective_user=SimpleNamespace(
            id=777,
            username="maharaja",
            first_name="Maha Raja",
        ),
    )

    await channel._on_start(update, None)

    channel._handle_message.assert_not_awaited()
    reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_telegram_send_uses_reply_to_message_id_for_text_reply():
    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._app = SimpleNamespace(
        bot=SimpleNamespace(
            send_message=AsyncMock(),
            edit_message_text=AsyncMock(),
            delete_message=AsyncMock(),
        )
    )
    channel._stop_typing = MagicMock()

    await channel.send(
        OutboundMessage(
            channel="telegram",
            chat_id="123456",
            content="Final answer",
            reply_to="77",
        )
    )

    channel._app.bot.send_message.assert_awaited_once()
    assert channel._app.bot.send_message.await_args.kwargs["reply_to_message_id"] == 77


@pytest.mark.asyncio
async def test_telegram_send_document_preserves_reply_to_message_id(tmp_path):
    attachment = tmp_path / "report.txt"
    attachment.write_text("hello", encoding="utf-8")

    channel = TelegramChannel(TelegramConfig(token="test-token", enabled=True), MessageBus())
    channel._app = SimpleNamespace(
        bot=SimpleNamespace(
            send_message=AsyncMock(),
            send_document=AsyncMock(),
            edit_message_text=AsyncMock(),
            delete_message=AsyncMock(),
        )
    )
    channel._stop_typing = MagicMock()

    await channel.send(
        OutboundMessage(
            channel="telegram",
            chat_id="123456",
            content="",
            media=[str(attachment)],
            reply_to="88",
        )
    )

    channel._app.bot.send_document.assert_awaited_once()
    assert channel._app.bot.send_document.await_args.kwargs["reply_to_message_id"] == 88
