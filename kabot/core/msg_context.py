"""
Standardized Message Context for Kabot (Phase 9).

MsgContext replaces raw InboundMessage as the canonical message representation,
adding support for system events, directives, and channel metadata normalization.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Optional


class ChannelType(StrEnum):
    """Supported channel types."""
    CLI = "cli"
    WEB = "web"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    WHATSAPP = "whatsapp"
    SLACK = "slack"
    EMAIL = "email"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    QQ = "qq"
    SYSTEM = "system"  # Internal system events


@dataclass
class MsgContext:
    """
    Standardized message context — the single object that flows through the
    entire Kabot pipeline (Monitor → Dispatcher → Agent → Response).

    This replaces ad-hoc dict/InboundMessage usage with a rich, typed container.
    """

    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel: ChannelType = ChannelType.CLI
    sender_id: str = ""
    chat_id: str = ""

    # Content
    body: str = ""
    media: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Channel-specific metadata (e.g., Telegram message_id, Discord guild_id)
    metadata: dict[str, Any] = field(default_factory=dict)

    # System event flag (for heartbeat/cron injections)
    is_system_event: bool = False
    event_type: Optional[str] = None  # e.g., "cron_result", "heartbeat", "startup"
    event_data: dict[str, Any] = field(default_factory=dict)

    # Directives parsed from the message body (Phase 9.2)
    directives: dict[str, Any] = field(default_factory=dict)

    # Processed body (after stripping directives)
    clean_body: str = ""

    @property
    def session_key(self) -> str:
        """Unique session identifier."""
        return f"{self.channel}:{self.chat_id}"

    @classmethod
    def from_inbound(cls, msg: Any) -> "MsgContext":
        """
        Create MsgContext from an existing InboundMessage.
        
        This is the bridge for backward compatibility during migration.
        """
        from kabot.bus.events import InboundMessage
        if isinstance(msg, InboundMessage):
            channel = msg.channel
            try:
                channel_type = ChannelType(channel)
            except ValueError:
                channel_type = ChannelType.CLI

            return cls(
                channel=channel_type,
                sender_id=msg.sender_id,
                chat_id=msg.chat_id,
                body=msg.content,
                clean_body=msg.content,
                media=msg.media,
                timestamp=msg.timestamp,
                metadata=msg.metadata,
            )
        raise TypeError(f"Cannot create MsgContext from {type(msg)}")

    @classmethod
    def system_event(cls, event_type: str, data: dict[str, Any] | None = None, body: str = "") -> "MsgContext":
        """Create a system event MsgContext (for heartbeat/cron injections)."""
        return cls(
            channel=ChannelType.SYSTEM,
            is_system_event=True,
            event_type=event_type,
            event_data=data or {},
            body=body,
            clean_body=body,
        )

    def __repr__(self) -> str:
        event_info = f", event={self.event_type}" if self.is_system_event else ""
        return (
            f"MsgContext(channel={self.channel}, sender={self.sender_id}, "
            f"body={self.body[:40]}...{event_info})"
        )
