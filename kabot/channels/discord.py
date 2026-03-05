"""Discord channel implementation using Discord Gateway websocket."""

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import websockets
from loguru import logger

from kabot.bus.events import OutboundMessage
from kabot.bus.queue import MessageBus
from kabot.channels.base import BaseChannel
from kabot.config.schema import DiscordConfig

DISCORD_API_BASE = "https://discord.com/api/v10"
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024  # 20MB
_DISCORD_TYPING_INTERVAL_SECONDS = 8.0
_DISCORD_TYPING_RETRY_DELAY_SECONDS = 3.0
_DISCORD_TYPING_MAX_DURATION_SECONDS = 120.0
_DISCORD_TYPING_MAX_CONSECUTIVE_FAILURES = 6


class DiscordChannel(BaseChannel):
    """Discord channel using Gateway websocket."""

    name = "discord"

    def __init__(self, config: DiscordConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: DiscordConfig = config
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._seq: int | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._typing_tasks: dict[str, asyncio.Task] = {}
        # Keep one mutable status message per channel for phase updates.
        self._status_message_ids: dict[str, str] = {}
        # Track stale status bubbles that must be cleaned before/after final reply.
        self._stale_status_message_ids: dict[str, set[str]] = {}
        self._http: httpx.AsyncClient | None = None

    def _allow_keepalive_passthrough(self) -> bool:
        """Discord uses keepalive pulses to keep typing/status lane responsive."""
        return True

    def _uses_mutable_status_lane(self) -> bool:
        """Discord updates a mutable status message across phases."""
        return True

    @staticmethod
    def _is_transient_http_status(status_code: int) -> bool:
        return status_code == 429 or 500 <= status_code <= 599

    async def start(self) -> None:
        """Start the Discord gateway connection."""
        if not self.config.token:
            logger.error("Discord bot token not configured")
            return

        self._running = True
        self._http = httpx.AsyncClient(timeout=30.0)

        while self._running:
            try:
                logger.info("Connecting to Discord gateway...")
                async with websockets.connect(self.config.gateway_url) as ws:
                    self._ws = ws
                    await self._gateway_loop()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Discord gateway error: {e}")
                if self._running:
                    logger.info("Reconnecting to Discord gateway in 5 seconds...")
                    await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop the Discord channel."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        for task in self._typing_tasks.values():
            task.cancel()
        self._typing_tasks.clear()
        self._status_message_ids.clear()
        self._stale_status_message_ids.clear()
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._http:
            await self._http.aclose()
            self._http = None

    def _mark_stale_status(self, chat_id: str, message_id: str | None) -> None:
        if not message_id:
            return
        bucket = self._stale_status_message_ids.setdefault(str(chat_id), set())
        bucket.add(str(message_id))

    async def _cleanup_stale_status_messages(
        self,
        chat_id_str: str,
        url: str,
        headers: dict[str, str],
    ) -> None:
        stale_ids = sorted(self._stale_status_message_ids.get(chat_id_str, set()))
        if not stale_ids or self._http is None:
            return

        remaining: set[str] = set()
        for stale_id in stale_ids:
            try:
                response = await self._http.delete(f"{url}/{stale_id}", headers=headers)
                if 200 <= response.status_code < 300 or response.status_code == 404:
                    continue
                if self._is_transient_http_status(response.status_code):
                    remaining.add(stale_id)
                    continue
            except Exception:
                # Keep stale id for retry on next final send.
                remaining.add(stale_id)

        if remaining:
            self._stale_status_message_ids[chat_id_str] = remaining
        else:
            self._stale_status_message_ids.pop(chat_id_str, None)

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Discord REST API."""
        if not self._http:
            logger.warning("Discord HTTP client not initialized")
            return
        chat_id_str = str(msg.chat_id)
        is_progress_update, _phase, _status_text = self._status_update_payload(msg)
        if not is_progress_update:
            self._clear_status_state(msg.chat_id)

        url = f"{DISCORD_API_BASE}/channels/{chat_id_str}/messages"
        payload: dict[str, Any] = {"content": msg.content}
        components = None
        if isinstance(msg.metadata, dict):
            value = msg.metadata.get("components")
            if isinstance(value, list) and value:
                components = value

        if msg.reply_to:
            payload["message_reference"] = {"message_id": msg.reply_to}
            payload["allowed_mentions"] = {"replied_user": False}
        if components:
            payload["components"] = components

        headers = {"Authorization": f"Bot {self.config.token}"}

        try:
            if is_progress_update:
                await self._ensure_typing(chat_id_str)
                async with self._get_chat_send_lock(chat_id_str):
                    if self._should_skip_status_update(msg):
                        return
                    status_content = str(msg.content or "").strip()
                    if not status_content:
                        return
                    status_payload = {"content": status_content}
                    existing_status_id = self._status_message_ids.get(chat_id_str)
                    if existing_status_id:
                        update_url = f"{url}/{existing_status_id}"
                        try:
                            response = await self._http.patch(update_url, headers=headers, json=status_payload)
                            if 200 <= response.status_code < 300:
                                return
                            if response.status_code == 404:
                                self._status_message_ids.pop(chat_id_str, None)
                            elif self._is_transient_http_status(response.status_code):
                                return
                            else:
                                self._mark_stale_status(chat_id_str, existing_status_id)
                                self._status_message_ids.pop(chat_id_str, None)
                        except Exception:
                            # Keep existing status id on transport issues to avoid duplicate status bubbles.
                            return
                    created = await self._http.post(url, headers=headers, json=status_payload)
                    if not (200 <= created.status_code < 300):
                        logger.warning(
                            f"Discord status update failed: status={created.status_code} chat_id={chat_id_str}"
                        )
                        return
                    try:
                        created_data = created.json()
                    except Exception:
                        created_data = {}
                    created_id = created_data.get("id")
                    if created_id:
                        self._status_message_ids[chat_id_str] = str(created_id)
                return

            async with self._get_chat_send_lock(chat_id_str):
                existing_status_id = self._status_message_ids.get(chat_id_str)
                if existing_status_id:
                    try:
                        response = await self._http.delete(f"{url}/{existing_status_id}", headers=headers)
                        if 200 <= response.status_code < 300 or response.status_code == 404:
                            self._status_message_ids.pop(chat_id_str, None)
                        elif not self._is_transient_http_status(response.status_code):
                            self._status_message_ids.pop(chat_id_str, None)
                    except Exception:
                        pass
                await self._cleanup_stale_status_messages(chat_id_str, url, headers)

            # 1. Send text only
            if not msg.media:
                payload = {"content": msg.content}
                if msg.reply_to:
                    payload["message_reference"] = {"message_id": msg.reply_to}
                    payload["allowed_mentions"] = {"replied_user": False}
                if components:
                    payload["components"] = components

                await self._http.post(url, headers=headers, json=payload)
                return

            # 2. Send with attachments (multipart/form-data)
            # Discord requires complex multipart payload for files + json
            # We'll send files one by one or batch if possible, but simplicity first:
            # For now, let's send files as separate messages or attached to text

            # Use httpx for multipart upload
            files = {}
            for i, file_path in enumerate(msg.media):
                path = Path(file_path)
                if path.exists():
                    files[f"files[{i}]"] = (path.name, path.read_bytes())

            if files:
                payload_json = {"content": msg.content or ""}
                if msg.reply_to:
                    payload_json["message_reference"] = {"message_id": msg.reply_to}
                if components:
                    payload_json["components"] = components

                # httpx handles multipart boundary automatically
                await self._http.post(
                    url,
                    headers=headers,
                    data={"payload_json": json.dumps(payload_json)},
                    files=files
                )
            else:
                # Fallback if files don't exist
                fallback_payload = {"content": msg.content}
                if components:
                    fallback_payload["components"] = components
                await self._http.post(url, headers=headers, json=fallback_payload)

        except Exception as e:
            logger.error(f"Error sending Discord message: {e}")
        finally:
            if not is_progress_update:
                await self._stop_typing(msg.chat_id)

    async def _gateway_loop(self) -> None:
        """Main gateway loop: identify, heartbeat, dispatch events."""
        if not self._ws:
            return

        async for raw in self._ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from Discord gateway: {raw[:100]}")
                continue

            op = data.get("op")
            event_type = data.get("t")
            seq = data.get("s")
            payload = data.get("d")

            if seq is not None:
                self._seq = seq

            if op == 10:
                # HELLO: start heartbeat and identify
                interval_ms = payload.get("heartbeat_interval", 45000)
                await self._start_heartbeat(interval_ms / 1000)
                await self._identify()
            elif op == 0 and event_type == "READY":
                logger.info("Discord gateway READY")
            elif op == 0 and event_type == "MESSAGE_CREATE":
                await self._handle_message_create(payload)
            elif op == 0 and event_type == "INTERACTION_CREATE":
                await self._handle_interaction_create(payload)
            elif op == 7:
                # RECONNECT: exit loop to reconnect
                logger.info("Discord gateway requested reconnect")
                break
            elif op == 9:
                # INVALID_SESSION: reconnect
                logger.warning("Discord gateway invalid session")
                break

    async def _identify(self) -> None:
        """Send IDENTIFY payload."""
        if not self._ws:
            return

        identify = {
            "op": 2,
            "d": {
                "token": self.config.token,
                "intents": self.config.intents,
                "properties": {
                    "os": "kabot",
                    "browser": "kabot",
                    "device": "kabot",
                },
            },
        }
        await self._ws.send(json.dumps(identify))

    async def _start_heartbeat(self, interval_s: float) -> None:
        """Start or restart the heartbeat loop."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        async def heartbeat_loop() -> None:
            while self._running and self._ws:
                payload = {"op": 1, "d": self._seq}
                try:
                    await self._ws.send(json.dumps(payload))
                except Exception as e:
                    logger.warning(f"Discord heartbeat failed: {e}")
                    break
                await asyncio.sleep(interval_s)

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())

    async def _handle_message_create(self, payload: dict[str, Any]) -> None:
        """Handle incoming Discord messages."""
        author = payload.get("author") or {}
        if author.get("bot"):
            return

        sender_id = str(author.get("id", ""))
        channel_id = str(payload.get("channel_id", ""))
        content = payload.get("content") or ""

        if not sender_id or not channel_id:
            return

        if not self.is_allowed(sender_id):
            return

        content_parts = [content] if content else []
        media_paths: list[str] = []
        media_dir = Path.home() / ".kabot" / "media"

        for attachment in payload.get("attachments") or []:
            url = attachment.get("url")
            filename = attachment.get("filename") or "attachment"
            size = attachment.get("size") or 0
            if not url or not self._http:
                continue
            if size and size > MAX_ATTACHMENT_BYTES:
                content_parts.append(f"[attachment: {filename} - too large]")
                continue
            try:
                media_dir.mkdir(parents=True, exist_ok=True)
                file_path = media_dir / f"{attachment.get('id', 'file')}_{filename.replace('/', '_')}"
                resp = await self._http.get(url)
                resp.raise_for_status()
                file_path.write_bytes(resp.content)
                media_paths.append(str(file_path))
                content_parts.append(f"[attachment: {file_path}]")
            except Exception as e:
                logger.warning(f"Failed to download Discord attachment: {e}")
                content_parts.append(f"[attachment: {filename} - download failed]")

        reply_to = (payload.get("referenced_message") or {}).get("id")

        await self._start_typing(channel_id)

        await self._handle_message(
            sender_id=sender_id,
            chat_id=channel_id,
            content="\n".join(p for p in content_parts if p) or "[empty message]",
            media=media_paths,
            metadata={
                "message_id": str(payload.get("id", "")),
                "guild_id": payload.get("guild_id"),
                "reply_to": reply_to,
            },
        )

    async def _handle_interaction_create(self, payload: dict[str, Any]) -> None:
        """Handle Discord INTERACTION_CREATE events."""
        member = payload.get("member") or {}
        user = member.get("user") or payload.get("user") or {}
        sender_id = str(user.get("id", "")).strip()
        channel_id = str(payload.get("channel_id", "")).strip()
        interaction_data = payload.get("data") or {}

        if not sender_id or not channel_id:
            return
        if not self.is_allowed(sender_id):
            return

        custom_id = str(interaction_data.get("custom_id", "")).strip()
        values = interaction_data.get("values")
        if not custom_id and isinstance(values, list) and values:
            custom_id = str(values[0]).strip()
        content = custom_id or "/interaction"

        await self._handle_message(
            sender_id=sender_id,
            chat_id=channel_id,
            content=content,
            metadata={
                "is_interaction": True,
                "interaction_id": str(payload.get("id", "")),
                "interaction_type": payload.get("type"),
                "custom_id": custom_id,
                "component_type": interaction_data.get("component_type"),
                "values": values if isinstance(values, list) else [],
                "guild_id": payload.get("guild_id"),
            },
        )

    async def _start_typing(self, channel_id: str) -> None:
        """Start periodic typing indicator for a channel."""
        await self._stop_typing(channel_id)

        async def typing_loop() -> None:
            url = f"{DISCORD_API_BASE}/channels/{channel_id}/typing"
            headers = {"Authorization": f"Bot {self.config.token}"}
            loop = asyncio.get_running_loop()
            started_at = loop.time()
            consecutive_failures = 0
            current_task = asyncio.current_task()
            while self._running:
                if (loop.time() - started_at) >= float(_DISCORD_TYPING_MAX_DURATION_SECONDS):
                    logger.debug(f"Discord typing TTL reached for channel={channel_id}; stopping loop")
                    break
                try:
                    if self._http is None:
                        break
                    await self._http.post(url, headers=headers)
                    consecutive_failures = 0
                except Exception:
                    consecutive_failures += 1
                    if consecutive_failures >= int(_DISCORD_TYPING_MAX_CONSECUTIVE_FAILURES):
                        logger.warning(
                            "Discord typing stopped after repeated failures "
                            f"channel={channel_id} failures={consecutive_failures}"
                        )
                        break
                    await asyncio.sleep(float(_DISCORD_TYPING_RETRY_DELAY_SECONDS))
                    continue
                await asyncio.sleep(float(_DISCORD_TYPING_INTERVAL_SECONDS))

            existing = self._typing_tasks.get(channel_id)
            if existing is current_task:
                self._typing_tasks.pop(channel_id, None)

        self._typing_tasks[channel_id] = asyncio.create_task(typing_loop())

    async def _ensure_typing(self, channel_id: str) -> None:
        """Ensure typing keepalive is active for progress updates."""
        if not self._running:
            return
        task = self._typing_tasks.get(channel_id)
        if task and not task.done():
            return
        await self._start_typing(channel_id)

    async def _stop_typing(self, channel_id: str) -> None:
        """Stop typing indicator for a channel."""
        task = self._typing_tasks.pop(channel_id, None)
        if task:
            task.cancel()
