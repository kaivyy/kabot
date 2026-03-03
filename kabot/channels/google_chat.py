"""Google Chat channel implementation via websocket bridge."""

from kabot.bus.queue import MessageBus
from kabot.channels.bridge_ws import BridgeWebSocketChannel
from kabot.config.schema import GoogleChatConfig


class GoogleChatChannel(BridgeWebSocketChannel):
    """Google Chat adapter using external bridge transport."""

    name = "google_chat"

    def __init__(self, config: GoogleChatConfig, bus: MessageBus):
        super().__init__(config, bus, channel_name="google_chat")
