from unittest.mock import patch

from kabot.bus.queue import MessageBus
from kabot.channels.adapters import AdapterRegistry
from kabot.config.schema import ChannelInstance, Config


def test_adapter_registry_flags_production_and_experimental():
    registry = AdapterRegistry()
    statuses = {s.key: s for s in registry.list_status()}

    assert statuses["telegram"].production is True
    assert statuses["telegram"].experimental is False
    assert statuses["irc"].experimental is True
    assert statuses["irc"].enabled is False


def test_adapter_registry_creates_legacy_telegram_channel_when_enabled():
    config = Config()
    config.channels.telegram.enabled = True
    config.channels.telegram.token = "123:ABC"
    bus = MessageBus()

    registry = AdapterRegistry()
    with patch("kabot.channels.telegram.TelegramChannel") as mock_channel:
        channel = registry.create_legacy_channel("telegram", config=config, bus=bus, session_manager=None)

    assert channel is not None
    assert mock_channel.call_count == 1


def test_adapter_registry_handles_unknown_instance_type():
    config = Config()
    bus = MessageBus()
    registry = AdapterRegistry()

    instance = ChannelInstance(
        id="unknown-1",
        type="unknown-type",
        enabled=True,
        config={},
    )

    channel = registry.create_instance_channel(instance, config=config, bus=bus, session_manager=None)
    assert channel is None
