"""Heartbeat service for periodic agent wake-ups."""

import asyncio
from typing import Callable, Coroutine, Any
from loguru import logger

class HeartbeatService:
    def __init__(
        self,
        workspace: Any = None,
        interval_s: int = 60,
        on_heartbeat: Callable[[], Coroutine[Any, Any, None]] | None = None,
        enabled: bool = True,
    ):
        self.workspace = workspace
        self.interval_ms = interval_s * 1000
        self.on_beat = on_heartbeat
        self._enabled = enabled
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
            await asyncio.sleep(self.interval_ms / 1000)
            if self.on_beat:
                try:
                    # Pass a default prompt if on_beat expects arguments, 
                    # but based on commands.py usage (on_heartbeat(prompt: str)), 
                    # we should probably pass a prompt string.
                    # commands.py: async def on_heartbeat(prompt: str) -> str:
                    
                    if self.on_beat.__code__.co_argcount > 0:
                        await self.on_beat("Current time heartbeat check.")
                    else:
                        await self.on_beat()
                except Exception as e:
                    logger.error(f"Heartbeat callback error: {e}")
