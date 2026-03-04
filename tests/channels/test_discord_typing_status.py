"""Tests for Discord typing keepalive behavior with status updates."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from kabot.bus.events import OutboundMessage
from kabot.bus.queue import MessageBus
from kabot.channels.discord import DiscordChannel
from kabot.config.schema import DiscordConfig


@pytest.mark.asyncio
async def test_discord_send_keeps_typing_for_status_updates():
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._http = SimpleNamespace(
        post=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {"id": "status-1"})),
        patch=AsyncMock(return_value=SimpleNamespace(status_code=200)),
        delete=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    )
    channel._stop_typing = AsyncMock()

    msg = OutboundMessage(
        channel="discord",
        chat_id="1234567890",
        content="Queued. Preparing your request...",
        metadata={"type": "status_update", "phase": "queued"},
    )

    await channel.send(msg)

    channel._stop_typing.assert_not_awaited()
    channel._http.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_discord_send_stops_typing_for_regular_messages():
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._http = SimpleNamespace(
        post=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {})),
        patch=AsyncMock(return_value=SimpleNamespace(status_code=200)),
        delete=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    )
    channel._stop_typing = AsyncMock()

    msg = OutboundMessage(
        channel="discord",
        chat_id="1234567890",
        content="Final answer",
    )

    await channel.send(msg)

    channel._stop_typing.assert_awaited_once_with("1234567890")
    channel._http.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_discord_status_update_edits_existing_status_message():
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._http = SimpleNamespace(
        post=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {"id": "status-1"})),
        patch=AsyncMock(return_value=SimpleNamespace(status_code=200)),
        delete=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    )
    channel._stop_typing = AsyncMock()

    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Queued...",
            metadata={"type": "status_update", "phase": "queued"},
        )
    )
    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Thinking...",
            metadata={"type": "status_update", "phase": "thinking"},
        )
    )

    channel._http.post.assert_awaited_once()
    channel._http.patch.assert_awaited_once()
    channel._stop_typing.assert_not_awaited()


@pytest.mark.asyncio
async def test_discord_draft_update_edits_existing_progress_message():
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._http = SimpleNamespace(
        post=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {"id": "status-1"})),
        patch=AsyncMock(return_value=SimpleNamespace(status_code=200)),
        delete=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    )
    channel._stop_typing = AsyncMock()

    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Draft awal",
            metadata={"type": "draft_update", "phase": "thinking"},
        )
    )
    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Draft awal",
            metadata={"type": "draft_update", "phase": "thinking"},
        )
    )
    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Draft revisi",
            metadata={"type": "draft_update", "phase": "thinking"},
        )
    )

    channel._http.post.assert_awaited_once()
    channel._http.patch.assert_awaited_once()
    channel._stop_typing.assert_not_awaited()


@pytest.mark.asyncio
async def test_discord_regular_message_clears_status_message():
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._http = SimpleNamespace(
        post=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {})),
        patch=AsyncMock(return_value=SimpleNamespace(status_code=200)),
        delete=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    )
    channel._stop_typing = AsyncMock()
    channel._status_message_ids["1234567890"] = "status-99"

    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Final answer",
        )
    )

    channel._http.delete.assert_awaited_once()
    channel._stop_typing.assert_awaited_once_with("1234567890")


@pytest.mark.asyncio
async def test_discord_status_update_transient_patch_keeps_existing_status_message():
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._http = SimpleNamespace(
        post=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {"id": "status-2"})),
        patch=AsyncMock(return_value=SimpleNamespace(status_code=429)),
        delete=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    )
    channel._status_message_ids["1234567890"] = "status-1"
    channel._stop_typing = AsyncMock()

    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Still working...",
            metadata={"type": "status_update", "phase": "thinking", "keepalive": True},
        )
    )

    channel._http.patch.assert_awaited_once()
    channel._http.post.assert_not_awaited()
    assert channel._status_message_ids["1234567890"] == "status-1"


@pytest.mark.asyncio
async def test_discord_regular_message_transient_delete_keeps_status_message_for_retry():
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._http = SimpleNamespace(
        post=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {})),
        patch=AsyncMock(return_value=SimpleNamespace(status_code=200)),
        delete=AsyncMock(return_value=SimpleNamespace(status_code=429)),
    )
    channel._status_message_ids["1234567890"] = "status-1"
    channel._stop_typing = AsyncMock()

    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Final answer",
        )
    )

    channel._http.delete.assert_awaited_once()
    channel._http.post.assert_awaited_once()
    assert channel._status_message_ids["1234567890"] == "status-1"
