"""Shared websocket-bridge channel implementation for lightweight adapters."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from loguru import logger

from kabot.bus.events import OutboundMessage
from kabot.bus.queue import MessageBus
from kabot.channels.base import BaseChannel


class BridgeWebSocketChannel(BaseChannel):
    """Generic channel that relays inbound/outbound messages through a websocket bridge."""

    name = "bridge"

    def __init__(self, config: Any, bus: MessageBus, *, channel_name: str):
        super().__init__(config, bus)
        self.name = channel_name
        self._ws = None
        self._connected = False

    async def start(self) -> None:
        """Connect to websocket bridge and forward inbound messages."""
        import websockets

        bridge_url = str(getattr(self.config, "bridge_url", "") or "").strip()
        if not bridge_url:
            logger.error(f"{self.name} bridge URL not configured")
            return

        logger.info(f"Connecting {self.name} channel bridge at {bridge_url}...")
        self._running = True

        while self._running:
            try:
                async with websockets.connect(bridge_url) as ws:
                    self._ws = ws
                    self._connected = True
                    logger.info(f"{self.name} bridge connected")

                    async for raw in ws:
                        try:
                            await self._handle_bridge_message(raw)
                        except Exception as exc:
                            logger.warning(f"{self.name} bridge message handling error: {exc}")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._connected = False
                self._ws = None
                if self._running:
                    logger.warning(f"{self.name} bridge connection error: {exc}")
                    await asyncio.sleep(5)

    async def stop(self) -> None:
        self._running = False
        self._connected = False
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def send(self, msg: OutboundMessage) -> None:
        if not self._connected or self._ws is None:
            logger.warning(f"{self.name} bridge not connected")
            return
        chat_id = str(msg.chat_id or "").strip()
        if not chat_id:
            logger.warning(f"{self.name} outbound dropped: missing chat_id")
            return
        has_text = bool(str(msg.content or "").strip())
        has_media = bool(msg.media)
        if not has_text and not has_media:
            logger.debug(f"{self.name} outbound dropped: empty content and media")
            return

        payload: dict[str, Any] = {
            "type": "send",
            "to": chat_id,
            "text": msg.content,
        }
        if msg.media:
            payload["media"] = list(msg.media)
        if msg.metadata:
            payload["metadata"] = dict(msg.metadata)
        await self._ws.send(json.dumps(payload))

    async def _handle_bridge_message(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from {self.name} bridge: {raw[:120]}")
            return
        if not isinstance(data, dict):
            logger.warning(f"Invalid payload type from {self.name} bridge: {type(data).__name__}")
            return

        msg_type = str(data.get("type") or "").strip().lower()
        if msg_type == "status":
            status = str(data.get("status") or "").strip().lower()
            if status == "connected":
                self._connected = True
            elif status == "disconnected":
                self._connected = False
            logger.info(f"{self.name} bridge status: {status or 'unknown'}")
            return

        if msg_type != "message":
            return

        sender = (
            str(data.get("sender") or data.get("from") or data.get("pn") or "").strip()
            or "unknown"
        )
        sender_id = sender.split("@")[0] if "@" in sender else sender
        chat_id = str(
            data.get("chat_id")
            or data.get("chatId")
            or data.get("room_id")
            or data.get("roomId")
            or data.get("conversation_id")
            or data.get("conversationId")
            or sender
        ).strip()
        content = str(data.get("content") or data.get("text") or "").strip()
        media = data.get("media")
        if not isinstance(media, list):
            media = []
        metadata = data.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        if not content and not media:
            logger.debug(f"{self.name} inbound message dropped: empty content and media")
            return

        await self._handle_message(
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            media=media,
            metadata=metadata,
        )
