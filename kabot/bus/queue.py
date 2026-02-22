"""Async message queue for decoupled channel-agent communication."""

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from loguru import logger

from kabot.bus.events import InboundMessage, OutboundMessage, SystemEvent


@dataclass
class AgentMessage:
    msg_id: str
    from_agent: str
    to_agent: str | None
    msg_type: str
    content: dict
    timestamp: float
    reply_to: str | None = None


class MessageBus:
    """
    Async message bus that decouples chat channels from the agent core.

    Phase 14: Expanded to support full system events (lifecycle, tool, error)
    Pattern from OpenClaw: src/infra/agent-events.ts

    Channels push messages to the inbound queue, and the agent processes
    them and pushes responses to the outbound queue.
    """

    def __init__(self):
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self._outbound_subscribers: dict[str, list[Callable[[OutboundMessage], Awaitable[None]]]] = {}

        # Phase 14: System event support
        self.system_events: asyncio.Queue[SystemEvent] = asyncio.Queue()
        self._system_event_subscribers: list[Callable[[SystemEvent], Awaitable[None]]] = []
        self._seq_by_run: dict[str, int] = {}  # Monotonic sequence counter per run

        # Phase 2 Task 11: Agent-to-agent communication
        self.agent_messages: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self._agent_subscribers: dict[str, asyncio.Queue[AgentMessage]] = {}

        self._running = False

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish a message from a channel to the agent."""
        await self.inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message (blocks until available)."""
        return await self.inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """Publish a response from the agent to channels."""
        await self.outbound.put(msg)

    async def consume_outbound(self) -> OutboundMessage:
        """Consume the next outbound message (blocks until available)."""
        return await self.outbound.get()

    def subscribe_outbound(
        self,
        channel: str,
        callback: Callable[[OutboundMessage], Awaitable[None]]
    ) -> None:
        """Subscribe to outbound messages for a specific channel."""
        if channel not in self._outbound_subscribers:
            self._outbound_subscribers[channel] = []
        self._outbound_subscribers[channel].append(callback)

    async def dispatch_outbound(self) -> None:
        """
        Dispatch outbound messages to subscribed channels.
        Run this as a background task.
        """
        self._running = True
        while self._running:
            try:
                msg = await asyncio.wait_for(self.outbound.get(), timeout=1.0)
                subscribers = self._outbound_subscribers.get(msg.channel, [])
                for callback in subscribers:
                    try:
                        await callback(msg)
                    except Exception as e:
                        logger.error(f"Error dispatching to {msg.channel}: {e}")
            except asyncio.TimeoutError:
                continue

    # Phase 14: System event methods
    def get_next_seq(self, run_id: str) -> int:
        """Get next monotonic sequence number for a run."""
        if run_id not in self._seq_by_run:
            self._seq_by_run[run_id] = 0
        self._seq_by_run[run_id] += 1
        return self._seq_by_run[run_id]

    async def emit_system_event(self, event: SystemEvent) -> None:
        """Emit a system event to all subscribers."""
        await self.system_events.put(event)

        # Dispatch to subscribers immediately
        for callback in self._system_event_subscribers:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Error dispatching system event: {e}")

    def subscribe_system_events(
        self,
        callback: Callable[[SystemEvent], Awaitable[None]]
    ) -> None:
        """Subscribe to system events."""
        self._system_event_subscribers.append(callback)

    async def dispatch_system_events(self) -> None:
        """
        Dispatch system events to subscribers.
        Run this as a background task.
        """
        self._running = True
        while self._running:
            try:
                event = await asyncio.wait_for(self.system_events.get(), timeout=1.0)
                for callback in self._system_event_subscribers:
                    try:
                        await callback(event)
                    except Exception as e:
                        logger.error(f"Error dispatching system event: {e}")
            except asyncio.TimeoutError:
                continue

    def stop(self) -> None:
        """Stop the dispatcher loop."""
        self._running = False

    @property
    def inbound_size(self) -> int:
        """Number of pending inbound messages."""
        return self.inbound.qsize()

    @property
    def outbound_size(self) -> int:
        """Number of pending outbound messages."""
        return self.outbound.qsize()

    @property
    def system_events_size(self) -> int:
        """Number of pending system events."""
        return self.system_events.qsize()
