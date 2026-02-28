from kabot.bus.queue import MessageBus
from kabot.channels.base import BaseChannel


class _DummyChannel(BaseChannel):
    name = "dummy"

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def send(self, msg) -> None:
        return None


def test_allow_from_empty_is_open_in_balanced_mode():
    cfg = type("Cfg", (), {"allow_from": []})()
    ch = _DummyChannel(cfg, MessageBus())
    setattr(ch, "_security_policy_preset", "balanced")
    assert ch.is_allowed("user-1") is True


def test_allow_from_empty_is_fail_closed_in_strict_mode():
    cfg = type("Cfg", (), {"allow_from": []})()
    ch = _DummyChannel(cfg, MessageBus())
    setattr(ch, "_security_policy_preset", "strict")
    assert ch.is_allowed("user-1") is False


def test_allow_from_list_still_works_in_strict_mode():
    cfg = type("Cfg", (), {"allow_from": ["user-1"]})()
    ch = _DummyChannel(cfg, MessageBus())
    setattr(ch, "_security_policy_preset", "strict")
    assert ch.is_allowed("user-1") is True
    assert ch.is_allowed("user-2") is False
