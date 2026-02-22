"""
Slash Command Router for Kabot.

Intercepts messages starting with `/` before they reach the LLM.
Dispatches to registered command handlers and returns immediate responses.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class CommandContext:
    """Context passed to every command handler."""
    message: str           # Full original message
    args: list[str]        # Parsed arguments after the command name
    sender_id: str         # Who sent the command
    channel: str           # Channel (cli, whatsapp, telegram, etc.)
    chat_id: str           # Chat/conversation ID
    session_key: str       # Session key
    agent_loop: Any = None # Reference to AgentLoop (for advanced commands)


@dataclass
class CommandRegistration:
    """Internal registration record for a command."""
    name: str
    handler: Callable[[CommandContext], Awaitable[str]]
    description: str
    admin_only: bool = False


class CommandRouter:
    """
    Routes `/command arg1 arg2` messages to registered handlers.

    Usage:
        router = CommandRouter()
        router.register("/status", status_handler, "Show system status")
        result = await router.route("/status", ctx)
    """

    def __init__(self):
        self._commands: dict[str, CommandRegistration] = {}
        self._start_time = time.time()

    def register(
        self,
        name: str,
        handler: Callable[[CommandContext], Awaitable[str]],
        description: str = "",
        admin_only: bool = False,
    ) -> None:
        """Register a slash command handler."""
        normalized = name.lower().strip()
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        self._commands[normalized] = CommandRegistration(
            name=normalized,
            handler=handler,
            description=description,
            admin_only=admin_only,
        )
        logger.debug(f"Registered command: {normalized}")

    def is_command(self, message: str) -> bool:
        """Check if a message is a registered slash command."""
        if not message or not message.strip().startswith("/"):
            return False
        parts = message.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        return cmd in self._commands

    async def route(self, message: str, context: CommandContext) -> Optional[str]:
        """
        Route a slash command to its handler.

        Returns:
            Response string if command was handled, None if not a command.
        """
        if not message or not message.strip().startswith("/"):
            return None

        parts = message.strip().split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd not in self._commands:
            return None

        registration = self._commands[cmd]
        context.args = args

        try:
            logger.info(f"Executing command: {cmd} (args={args})")
            result = await registration.handler(context)
            return result
        except Exception as e:
            logger.error(f"Command {cmd} failed: {e}", exc_info=True)
            return f"❌ Command `{cmd}` failed: {str(e)}"

    def get_help_text(self) -> str:
        """Generate help text listing all registered commands."""
        if not self._commands:
            return "No commands registered."

        lines = ["🤖 *Available Commands:*\n"]
        for name, reg in sorted(self._commands.items()):
            admin_badge = " 🔒" if reg.admin_only else ""
            lines.append(f"  `{name}` — {reg.description}{admin_badge}")
        return "\n".join(lines)

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._start_time
