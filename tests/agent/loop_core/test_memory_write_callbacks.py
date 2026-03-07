import asyncio
from contextlib import suppress
from types import SimpleNamespace

import pytest

from kabot.agent.loop_core.execution_runtime import (
    _schedule_memory_write as schedule_exec_memory_write,
)
from kabot.agent.loop_core.session_flow import (
    _schedule_memory_write as schedule_session_memory_write,
)


@pytest.mark.asyncio
async def test_session_memory_write_callback_ignores_cancelled_error():
    loop_obj = SimpleNamespace(_pending_memory_tasks=set())
    blocker = asyncio.Event()

    async def _pending_write() -> None:
        await blocker.wait()

    schedule_session_memory_write(loop_obj, _pending_write(), label="session-test")
    task = next(iter(loop_obj._pending_memory_tasks))
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)

    assert not loop_obj._pending_memory_tasks


@pytest.mark.asyncio
async def test_execution_memory_write_callback_ignores_cancelled_error():
    loop_obj = SimpleNamespace(_pending_memory_tasks=set())
    blocker = asyncio.Event()

    async def _pending_write() -> None:
        await blocker.wait()

    schedule_exec_memory_write(loop_obj, _pending_write(), label="execution-test")
    task = next(iter(loop_obj._pending_memory_tasks))
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)

    assert not loop_obj._pending_memory_tasks
