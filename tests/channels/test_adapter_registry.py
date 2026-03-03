from unittest.mock import patch

from kabot.bus.queue import MessageBus
from kabot.channels.adapters import AdapterRegistry
from kabot.channels.manager import ChannelManager
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


def test_channel_manager_passes_adapter_feature_flags_from_config(monkeypatch):
    config = Config()
    config.channels.adapters = {"irc": True, "matrix": False}
    bus = MessageBus()
    captured: dict[str, dict] = {}

    def _fake_registry(feature_flags=None):  # noqa: ANN001
        captured["flags"] = dict(feature_flags or {})
        return AdapterRegistry(feature_flags=feature_flags)

    monkeypatch.setattr("kabot.channels.manager.AdapterRegistry", _fake_registry)
    ChannelManager(config=config, bus=bus, session_manager=None)

    assert captured["flags"] == {"irc": True, "matrix": False}


def test_adapter_registry_allows_disabling_production_adapter_via_flag():
    registry = AdapterRegistry(feature_flags={"telegram": False})
    statuses = {s.key: s for s in registry.list_status()}

    assert statuses["telegram"].enabled is False


def test_adapter_registry_allows_enabling_experimental_adapter_via_flag():
    registry = AdapterRegistry(feature_flags={"irc": True})
    statuses = {s.key: s for s in registry.list_status()}

    assert statuses["irc"].experimental is True
    assert statuses["irc"].enabled is True


def test_adapter_registry_does_not_init_legacy_channel_when_production_flag_disabled():
    config = Config()
    config.channels.telegram.enabled = True
    config.channels.telegram.token = "123:ABC"
    bus = MessageBus()

    registry = AdapterRegistry(feature_flags={"telegram": False})
    with patch("kabot.channels.telegram.TelegramChannel") as mock_channel:
        channel = registry.create_legacy_channel("telegram", config=config, bus=bus, session_manager=None)

    assert channel is None
    assert mock_channel.call_count == 0


def test_adapter_registry_promotes_signal_matrix_teams_without_placeholder_description():
    registry = AdapterRegistry()
    statuses = {s.key: s for s in registry.list_status()}

    for key in ("signal", "matrix", "teams"):
        assert statuses[key].production is True
        assert statuses[key].experimental is False
        assert "(planned)" not in statuses[key].description


def test_adapter_registry_creates_signal_instance_channel():
    config = Config()
    bus = MessageBus()
    registry = AdapterRegistry()

    instance = ChannelInstance(
        id="signal-ops",
        type="signal",
        enabled=True,
        config={"bridge_url": "ws://localhost:3011", "allow_from": []},
    )

    with patch("kabot.channels.signal.SignalChannel") as mock_channel:
        channel = registry.create_instance_channel(instance, config=config, bus=bus, session_manager=None)

    assert channel is not None
    assert mock_channel.call_count == 1


def test_adapter_registry_promotes_googlechat_mattermost_webex_line():
    registry = AdapterRegistry()
    statuses = {s.key: s for s in registry.list_status()}

    for key in ("google_chat", "mattermost", "webex", "line"):
        assert statuses[key].production is True
        assert statuses[key].experimental is False
        assert "(planned)" not in statuses[key].description


def test_adapter_registry_creates_googlechat_instance_channel():
    config = Config()
    bus = MessageBus()
    registry = AdapterRegistry()

    instance = ChannelInstance(
        id="gchat-ops",
        type="google_chat",
        enabled=True,
        config={"bridge_url": "ws://localhost:3014", "allow_from": []},
    )

    with patch("kabot.channels.google_chat.GoogleChatChannel") as mock_channel:
        channel = registry.create_instance_channel(instance, config=config, bus=bus, session_manager=None)

    assert channel is not None
    assert mock_channel.call_count == 1
