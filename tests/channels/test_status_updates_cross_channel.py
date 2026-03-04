from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.bus.events import OutboundMessage
from kabot.bus.queue import MessageBus
from kabot.channels.bridge_ws import BridgeWebSocketChannel
from kabot.channels.email import EmailChannel
from kabot.channels.slack import SlackChannel
from kabot.config.schema import EmailConfig, SignalConfig, SlackConfig


@pytest.mark.asyncio
async def test_slack_status_updates_are_deduped_and_cleared():
    channel = SlackChannel(SlackConfig(enabled=True, bot_token="x", app_token="y"), MessageBus())
    channel._web_client = SimpleNamespace(
        chat_postMessage=AsyncMock(side_effect=[{"ts": "status-1"}, {"ts": "final-1"}]),
        chat_update=AsyncMock(return_value={}),
        chat_delete=AsyncMock(return_value={}),
        files_upload_v2=AsyncMock(return_value={}),
    )

    await channel.send(
        OutboundMessage(
            channel="slack",
            chat_id="C123",
            content="Queued...",
            metadata={"type": "status_update", "phase": "queued"},
        )
    )
    await channel.send(
        OutboundMessage(
            channel="slack",
            chat_id="C123",
            content="Queued...",
            metadata={"type": "status_update", "phase": "queued"},
        )
    )
    await channel.send(
        OutboundMessage(
            channel="slack",
            chat_id="C123",
            content="Thinking...",
            metadata={"type": "status_update", "phase": "thinking"},
        )
    )
    await channel.send(
        OutboundMessage(
            channel="slack",
            chat_id="C123",
            content="Final answer",
        )
    )

    assert channel._web_client.chat_postMessage.await_count == 2
    channel._web_client.chat_update.assert_awaited_once()
    channel._web_client.chat_delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_slack_status_update_not_modified_does_not_create_duplicate_message():
    channel = SlackChannel(SlackConfig(enabled=True, bot_token="x", app_token="y"), MessageBus())
    channel._web_client = SimpleNamespace(
        chat_postMessage=AsyncMock(return_value={"ts": "final-1"}),
        chat_update=AsyncMock(side_effect=Exception("message_not_modified")),
        chat_delete=AsyncMock(return_value={}),
        files_upload_v2=AsyncMock(return_value={}),
    )
    channel._status_message_ts["C123"] = "status-1"

    await channel.send(
        OutboundMessage(
            channel="slack",
            chat_id="C123",
            content="Processing your request, please wait...",
            metadata={"type": "status_update", "phase": "thinking", "keepalive": True},
        )
    )

    channel._web_client.chat_update.assert_awaited_once()
    channel._web_client.chat_postMessage.assert_not_awaited()
    assert channel._status_message_ts["C123"] == "status-1"


@pytest.mark.asyncio
async def test_slack_final_message_transient_delete_keeps_status_message_for_retry():
    channel = SlackChannel(SlackConfig(enabled=True, bot_token="x", app_token="y"), MessageBus())
    channel._web_client = SimpleNamespace(
        chat_postMessage=AsyncMock(return_value={"ts": "final-1"}),
        chat_update=AsyncMock(return_value={}),
        chat_delete=AsyncMock(side_effect=Exception("timed out")),
        files_upload_v2=AsyncMock(return_value={}),
    )
    channel._status_message_ts["C123"] = "status-1"

    await channel.send(
        OutboundMessage(
            channel="slack",
            chat_id="C123",
            content="Final answer",
        )
    )

    channel._web_client.chat_delete.assert_awaited_once()
    channel._web_client.chat_postMessage.assert_awaited_once()
    assert channel._status_message_ts["C123"] == "status-1"


@pytest.mark.asyncio
async def test_bridge_ws_status_updates_are_deduped():
    channel = BridgeWebSocketChannel(
        SignalConfig(enabled=True, bridge_url="ws://localhost:3011"),
        MessageBus(),
        channel_name="signal",
    )
    channel._connected = True
    channel._ws = SimpleNamespace(send=AsyncMock(return_value=None))

    status = OutboundMessage(
        channel="signal",
        chat_id="peer-1",
        content="Processing your request...",
        metadata={"type": "status_update", "phase": "thinking"},
    )
    await channel.send(status)
    await channel.send(status)
    await channel.send(
        OutboundMessage(
            channel="signal",
            chat_id="peer-1",
            content="Done",
        )
    )

    # First status emits activity + payload; duplicate is dropped; final emits one payload.
    assert channel._ws.send.await_count == 3


@pytest.mark.asyncio
async def test_bridge_ws_keepalive_status_updates_are_not_deduped():
    channel = BridgeWebSocketChannel(
        SignalConfig(enabled=True, bridge_url="ws://localhost:3011"),
        MessageBus(),
        channel_name="signal",
    )
    channel._connected = True
    channel._ws = SimpleNamespace(send=AsyncMock(return_value=None))

    keepalive_status = OutboundMessage(
        channel="signal",
        chat_id="peer-1",
        content="Processing your request...",
        metadata={"type": "status_update", "phase": "thinking", "keepalive": True},
    )
    await channel.send(keepalive_status)
    await channel.send(keepalive_status)

    # Keepalive pulses should pass through for typing/activity continuity.
    assert channel._ws.send.await_count == 4


@pytest.mark.asyncio
async def test_email_channel_skips_status_updates():
    channel = EmailChannel(EmailConfig(enabled=True, consent_granted=True), MessageBus())
    channel._smtp_send = MagicMock()

    await channel.send(
        OutboundMessage(
            channel="email",
            chat_id="user@example.com",
            content="Processing...",
            metadata={"type": "status_update", "phase": "thinking"},
        )
    )

    channel._smtp_send.assert_not_called()
