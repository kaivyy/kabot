# kabot/agent/coordinator.py
import asyncio
import uuid
from time import time

from kabot.agent.agent_comm import AgentComm
from kabot.bus.queue import MessageBus


class Coordinator:
    def __init__(self, bus: MessageBus, agent_id: str):
        self.bus = bus
        self.agent_id = agent_id
        self.comm = AgentComm(bus, agent_id)
        self._pending_tasks: dict[str, dict] = {}
        self._task_results: dict[str, dict] = {}

    async def delegate_task(
        self,
        task: str,
        target_role: str,
        context: dict | None = None
    ) -> str:
        task_id = str(uuid.uuid4())[:8]

        self._pending_tasks[task_id] = {
            "task": task,
            "role": target_role,
            "context": context or {},
            "created_at": time()
        }

        # Send task to role-specific agent
        await self.comm.send(
            to_agent=f"role:{target_role}",
            content={
                "task_id": task_id,
                "task": task,
                "context": context or {}
            },
            msg_type="task_delegation"
        )

        return task_id

    async def collect_results(
        self,
        task_id: str,
        timeout: float = 30.0
    ) -> dict:
        start_time = time()

        while time() - start_time < timeout:
            if task_id in self._task_results:
                result = self._task_results.pop(task_id)
                self._pending_tasks.pop(task_id, None)
                return result

            await asyncio.sleep(0.1)

        raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")

    async def aggregate_results(self, results: list[dict]) -> dict:
        """Aggregate results from multiple agents."""
        return {
            "aggregated": True,
            "count": len(results),
            "results": results,
            "summary": self._summarize_results(results)
        }

    def _summarize_results(self, results: list[dict]) -> str:
        return f"Collected {len(results)} results"
