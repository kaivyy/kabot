"""Heartbeat service for periodic agent wake-ups."""

import asyncio
import re
from pathlib import Path
from typing import Any, Callable, Coroutine

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
        max_tasks_per_beat: int = 5,
    ):
        self.workspace = workspace
        self.interval_ms = interval_s * 1000
        self.on_beat = on_heartbeat
        self._enabled = enabled
        self.active_hours_start = active_hours_start
        self.active_hours_end = active_hours_end
        self.max_tasks_per_beat = max(1, int(max_tasks_per_beat))
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
                    tasks = self._load_tasks()
                    if tasks:
                        for task in tasks[:self.max_tasks_per_beat]:
                            await self._dispatch_heartbeat(task)
                    else:
                        await self._dispatch_heartbeat("Current time heartbeat check.")
                except Exception as e:
                    logger.error(f"Heartbeat callback error: {e}")
            await asyncio.sleep(self.interval_ms / 1000)

    def _load_tasks(self) -> list[str]:
        if not self.workspace:
            return []
        path = Path(self.workspace) / "HEARTBEAT.md"
        if not path.exists():
            return []
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return []
        in_active = False
        tasks: list[str] = []
        for line in content.splitlines():
            header = line.strip().lower()
            if header.startswith("## "):
                if "active tasks" in header:
                    in_active = True
                elif "completed" in header:
                    in_active = False
                continue
            if not in_active:
                continue
            match = re.match(r"\s*-\s*\[\s\]\s+(.*)", line)
            if match:
                task = match.group(1).strip()
                if task:
                    tasks.append(task)
        return tasks

    async def _dispatch_heartbeat(self, payload: str) -> None:
        if self.on_beat.__code__.co_argcount > 0:
            await self.on_beat(f"Heartbeat task: {payload}")
        else:
            await self.on_beat()
