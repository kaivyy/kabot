"""Base channel interface for chat platforms."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from loguru import logger

from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.bus.queue import MessageBus


class BaseChannel(ABC):
    """
    Abstract base class for chat channel implementations.

    Each channel (Telegram, Discord, etc.) should implement this interface
    to integrate with the kabot message bus.
    """

    name: str = "base"

    def __init__(self, config: Any, bus: MessageBus):
        """
        Initialize the channel.

        Args:
            config: Channel-specific configuration.
            bus: The message bus for communication.
        """
        self.config = config
        self.bus = bus
        self._running = False
        # Per-chat status phase cache used to dedupe interim status updates.
        self._status_phase_cache: dict[str, str] = {}
        self._status_text_cache: dict[str, str] = {}
        # Per-chat send locks prevent status/final message races.
        self._chat_send_locks: dict[str, asyncio.Lock] = {}

    @abstractmethod
    async def start(self) -> None:
        """
        Start the channel and begin listening for messages.

        This should be a long-running async task that:
        1. Connects to the chat platform
        2. Listens for incoming messages
        3. Forwards messages to the bus via _handle_message()
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel and clean up resources."""
        pass

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """
        Send a message through this channel.

        Args:
            msg: The message to send.
        """
        pass

    def is_allowed(self, sender_id: str) -> bool:
        """
        Check if a sender is allowed to use this bot.

        Args:
            sender_id: The sender's identifier.

        Returns:
            True if allowed, False otherwise.
        """
        allow_list = getattr(self.config, "allow_from", [])

        # In strict preset, empty allow_from becomes fail-closed.
        if not allow_list:
            preset = str(getattr(self, "_security_policy_preset", "")).strip().lower()
            if preset == "strict":
                return False
            return True

        sender_str = str(sender_id)
        if sender_str in allow_list:
            return True
        if "|" in sender_str:
            for part in sender_str.split("|"):
                if part and part in allow_list:
                    return True
        return False

    async def _handle_message(
        self,
        sender_id: str,
        chat_id: str,
        content: str,
        media: list[str] | None = None,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """
        Handle an incoming message from the chat platform.

        This method checks permissions and forwards to the bus.

        Args:
            sender_id: The sender's identifier.
            chat_id: The chat/channel identifier.
            content: Message text content.
            media: Optional list of media URLs.
            metadata: Optional channel-specific metadata.
        """
        if not self.is_allowed(sender_id):
            allow_list = getattr(self.config, "allow_from", [])
            preset = str(getattr(self, "_security_policy_preset", "")).strip().lower()
            if preset == "strict" and not allow_list:
                logger.warning(
                    f"Access denied for sender {sender_id} on channel {self.name}. "
                    "Strict preset is active and allowFrom is empty (fail-closed)."
                )
            else:
                logger.warning(
                    f"Access denied for sender {sender_id} on channel {self.name}. "
                    f"Add them to allowFrom list in config to grant access."
                )
            return

        merged_metadata = dict(metadata or {})

        # Multi-instance channels can inject stable instance identity metadata.
        instance_meta = getattr(self, "_channel_instance_metadata", None)
        if isinstance(instance_meta, dict) and instance_meta:
            merged_metadata.setdefault("channel_instance", instance_meta)

        routing = self._extract_routing_fields(str(chat_id), merged_metadata)
        channel_name = str(getattr(self, "_channel_name", self.name))

        msg = InboundMessage(
            channel=channel_name,
            sender_id=str(sender_id),
            chat_id=str(chat_id),
            content=content,
            media=media or [],
            metadata=merged_metadata,
            account_id=routing["account_id"],
            peer_kind=routing["peer_kind"],
            peer_id=routing["peer_id"],
            guild_id=routing["guild_id"],
            team_id=routing["team_id"],
            thread_id=routing["thread_id"],
            parent_peer=routing["parent_peer"],
        )

        await self.bus.publish_inbound(msg)

    def _extract_routing_fields(self, chat_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """Extract Kabot-style routing fields from channel metadata."""
        routing: dict[str, Any] = {
            "account_id": None,
            "peer_kind": None,
            "peer_id": None,
            "guild_id": None,
            "team_id": None,
            "thread_id": None,
            "parent_peer": None,
        }

        account_id = metadata.get("account_id")
        if isinstance(account_id, (str, int)):
            account_id_str = str(account_id).strip()
            if account_id_str:
                routing["account_id"] = account_id_str

        peer_kind = metadata.get("peer_kind")
        if isinstance(peer_kind, str) and peer_kind.strip():
            routing["peer_kind"] = peer_kind.strip()
        elif metadata.get("is_group") is True:
            routing["peer_kind"] = "group"
        elif metadata.get("is_group") is False:
            routing["peer_kind"] = "direct"

        peer_id = metadata.get("peer_id")
        if isinstance(peer_id, (str, int)):
            peer_id_str = str(peer_id).strip()
            if peer_id_str:
                routing["peer_id"] = peer_id_str
        if routing["peer_id"] is None and chat_id:
            routing["peer_id"] = chat_id

        guild_id = metadata.get("guild_id")
        if isinstance(guild_id, (str, int)):
            guild_id_str = str(guild_id).strip()
            if guild_id_str:
                routing["guild_id"] = guild_id_str

        team_id = metadata.get("team_id")
        if isinstance(team_id, (str, int)):
            team_id_str = str(team_id).strip()
            if team_id_str:
                routing["team_id"] = team_id_str

        thread_id = metadata.get("thread_id")
        if isinstance(thread_id, (str, int)):
            thread_id_str = str(thread_id).strip()
            if thread_id_str:
                routing["thread_id"] = thread_id_str

        # Slack metadata is nested under metadata["slack"].
        slack_meta = metadata.get("slack")
        if isinstance(slack_meta, dict):
            if routing["thread_id"] is None:
                thread_ts = slack_meta.get("thread_ts")
                if isinstance(thread_ts, (str, int)):
                    thread_ts_str = str(thread_ts).strip()
                    if thread_ts_str:
                        routing["thread_id"] = thread_ts_str
            slack_event = slack_meta.get("event")
            if isinstance(slack_event, dict):
                if routing["team_id"] is None:
                    team = slack_event.get("team")
                    if isinstance(team, (str, int)):
                        team_str = str(team).strip()
                        if team_str:
                            routing["team_id"] = team_str

        parent_peer = metadata.get("parent_peer")
        if isinstance(parent_peer, dict):
            kind = str(parent_peer.get("kind", "")).strip()
            peer = str(parent_peer.get("id", "")).strip()
            if kind and peer:
                routing["parent_peer"] = {"kind": kind, "id": peer}

        return routing

    @property
    def is_running(self) -> bool:
        """Check if the channel is running."""
        return self._running

    def _status_update_payload(self, msg: OutboundMessage) -> tuple[bool, str, str]:
        """Extract normalized progress-update info from outbound message."""
        metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
        update_type = str(metadata.get("type") or "").strip().lower()
        # Keep backward compatibility with existing status updates while
        # allowing richer draft/partial updates on the same mutable lane.
        if update_type not in {"status_update", "draft_update", "reasoning_update"}:
            return False, "", ""
        default_phase = "reasoning" if update_type == "reasoning_update" else "thinking"
        phase = str(metadata.get("phase") or "").strip().lower() or default_phase
        text = str(msg.content or "").strip()
        return True, phase, text

    def _should_skip_status_update(self, msg: OutboundMessage) -> bool:
        """Return True when a status update is duplicate/no-op for this chat."""
        is_status, phase, text = self._status_update_payload(msg)
        if not is_status:
            return False
        metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
        # Keepalive pulses must pass through even when phase/text are unchanged,
        # otherwise typing/activity indicators can appear stalled on long turns.
        if bool(metadata.get("keepalive", False)) and self._allow_keepalive_passthrough():
            return False
        if not text:
            return True
        chat_key = str(msg.chat_id)
        if (
            self._status_phase_cache.get(chat_key) == phase
            and self._status_text_cache.get(chat_key) == text
        ):
            return True
        self._status_phase_cache[chat_key] = phase
        self._status_text_cache[chat_key] = text
        return False

    def _clear_status_state(self, chat_id: str) -> None:
        """Clear cached interim status state for a chat after final response."""
        chat_key = str(chat_id)
        self._status_phase_cache.pop(chat_key, None)
        self._status_text_cache.pop(chat_key, None)

    def _allow_keepalive_passthrough(self) -> bool:
        """
        Whether keepalive status pulses should bypass dedupe.

        Default is False to prevent duplicate "processing" messages on channels
        that do not support mutable status bubbles or typing activity hints.
        """
        return False

    def _uses_mutable_status_lane(self) -> bool:
        """
        Whether status phases are rendered as a mutable lane (edit/update style).

        Channels returning False should prefer minimal phase emissions to avoid
        user-facing status spam.
        """
        return False

    def _get_chat_send_lock(self, chat_id: str) -> asyncio.Lock:
        """Return per-chat send lock for serialized outbound updates."""
        chat_key = str(chat_id)
        lock = self._chat_send_locks.get(chat_key)
        if lock is None:
            lock = asyncio.Lock()
            self._chat_send_locks[chat_key] = lock
        return lock


