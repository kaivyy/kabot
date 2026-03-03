"""Mattermost channel implementation via websocket bridge."""

from kabot.bus.queue import MessageBus
from kabot.channels.bridge_ws import BridgeWebSocketChannel
from kabot.config.schema import MattermostConfig


class MattermostChannel(BridgeWebSocketChannel):
    """Mattermost adapter using external bridge transport."""

    name = "mattermost"

    def __init__(self, config: MattermostConfig, bus: MessageBus):
        super().__init__(config, bus, channel_name="mattermost")
