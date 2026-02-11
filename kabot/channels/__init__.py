"""Chat channels module with plugin architecture."""

from kabot.channels.base import BaseChannel
from kabot.channels.manager import ChannelManager

__all__ = ["BaseChannel", "ChannelManager"]
