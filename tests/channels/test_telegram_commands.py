"""Test Telegram command registration."""

import pytest
from telegram import BotCommand

from kabot.bus.queue import MessageBus
from kabot.channels.telegram import TelegramChannel
from kabot.config.schema import TelegramConfig
from kabot.core.command_router import CommandRouter


@pytest.mark.asyncio
async def test_telegram_registers_all_system_commands():
    """Verify that Telegram registers all system commands with bot API."""
    # Setup
    config = TelegramConfig(token="test_token", enabled=True)
    bus = MessageBus()
    channel = TelegramChannel(config, bus)

    # Create a mock router with system commands
    router = CommandRouter()

    async def dummy_handler(ctx):
        return "OK"

    router.register("/help", dummy_handler, "Show help")
    router.register("/status", dummy_handler, "Show status")
    router.register("/switch", dummy_handler, "Switch model")
    router.register("/doctor", dummy_handler, "Run diagnostics")
    router.register("/update", dummy_handler, "Update bot")
    router.register("/restart", dummy_handler, "Restart bot")
    router.register("/sysinfo", dummy_handler, "System info")
    router.register("/clip", dummy_handler, "Copy to clipboard")
    router.register("/uptime", dummy_handler, "Show uptime")
    router.register("/benchmark", dummy_handler, "Run benchmark")

    # Get commands that should be registered
    expected_commands = channel.get_bot_commands_from_router(router)

    # Verify all system commands are included
    command_names = [cmd.command for cmd in expected_commands]

    assert "start" in command_names
    assert "reset" in command_names
    assert "help" in command_names
    assert "status" in command_names
    assert "switch" in command_names
    assert "doctor" in command_names
    assert "update" in command_names
    assert "restart" in command_names
    assert "sysinfo" in command_names
    assert "clip" in command_names
    assert "uptime" in command_names
    assert "benchmark" in command_names

    # Verify command format
    for cmd in expected_commands:
        assert isinstance(cmd, BotCommand)
        assert cmd.command  # Has command name
        assert cmd.description  # Has description


def test_telegram_static_commands_still_present():
    """Verify that static commands (start, reset, help) are still defined."""
    # These are the basic commands that should always be present
    assert len(TelegramChannel.BOT_COMMANDS) == 3

    command_names = [cmd.command for cmd in TelegramChannel.BOT_COMMANDS]
    assert "start" in command_names
    assert "reset" in command_names
    assert "help" in command_names
