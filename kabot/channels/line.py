"""LINE channel implementation via websocket bridge."""

from kabot.bus.queue import MessageBus
from kabot.channels.bridge_ws import BridgeWebSocketChannel
from kabot.config.schema import LineConfig


class LineChannel(BridgeWebSocketChannel):
    """LINE adapter using external bridge transport."""

    name = "line"

    def __init__(self, config: LineConfig, bus: MessageBus):
        super().__init__(config, bus, channel_name="line")
