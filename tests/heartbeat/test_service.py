import asyncio

import pytest

from kabot.heartbeat.service import HeartbeatService


@pytest.mark.asyncio
async def test_heartbeat_starts_and_stops():
    """Test that heartbeat service can start and stop."""
    beat_count = []

    async def on_beat():
        beat_count.append(1)

    service = HeartbeatService(interval_s=0.1, on_heartbeat=on_beat)
    await service.start()

    # Wait for at least 2 beats
    await asyncio.sleep(0.25)

    service.stop()

    assert len(beat_count) >= 2, "Should have at least 2 heartbeats"

@pytest.mark.asyncio
async def test_heartbeat_callback_error_handling():
    """Test that heartbeat continues even if callback raises error."""
    beat_count = []

    async def on_beat():
        beat_count.append(1)
        if len(beat_count) == 1:
            raise Exception("Test error")

    service = HeartbeatService(interval_s=0.1, on_heartbeat=on_beat)
    await service.start()

    # Wait for multiple beats
    await asyncio.sleep(0.25)

    service.stop()

    # Should continue after error
    assert len(beat_count) >= 2, "Should continue after callback error"

