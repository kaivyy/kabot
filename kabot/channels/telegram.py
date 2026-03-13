"""Telegram channel implementation using python-telegram-bot."""

from __future__ import annotations

import asyncio
import hashlib
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import Conflict, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from kabot.bus.events import OutboundMessage
from kabot.bus.queue import MessageBus
from kabot.channels.base import BaseChannel
from kabot.config.schema import TelegramConfig
from kabot.core.command_surfaces import (
    CommandSurfaceSpec,
    build_command_surface_specs,
    list_workspace_skill_command_specs,
)
from kabot.core.command_router import CommandContext
from kabot.utils.helpers import get_data_path
from kabot.utils.text_safety import ensure_utf8_text

if TYPE_CHECKING:
    from kabot.session.manager import SessionManager

_TELEGRAM_TYPING_INTERVAL_SECONDS = 4.0
_TELEGRAM_TYPING_RETRY_DELAY_SECONDS = 2.0
_TELEGRAM_TYPING_MAX_DURATION_SECONDS = 120.0
_TELEGRAM_TYPING_MAX_CONSECUTIVE_FAILURES = 6
_TELEGRAM_MAX_COMMANDS = 100
_TELEGRAM_COMMAND_NAME_RE = re.compile(r"^[a-z0-9_]{1,32}$")
_TELEGRAM_COMMAND_RETRY_RATIO = 0.8


def _markdown_to_telegram_html(text: str) -> str:
    """
    Convert markdown to Telegram-safe HTML.
    """
    if not text:
        return ""

    # 1. Extract and protect code blocks (preserve content from other processing)
    code_blocks: list[str] = []
    def save_code_block(m: re.Match) -> str:
        code_blocks.append(m.group(1))
        return f"\x00CB{len(code_blocks) - 1}\x00"

    text = re.sub(r'```[\w]*\n?([\s\S]*?)```', save_code_block, text)

    # 2. Extract and protect inline code
    inline_codes: list[str] = []
    def save_inline_code(m: re.Match) -> str:
        inline_codes.append(m.group(1))
        return f"\x00IC{len(inline_codes) - 1}\x00"

    text = re.sub(r'`([^`]+)`', save_inline_code, text)

    # 3. Headers # Title -> just the title text
    text = re.sub(r'^#{1,6}\s+(.+)$', r'\1', text, flags=re.MULTILINE)

    # 4. Blockquotes > text -> just the text (before HTML escaping)
    text = re.sub(r'^>\s*(.*)$', r'\1', text, flags=re.MULTILINE)

    # 5. Escape HTML special characters
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # 6. Links [text](url) - must be before bold/italic to handle nested cases
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

    # 7. Bold **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)

    # 8. Italic _text_ (avoid matching inside words like some_var_name)
    text = re.sub(r'(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])', r'<i>\1</i>', text)

    # 9. Strikethrough ~~text~~
    text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)

    # 10. Bullet lists - item -> • item
    text = re.sub(r'^[-*]\s+', '• ', text, flags=re.MULTILINE)

    # 11. Restore inline code with HTML tags
    for i, code in enumerate(inline_codes):
        # Escape HTML in code content
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00IC{i}\x00", f"<code>{escaped}</code>")

    # 12. Restore code blocks with HTML tags
    for i, code in enumerate(code_blocks):
        # Escape HTML in code content
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00CB{i}\x00", f"<pre><code>{escaped}</code></pre>")

    return text


def build_inline_keyboard(rows: list[list[dict]]) -> InlineKeyboardMarkup | None:
    """Build Telegram inline keyboard markup from button specs."""
    if not rows:
        return None

    keyboard: list[list[InlineKeyboardButton]] = []
    for row in rows:
        keyboard_row: list[InlineKeyboardButton] = []
        for button in row:
            text = str(button.get("text", "")).strip()
            if not text:
                continue
            if "url" in button and button.get("url"):
                keyboard_row.append(InlineKeyboardButton(text=text, url=str(button["url"])))
            else:
                callback_data = str(button.get("callback_data", text))
                keyboard_row.append(
                    InlineKeyboardButton(text=text, callback_data=callback_data)
                )
        if keyboard_row:
            keyboard.append(keyboard_row)

    if not keyboard:
        return None
    return InlineKeyboardMarkup(keyboard)

def _split_message(text: str, max_length: int = 4000) -> list[str]:
    """Split a long message into chunks, preserving code blocks if possible."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    lines = text.split("\n")
    current_chunk = []
    current_length = 0
    in_code_block = False
    code_block_lang = ""

    for line in lines:
        is_fence = line.strip().startswith("```")
        if is_fence:
            if not in_code_block:
                in_code_block = True
                code_block_lang = line.strip()[3:]
            else:
                in_code_block = False
                code_block_lang = ""

        line_len = len(line) + 1 # +1 for newline

        # If adding this line exceeds max length
        if current_length + line_len > max_length and current_chunk:
            if in_code_block and not is_fence:
                # Close the code block in the current chunk and reopen in the next
                current_chunk.append("```")
                chunks.append("\n".join(current_chunk))
                current_chunk = [f"```{code_block_lang}", line]
                current_length = len(current_chunk[0]) + 1 + line_len
            else:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_length = line_len
        else:
            current_chunk.append(line)
            current_length += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    # Safety fallback for extremely long lines that are still > max_length
    final_chunks = []
    for chunk in chunks:
        if len(chunk) > max_length:
            for i in range(0, len(chunk), max_length):
                final_chunks.append(chunk[i:i+max_length])
        else:
            final_chunks.append(chunk)

    return final_chunks

class TelegramChannel(BaseChannel):
    """
    Telegram channel using long polling.

    Simple and reliable - no webhook/public IP needed.
    """

    name = "telegram"

    # Commands registered with Telegram's command menu
    BOT_COMMANDS = [
        BotCommand("start", "Start the bot"),
        BotCommand("reset", "Reset conversation history"),
        BotCommand("help", "Show available commands"),
    ]

    def __init__(
        self,
        config: TelegramConfig,
        bus: MessageBus,
        groq_api_key: str = "",
        session_manager: SessionManager | None = None,
        command_router: Any = None,
        workspace: str | Path | None = None,
    ):
        super().__init__(config, bus)
        self.config: TelegramConfig = config
        self.groq_api_key = groq_api_key
        self.session_manager = session_manager
        self.command_router = command_router
        self.workspace = Path(workspace).expanduser() if workspace else None
        self._app: Application | None = None
        self._chat_ids: dict[str, int] = {}  # Map sender_id to chat_id for replies
        self._typing_tasks: dict[str, asyncio.Task] = {}  # chat_id -> typing loop task
        # Keep one mutable status message per chat for phase updates.
        self._status_message_ids: dict[str, int] = {}
        # Track stale status bubbles that should be cleaned before final reply.
        self._stale_status_message_ids: dict[str, set[int]] = {}
        # Keep one mutable preview message per chat for draft/reasoning updates.
        self._preview_message_ids: dict[str, int] = {}
        # Track stale preview bubbles that should be cleaned before/after final reply.
        self._stale_preview_message_ids: dict[str, set[int]] = {}
        self._polling_conflict_handled: bool = False

    @staticmethod
    def _normalize_telegram_command_name(value: str) -> str:
        raw = str(value or "").strip()
        raw = raw.split(None, 1)[0] if raw else raw
        if raw.startswith("/"):
            raw = raw[1:]
        raw = raw.split("@", 1)[0]
        return raw.strip().lower().replace("-", "_").replace(" ", "_")

    def _is_valid_telegram_command_name(self, value: str) -> bool:
        return bool(value and _TELEGRAM_COMMAND_NAME_RE.match(value))

    def _get_skill_command_specs(self, reserved: set[str] | None = None) -> list[CommandSurfaceSpec]:
        return list_workspace_skill_command_specs(
            self.workspace,
            normalize_name=self._normalize_telegram_command_name,
            is_valid_name=self._is_valid_telegram_command_name,
            reserved=reserved,
        )

    def _get_command_surface_specs(self, router: Any | None = None) -> list[CommandSurfaceSpec]:
        static_commands = [(cmd.command, cmd.description) for cmd in self.BOT_COMMANDS]
        return build_command_surface_specs(
            static_commands=static_commands,
            router=router if router is not None else self.command_router,
            workspace=self.workspace,
            normalize_name=self._normalize_telegram_command_name,
            is_valid_name=self._is_valid_telegram_command_name,
            max_commands=_TELEGRAM_MAX_COMMANDS,
        )

    def _allow_keepalive_passthrough(self) -> bool:
        """Telegram needs keepalive pulses to maintain typing continuity."""
        return True

    def _uses_mutable_status_lane(self) -> bool:
        """Telegram edits a single status bubble across phases."""
        return True

    def get_bot_commands_from_router(self, router: Any) -> list[BotCommand]:
        """Generate BotCommand list from CommandRouter.

        Args:
            router: CommandRouter instance with registered commands

        Returns:
            List of BotCommand objects for Telegram bot API
        """
        return [
            BotCommand(spec.name, spec.description)
            for spec in self._get_command_surface_specs(router)
        ]

    def _get_reserved_non_skill_commands(self) -> set[str]:
        """Return static + router command names so skill slash commands can avoid collisions."""
        return {
            spec.name
            for spec in self._get_command_surface_specs()
            if spec.source != "skill"
        }

    @staticmethod
    def _hash_bot_commands(commands: list[BotCommand]) -> str:
        payload = sorted(
            [{"command": cmd.command, "description": cmd.description} for cmd in commands],
            key=lambda item: item["command"],
        )
        return hashlib.sha256(str(payload).encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _command_cache_suffix(bot_identity: str = "") -> str:
        normalized = str(bot_identity or "").strip() or "default"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    def _command_hash_cache_path(self, bot_identity: str = "") -> Path:
        state_dir = get_data_path() / "telegram"
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir / f"command-hash-{self._command_cache_suffix(bot_identity)}.txt"

    def _read_cached_command_hash(self, bot_identity: str = "") -> str:
        try:
            return self._command_hash_cache_path(bot_identity).read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    def _write_cached_command_hash(self, command_hash: str, bot_identity: str = "") -> None:
        try:
            self._command_hash_cache_path(bot_identity).write_text(command_hash, encoding="utf-8")
        except Exception as exc:
            logger.debug(f"Failed to cache Telegram command hash: {exc}")

    @staticmethod
    def _is_bot_commands_too_much_error(err: Exception | str | None) -> bool:
        if not err:
            return False
        if isinstance(err, str):
            return "BOT_COMMANDS_TOO_MUCH" in err.upper()
        text = str(err)
        return "BOT_COMMANDS_TOO_MUCH" in text.upper()

    async def _sync_bot_commands(self, bot: Any, commands_to_register: list[BotCommand], *, bot_identity: str = "") -> None:
        current_hash = self._hash_bot_commands(commands_to_register)
        if self._read_cached_command_hash(bot_identity) == current_hash:
            logger.debug("Telegram bot commands unchanged; skipping sync")
            return

        delete_succeeded = True
        delete_fn = getattr(bot, "delete_my_commands", None)
        if callable(delete_fn):
            try:
                await delete_fn()
            except Exception as exc:
                delete_succeeded = False
                logger.warning(f"Failed to clear Telegram bot commands before sync: {exc}")

        if not commands_to_register:
            if delete_succeeded:
                self._write_cached_command_hash(current_hash, bot_identity)
            return

        retry_commands = list(commands_to_register)
        while retry_commands:
            try:
                await bot.set_my_commands(retry_commands)
                self._write_cached_command_hash(current_hash, bot_identity)
                logger.debug(f"Telegram bot commands registered: {len(retry_commands)} commands")
                return
            except Exception as exc:
                if not self._is_bot_commands_too_much_error(exc):
                    raise
                next_count = int(len(retry_commands) * _TELEGRAM_COMMAND_RETRY_RATIO)
                reduced_count = next_count if next_count < len(retry_commands) else len(retry_commands) - 1
                if reduced_count <= 0:
                    logger.warning(
                        "Telegram rejected command menu with BOT_COMMANDS_TOO_MUCH; "
                        "no commands were registered."
                    )
                    return
                logger.warning(
                    "Telegram rejected {} commands with BOT_COMMANDS_TOO_MUCH; retrying with {}",
                    len(retry_commands),
                    reduced_count,
                )
                retry_commands = retry_commands[:reduced_count]

    async def start(self) -> None:
        """Start the Telegram bot with long polling."""
        if not self.config.token:
            logger.error("Telegram bot token not configured")
            return

        self._running = True
        self._polling_conflict_handled = False

        # Build the application with increased timeouts to prevent httpx.ReadError
        from telegram.request import HTTPXRequest

        req = HTTPXRequest(connection_pool_size=8, connect_timeout=15.0, read_timeout=30.0)
        builder = Application.builder().token(self.config.token).request(req).get_updates_request(req)

        if self.config.proxy:
            builder = builder.proxy(self.config.proxy).get_updates_proxy(self.config.proxy)
        self._app = builder.build()

        # Add command handlers
        self._app.add_handler(CommandHandler("start", self._on_start))
        self._app.add_handler(CommandHandler("reset", self._on_reset))
        self._app.add_handler(CommandHandler("help", self._on_help))
        self._app.add_handler(CallbackQueryHandler(self._on_callback_query))
        self._app.add_handler(MessageHandler(filters.COMMAND, self._on_router_command))

        # Add message handler for text, photos, voice, documents
        self._app.add_handler(
            MessageHandler(
                (filters.TEXT | filters.PHOTO | filters.VOICE | filters.AUDIO | filters.Document.ALL)
                & ~filters.COMMAND,
                self._on_message
            )
        )

        logger.info("Starting Telegram bot (polling mode)...")

        # Initialize and start polling
        await self._app.initialize()
        await self._app.start()

        # Get bot info and register command menu
        bot_info = await self._app.bot.get_me()
        logger.info(f"Telegram bot @{bot_info.username} connected")

        try:
            commands_to_register = self.get_bot_commands_from_router(self.command_router)
            await self._sync_bot_commands(
                self._app.bot,
                commands_to_register,
                bot_identity=str(getattr(bot_info, "username", "") or ""),
            )
        except Exception as e:
            logger.warning(f"Failed to register bot commands: {e}")

        # Start polling (this runs until stopped)
        await self._app.updater.start_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,  # Ignore old messages on startup
            error_callback=self._on_polling_error,
        )

        # Keep running until stopped
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        self._running = False

        # Cancel all typing indicators
        for chat_id in list(self._typing_tasks):
            self._stop_typing(chat_id)
        self._status_message_ids.clear()
        self._stale_status_message_ids.clear()
        self._preview_message_ids.clear()
        self._stale_preview_message_ids.clear()

        if self._app:
            logger.info("Stopping Telegram bot...")
            try:
                await self._app.updater.stop()
            except Exception as e:
                logger.debug(f"Telegram updater stop skipped: {e}")
            try:
                await self._app.stop()
            except Exception as e:
                logger.debug(f"Telegram app stop skipped: {e}")
            try:
                await self._app.shutdown()
            except Exception as e:
                logger.debug(f"Telegram app shutdown skipped: {e}")
            self._app = None

    def _on_polling_error(self, exc: TelegramError) -> None:
        """Handle polling transport errors without uncontrolled traceback spam."""
        if isinstance(exc, Conflict):
            if self._polling_conflict_handled:
                return
            self._polling_conflict_handled = True
            self._running = False
            logger.error(
                "Telegram polling conflict detected: another bot instance is using the same token. "
                "Stopping this channel."
            )
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.stop())
            except RuntimeError:
                # No running loop: channel manager will stop this channel on shutdown.
                pass
            return

        logger.warning(f"Telegram polling transient error: {exc}")

    @staticmethod
    def _exc_text(exc: Exception) -> str:
        return str(exc or "").strip().lower()

    @staticmethod
    def _is_message_not_modified_error(exc: Exception) -> bool:
        text = TelegramChannel._exc_text(exc)
        return "message is not modified" in text or "message not modified" in text

    @staticmethod
    def _is_message_not_found_error(exc: Exception) -> bool:
        text = TelegramChannel._exc_text(exc)
        return "message to edit not found" in text or "message to delete not found" in text or "message not found" in text

    @staticmethod
    def _is_transient_message_error(exc: Exception) -> bool:
        text = TelegramChannel._exc_text(exc)
        transient_markers = (
            "timed out",
            "timeout",
            "temporarily",
            "network error",
            "connection reset",
            "connection aborted",
            "too many requests",
            "retry after",
            "flood control",
        )
        return any(marker in text for marker in transient_markers)

    def _mark_stale_status(self, chat_id: str, message_id: int | None) -> None:
        if not message_id:
            return
        bucket = self._stale_status_message_ids.setdefault(str(chat_id), set())
        bucket.add(int(message_id))

    def _mark_stale_preview(self, chat_id: str, message_id: int | None) -> None:
        if not message_id:
            return
        bucket = self._stale_preview_message_ids.setdefault(str(chat_id), set())
        bucket.add(int(message_id))

    async def _cleanup_stale_status_messages(self, chat_id_str: str, chat_id: int) -> None:
        stale_ids = sorted(self._stale_status_message_ids.get(chat_id_str, set()))
        if not stale_ids:
            return
        for stale_id in stale_ids:
            try:
                await self._app.bot.delete_message(chat_id=chat_id, message_id=stale_id)
            except Exception as exc:
                if self._is_message_not_found_error(exc):
                    continue
                if self._is_transient_message_error(exc):
                    continue
                logger.debug(
                    f"Telegram stale status delete failed chat={chat_id_str} msg_id={stale_id}: {exc}"
                )
        self._stale_status_message_ids.pop(chat_id_str, None)

    async def _cleanup_stale_preview_messages(self, chat_id_str: str, chat_id: int) -> None:
        stale_ids = sorted(self._stale_preview_message_ids.get(chat_id_str, set()))
        if not stale_ids:
            return
        for stale_id in stale_ids:
            try:
                await self._app.bot.delete_message(chat_id=chat_id, message_id=stale_id)
            except Exception as exc:
                if self._is_message_not_found_error(exc):
                    continue
                if self._is_transient_message_error(exc):
                    continue
                logger.debug(
                    f"Telegram stale preview delete failed chat={chat_id_str} msg_id={stale_id}: {exc}"
                )
        self._stale_preview_message_ids.pop(chat_id_str, None)

    @staticmethod
    def _progress_update_type(msg: OutboundMessage) -> str:
        metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
        return str(metadata.get("type") or "").strip().lower()

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Telegram."""
        if not self._app:
            logger.warning("Telegram bot not running")
            return

        chat_id_str = str(msg.chat_id)
        is_progress_update, _phase, _status_text = self._status_update_payload(msg)
        progress_update_type = self._progress_update_type(msg)
        is_preview_update = progress_update_type in {"draft_update", "reasoning_update"}

        if not is_progress_update:
            self._clear_status_state(msg.chat_id)
            # Keep typing indicator alive across interim status updates.
            self._stop_typing(msg.chat_id)

        try:
            # chat_id should be the Telegram chat ID (integer)
            chat_id = int(msg.chat_id)
            if is_progress_update:
                async with self._get_chat_send_lock(chat_id_str):
                    if self._should_skip_status_update(msg):
                        return
                    self._ensure_typing(chat_id_str)
                    status_text = ensure_utf8_text(msg.content or "").strip()
                    if not status_text:
                        return
                    active_message_ids = (
                        self._preview_message_ids if is_preview_update else self._status_message_ids
                    )
                    existing_status_id = active_message_ids.get(chat_id_str)
                    reply_to_message_id = (
                        int(str(msg.reply_to).strip())
                        if str(msg.reply_to or "").strip().isdigit()
                        else None
                    )
                    if existing_status_id:
                        try:
                            await self._app.bot.edit_message_text(
                                chat_id=chat_id,
                                message_id=existing_status_id,
                                text=status_text,
                            )
                            return
                        except Exception as exc:
                            if self._is_message_not_modified_error(exc):
                                # Keep existing mutable status bubble and avoid creating duplicates.
                                return
                            if self._is_transient_message_error(exc):
                                # Keep current status bubble and retry on next keepalive/status pulse.
                                return
                            if is_preview_update:
                                self._mark_stale_preview(chat_id_str, existing_status_id)
                            else:
                                self._mark_stale_status(chat_id_str, existing_status_id)
                            active_message_ids.pop(chat_id_str, None)
                    sent_status = await self._app.bot.send_message(
                        chat_id=chat_id,
                        text=status_text,
                        reply_to_message_id=reply_to_message_id,
                    )
                    if getattr(sent_status, "message_id", None):
                        active_message_ids[chat_id_str] = int(sent_status.message_id)
                    return

            # Clear stale status indicator when sending the final/non-progress response.
            async with self._get_chat_send_lock(chat_id_str):
                existing_status_id = self._status_message_ids.get(chat_id_str)
                if existing_status_id:
                    try:
                        await self._app.bot.delete_message(chat_id=chat_id, message_id=existing_status_id)
                        self._status_message_ids.pop(chat_id_str, None)
                    except Exception as exc:
                        if self._is_message_not_found_error(exc):
                            self._status_message_ids.pop(chat_id_str, None)
                        else:
                            # Do not keep stale mutable status as "current" after a failed delete.
                            # Track it for best-effort cleanup so old "processing" bubbles do not linger.
                            self._mark_stale_status(chat_id_str, existing_status_id)
                            self._status_message_ids.pop(chat_id_str, None)
                            logger.warning(f"Telegram status delete deferred for chat={chat_id_str}: {exc}")
                await self._cleanup_stale_status_messages(chat_id_str, chat_id)
            reply_markup = None
            if isinstance(msg.metadata, dict):
                inline_rows = msg.metadata.get("inline_keyboard")
                if isinstance(inline_rows, list):
                    reply_markup = build_inline_keyboard(inline_rows)
            reply_to_message_id = (
                int(str(msg.reply_to).strip())
                if str(msg.reply_to or "").strip().isdigit()
                else None
            )
            preview_message_id = self._preview_message_ids.get(chat_id_str)
            materialized_preview = False
            if preview_message_id and (msg.media or not (msg.content and msg.content.strip())):
                self._mark_stale_preview(chat_id_str, preview_message_id)
                self._preview_message_ids.pop(chat_id_str, None)
                preview_message_id = None

            # 1. Send text content if present (and not just a placeholder)
            if msg.content and msg.content.strip():
                safe_content = ensure_utf8_text(msg.content)
                chunks = _split_message(safe_content, max_length=4000)
                if preview_message_id and len(chunks) != 1:
                    self._mark_stale_preview(chat_id_str, preview_message_id)
                    self._preview_message_ids.pop(chat_id_str, None)
                    preview_message_id = None

                if preview_message_id and not msg.media and len(chunks) == 1:
                    chunk = ensure_utf8_text(chunks[0])
                    try:
                        html_content = _markdown_to_telegram_html(chunk)
                        await self._app.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=preview_message_id,
                            text=html_content,
                            parse_mode="HTML",
                            reply_markup=reply_markup,
                        )
                        materialized_preview = True
                    except Exception as exc:
                        if self._is_message_not_modified_error(exc):
                            materialized_preview = True
                        else:
                            try:
                                await self._app.bot.edit_message_text(
                                    chat_id=chat_id,
                                    message_id=preview_message_id,
                                    text=chunk,
                                    reply_markup=reply_markup,
                                )
                                materialized_preview = True
                            except Exception as fallback_exc:
                                if self._is_message_not_modified_error(fallback_exc):
                                    materialized_preview = True
                                else:
                                    self._mark_stale_preview(chat_id_str, preview_message_id)
                                    logger.warning(
                                        f"Telegram preview materialization failed for chat={chat_id_str}: {fallback_exc}"
                                    )
                    finally:
                        self._preview_message_ids.pop(chat_id_str, None)

                if not materialized_preview:
                    for i, chunk in enumerate(chunks):
                        chunk = ensure_utf8_text(chunk)
                        # Only attach reply_markup to the last chunk
                        chunk_markup = reply_markup if i == len(chunks) - 1 else None

                        try:
                            # Convert markdown to Telegram HTML
                            html_content = _markdown_to_telegram_html(chunk)
                            await self._app.bot.send_message(
                                chat_id=chat_id,
                                text=html_content,
                                parse_mode="HTML",
                                reply_markup=chunk_markup,
                                reply_to_message_id=reply_to_message_id,
                            )
                        except Exception as e:
                            logger.warning(f"HTML parse failed for chunk {i+1}/{len(chunks)}, falling back to plain text: {e}")
                            try:
                                await self._app.bot.send_message(
                                    chat_id=chat_id,
                                    text=chunk,
                                    reply_markup=chunk_markup,
                                    reply_to_message_id=reply_to_message_id,
                                )
                            except Exception as e2:
                                logger.error(f"Error sending Telegram chunk {i+1}/{len(chunks)}: {e2}")

            # 2. Send media files if present
            if msg.media:
                for file_path in msg.media:
                    try:
                        from pathlib import Path
                        path = Path(file_path)
                        if not path.exists():
                            logger.error(f"File to send not found: {file_path}")
                            await self._app.bot.send_message(
                                chat_id=chat_id,
                                text=f"⚠️ Error: File not found: {path.name}"
                            )
                            continue

                        # Send as document to preserve format
                        logger.info(f"Sending file {file_path} to {chat_id}...")
                        with open(file_path, 'rb') as f:
                            await self._app.bot.send_document(
                                chat_id=chat_id,
                                document=f,
                                filename=path.name,
                                reply_to_message_id=reply_to_message_id,
                            )
                    except Exception as e:
                        logger.error(f"Failed to send file {file_path}: {e}")
                        await self._app.bot.send_message(
                            chat_id=chat_id,
                            text=f"⚠️ Failed to send file {path.name}: {str(e)}"
                        )

            await self._cleanup_stale_preview_messages(chat_id_str, chat_id)

        except ValueError:
            logger.error(f"Invalid chat_id: {msg.chat_id}")
        except Exception as e:
            logger.error(f"Critical error in Telegram send routine: {e}")

    async def _on_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline button callback query events."""
        query = update.callback_query
        if not query or not query.from_user:
            return

        try:
            await query.answer()
        except Exception as e:
            logger.debug(f"Failed to acknowledge callback query: {e}")

        if query.message:
            chat_id = str(query.message.chat_id)
            message_id = query.message.message_id
            is_group = query.message.chat.type != "private"
        elif update.effective_chat:
            chat_id = str(update.effective_chat.id)
            message_id = None
            is_group = update.effective_chat.type != "private"
        else:
            return

        user = query.from_user
        sender_id = str(user.id)
        if user.username:
            sender_id = f"{sender_id}|{user.username}"
        self._chat_ids[sender_id] = int(chat_id)

        callback_data = (query.data or "").strip()
        content = callback_data or "[telegram_callback]"

        await self._handle_message(
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            metadata={
                "is_callback_query": True,
                "callback_data": callback_data,
                "callback_query_id": query.id,
                "message_id": message_id,
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "is_group": is_group,
            },
        )

    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not update.message or not update.effective_user:
            return

        user = update.effective_user
        bootstrap_path = self.workspace / "BOOTSTRAP.md" if isinstance(self.workspace, Path) else None
        if bootstrap_path and bootstrap_path.exists():
            chat_type = getattr(getattr(update.message, "chat", None), "type", "private")
            await self._handle_message(
                sender_id=str(user.id),
                chat_id=str(update.message.chat_id),
                content="/start",
                metadata={
                    "message_id": update.message.message_id,
                    "user_id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "is_group": chat_type != "private",
                },
            )
            return
        await update.message.reply_text(
            f"👋 Hi {user.first_name}! I'm kabot.\n\n"
            "Send me a message and I'll respond!\n"
            "Type /help to see available commands."
        )

    async def _on_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /reset command — clear conversation history."""
        if not update.message or not update.effective_user:
            return

        chat_id = str(update.message.chat_id)
        session_key = f"{self.name}:{chat_id}"

        if self.session_manager is None:
            logger.warning("/reset called but session_manager is not available")
            await update.message.reply_text("⚠️ Session management is not available.")
            return

        session = self.session_manager.get_or_create(session_key)
        msg_count = len(session.messages)
        session.clear()
        self.session_manager.save(session)

        logger.info(f"Session reset for {session_key} (cleared {msg_count} messages)")
        await update.message.reply_text("🔄 Conversation history cleared. Let's start fresh!")

    async def _on_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command — show available commands."""
        if not update.message:
            return

        # Build dynamic help text from all registered sources
        lines = ["🐺 <b>kabot commands</b>\n"]

        # 1. Built-in Telegram commands (always present)
        lines.append("/start — Start the bot")
        lines.append("/reset — Reset conversation history")
        lines.append("/help — Show this help message")
        command_specs = self._get_command_surface_specs()
        for spec in command_specs:
            if spec.source in {"static", "skill"}:
                continue
            admin_badge = " 🔒" if getattr(spec, "admin_only", False) else ""
            lines.append(f"/{spec.name} — {spec.description}{admin_badge}")

        skill_commands = [spec for spec in command_specs if spec.source == "skill"]
        if skill_commands:
            lines.append("\n<b>Skills</b>")
            for spec in skill_commands:
                lines.append(f"/{spec.name} — {spec.description}")

        lines.append("\nJust send me a text message to chat!")
        help_text = "\n".join(lines)
        await update.message.reply_text(help_text, parse_mode="HTML")

    async def _on_router_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle non-static slash commands via CommandRouter or workspace skill commands."""
        if not update.message or not update.effective_user:
            return

        message_text = str(update.message.text or "").strip()
        if not message_text.startswith("/"):
            return

        command_name = self._normalize_telegram_command_name(message_text)
        if command_name in {cmd.command for cmd in self.BOT_COMMANDS}:
            return

        user = update.effective_user
        sender_id = str(user.id)
        if user.username:
            sender_id = f"{sender_id}|{user.username}"
        chat_id = str(update.message.chat_id)
        self._chat_ids[sender_id] = update.message.chat_id

        if self.command_router and self.command_router.is_command(message_text):
            result = await self.command_router.route(
                message_text,
                CommandContext(
                    message=message_text,
                    args=[],
                    sender_id=sender_id,
                    channel=self.name,
                    chat_id=chat_id,
                    session_key=f"{self.name}:{chat_id}",
                    agent_loop=getattr(self, "agent_loop", None),
                ),
            )
            if result is not None:
                await update.message.reply_text(result)
                return

        skill_commands = {
            spec.name: spec
            for spec in self._get_skill_command_specs()
        }
        skill_spec = skill_commands.get(command_name)
        if skill_spec:
            parts = message_text.split(maxsplit=1)
            trailing = parts[1].strip() if len(parts) > 1 else ""
            skill_name = skill_spec.skill_name
            metadata = {
                "message_id": update.message.message_id,
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "is_group": update.message.chat.type != "private",
                "is_native_skill_command": True,
                "skill_name": skill_name,
                "original_command": message_text,
            }
            if skill_spec.command_dispatch == "tool" and skill_spec.command_tool:
                content = trailing
                metadata.update(
                    {
                        "skill_command_dispatch": "tool",
                        "skill_command_tool": skill_spec.command_tool,
                        "skill_command_name": skill_spec.name,
                        "skill_command_arg_mode": skill_spec.command_arg_mode or "raw",
                        "required_tool": skill_spec.command_tool,
                        "required_tool_query": trailing,
                        "suppress_required_tool_inference": True,
                    }
                )
            else:
                content = f"Please use the {skill_name} skill for this request."
                if trailing:
                    content = f"{content}\n\n{trailing}"
            await self._handle_message(
                sender_id=sender_id,
                chat_id=chat_id,
                content=content,
                metadata=metadata,
            )
            return

        await update.message.reply_text("Unknown command. Type /help to see available commands.")

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages (text, photos, voice, documents)."""
        if not update.message or not update.effective_user:
            return

        message = update.message
        user = update.effective_user
        chat_id = message.chat_id

        # Use stable numeric ID, but keep username for allowlist compatibility
        sender_id = str(user.id)
        if user.username:
            sender_id = f"{sender_id}|{user.username}"

        # Store chat_id for replies
        self._chat_ids[sender_id] = chat_id

        # Build content from text and/or media
        content_parts = []
        media_paths = []

        # Text content
        if message.text:
            content_parts.append(message.text)
        if message.caption:
            content_parts.append(message.caption)

        # Handle media files
        media_file = None
        media_type = None

        if message.photo:
            media_file = message.photo[-1]  # Largest photo
            media_type = "image"
        elif message.voice:
            media_file = message.voice
            media_type = "voice"
        elif message.audio:
            media_file = message.audio
            media_type = "audio"
        elif message.document:
            media_file = message.document
            media_type = "file"

        # Download media if present
        if media_file and self._app:
            try:
                file = await self._app.bot.get_file(media_file.file_id)
                ext = self._get_extension(media_type, getattr(media_file, 'mime_type', None))

                # Save to workspace/media/
                from pathlib import Path
                media_dir = Path.home() / ".kabot" / "media"
                media_dir.mkdir(parents=True, exist_ok=True)

                file_path = media_dir / f"{media_file.file_id[:16]}{ext}"
                await file.download_to_drive(str(file_path))

                media_paths.append(str(file_path))

                # Handle voice transcription
                if media_type == "voice" or media_type == "audio":
                    from kabot.providers.transcription import GroqTranscriptionProvider
                    transcriber = GroqTranscriptionProvider(api_key=self.groq_api_key)
                    transcription = await transcriber.transcribe(file_path)
                    if transcription:
                        logger.info(f"Transcribed {media_type}: {transcription[:50]}...")
                        content_parts.append(f"[transcription: {transcription}]")
                    else:
                        content_parts.append(f"[{media_type}: {file_path}]")
                else:
                    content_parts.append(f"[{media_type}: {file_path}]")

                logger.debug(f"Downloaded {media_type} to {file_path}")
            except Exception as e:
                logger.error(f"Failed to download media: {e}")
                content_parts.append(f"[{media_type}: download failed]")

        content = "\n".join(content_parts) if content_parts else "[empty message]"

        logger.debug(f"Telegram message from {sender_id}: {content[:50]}...")

        str_chat_id = str(chat_id)

        # Start typing indicator before processing
        self._start_typing(str_chat_id)

        # Forward to the message bus
        await self._handle_message(
            sender_id=sender_id,
            chat_id=str_chat_id,
            content=content,
            media=media_paths,
            metadata={
                "message_id": message.message_id,
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "is_group": message.chat.type != "private"
            }
        )

    def _start_typing(self, chat_id: str) -> None:
        """Start sending 'typing...' indicator for a chat."""
        # Cancel any existing typing task for this chat
        self._stop_typing(chat_id)
        self._typing_tasks[chat_id] = asyncio.create_task(self._typing_loop(chat_id))

    def _ensure_typing(self, chat_id: str) -> None:
        """Start typing loop only when one isn't already active."""
        task = self._typing_tasks.get(chat_id)
        if task and not task.done():
            return
        self._typing_tasks[chat_id] = asyncio.create_task(self._typing_loop(chat_id))

    def _stop_typing(self, chat_id: str) -> None:
        """Stop the typing indicator for a chat."""
        task = self._typing_tasks.pop(chat_id, None)
        if task and not task.done():
            task.cancel()

    async def _typing_loop(self, chat_id: str) -> None:
        """Repeatedly send 'typing' action until cancelled."""
        loop = asyncio.get_running_loop()
        started_at = loop.time()
        consecutive_failures = 0
        current_task = asyncio.current_task()
        try:
            while self._app:
                if (loop.time() - started_at) >= float(_TELEGRAM_TYPING_MAX_DURATION_SECONDS):
                    logger.debug(f"Typing indicator TTL reached for {chat_id}; stopping loop")
                    break
                try:
                    await self._app.bot.send_chat_action(chat_id=int(chat_id), action="typing")
                    consecutive_failures = 0
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    # Keepalive must survive transient transport errors.
                    consecutive_failures += 1
                    logger.debug(f"Typing indicator transient failure for {chat_id}: {e}")
                    if consecutive_failures >= int(_TELEGRAM_TYPING_MAX_CONSECUTIVE_FAILURES):
                        logger.warning(
                            "Typing indicator stopped after repeated failures "
                            f"for chat={chat_id} failures={consecutive_failures}"
                        )
                        break
                    await asyncio.sleep(float(_TELEGRAM_TYPING_RETRY_DELAY_SECONDS))
                    continue
                await asyncio.sleep(float(_TELEGRAM_TYPING_INTERVAL_SECONDS))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Typing indicator stopped for {chat_id}: {e}")
        finally:
            existing = self._typing_tasks.get(chat_id)
            if existing is current_task:
                self._typing_tasks.pop(chat_id, None)

    def _get_extension(self, media_type: str, mime_type: str | None) -> str:
        """Get file extension based on media type."""
        if mime_type:
            ext_map = {
                "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
                "audio/ogg": ".ogg", "audio/mpeg": ".mp3", "audio/mp4": ".m4a",
            }
            if mime_type in ext_map:
                return ext_map[mime_type]

        type_map = {"image": ".jpg", "voice": ".ogg", "audio": ".mp3", "file": ""}
        return type_map.get(media_type, "")
