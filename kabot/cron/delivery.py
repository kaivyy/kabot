"""Cron delivery planning helpers."""

from __future__ import annotations

from kabot.cron.types import CronJob


def resolve_delivery_plan(job: CronJob) -> dict:
    """Resolve delivery mode from explicit config or legacy payload fields."""
    if job.delivery:
        delivery = job.delivery
        if delivery.mode == "announce":
            return {
                "mode": "announce",
                "channel": delivery.channel or "last",
                "to": delivery.to or None,
                "webhook_url": None,
                "webhook_secret": None,
            }
        if delivery.mode == "webhook":
            return {
                "mode": "webhook",
                "channel": None,
                "to": None,
                "webhook_url": delivery.webhook_url or None,
                "webhook_secret": delivery.webhook_secret or None,
            }
        return {
            "mode": "none",
            "channel": None,
            "to": None,
            "webhook_url": None,
            "webhook_secret": None,
        }

    if job.payload.deliver:
        return {
            "mode": "announce",
            "channel": job.payload.channel or "last",
            "to": job.payload.to,
            "webhook_url": None,
            "webhook_secret": None,
        }

    return {
        "mode": "none",
        "channel": None,
        "to": None,
        "webhook_url": None,
        "webhook_secret": None,
    }


def infer_delivery(session_key: str) -> dict | None:
    """Auto-detect channel and recipient from a session key.

    Session keys follow the format: channel:chat_id
    Background sessions (background:*) return None.
    """
    if not session_key or session_key.startswith("background:"):
        return None

    parts = session_key.split(":", 1)
    if len(parts) < 2:
        return None

    channel, to = parts[0].strip(), parts[1].strip()
    if not channel or not to:
        return None

    return {"channel": channel, "to": to}
