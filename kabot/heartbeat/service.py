"""Heartbeat service for periodic agent wake-ups."""

import asyncio
from typing import Callable, Coroutine, Any
from loguru import logger

class HeartbeatService:
    def __init__(self, interval_ms: int = 60_000,
                 on_beat: Callable[[], Coroutine[Any, Any, None]] | None = None):
        self.interval_ms = interval_ms
        self.on_beat = on_beat
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Heartbeat started (interval={self.interval_ms}ms)")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _loop(self):
        while self._running:
            await asyncio.sleep(self.interval_ms / 1000)
            if self.on_beat:
                try:
                    await self.on_beat()
                except Exception as e:
                    logger.error(f"Heartbeat callback error: {e}")
