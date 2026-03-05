"""Slack channel implementation using Socket Mode."""

import asyncio
import re

from loguru import logger
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.websockets import SocketModeClient
from slack_sdk.web.async_client import AsyncWebClient

from kabot.bus.events import OutboundMessage
from kabot.bus.queue import MessageBus
from kabot.channels.base import BaseChannel
from kabot.config.schema import SlackConfig


class SlackChannel(BaseChannel):
    """Slack channel using Socket Mode."""

    name = "slack"

    def __init__(self, config: SlackConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: SlackConfig = config
        self._web_client: AsyncWebClient | None = None
        self._socket_client: SocketModeClient | None = None
        self._bot_user_id: str | None = None
        self._status_message_ts: dict[str, str] = {}
        self._stale_status_message_ts: dict[str, set[str]] = {}

    def _uses_mutable_status_lane(self) -> bool:
        """Slack updates a mutable status message across phases."""
        return True

    @staticmethod
    def _is_not_modified_update_error(exc: Exception) -> bool:
        text = str(exc or "").strip().lower()
        return "message_not_modified" in text or "not modified" in text

    @staticmethod
    def _is_message_not_found_error(exc: Exception) -> bool:
        text = str(exc or "").strip().lower()
        return "message_not_found" in text or "cant_update_message" in text

    @staticmethod
    def _is_transient_update_error(exc: Exception) -> bool:
        text = str(exc or "").strip().lower()
        transient_markers = (
            "timed out",
            "timeout",
            "temporarily",
            "ratelimited",
            "rate limited",
            "connection reset",
            "connection aborted",
        )
        return any(marker in text for marker in transient_markers)

    async def start(self) -> None:
        """Start the Slack Socket Mode client."""
        if not self.config.bot_token or not self.config.app_token:
            logger.error("Slack bot/app token not configured")
            return
        if self.config.mode != "socket":
            logger.error(f"Unsupported Slack mode: {self.config.mode}")
            return

        self._running = True

        self._web_client = AsyncWebClient(token=self.config.bot_token)
        self._socket_client = SocketModeClient(
            app_token=self.config.app_token,
            web_client=self._web_client,
        )

        self._socket_client.socket_mode_request_listeners.append(self._on_socket_request)

        # Resolve bot user ID for mention handling
        try:
            auth = await self._web_client.auth_test()
            self._bot_user_id = auth.get("user_id")
            logger.info(f"Slack bot connected as {self._bot_user_id}")
        except Exception as e:
            logger.warning(f"Slack auth_test failed: {e}")

        logger.info("Starting Slack Socket Mode client...")
        await self._socket_client.connect()

        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the Slack client."""
        self._running = False
        self._status_message_ts.clear()
        self._stale_status_message_ts.clear()
        if self._socket_client:
            try:
                await self._socket_client.close()
            except Exception as e:
                logger.warning(f"Slack socket close failed: {e}")
            self._socket_client = None

    def _mark_stale_status(self, chat_id: str, ts: str | None) -> None:
        if not ts:
            return
        bucket = self._stale_status_message_ts.setdefault(str(chat_id), set())
        bucket.add(str(ts))

    async def _cleanup_stale_status_messages(self, chat_id_str: str, channel: str) -> None:
        if not self._web_client:
            return
        stale_ts = sorted(self._stale_status_message_ts.get(chat_id_str, set()))
        if not stale_ts:
            return

        remaining: set[str] = set()
        for ts in stale_ts:
            try:
                await self._web_client.chat_delete(channel=channel, ts=ts)
            except Exception as exc:
                if self._is_message_not_found_error(exc):
                    continue
                if self._is_transient_update_error(exc):
                    remaining.add(ts)
                    continue
                continue

        if remaining:
            self._stale_status_message_ts[chat_id_str] = remaining
        else:
            self._stale_status_message_ts.pop(chat_id_str, None)

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Slack."""
        if not self._web_client:
            logger.warning("Slack client not running")
            return
        chat_id_str = str(msg.chat_id)
        is_status_update, _phase, status_text = self._status_update_payload(msg)
        if not is_status_update:
            self._clear_status_state(msg.chat_id)

        thread_ts = msg.reply_to or msg.metadata.get("thread_ts")
        use_thread = bool(thread_ts)
        try:
            if is_status_update:
                async with self._get_chat_send_lock(chat_id_str):
                    if self._should_skip_status_update(msg):
                        return
                    if not status_text:
                        return
                    existing_ts = self._status_message_ts.get(chat_id_str)
                    if existing_ts:
                        try:
                            await self._web_client.chat_update(
                                channel=msg.chat_id,
                                ts=existing_ts,
                                text=status_text,
                            )
                            return
                        except Exception as exc:
                            if self._is_not_modified_update_error(exc):
                                return
                            if self._is_transient_update_error(exc):
                                return
                            if self._is_message_not_found_error(exc):
                                self._status_message_ts.pop(chat_id_str, None)
                            else:
                                self._mark_stale_status(chat_id_str, existing_ts)
                                self._status_message_ts.pop(chat_id_str, None)
                    created = await self._web_client.chat_postMessage(
                        channel=msg.chat_id,
                        text=status_text,
                        thread_ts=thread_ts if use_thread else None,
                    )
                    created_ts = created.get("ts") if isinstance(created, dict) else None
                    if isinstance(created_ts, str) and created_ts.strip():
                        self._status_message_ts[chat_id_str] = created_ts
                return

            async with self._get_chat_send_lock(chat_id_str):
                existing_ts = self._status_message_ts.get(chat_id_str)
                if existing_ts:
                    try:
                        await self._web_client.chat_delete(
                            channel=msg.chat_id,
                            ts=existing_ts,
                        )
                        self._status_message_ts.pop(chat_id_str, None)
                    except Exception as exc:
                        if self._is_message_not_found_error(exc):
                            self._status_message_ts.pop(chat_id_str, None)
                        elif not self._is_transient_update_error(exc):
                            self._status_message_ts.pop(chat_id_str, None)
                await self._cleanup_stale_status_messages(chat_id_str, msg.chat_id)

            # 1. Send files if present
            if msg.media:
                for file_path in msg.media:
                    try:
                        from pathlib import Path
                        path = Path(file_path)
                        if path.exists():
                            # Use files_upload_v2 for modern file uploading
                            await self._web_client.files_upload_v2(
                                channel=msg.chat_id,
                                file=str(path),
                                title=path.name,
                                initial_comment=msg.content if msg.content else None,
                                thread_ts=thread_ts if use_thread else None
                            )
                            # Clear content since we sent it with the file
                            msg.content = ""
                        else:
                            logger.error(f"Slack file not found: {file_path}")
                    except Exception as e:
                        logger.error(f"Slack file upload failed: {e}")

            # 2. Send text if still remaining (or if no files were sent)
            if msg.content:
                await self._web_client.chat_postMessage(
                    channel=msg.chat_id,
                    text=msg.content,
                    thread_ts=thread_ts if use_thread else None,
                )
        except Exception as e:
            logger.error(f"Error sending Slack message: {e}")

    async def _on_socket_request(
        self,
        client: SocketModeClient,
        req: SocketModeRequest,
    ) -> None:
        """Handle incoming Socket Mode requests."""
        if req.type != "events_api":
            return

        # Acknowledge right away
        await client.send_socket_mode_response(
            SocketModeResponse(envelope_id=req.envelope_id)
        )

        payload = req.payload or {}
        event = payload.get("event") or {}
        event_type = event.get("type")

        # Handle app mentions or plain messages
        if event_type not in ("message", "app_mention"):
            return

        sender_id = event.get("user")
        chat_id = event.get("channel")

        # Ignore bot/system messages (any subtype = not a normal user message)
        if event.get("subtype"):
            return
        if self._bot_user_id and sender_id == self._bot_user_id:
            return

        # Avoid double-processing: Slack sends both `message` and `app_mention`
        # for mentions in channels. Prefer `app_mention`.
        text = event.get("text") or ""
        if event_type == "message" and self._bot_user_id and f"<@{self._bot_user_id}>" in text:
            return

        # Debug: log basic event shape
        logger.debug(
            "Slack event: type={} subtype={} user={} channel={} channel_type={} text={}",
            event_type,
            event.get("subtype"),
            sender_id,
            chat_id,
            event.get("channel_type"),
            text[:80],
        )
        if not sender_id or not chat_id:
            return

        channel_type = event.get("channel_type") or ""

        if not self._is_allowed(sender_id, chat_id, channel_type):
            return

        if channel_type != "im" and not self._should_respond_in_channel(event_type, text, chat_id):
            return

        text = self._strip_bot_mention(text)

        thread_ts = event.get("thread_ts") or event.get("ts")
        # Add :eyes: reaction to the triggering message (best-effort)
        try:
            if self._web_client and event.get("ts"):
                await self._web_client.reactions_add(
                    channel=chat_id,
                    name="eyes",
                    timestamp=event.get("ts"),
                )
        except Exception as e:
            logger.debug(f"Slack reactions_add failed: {e}")

        await self._handle_message(
            sender_id=sender_id,
            chat_id=chat_id,
            content=text,
            metadata={
                "slack": {
                    "event": event,
                    "thread_ts": thread_ts,
                    "channel_type": channel_type,
                }
            },
        )

    def _is_allowed(self, sender_id: str, chat_id: str, channel_type: str) -> bool:
        if channel_type == "im":
            if not self.config.dm.enabled:
                return False
            if self.config.dm.policy == "allowlist":
                return sender_id in self.config.dm.allow_from
            return True

        # Group / channel messages
        if self.config.group_policy == "allowlist":
            return chat_id in self.config.group_allow_from
        return True

    def _should_respond_in_channel(self, event_type: str, text: str, chat_id: str) -> bool:
        if self.config.group_policy == "open":
            return True
        if self.config.group_policy == "mention":
            if event_type == "app_mention":
                return True
            return self._bot_user_id is not None and f"<@{self._bot_user_id}>" in text
        if self.config.group_policy == "allowlist":
            return chat_id in self.config.group_allow_from
        return False

    def _strip_bot_mention(self, text: str) -> str:
        if not text or not self._bot_user_id:
            return text
        return re.sub(rf"<@{re.escape(self._bot_user_id)}>\s*", "", text).strip()
