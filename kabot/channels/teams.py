"""Microsoft Teams channel implementation via websocket bridge."""

from kabot.bus.queue import MessageBus
from kabot.channels.bridge_ws import BridgeWebSocketChannel
from kabot.config.schema import TeamsConfig


class TeamsChannel(BridgeWebSocketChannel):
    """Teams adapter using external bridge transport."""

    name = "teams"

    def __init__(self, config: TeamsConfig, bus: MessageBus):
        super().__init__(config, bus, channel_name="teams")
