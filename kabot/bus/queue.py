"""Async message queue for decoupled channel-agent communication."""

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

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

    Channels push messages to the inbound queue, and the agent processes
    them and pushes responses to the outbound queue.
    """

    def __init__(self):
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self._outbound_subscribers: dict[str, list[Callable[[OutboundMessage], Awaitable[None]]]] = {}

        # Runtime inbound queue controls (debounce/cap/drop).
        self._queue_enabled = False
        self._queue_mode = "off"
        self._queue_debounce_window_ms = 0
        self._queue_max_pending_per_session = 0
        self._queue_drop_policy = "drop_oldest"
        self._queue_summarize_dropped = True
        self._inbound_token_seq = 0
        self._inbound_pending_by_session: dict[str, deque[str]] = {}
        self._inbound_session_by_token: dict[str, str] = {}
        self._inbound_message_by_token: dict[str, InboundMessage] = {}
        self._suppressed_inbound_tokens: set[str] = set()
        self._last_enqueue_ms_by_session: dict[str, float] = {}
        self._dropped_summary_by_session: dict[str, dict[str, Any]] = {}

        # Phase 14: System event support
        self.system_events: asyncio.Queue[SystemEvent] = asyncio.Queue()
        self._system_event_subscribers: list[Callable[[SystemEvent], Awaitable[None]]] = []
        self._seq_by_run: dict[str, int] = {}  # Monotonic sequence counter per run

        # Phase 2 Task 11: Agent-to-agent communication
        self.agent_messages: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self._agent_subscribers: dict[str, asyncio.Queue[AgentMessage]] = {}

        self._running = False

    def configure_inbound_queue(self, runtime_queue: Any | None) -> None:
        """Apply runtime queue policy from config object/dict."""
        if runtime_queue is None:
            return

        def _pick(name: str, default: Any) -> Any:
            if isinstance(runtime_queue, dict):
                if name in runtime_queue:
                    return runtime_queue[name]
                camel = "".join([name.split("_")[0], *[part.title() for part in name.split("_")[1:]]])
                return runtime_queue.get(camel, default)
            return getattr(runtime_queue, name, default)

        enabled = bool(_pick("enabled", True))
        mode = str(_pick("mode", "debounce") or "debounce").strip().lower()
        if mode not in {"off", "debounce"}:
            mode = "debounce"
        debounce_window_ms = int(_pick("debounce_window_ms", 1200) or 0)
        max_pending = int(_pick("max_pending_per_session", 4) or 0)
        drop_policy = str(_pick("drop_policy", "drop_oldest") or "drop_oldest").strip().lower()
        if drop_policy not in {"drop_oldest", "drop_newest"}:
            drop_policy = "drop_oldest"
        summarize_dropped = bool(_pick("summarize_dropped", True))

        self._queue_enabled = enabled
        self._queue_mode = mode
        self._queue_debounce_window_ms = max(0, debounce_window_ms)
        self._queue_max_pending_per_session = max(1, max_pending) if max_pending else 0
        self._queue_drop_policy = drop_policy
        self._queue_summarize_dropped = summarize_dropped

    def _queue_policy_enabled_for(self, msg: InboundMessage) -> bool:
        if not self._queue_enabled or self._queue_mode == "off":
            return False
        channel = str(msg.channel or "").lower()
        sender = str(msg.sender_id or "").lower()
        if channel in {"system", "agent", "background"} or sender == "system":
            return False
        return True

    def _next_inbound_token(self) -> str:
        self._inbound_token_seq += 1
        return f"in-{self._inbound_token_seq}"

    @staticmethod
    def _token_from_message(msg: InboundMessage) -> str:
        metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
        return str(metadata.get("__bus_inbound_token") or "")

    @staticmethod
    def _drop_preview_text(content: str) -> str:
        text = " ".join(str(content or "").split())
        if len(text) > 80:
            return text[:77] + "..."
        return text

    def _record_dropped_message(self, session_key: str, msg: InboundMessage, reason: str) -> None:
        if not self._queue_summarize_dropped:
            return
        summary = self._dropped_summary_by_session.get(session_key)
        if summary is None:
            summary = {"count": 0, "preview": [], "reasons": set()}
            self._dropped_summary_by_session[session_key] = summary
        summary["count"] = int(summary.get("count", 0)) + 1
        preview = summary.get("preview")
        if isinstance(preview, list) and len(preview) < 3:
            preview.append(self._drop_preview_text(msg.content))
        reasons = summary.get("reasons")
        if isinstance(reasons, set):
            reasons.add(reason)

    def _pop_drop_summary(self, session_key: str) -> dict[str, Any] | None:
        summary = self._dropped_summary_by_session.pop(session_key, None)
        if not isinstance(summary, dict):
            return None
        count = int(summary.get("count", 0))
        if count <= 0:
            return None
        preview = summary.get("preview")
        reasons = summary.get("reasons")
        return {
            "dropped_count": count,
            "dropped_preview": list(preview) if isinstance(preview, list) else [],
            "drop_reasons": sorted(reasons) if isinstance(reasons, set) else [],
        }

    def _attach_drop_summary_to_message(self, msg: InboundMessage, session_key: str) -> None:
        summary = self._pop_drop_summary(session_key)
        if not summary:
            return
        if not isinstance(msg.metadata, dict):
            msg.metadata = {}
        queue_meta = msg.metadata.get("queue")
        if not isinstance(queue_meta, dict):
            queue_meta = {}
        existing_count = int(queue_meta.get("dropped_count", 0) or 0)
        queue_meta["dropped_count"] = existing_count + summary["dropped_count"]
        existing_preview = queue_meta.get("dropped_preview")
        merged_preview: list[str] = list(existing_preview) if isinstance(existing_preview, list) else []
        merged_preview.extend(summary["dropped_preview"])
        if merged_preview:
            queue_meta["dropped_preview"] = merged_preview[:3]
        existing_reasons = queue_meta.get("drop_reasons")
        merged_reasons = set(existing_reasons) if isinstance(existing_reasons, list) else set()
        merged_reasons.update(summary["drop_reasons"])
        if merged_reasons:
            queue_meta["drop_reasons"] = sorted(merged_reasons)
        msg.metadata["queue"] = queue_meta

    def _attach_drop_summary_to_token(self, session_key: str, token: str) -> None:
        target_msg = self._inbound_message_by_token.get(token)
        if target_msg is None:
            return
        self._attach_drop_summary_to_message(target_msg, session_key)

    def _forget_inbound_token(self, token: str) -> None:
        session_key = self._inbound_session_by_token.pop(token, None)
        self._inbound_message_by_token.pop(token, None)
        if not session_key:
            return
        pending = self._inbound_pending_by_session.get(session_key)
        if pending is None:
            return
        try:
            pending.remove(token)
        except ValueError:
            pass
        if not pending:
            self._inbound_pending_by_session.pop(session_key, None)

    def _suppress_pending_token(self, session_key: str, token: str, reason: str) -> None:
        pending = self._inbound_pending_by_session.get(session_key)
        if pending is not None:
            try:
                pending.remove(token)
            except ValueError:
                pass
            if not pending:
                self._inbound_pending_by_session.pop(session_key, None)
        existing = self._inbound_message_by_token.get(token)
        if existing is not None:
            self._record_dropped_message(session_key, existing, reason=reason)
        self._suppressed_inbound_tokens.add(token)

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish a message from a channel to the agent."""
        if self._queue_policy_enabled_for(msg):
            session_key = msg.session_key
            now_ms = time.monotonic() * 1000.0
            token = self._next_inbound_token()
            if not isinstance(msg.metadata, dict):
                msg.metadata = {}
            msg.metadata["__bus_inbound_token"] = token
            pending = self._inbound_pending_by_session.setdefault(session_key, deque())

            should_debounce = (
                self._queue_mode == "debounce"
                and pending
                and self._queue_debounce_window_ms > 0
            )
            last_enqueue_ms = self._last_enqueue_ms_by_session.get(session_key)
            if should_debounce and isinstance(last_enqueue_ms, float):
                if (now_ms - last_enqueue_ms) <= self._queue_debounce_window_ms:
                    if self._queue_drop_policy == "drop_newest":
                        self._record_dropped_message(session_key, msg, reason="debounce_drop_newest")
                        self._attach_drop_summary_to_token(session_key, pending[-1])
                        return
                    for existing_token in list(pending):
                        self._suppress_pending_token(session_key, existing_token, reason="debounce_drop_oldest")

            max_pending = self._queue_max_pending_per_session
            if max_pending > 0 and len(pending) >= max_pending:
                if self._queue_drop_policy == "drop_newest":
                    self._record_dropped_message(session_key, msg, reason="cap_drop_newest")
                    if pending:
                        self._attach_drop_summary_to_token(session_key, pending[-1])
                    return
                while len(pending) >= max_pending:
                    self._suppress_pending_token(
                        session_key,
                        pending[0],
                        reason="cap_drop_oldest",
                    )

            self._inbound_session_by_token[token] = session_key
            self._inbound_message_by_token[token] = msg
            pending.append(token)
            self._last_enqueue_ms_by_session[session_key] = now_ms
            self._attach_drop_summary_to_message(msg, session_key)
        await self.inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message (blocks until available)."""
        while True:
            msg = await self.inbound.get()
            token = self._token_from_message(msg)
            if token and token in self._suppressed_inbound_tokens:
                self._suppressed_inbound_tokens.discard(token)
                self._forget_inbound_token(token)
                continue
            if token:
                self._forget_inbound_token(token)
            return msg

    def take_pending_inbound_for_session(self, session_key: str, *, limit: int = 3) -> list[InboundMessage]:
        """Non-blockingly drain up to `limit` pending inbound messages for one session."""
        if not session_key or limit <= 0:
            return []
        raw_queue = getattr(self.inbound, "_queue", None)
        if raw_queue is None:
            return []

        retained = deque()
        taken: list[InboundMessage] = []
        try:
            while raw_queue:
                msg = raw_queue.popleft()
                if (
                    isinstance(msg, InboundMessage)
                    and msg.session_key == session_key
                    and len(taken) < limit
                ):
                    taken.append(msg)
                    token = self._token_from_message(msg)
                    if token:
                        self._forget_inbound_token(token)
                    continue
                retained.append(msg)
        finally:
            raw_queue.extend(retained)
        return taken

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
