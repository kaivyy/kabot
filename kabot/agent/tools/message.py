"""Message tool for sending messages to users."""

from typing import Any, Awaitable, Callable

from kabot.agent.fallback_i18n import t as i18n_t
from kabot.agent.tools.base import Tool
from kabot.bus.events import OutboundMessage


class MessageTool(Tool):
    """Tool to send messages to users on chat channels."""

    def __init__(
        self,
        send_callback: Callable[[OutboundMessage], Awaitable[None]] | None = None,
        default_channel: str = "",
        default_chat_id: str = ""
    ):
        self._send_callback = send_callback
        self._default_channel = default_channel
        self._default_chat_id = default_chat_id

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the current message context."""
        self._default_channel = channel
        self._default_chat_id = chat_id

    def set_send_callback(self, callback: Callable[[OutboundMessage], Awaitable[None]]) -> None:
        """Set the callback for sending messages."""
        self._send_callback = callback

    @property
    def name(self) -> str:
        return "message"

    @property
    def description(self) -> str:
        return (
            "Send an EXTRA message or local file attachment to a user. "
            "DO NOT use this for normal conversation replies. "
            "Use it when the user explicitly wants a file or follow-up message sent, "
            "including back to the current chat/channel via the existing session context."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The message content to send"
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: List of local file paths to send as attachments"
                },
                "channel": {
                    "type": "string",
                    "description": "Optional: target channel (telegram, discord, etc.)"
                },
                "chat_id": {
                    "type": "string",
                    "description": "Optional: target chat/user ID"
                }
            },
            "required": ["content"]
        }

    async def execute(
        self,
        content: str,
        files: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
        **kwargs: Any
    ) -> str:
        channel = channel or self._default_channel
        chat_id = chat_id or self._default_chat_id
        context_text = str(kwargs.get("context_text") or content or "").strip()

        if not channel or not chat_id:
            return i18n_t("message.no_target", context_text)

        if not self._send_callback:
            return i18n_t("message.not_configured", context_text)

        metadata = kwargs.get("metadata")
        outbound_metadata = dict(metadata) if isinstance(metadata, dict) else {}
        phase = str(kwargs.get("phase") or "").strip()
        if phase and "phase" not in outbound_metadata:
            outbound_metadata["phase"] = phase
            outbound_metadata.setdefault("type", "status_update")
            outbound_metadata.setdefault("lane", "status")

        msg = OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=content,
            media=files or [],
            metadata=outbound_metadata,
        )

        try:
            await self._send_callback(msg)
            return f"Message sent to {channel}:{chat_id}"
        except Exception as e:
            return i18n_t("message.send_error", context_text, error=str(e))
