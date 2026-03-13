"""Test Telegram command registration."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram import BotCommand

from kabot.bus.queue import MessageBus
from kabot.channels.adapters import AdapterRegistry
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


def test_adapter_registry_injects_command_router_into_telegram_channel(tmp_path):
    config = SimpleNamespace(
        channels=SimpleNamespace(telegram=TelegramConfig(token="test_token", enabled=True)),
        providers=SimpleNamespace(groq=SimpleNamespace(api_key="")),
        agents=SimpleNamespace(defaults=SimpleNamespace(workspace=Path(tmp_path))),
    )
    bus = MessageBus()
    router = CommandRouter()
    registry = AdapterRegistry()

    channel = registry.create_legacy_channel(
        "telegram",
        config=config,
        bus=bus,
        session_manager=None,
        command_router=router,
    )

    assert isinstance(channel, TelegramChannel)
    assert channel.command_router is router


@pytest.mark.asyncio
async def test_telegram_routes_registered_router_command_via_generic_handler():
    config = TelegramConfig(token="test_token", enabled=True)
    bus = MessageBus()
    router = CommandRouter()

    async def dummy_handler(ctx):
        assert ctx.message == "/status"
        assert ctx.chat_id == "123456"
        return "Status OK"

    router.register("/status", dummy_handler, "Show status")
    channel = TelegramChannel(config, bus, command_router=router)

    reply_text = AsyncMock()
    update = SimpleNamespace(
        message=SimpleNamespace(
            text="/status",
            chat_id=123456,
            chat=SimpleNamespace(type="private"),
            reply_text=reply_text,
        ),
        effective_user=SimpleNamespace(
            id=777,
            username="maharaja",
            first_name="Maha Raja",
        ),
    )

    await channel._on_router_command(update, None)

    reply_text.assert_awaited_once_with("Status OK")


def test_telegram_includes_workspace_skill_commands_in_menu(tmp_path):
    config = TelegramConfig(token="test_token", enabled=True)
    bus = MessageBus()
    router = CommandRouter()
    workspace = tmp_path / "workspace"
    skill_dir = workspace / "skills" / "cek-runtime-vps"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: cek-runtime-vps\ndescription: Check VPS runtime quickly\n---\n\n# Skill\n",
        encoding="utf-8",
    )

    channel = TelegramChannel(config, bus, command_router=router, workspace=workspace)
    commands = channel.get_bot_commands_from_router(router)

    assert "cek_runtime_vps" in [cmd.command for cmd in commands]


@pytest.mark.asyncio
async def test_telegram_routes_workspace_skill_command_via_generic_handler(tmp_path):
    config = TelegramConfig(token="test_token", enabled=True)
    bus = MessageBus()
    workspace = tmp_path / "workspace"
    skill_dir = workspace / "skills" / "cek-runtime-vps"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: cek-runtime-vps\ndescription: Check VPS runtime quickly\n---\n\n# Skill\n",
        encoding="utf-8",
    )

    channel = TelegramChannel(config, bus, workspace=workspace)
    channel._handle_message = AsyncMock()
    update = SimpleNamespace(
        message=SimpleNamespace(
            text="/cek_runtime_vps cpu tinggi sekarang",
            message_id=88,
            chat_id=123456,
            chat=SimpleNamespace(type="private"),
            reply_text=AsyncMock(),
        ),
        effective_user=SimpleNamespace(
            id=777,
            username="maharaja",
            first_name="Maha Raja",
        ),
    )

    await channel._on_router_command(update, None)

    channel._handle_message.assert_awaited_once()
    kwargs = channel._handle_message.await_args.kwargs
    assert kwargs["sender_id"] == "777|maharaja"
    assert kwargs["chat_id"] == "123456"
    assert kwargs["content"] == (
        "Please use the cek-runtime-vps skill for this request.\n\ncpu tinggi sekarang"
    )


@pytest.mark.asyncio
async def test_telegram_routes_workspace_skill_command_with_tool_dispatch_metadata(tmp_path):
    config = TelegramConfig(token="test_token", enabled=True)
    bus = MessageBus()
    workspace = tmp_path / "workspace"
    skill_dir = workspace / "skills" / "meta-threads-official"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        (
            "---\n"
            "name: meta-threads-official\n"
            "description: Use Meta Threads integration\n"
            "user-invocable: true\n"
            "command-dispatch: tool\n"
            "command-tool: meta_threads_post\n"
            "---\n\n"
            "# Skill\n"
        ),
        encoding="utf-8",
    )

    channel = TelegramChannel(config, bus, workspace=workspace)
    channel._handle_message = AsyncMock()
    update = SimpleNamespace(
        message=SimpleNamespace(
            text="/meta_threads_official halo dari slash",
            message_id=89,
            chat_id=123456,
            chat=SimpleNamespace(type="private"),
            reply_text=AsyncMock(),
        ),
        effective_user=SimpleNamespace(
            id=777,
            username="maharaja",
            first_name="Maha Raja",
        ),
    )

    await channel._on_router_command(update, None)

    channel._handle_message.assert_awaited_once()
    kwargs = channel._handle_message.await_args.kwargs
    assert kwargs["content"] == "halo dari slash"
    metadata = kwargs["metadata"]
    assert metadata["skill_name"] == "meta-threads-official"
    assert metadata["skill_command_dispatch"] == "tool"
    assert metadata["skill_command_tool"] == "meta_threads_post"
    assert metadata["required_tool"] == "meta_threads_post"
    assert metadata["required_tool_query"] == "halo dari slash"
    assert metadata["suppress_required_tool_inference"] is True
    assert metadata["is_native_skill_command"] is True


def test_telegram_menu_includes_workspace_skills_even_without_router(tmp_path):
    config = TelegramConfig(token="test_token", enabled=True)
    bus = MessageBus()
    workspace = tmp_path / "workspace"
    skill_dir = workspace / "skills" / "meta-threads-official"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: meta-threads-official\ndescription: Use Meta Threads integration\n---\n\n# Skill\n",
        encoding="utf-8",
    )

    channel = TelegramChannel(config, bus, workspace=workspace)
    commands = channel.get_bot_commands_from_router(None)

    assert "meta_threads_official" in [cmd.command for cmd in commands]


def test_telegram_normalizes_router_command_names_for_menu():
    config = TelegramConfig(token="test_token", enabled=True)
    bus = MessageBus()
    router = CommandRouter()

    async def dummy_handler(ctx):
        return "ok"

    router.register("/system-info", dummy_handler, "System info")
    router.register("/status", dummy_handler, "Show status")
    channel = TelegramChannel(config, bus, command_router=router)

    commands = channel.get_bot_commands_from_router(router)
    command_names = [cmd.command for cmd in commands]

    assert "system_info" in command_names
    assert "status" in command_names


@pytest.mark.asyncio
async def test_telegram_help_groups_router_and_skill_commands_without_duplicate_skill_entries(tmp_path):
    config = TelegramConfig(token="test_token", enabled=True)
    bus = MessageBus()
    router = CommandRouter()
    workspace = tmp_path / "workspace"
    skill_dir = workspace / "skills" / "meta-threads-official"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: meta-threads-official\ndescription: Use Meta Threads integration\n---\n\n# Skill\n",
        encoding="utf-8",
    )

    async def dummy_handler(ctx):
        return "ok"

    router.register("/update", dummy_handler, "Update bot", admin_only=True)
    channel = TelegramChannel(config, bus, command_router=router, workspace=workspace)
    update = SimpleNamespace(
        message=SimpleNamespace(
            reply_text=AsyncMock(),
        ),
    )

    await channel._on_help(update, None)

    help_text = update.message.reply_text.await_args.args[0]
    assert "/update — Update bot 🔒" in help_text
    assert "<b>Skills</b>" in help_text
    assert help_text.count("/meta_threads_official — Use Meta Threads integration") == 1


@pytest.mark.asyncio
async def test_telegram_sync_bot_commands_skips_when_hash_is_unchanged(tmp_path, monkeypatch):
    config = TelegramConfig(token="test_token", enabled=True)
    bus = MessageBus()
    channel = TelegramChannel(config, bus)
    monkeypatch.setattr("kabot.channels.telegram.get_data_path", lambda: tmp_path / ".kabot")

    bot = SimpleNamespace(
        delete_my_commands=AsyncMock(),
        set_my_commands=AsyncMock(),
    )
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("status", "Show status"),
    ]

    await channel._sync_bot_commands(bot, commands, bot_identity="kanca_bot")
    await channel._sync_bot_commands(bot, commands, bot_identity="kanca_bot")

    bot.delete_my_commands.assert_awaited_once()
    bot.set_my_commands.assert_awaited_once_with(commands)


@pytest.mark.asyncio
async def test_telegram_sync_bot_commands_retries_with_smaller_payload_on_overflow(tmp_path, monkeypatch):
    config = TelegramConfig(token="test_token", enabled=True)
    bus = MessageBus()
    channel = TelegramChannel(config, bus)
    monkeypatch.setattr("kabot.channels.telegram.get_data_path", lambda: tmp_path / ".kabot")

    async def set_my_commands(commands):
        if len(commands) == 5:
            raise RuntimeError("BOT_COMMANDS_TOO_MUCH")
        return None

    bot = SimpleNamespace(
        delete_my_commands=AsyncMock(),
        set_my_commands=AsyncMock(side_effect=set_my_commands),
    )
    commands = [BotCommand(f"cmd{i}", f"Command {i}") for i in range(5)]

    await channel._sync_bot_commands(bot, commands, bot_identity="kanca_bot")

    assert bot.set_my_commands.await_count == 2
    first_call_commands = bot.set_my_commands.await_args_list[0].args[0]
    second_call_commands = bot.set_my_commands.await_args_list[1].args[0]
    assert len(first_call_commands) == 5
    assert len(second_call_commands) == 4
