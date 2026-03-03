"""Signal channel implementation via websocket bridge."""

from kabot.bus.queue import MessageBus
from kabot.channels.bridge_ws import BridgeWebSocketChannel
from kabot.config.schema import SignalConfig


class SignalChannel(BridgeWebSocketChannel):
    """Signal adapter using external bridge transport."""

    name = "signal"

    def __init__(self, config: SignalConfig, bus: MessageBus):
        super().__init__(config, bus, channel_name="signal")
