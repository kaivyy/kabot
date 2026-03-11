"""Progress and interruption helpers for the agent execution loop."""

from __future__ import annotations

from typing import Any

from loguru import logger

from kabot.agent.fallback_i18n import t
from kabot.agent.loop_core.execution_runtime_parts.helpers import (
    _build_pending_interrupt_note,
    _take_pending_interrupt_messages,
)
from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.utils.text_safety import ensure_utf8_text


class TurnProgressRuntime:
    """Encapsulate status, draft, reasoning, and interrupt updates for one turn."""

    def __init__(
        self,
        *,
        loop: Any,
        msg: InboundMessage,
        session: Any,
        message_metadata: dict[str, Any],
        runtime_locale: str | None,
        question_text: str,
        is_background_task: bool,
        skill_creation_phase: str | None,
    ) -> None:
        self.loop = loop
        self.msg = msg
        self.session = session
        self.message_metadata = message_metadata
        self.runtime_locale = runtime_locale
        self.question_text = question_text
        self.is_background_task = bool(is_background_task)
        self.skill_creation_phase = str(skill_creation_phase or "").strip() or None
        self._status_updates_sent: set[str] = set()
        self._draft_updates_sent: set[str] = set()
        self._reasoning_updates_sent: set[str] = set()

    def phase_text(self, phase: str) -> str:
        key = f"runtime.status.{phase}"
        fallback_map = {
            "thinking": "runtime.status.thinking",
            "discovery": "runtime.status.thinking",
            "planning": "runtime.status.thinking",
            "executing": "runtime.status.thinking",
            "verified": "runtime.status.done",
        }
        fallback = fallback_map.get(phase, key)
        translated = t(key, locale=self.runtime_locale, text=self.question_text)
        if translated == key and fallback != key:
            return t(fallback, locale=self.runtime_locale, text=self.question_text)
        return translated

    async def publish_phase(self, phase: str) -> None:
        if self.is_background_task:
            return
        mutable_status_lane = self.message_metadata.get("status_mutable_lane")
        if (
            isinstance(mutable_status_lane, bool)
            and not mutable_status_lane
            and phase in {"thinking", "done", "error"}
        ):
            return
        if phase == "thinking" and bool(
            self.message_metadata.get("suppress_initial_thinking_status", False)
        ):
            self.message_metadata["suppress_initial_thinking_status"] = False
            return
        bus = getattr(self.loop, "bus", None)
        publish = getattr(bus, "publish_outbound", None)
        if not callable(publish):
            return
        text = self.phase_text(phase)
        dedupe_key = f"{phase}:{text}"
        if dedupe_key in self._status_updates_sent:
            return
        self._status_updates_sent.add(dedupe_key)
        try:
            await publish(
                OutboundMessage(
                    channel=self.msg.channel,
                    chat_id=self.msg.chat_id,
                    content=text,
                    metadata={"type": "status_update", "phase": phase, "lane": "status"},
                )
            )
        except Exception:
            return

    async def publish_draft(self, text: str, *, phase: str = "thinking") -> None:
        if self.is_background_task:
            return
        bus = getattr(self.loop, "bus", None)
        publish = getattr(bus, "publish_outbound", None)
        if not callable(publish):
            return
        normalized = ensure_utf8_text(text or "").strip()
        if not normalized:
            return
        if len(normalized) > 600:
            normalized = normalized[:597].rstrip() + "..."
        dedupe_key = f"{phase}:{normalized}"
        if dedupe_key in self._draft_updates_sent:
            return
        self._draft_updates_sent.add(dedupe_key)
        try:
            await publish(
                OutboundMessage(
                    channel=self.msg.channel,
                    chat_id=self.msg.chat_id,
                    content=normalized,
                    metadata={"type": "draft_update", "phase": phase, "lane": "partial"},
                )
            )
        except Exception:
            return

    async def publish_reasoning(self, reasoning_text: str) -> None:
        if self.is_background_task:
            return
        bus = getattr(self.loop, "bus", None)
        publish = getattr(bus, "publish_outbound", None)
        if not callable(publish):
            return
        normalized = ensure_utf8_text(reasoning_text or "").strip()
        if not normalized:
            return
        if len(normalized) > 600:
            normalized = normalized[:597].rstrip() + "..."
        if normalized in self._reasoning_updates_sent:
            return
        self._reasoning_updates_sent.add(normalized)
        try:
            await publish(
                OutboundMessage(
                    channel=self.msg.channel,
                    chat_id=self.msg.chat_id,
                    content=normalized,
                    metadata={
                        "type": "reasoning_update",
                        "phase": "thinking",
                        "lane": "reasoning",
                    },
                )
            )
        except Exception:
            return

    async def _publish_interrupt_ack(self, pending_messages: list[InboundMessage]) -> None:
        if self.is_background_task or not pending_messages:
            return
        interrupt_count = len(pending_messages)
        ack_text = (
            "I saw a new message while still working on this. I'm updating the task context and continuing."
            if interrupt_count == 1
            else f"I saw {interrupt_count} new messages while still working on this. I'm updating the task context and continuing."
        )
        message_tool = getattr(getattr(self.loop, "tools", None), "get", lambda _name: None)(
            "message"
        )
        if message_tool is not None and hasattr(message_tool, "execute"):
            try:
                await message_tool.execute(
                    content=ack_text,
                    phase="interrupt",
                    metadata={
                        "type": "status_update",
                        "phase": "interrupt",
                        "lane": "status",
                    },
                )
                return
            except Exception:
                pass
        bus = getattr(self.loop, "bus", None)
        publish = getattr(bus, "publish_outbound", None)
        if callable(publish):
            try:
                await publish(
                    OutboundMessage(
                        channel=self.msg.channel,
                        chat_id=self.msg.chat_id,
                        content=ack_text,
                        metadata={
                            "type": "status_update",
                            "phase": "interrupt",
                            "lane": "status",
                        },
                    )
                )
            except Exception:
                return

    async def inject_pending_interrupts(self, messages_in: list) -> list:
        pending_messages = await _take_pending_interrupt_messages(
            self.loop,
            self.msg,
            limit=3,
        )
        if not pending_messages:
            return messages_in
        self.message_metadata["pending_interrupt_count"] = int(
            self.message_metadata.get("pending_interrupt_count", 0) or 0
        ) + len(pending_messages)
        session_metadata = getattr(self.session, "metadata", None)
        if isinstance(session_metadata, dict):
            session_metadata["pending_interrupt_count"] = self.message_metadata[
                "pending_interrupt_count"
            ]
        logger.info(
            f"pending_interrupt_count={self.message_metadata['pending_interrupt_count']} session={self.msg.session_key}"
        )
        interrupt_note = _build_pending_interrupt_note(pending_messages)
        if not interrupt_note:
            return messages_in
        await self._publish_interrupt_ack(pending_messages)
        return [*messages_in, {"role": "user", "content": interrupt_note}]

    async def return_with_phase(self, content: str, *, phase: str = "done") -> str:
        if phase == "done" and self.skill_creation_phase == "executing":
            phase = "verified"
        await self.publish_phase(phase)
        return content
