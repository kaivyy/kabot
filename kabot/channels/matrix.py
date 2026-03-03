"""Matrix channel implementation via websocket bridge."""

from kabot.bus.queue import MessageBus
from kabot.channels.bridge_ws import BridgeWebSocketChannel
from kabot.config.schema import MatrixConfig


class MatrixChannel(BridgeWebSocketChannel):
    """Matrix adapter using external bridge transport."""

    name = "matrix"

    def __init__(self, config: MatrixConfig, bus: MessageBus):
        super().__init__(config, bus, channel_name="matrix")
