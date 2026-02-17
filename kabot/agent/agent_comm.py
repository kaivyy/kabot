import asyncio
import uuid
from time import time
from kabot.bus.queue import MessageBus, AgentMessage

class AgentComm:
    def __init__(self, bus: MessageBus, agent_id: str):
        self.bus = bus
        self.agent_id = agent_id
        self._inbox: asyncio.Queue[AgentMessage] = asyncio.Queue()

        # Subscribe to messages for this agent
        if agent_id not in bus._agent_subscribers:
            bus._agent_subscribers[agent_id] = self._inbox

    async def send(
        self,
        to_agent: str,
        content: dict,
        msg_type: str = "request",
        reply_to: str | None = None
    ) -> AgentMessage:
        msg = AgentMessage(
            msg_id=str(uuid.uuid4())[:8],
            from_agent=self.agent_id,
            to_agent=to_agent,
            msg_type=msg_type,
            content=content,
            timestamp=time(),
            reply_to=reply_to
        )

        # Route to target agent's inbox
        if to_agent in self.bus._agent_subscribers:
            await self.bus._agent_subscribers[to_agent].put(msg)

        return msg

    async def receive(self, timeout: float = 10.0) -> AgentMessage:
        return await asyncio.wait_for(self._inbox.get(), timeout=timeout)

    async def broadcast(self, content: dict, msg_type: str = "broadcast") -> None:
        for agent_id, inbox in self.bus._agent_subscribers.items():
            if agent_id != self.agent_id:
                msg = AgentMessage(
                    msg_id=str(uuid.uuid4())[:8],
                    from_agent=self.agent_id,
                    to_agent=agent_id,
                    msg_type=msg_type,
                    content=content,
                    timestamp=time()
                )
                await inbox.put(msg)
