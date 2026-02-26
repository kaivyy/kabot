from kabot.bus.queue import MessageBus
from kabot.channels.whatsapp import WhatsAppChannel
from kabot.config.schema import WhatsAppConfig


def _channel(bridge_url: str = "ws://localhost:3001") -> WhatsAppChannel:
    return WhatsAppChannel(
        WhatsAppConfig(enabled=True, bridge_url=bridge_url, allow_from=[]),
        MessageBus(),
    )


def test_ensure_bridge_ready_starts_background_bridge_when_local_unreachable(monkeypatch):
    channel = _channel("ws://localhost:3001")

    monkeypatch.setattr("kabot.channels.whatsapp.is_local_bridge_url", lambda _url: True)
    monkeypatch.setattr("kabot.channels.whatsapp.is_bridge_reachable", lambda _url: False)
    monkeypatch.setattr("kabot.channels.whatsapp.time.monotonic", lambda: 100.0)

    calls = {"start": 0}
    monkeypatch.setattr(
        "kabot.channels.whatsapp.start_bridge_background",
        lambda *args, **kwargs: calls.__setitem__("start", calls["start"] + 1) or True,
    )

    channel._ensure_bridge_ready()
    channel._ensure_bridge_ready()

    assert calls["start"] == 1


def test_ensure_bridge_ready_skips_non_local_bridge_urls(monkeypatch):
    channel = _channel("wss://bridge.example.com:443")

    monkeypatch.setattr("kabot.channels.whatsapp.is_local_bridge_url", lambda _url: False)
    calls = {"start": 0}
    monkeypatch.setattr(
        "kabot.channels.whatsapp.start_bridge_background",
        lambda *args, **kwargs: calls.__setitem__("start", calls["start"] + 1) or True,
    )

    channel._ensure_bridge_ready()

    assert calls["start"] == 0
