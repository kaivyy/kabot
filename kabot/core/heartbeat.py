"""
Heartbeat Injection for Kabot (Phase 9).

Makes the agent "aware" of background events naturally by injecting
system messages into the message stream.

Instead of cron jobs firing silently, they push "heartbeat events"
that the agent can read and decide how to present to the user.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from kabot.core.msg_context import MsgContext

logger = logging.getLogger(__name__)


class HeartbeatInjector:
    """
    Injects system events into the agent's message stream.

    Use cases:
        - Cron job results → agent can say "Your daily report is ready!"
        - Startup notification → "I'm back online!"
        - Error alerts → "I noticed an API key is expiring"
        - External triggers → Webhook events, monitoring alerts
    """

    def __init__(self, publish_fn: Callable[[MsgContext], Awaitable[None]] | None = None):
        """
        Args:
            publish_fn: Async function to publish a MsgContext into the agent pipeline.
                        Typically this is `bus.publish_inbound` adapted for MsgContext.
        """
        self._publish_fn = publish_fn
        self._event_log: list[dict[str, Any]] = []
        self._pending_events: asyncio.Queue[MsgContext] = asyncio.Queue()

    def set_publisher(self, publish_fn: Callable[[MsgContext], Awaitable[None]]) -> None:
        """Set the publish function (called after initialization)."""
        self._publish_fn = publish_fn

    async def inject_event(
        self,
        event_type: str,
        body: str,
        data: dict[str, Any] | None = None,
        immediate: bool = True,
    ) -> None:
        """
        Inject a system event into the message stream.

        Args:
            event_type: Type of event (e.g., "cron_result", "startup", "alert").
            body: Human-readable description of the event.
            data: Optional structured data about the event.
            immediate: If True, publish immediately. If False, queue for later.
        """
        ctx = MsgContext.system_event(
            event_type=event_type,
            data=data or {},
            body=body,
        )

        # Log the event
        self._event_log.append({
            "event_type": event_type,
            "body": body[:100],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self._event_log) > 100:
            self._event_log = self._event_log[-100:]

        if immediate and self._publish_fn:
            try:
                await self._publish_fn(ctx)
                logger.info(f"Heartbeat injected: {event_type} — {body[:50]}")
            except Exception as e:
                logger.error(f"Failed to inject heartbeat: {e}")
                self._pending_events.put_nowait(ctx)
        else:
            self._pending_events.put_nowait(ctx)
            logger.debug(f"Heartbeat queued: {event_type}")

    async def inject_cron_result(
        self,
        job_name: str,
        result: str | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
    ) -> None:
        """
        Convenience method: inject a cron job result as a system event.

        Args:
            job_name: Name of the cron job that completed.
            result: Job output/result text.
            channel: Target channel to deliver to.
            chat_id: Target chat/conversation.
        """
        body = f"[System] Cron job '{job_name}' completed."
        if result:
            body += f"\nResult: {result}"

        await self.inject_event(
            event_type="cron_result",
            body=body,
            data={
                "job_name": job_name,
                "result": result,
                "target_channel": channel,
                "target_chat": chat_id,
            },
        )

    async def inject_startup(self) -> None:
        """Inject a startup notification event."""
        await self.inject_event(
            event_type="startup",
            body="[System] Kabot is online and ready! 🟢",
        )

    async def inject_alert(self, alert_type: str, message: str) -> None:
        """Inject an alert event (error, warning, etc.)."""
        await self.inject_event(
            event_type="alert",
            body=f"[System Alert] {alert_type}: {message}",
            data={"alert_type": alert_type, "message": message},
        )

    async def flush_pending(self) -> int:
        """Publish all panding events. Returns count of events flushed."""
        if not self._publish_fn:
            return 0

        count = 0
        while not self._pending_events.empty():
            try:
                ctx = self._pending_events.get_nowait()
                await self._publish_fn(ctx)
                count += 1
            except Exception as e:
                logger.error(f"Failed to flush heartbeat: {e}")
                break

        if count > 0:
            logger.info(f"Flushed {count} pending heartbeat events")
        return count

    def get_recent_events(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent event log entries."""
        return self._event_log[-limit:]

    @property
    def pending_count(self) -> int:
        """Number of events waiting to be published."""
        return self._pending_events.qsize()
