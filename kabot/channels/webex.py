"""Webex channel implementation via websocket bridge."""

from kabot.bus.queue import MessageBus
from kabot.channels.bridge_ws import BridgeWebSocketChannel
from kabot.config.schema import WebexConfig


class WebexChannel(BridgeWebSocketChannel):
    """Webex adapter using external bridge transport."""

    name = "webex"

    def __init__(self, config: WebexConfig, bus: MessageBus):
        super().__init__(config, bus, channel_name="webex")
