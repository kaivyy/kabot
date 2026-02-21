"""Heartbeat service for periodic agent wake-ups."""

import asyncio
from typing import Callable, Coroutine, Any
from loguru import logger


def is_within_active_hours(start: str, end: str, *, test_hour: int | None = None) -> bool:
    """Return whether current time is inside active hours window."""
    if not start or not end:
        return True

    from datetime import datetime

    try:
        sh, sm = (int(x) for x in start.split(":", 1))
        eh, em = (int(x) for x in end.split(":", 1))
    except (TypeError, ValueError):
        return True

    now = datetime.now()
    if test_hour is None:
        now_min = now.hour * 60 + now.minute
    else:
        now_min = int(test_hour) * 60

    start_min = sh * 60 + sm
    end_min = eh * 60 + em

    if start_min <= end_min:
        return start_min <= now_min < end_min
    return now_min >= start_min or now_min < end_min


class HeartbeatService:
    def __init__(
        self,
        workspace: Any = None,
        interval_s: int = 60,
        on_heartbeat: Callable[[], Coroutine[Any, Any, None]] | None = None,
        enabled: bool = True,
        active_hours_start: str = "",
        active_hours_end: str = "",
    ):
        self.workspace = workspace
        self.interval_ms = interval_s * 1000
        self.on_beat = on_heartbeat
        self._enabled = enabled
        self.active_hours_start = active_hours_start
        self.active_hours_end = active_hours_end
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        if not self._enabled:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Heartbeat started (interval={self.interval_ms}ms)")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _loop(self):
        while self._running:
            if not is_within_active_hours(self.active_hours_start, self.active_hours_end):
                await asyncio.sleep(self.interval_ms / 1000)
                continue
            if self.on_beat:
                try:
                    # Pass a default prompt if on_beat expects arguments,
                    # while keeping zero-arg callbacks compatible.
                    if self.on_beat.__code__.co_argcount > 0:
                        await self.on_beat("Current time heartbeat check.")
                    else:
                        await self.on_beat()
                except Exception as e:
                    logger.error(f"Heartbeat callback error: {e}")
            await asyncio.sleep(self.interval_ms / 1000)
