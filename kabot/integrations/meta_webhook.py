"""Meta webhook signature verification and payload mapping."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from kabot.bus.events import InboundMessage


def verify_meta_signature(raw_body: bytes, app_secret: str, signature_header: str | None) -> bool:
    """Verify X-Hub-Signature-256 against request body."""
    if not app_secret:
        return False
    if not signature_header:
        return False

    signature = signature_header.strip()
    prefix = "sha256="
    if not signature.startswith(prefix):
        return False

    provided = signature[len(prefix) :].strip()
    digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, provided)


def parse_meta_inbound(payload: dict[str, Any]) -> list[InboundMessage]:
    """Map Meta webhook payload to inbound bus messages."""
    messages: list[InboundMessage] = []

    for entry in payload.get("entry", []):
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id", "meta"))

        for change in entry.get("changes", []):
            if not isinstance(change, dict):
                continue
            field = str(change.get("field", "threads"))
            value = change.get("value", {}) or {}
            if not isinstance(value, dict):
                continue

            text = _extract_text(value)
            if not text:
                continue

            sender_id = _extract_sender(value)
            chat_id = _extract_chat(value, sender_id, entry_id)
            channel = "meta:threads" if "thread" in field.lower() else "meta:instagram"

            messages.append(
                InboundMessage(
                    channel=channel,
                    sender_id=sender_id,
                    chat_id=chat_id,
                    content=text,
                    metadata={
                        "source": "meta_webhook",
                        "entry_id": entry_id,
                        "field": field,
                        "raw_value": value,
                    },
                )
            )

    return messages


def _extract_text(value: dict[str, Any]) -> str:
    text = value.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    message = value.get("message")
    if isinstance(message, dict):
        nested = message.get("text")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    if isinstance(message, str) and message.strip():
        return message.strip()

    caption = value.get("caption")
    if isinstance(caption, str) and caption.strip():
        return caption.strip()

    return ""


def _extract_sender(value: dict[str, Any]) -> str:
    sender = value.get("sender")
    if isinstance(sender, dict):
        sid = sender.get("id")
        if sid:
            return str(sid)

    from_obj = value.get("from")
    if isinstance(from_obj, dict):
        fid = from_obj.get("id")
        if fid:
            return str(fid)
    if from_obj:
        return str(from_obj)

    return "meta_user"


def _extract_chat(value: dict[str, Any], sender_id: str, entry_id: str) -> str:
    for key in ("thread_id", "conversation_id", "recipient_id"):
        val = value.get(key)
        if val:
            return str(val)

    conversation = value.get("conversation")
    if isinstance(conversation, dict):
        cid = conversation.get("id")
        if cid:
            return str(cid)

    return sender_id or entry_id
