"""Test multi-instance channel manager."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from kabot.config.schema import Config, ChannelsConfig, ChannelInstance
from kabot.channels.manager import ChannelManager
from kabot.bus.queue import MessageBus


@pytest.mark.asyncio
async def test_channel_manager_multiple_telegram_instances():
    """Test ChannelManager with multiple Telegram instances."""
    config = Config()
    config.channels = ChannelsConfig(
        instances=[
            ChannelInstance(
                id="work_bot",
                type="telegram",
                enabled=True,
                config={"token": "123:ABC", "allow_from": []}
            ),
            ChannelInstance(
                id="personal_bot",
                type="telegram",
                enabled=True,
                config={"token": "456:DEF", "allow_from": []}
            )
        ]
    )

    bus = MessageBus()

    with patch('kabot.channels.telegram.TelegramChannel') as MockTelegram:
        manager = ChannelManager(config, bus)

        # Should have 2 telegram instances
        assert "telegram:work_bot" in manager.channels
        assert "telegram:personal_bot" in manager.channels
        assert len(manager.channels) == 2

        # Verify TelegramChannel was instantiated twice
        assert MockTelegram.call_count == 2


@pytest.mark.asyncio
async def test_channel_manager_mixed_instances():
    """Test ChannelManager with multiple channel types."""
    config = Config()
    config.channels = ChannelsConfig(
        instances=[
            ChannelInstance(
                id="work_tele",
                type="telegram",
                enabled=True,
                config={"token": "123:ABC", "allow_from": []}
            ),
            ChannelInstance(
                id="work_discord",
                type="discord",
                enabled=True,
                config={"token": "XYZ", "allow_from": []}
            )
        ]
    )

    bus = MessageBus()

    with patch('kabot.channels.telegram.TelegramChannel'), \
         patch('kabot.channels.discord.DiscordChannel'):
        manager = ChannelManager(config, bus)

        # Should have both instances
        assert "telegram:work_tele" in manager.channels
        assert "discord:work_discord" in manager.channels
        assert len(manager.channels) == 2


@pytest.mark.asyncio
async def test_channel_manager_disabled_instance():
    """Test that disabled instances are not initialized."""
    config = Config()
    config.channels = ChannelsConfig(
        instances=[
            ChannelInstance(
                id="enabled_bot",
                type="telegram",
                enabled=True,
                config={"token": "123:ABC", "allow_from": []}
            ),
            ChannelInstance(
                id="disabled_bot",
                type="telegram",
                enabled=False,
                config={"token": "456:DEF", "allow_from": []}
            )
        ]
    )

    bus = MessageBus()

    with patch('kabot.channels.telegram.TelegramChannel') as MockTelegram:
        manager = ChannelManager(config, bus)

        # Should only have enabled instance
        assert "telegram:enabled_bot" in manager.channels
        assert "telegram:disabled_bot" not in manager.channels
        assert len(manager.channels) == 1
        assert MockTelegram.call_count == 1


@pytest.mark.asyncio
async def test_channel_manager_backward_compatibility():
    """Test that legacy single-instance configs still work."""
    config = Config()
    # Enable legacy telegram config
    config.channels.telegram.enabled = True
    config.channels.telegram.token = "legacy:TOKEN"

    bus = MessageBus()

    with patch('kabot.channels.telegram.TelegramChannel') as MockTelegram:
        manager = ChannelManager(config, bus)

        # Should have legacy telegram channel
        assert "telegram" in manager.channels
        assert MockTelegram.call_count == 1


@pytest.mark.asyncio
async def test_channel_manager_instances_and_legacy():
    """Test that instances and legacy configs can coexist."""
    config = Config()

    # Add instance
    config.channels.instances = [
        ChannelInstance(
            id="new_bot",
            type="discord",
            enabled=True,
            config={"token": "NEW:TOKEN", "allow_from": []}
        )
    ]

    # Enable legacy telegram
    config.channels.telegram.enabled = True
    config.channels.telegram.token = "legacy:TOKEN"

    bus = MessageBus()

    with patch('kabot.channels.telegram.TelegramChannel'), \
         patch('kabot.channels.discord.DiscordChannel'):
        manager = ChannelManager(config, bus)

        # Should have both
        assert "discord:new_bot" in manager.channels
        assert "telegram" in manager.channels
        assert len(manager.channels) == 2
