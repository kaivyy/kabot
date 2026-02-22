# tests/agent/test_coordinator.py
import pytest


@pytest.mark.asyncio
async def test_delegate_task():
    from kabot.agent.coordinator import Coordinator
    from kabot.bus.queue import MessageBus

    bus = MessageBus()
    coordinator = Coordinator(bus, "master-agent")

    task_id = await coordinator.delegate_task(
        task="Design authentication system",
        target_role="brainstorming"
    )

    assert task_id is not None
    assert task_id in coordinator._pending_tasks

@pytest.mark.asyncio
async def test_collect_results():
    from kabot.agent.coordinator import Coordinator
    from kabot.bus.queue import MessageBus

    bus = MessageBus()
    coordinator = Coordinator(bus, "master-agent")

    task_id = await coordinator.delegate_task("Test task", "executor")

    # Simulate result
    coordinator._task_results[task_id] = {"status": "completed", "output": "Done"}

    results = await coordinator.collect_results(task_id, timeout=0.1)
    assert results["status"] == "completed"
