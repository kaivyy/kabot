"""Tests for inbound queue debounce/cap/drop policy."""

from types import SimpleNamespace

import pytest

from kabot.bus.events import InboundMessage
from kabot.bus.queue import MessageBus


def _queue_cfg(
    *,
    enabled: bool = True,
    mode: str = "debounce",
    debounce_window_ms: int = 1200,
    max_pending_per_session: int = 4,
    drop_policy: str = "drop_oldest",
    summarize_dropped: bool = True,
):
    return SimpleNamespace(
        enabled=enabled,
        mode=mode,
        debounce_window_ms=debounce_window_ms,
        max_pending_per_session=max_pending_per_session,
        drop_policy=drop_policy,
        summarize_dropped=summarize_dropped,
    )


@pytest.mark.asyncio
async def test_inbound_queue_debounce_keeps_latest_message():
    bus = MessageBus()
    bus.configure_inbound_queue(_queue_cfg(debounce_window_ms=30_000))

    await bus.publish_inbound(
        InboundMessage(channel="telegram", sender_id="u1", chat_id="c1", content="first")
    )
    await bus.publish_inbound(
        InboundMessage(channel="telegram", sender_id="u1", chat_id="c1", content="second")
    )

    msg = await bus.consume_inbound()
    assert msg.content == "second"
    queue_meta = msg.metadata.get("queue", {})
    assert queue_meta.get("dropped_count") == 1


@pytest.mark.asyncio
async def test_inbound_queue_cap_drop_newest_preserves_oldest():
    bus = MessageBus()
    bus.configure_inbound_queue(
        _queue_cfg(
            debounce_window_ms=0,
            max_pending_per_session=1,
            drop_policy="drop_newest",
        )
    )

    await bus.publish_inbound(
        InboundMessage(channel="telegram", sender_id="u1", chat_id="c1", content="first")
    )
    await bus.publish_inbound(
        InboundMessage(channel="telegram", sender_id="u1", chat_id="c1", content="second")
    )

    msg = await bus.consume_inbound()
    assert msg.content == "first"
    queue_meta = msg.metadata.get("queue", {})
    assert queue_meta.get("dropped_count") == 1
    assert "second" in " ".join(queue_meta.get("dropped_preview", []))


@pytest.mark.asyncio
async def test_inbound_queue_policy_bypasses_system_messages():
    bus = MessageBus()
    bus.configure_inbound_queue(_queue_cfg(debounce_window_ms=30_000))

    await bus.publish_inbound(
        InboundMessage(channel="system", sender_id="system", chat_id="c1", content="one")
    )
    await bus.publish_inbound(
        InboundMessage(channel="system", sender_id="system", chat_id="c1", content="two")
    )

    first = await bus.consume_inbound()
    second = await bus.consume_inbound()
    assert first.content == "one"
    assert second.content == "two"
