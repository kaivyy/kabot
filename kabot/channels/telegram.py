"""Telegram channel implementation using python-telegram-bot."""

from __future__ import annotations

import asyncio
import re
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
from kabot.utils.text_safety import ensure_utf8_text

if TYPE_CHECKING:
    from kabot.session.manager import SessionManager

_TELEGRAM_TYPING_INTERVAL_SECONDS = 4.0
_TELEGRAM_TYPING_RETRY_DELAY_SECONDS = 2.0
_TELEGRAM_TYPING_MAX_DURATION_SECONDS = 120.0
_TELEGRAM_TYPING_MAX_CONSECUTIVE_FAILURES = 6


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
    ):
        super().__init__(config, bus)
        self.config: TelegramConfig = config
        self.groq_api_key = groq_api_key
        self.session_manager = session_manager
        self.command_router = command_router
        self._app: Application | None = None
        self._chat_ids: dict[str, int] = {}  # Map sender_id to chat_id for replies
        self._typing_tasks: dict[str, asyncio.Task] = {}  # chat_id -> typing loop task
        # Keep one mutable status message per chat for phase updates.
        self._status_message_ids: dict[str, int] = {}
        # Track stale status bubbles that should be cleaned before final reply.
        self._stale_status_message_ids: dict[str, set[int]] = {}
        self._polling_conflict_handled: bool = False

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
        commands = []

        # Always include static commands
        commands.extend(self.BOT_COMMANDS)

        # Add commands from router if available
        if router and hasattr(router, '_commands'):
            for cmd_name, registration in router._commands.items():
                # Remove leading slash for Telegram API
                cmd_name_clean = cmd_name.lstrip('/')

                # Skip if already in static commands
                if any(cmd.command == cmd_name_clean for cmd in self.BOT_COMMANDS):
                    continue

                # Add command with description
                commands.append(BotCommand(cmd_name_clean, registration.description))

        return commands

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
            # Get commands from router if available, otherwise use static commands
            commands_to_register = (
                self.get_bot_commands_from_router(self.command_router)
                if self.command_router
                else self.BOT_COMMANDS
            )
            await self._app.bot.set_my_commands(commands_to_register)
            logger.debug(f"Telegram bot commands registered: {len(commands_to_register)} commands")
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

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Telegram."""
        if not self._app:
            logger.warning("Telegram bot not running")
            return

        chat_id_str = str(msg.chat_id)
        is_progress_update, _phase, _status_text = self._status_update_payload(msg)

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
                    existing_status_id = self._status_message_ids.get(chat_id_str)
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
                            self._mark_stale_status(chat_id_str, existing_status_id)
                            self._status_message_ids.pop(chat_id_str, None)
                    sent_status = await self._app.bot.send_message(chat_id=chat_id, text=status_text)
                    if getattr(sent_status, "message_id", None):
                        self._status_message_ids[chat_id_str] = int(sent_status.message_id)
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

            # 1. Send text content if present (and not just a placeholder)
            if msg.content and msg.content.strip():
                safe_content = ensure_utf8_text(msg.content)
                chunks = _split_message(safe_content, max_length=4000)

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
                        )
                    except Exception as e:
                        logger.warning(f"HTML parse failed for chunk {i+1}/{len(chunks)}, falling back to plain text: {e}")
                        try:
                            await self._app.bot.send_message(
                                chat_id=chat_id,
                                text=chunk,
                                reply_markup=chunk_markup,
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
                                filename=path.name
                            )
                    except Exception as e:
                        logger.error(f"Failed to send file {file_path}: {e}")
                        await self._app.bot.send_message(
                            chat_id=chat_id,
                            text=f"⚠️ Failed to send file {path.name}: {str(e)}"
                        )

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

        # 2. Dynamic commands from CommandRouter
        if self.command_router and hasattr(self.command_router, '_commands'):
            for cmd_name, reg in sorted(self.command_router._commands.items()):
                cmd_clean = cmd_name.lstrip('/')
                # Skip if already listed above
                if cmd_clean in ("start", "reset", "help"):
                    continue
                admin_badge = " 🔒" if reg.admin_only else ""
                lines.append(f"/{cmd_clean} — {reg.description}{admin_badge}")

        lines.append("\nJust send me a text message to chat!")
        help_text = "\n".join(lines)
        await update.message.reply_text(help_text, parse_mode="HTML")

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
