import asyncio

import pytest

from kabot.heartbeat.service import HeartbeatService


@pytest.mark.asyncio
async def test_heartbeat_starts_and_stops():
    """Test that heartbeat service can start and stop."""
    beat_count = []

    async def on_beat():
        beat_count.append(1)

    service = HeartbeatService(interval_s=0.1, on_heartbeat=on_beat, startup_delay_s=0)
    await service.start()

    # Wait for at least 2 beats
    await asyncio.sleep(0.5)

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

    service = HeartbeatService(interval_s=0.1, on_heartbeat=on_beat, startup_delay_s=0)
    await service.start()

    # Wait for multiple beats
    await asyncio.sleep(0.5)

    service.stop()

    # Should continue after error
    assert len(beat_count) >= 2, "Should continue after callback error"


@pytest.mark.asyncio
async def test_heartbeat_autopilot_runs_when_no_active_tasks(tmp_path):
    """If HEARTBEAT.md has no tasks, autopilot prompt should still be dispatched."""
    payloads: list[str] = []

    async def on_beat(prompt: str):
        payloads.append(prompt)

    service = HeartbeatService(
        workspace=tmp_path,
        interval_s=0.1,
        on_heartbeat=on_beat,
        startup_delay_s=0,
        autopilot_enabled=True,
        autopilot_prompt="autopilot patrol",
    )
    await service.start()
    await asyncio.sleep(0.35)
    service.stop()

    assert payloads
    assert any("autopilot patrol" in p for p in payloads)


@pytest.mark.asyncio
async def test_heartbeat_autopilot_disabled_without_tasks(tmp_path):
    """When autopilot is disabled and no active tasks exist, no payload is dispatched."""
    payloads: list[str] = []

    async def on_beat(prompt: str):
        payloads.append(prompt)

    service = HeartbeatService(
        workspace=tmp_path,
        interval_s=0.1,
        on_heartbeat=on_beat,
        startup_delay_s=0,
        autopilot_enabled=False,
    )
    await service.start()
    await asyncio.sleep(0.35)
    service.stop()

    assert payloads == []


