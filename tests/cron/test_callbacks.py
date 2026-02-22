from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.cron.types import CronJob, CronPayload, CronSchedule


def _make_job(
    *,
    message: str = "ingat minum air",
    deliver: bool = True,
    channel: str | None = "cli",
    to: str | None = "direct",
) -> CronJob:
    return CronJob(
        id="job12345",
        name="reminder",
        schedule=CronSchedule(kind="at", at_ms=1),
        payload=CronPayload(
            message=message,
            deliver=deliver,
            channel=channel,
            to=to,
        ),
    )


@pytest.mark.asyncio
async def test_build_bus_cron_callback_uses_fallback_and_publishes():
    from kabot.bus.events import OutboundMessage
    from kabot.cron.callbacks import build_bus_cron_callback

    provider = MagicMock()
    provider.chat = AsyncMock(
        return_value=SimpleNamespace(
            content="All models failed. Last error: RateLimitError",
            has_tool_calls=False,
        )
    )
    publish = AsyncMock()

    callback = build_bus_cron_callback(
        provider=provider,
        model="openai-codex/gpt-5.3-codex",
        publish_outbound=publish,
    )
    job = _make_job(
        message="ingat minum air\n\nRecent context:\n- User: meeting tadi",
        deliver=True,
        channel="telegram",
        to="12345",
    )

    result = await callback(job)
    assert result == "ingat minum air"
    publish.assert_awaited_once()

    outbound = publish.await_args.args[0]
    assert isinstance(outbound, OutboundMessage)
    assert outbound.channel == "telegram"
    assert outbound.chat_id == "12345"
    assert outbound.content == "ingat minum air"


@pytest.mark.asyncio
async def test_build_cli_cron_callback_ignores_non_cli_jobs():
    from kabot.cron.callbacks import build_cli_cron_callback

    provider = MagicMock()
    provider.chat = AsyncMock()
    printed: list[str] = []

    callback = build_cli_cron_callback(
        provider=provider,
        model="openai-codex/gpt-5.3-codex",
        on_print=lambda content: printed.append(content),
    )
    job = _make_job(channel="telegram", to="12345")

    result = await callback(job)
    assert result is None
    provider.chat.assert_not_called()
    assert printed == []


@pytest.mark.asyncio
async def test_build_cli_cron_callback_prints_resolved_delivery():
    from kabot.cron.callbacks import build_cli_cron_callback

    provider = MagicMock()
    provider.chat = AsyncMock(
        return_value=SimpleNamespace(
            content="Yuk, waktunya istirahat sebentar.",
            has_tool_calls=False,
        )
    )
    printed: list[str] = []

    callback = build_cli_cron_callback(
        provider=provider,
        model="openai-codex/gpt-5.3-codex",
        on_print=lambda content: printed.append(content),
    )
    job = _make_job(message="ingat istirahat", deliver=True, channel="cli", to="direct")

    result = await callback(job)
    assert result == "Yuk, waktunya istirahat sebentar."
    assert printed == ["Yuk, waktunya istirahat sebentar."]
