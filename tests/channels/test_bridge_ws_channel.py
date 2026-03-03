from types import SimpleNamespace

import pytest

from kabot.bus.events import OutboundMessage
from kabot.bus.queue import MessageBus
from kabot.channels.bridge_ws import BridgeWebSocketChannel


class _DummyWS:
    def __init__(self):
        self.sent: list[str] = []

    async def send(self, payload: str) -> None:
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_bridge_ws_send_skips_empty_payload():
    bus = MessageBus()
    cfg = SimpleNamespace(bridge_url="ws://localhost:3011", allow_from=[])
    channel = BridgeWebSocketChannel(cfg, bus, channel_name="signal")
    channel._connected = True
    channel._ws = _DummyWS()

    await channel.send(OutboundMessage(channel="signal", chat_id="room-1", content="", media=[]))

    assert channel._ws.sent == []


@pytest.mark.asyncio
async def test_bridge_ws_handle_message_ignores_non_object_json():
    bus = MessageBus()
    cfg = SimpleNamespace(bridge_url="ws://localhost:3011", allow_from=[])
    channel = BridgeWebSocketChannel(cfg, bus, channel_name="signal")

    await channel._handle_bridge_message("[]")

    assert bus.inbound_size == 0


@pytest.mark.asyncio
async def test_bridge_ws_handle_message_publishes_valid_inbound():
    bus = MessageBus()
    cfg = SimpleNamespace(bridge_url="ws://localhost:3011", allow_from=[])
    channel = BridgeWebSocketChannel(cfg, bus, channel_name="signal")

    await channel._handle_bridge_message(
        '{"type":"message","sender":"62812@s.whatsapp.net","chat_id":"room-7","text":"halo","metadata":{"x":1}}'
    )

    inbound = await bus.consume_inbound()
    assert inbound.channel == "signal"
    assert inbound.sender_id == "62812"
    assert inbound.chat_id == "room-7"
    assert inbound.content == "halo"


@pytest.mark.asyncio
async def test_bridge_ws_handle_message_ignores_empty_payload():
    bus = MessageBus()
    cfg = SimpleNamespace(bridge_url="ws://localhost:3011", allow_from=[])
    channel = BridgeWebSocketChannel(cfg, bus, channel_name="signal")

    await channel._handle_bridge_message('{"type":"message"}')

    assert bus.inbound_size == 0
