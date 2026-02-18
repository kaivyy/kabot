"""Event types for the message bus."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


@dataclass
class InboundMessage:
    """Message received from a chat channel (OpenClaw-compatible)."""

    channel: str  # telegram, discord, slack, whatsapp
    sender_id: str  # User identifier
    chat_id: str  # Chat/channel identifier
    content: str  # Message text
    timestamp: datetime = field(default_factory=datetime.now)
    media: list[str] = field(default_factory=list)  # Media URLs
    metadata: dict[str, Any] = field(default_factory=dict)  # Channel-specific data
    _session_key: str | None = None  # Override for session key

    # OpenClaw-compatible routing fields
    account_id: str | None = None  # Account/user identifier for routing
    peer_kind: str | None = None  # Peer type: "direct", "group", "channel"
    peer_id: str | None = None  # Peer identifier
    guild_id: str | None = None  # Discord guild ID
    team_id: str | None = None  # Slack team ID
    thread_id: str | None = None  # Thread identifier
    parent_peer: dict[str, str] | None = None  # Parent peer for thread inheritance

    @property
    def session_key(self) -> str:
        """Unique key for session identification."""
        if self._session_key:
            return self._session_key
        return f"{self.channel}:{self.chat_id}"


@dataclass
class OutboundMessage:
    """Message to send to a chat channel."""

    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemEvent:
    """
    System event for monitoring and debugging.

    Pattern from OpenClaw: src/infra/agent-events.ts
    Enables real-time monitoring of agent internals.
    """

    run_id: str  # Unique run identifier
    seq: int  # Monotonic sequence number per run
    stream: Literal["lifecycle", "tool", "assistant", "error"]  # Event type
    timestamp: float  # Unix timestamp
    data: dict[str, Any]  # Event-specific data

    @staticmethod
    def lifecycle(run_id: str, seq: int, action: str, **kwargs: Any) -> "SystemEvent":
        """Create a lifecycle event (start, stop, pause, resume)."""
        return SystemEvent(
            run_id=run_id,
            seq=seq,
            stream="lifecycle",
            timestamp=datetime.now().timestamp(),
            data={"action": action, **kwargs}
        )

    @staticmethod
    def tool(run_id: str, seq: int, tool_name: str, status: str, **kwargs: Any) -> "SystemEvent":
        """Create a tool execution event (start, complete, error)."""
        return SystemEvent(
            run_id=run_id,
            seq=seq,
            stream="tool",
            timestamp=datetime.now().timestamp(),
            data={"tool": tool_name, "status": status, **kwargs}
        )

    @staticmethod
    def assistant(run_id: str, seq: int, content: str, **kwargs: Any) -> "SystemEvent":
        """Create an assistant token/message event."""
        return SystemEvent(
            run_id=run_id,
            seq=seq,
            stream="assistant",
            timestamp=datetime.now().timestamp(),
            data={"content": content, **kwargs}
        )

    @staticmethod
    def error(run_id: str, seq: int, error_type: str, message: str, **kwargs: Any) -> "SystemEvent":
        """Create an error event."""
        return SystemEvent(
            run_id=run_id,
            seq=seq,
            stream="error",
            timestamp=datetime.now().timestamp(),
            data={"error_type": error_type, "message": message, **kwargs}
        )
