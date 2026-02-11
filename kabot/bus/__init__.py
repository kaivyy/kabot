"""Message bus module for decoupled channel-agent communication."""

from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
