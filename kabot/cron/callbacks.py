"""Cron delivery callback and fallback helpers."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from kabot.bus.events import OutboundMessage
from kabot.cron.types import CronJob

REMINDER_CONTEXT_MARKER = "\n\nRecent context:\n"
REMINDER_FAILURE_MARKERS = (
    "all models failed",
    "error:",
    "authentication failed",
    "rate limit",
    "unauthorized",
    "forbidden",
    "quota",
)


def strip_reminder_context(message: str) -> str:
    """Return reminder message without attached context block."""
    if not message:
        return ""
    if REMINDER_CONTEXT_MARKER in message:
        return message.split(REMINDER_CONTEXT_MARKER, 1)[0].strip()
    return message.strip()


def should_use_reminder_fallback(response: str | None) -> bool:
    """Detect provider/error outputs where reminder should fallback to raw text."""
    if not response or not response.strip():
        return True
    lowered = response.lower()
    return any(marker in lowered for marker in REMINDER_FAILURE_MARKERS)


def resolve_cron_delivery_content(job_message: str, assistant_response: str | None) -> str:
    """Resolve outbound reminder text, falling back to deterministic payload."""
    fallback = strip_reminder_context(job_message)
    if should_use_reminder_fallback(assistant_response):
        return fallback
    return (assistant_response or "").strip()


async def render_cron_delivery_with_ai(provider: Any, model: str, job_message: str) -> str | None:
    """Generate lightweight natural reminder text using AI without full agent loop."""
    reminder_text = strip_reminder_context(job_message)
    if not reminder_text:
        return None

    system_prompt = (
        "You are Kabot, a friendly AI assistant delivering a scheduled reminder to the user. "
        "DETECT the language of the original reminder and rewrite it so it sounds totally natural, warm, and conversational EXCLUSIVELY in that same language. "
        "Do NOT mention 'this is a reminder to deliver' or use formal templates like 'It is time to send'. "
        "Just directly remind the user like a friend (e.g. 'Hey! Time for your meeting!', 'Halo! Waktunya buka WA ya 😊', 'Hola! Es hora de...'). "
        "Keep it strictly under 2 short lines, no markdown."
    )
    user_prompt = f"Reminder note: {reminder_text}"

    try:
        response = await provider.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            max_tokens=120,
            temperature=0.4,
        )
    except Exception:
        return None

    if getattr(response, "has_tool_calls", False):
        return None

    content = (getattr(response, "content", None) or "").strip()
    if not content or should_use_reminder_fallback(content):
        return None
    return content


def build_bus_cron_callback(
    *,
    provider: Any,
    model: str,
    publish_outbound: Callable[[OutboundMessage], Awaitable[None]],
) -> Callable[[CronJob], Awaitable[str | None]]:
    """Create cron callback that publishes reminder delivery to message bus."""

    async def _on_cron_job(job: CronJob) -> str | None:
        assistant_response = await render_cron_delivery_with_ai(
            provider=provider,
            model=model,
            job_message=job.payload.message,
        )
        delivery_content = resolve_cron_delivery_content(
            job.payload.message,
            assistant_response,
        )

        if job.payload.deliver and job.payload.to:
            await publish_outbound(
                OutboundMessage(
                    channel=job.payload.channel or "cli",
                    chat_id=job.payload.to,
                    content=delivery_content,
                )
            )
        return delivery_content

    return _on_cron_job


def build_cli_cron_callback(
    *,
    provider: Any,
    model: str,
    on_print: Callable[[str], None],
) -> Callable[[CronJob], Awaitable[str | None]]:
    """Create cron callback for CLI mode with local reminder print."""

    async def _on_cron_job(job: CronJob) -> str | None:
        target = job.payload.channel
        if target and target != "cli":
            return None

        assistant_response = await render_cron_delivery_with_ai(
            provider=provider,
            model=model,
            job_message=job.payload.message,
        )
        delivery_content = resolve_cron_delivery_content(
            job.payload.message,
            assistant_response,
        )

        if delivery_content and job.payload.deliver:
            on_print(delivery_content)
        return delivery_content

    return _on_cron_job
