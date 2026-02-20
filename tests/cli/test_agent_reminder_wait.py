import shutil
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from kabot.cli.commands import (
    _next_cli_reminder_delay_seconds,
    _render_cron_delivery_with_ai,
    _resolve_cron_delivery_content,
    _strip_reminder_context,
)
from kabot.cron.service import CronService
from kabot.cron.types import CronSchedule


def _make_store_path() -> Path:
    root = Path.cwd() / ".tmp-test-cron-wait"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root / "jobs.json"


def test_next_cli_reminder_delay_seconds_returns_due_delay():
    store_path = _make_store_path()
    cron = CronService(store_path)

    now_ms = int(time.time() * 1000)
    cron.add_job(
        name="reminder",
        schedule=CronSchedule(kind="at", at_ms=now_ms + 2000),
        message="test",
        deliver=True,
        channel="cli",
        to="direct",
    )

    delay = _next_cli_reminder_delay_seconds(cron, max_wait_seconds=10)
    assert delay is not None
    assert 0 <= delay <= 10

    shutil.rmtree(store_path.parent, ignore_errors=True)


def test_next_cli_reminder_delay_seconds_ignores_non_cli_delivery():
    store_path = _make_store_path()
    cron = CronService(store_path)

    now_ms = int(time.time() * 1000)
    cron.add_job(
        name="reminder",
        schedule=CronSchedule(kind="at", at_ms=now_ms + 2000),
        message="test",
        deliver=True,
        channel="telegram",
        to="123",
    )

    delay = _next_cli_reminder_delay_seconds(cron, max_wait_seconds=10)
    assert delay is None

    shutil.rmtree(store_path.parent, ignore_errors=True)


def test_next_cli_reminder_delay_seconds_respects_max_window():
    store_path = _make_store_path()
    cron = CronService(store_path)

    now_ms = int(time.time() * 1000)
    cron.add_job(
        name="reminder",
        schedule=CronSchedule(kind="at", at_ms=now_ms + (20 * 60 * 1000)),
        message="test",
        deliver=True,
        channel="cli",
        to="direct",
    )

    delay_short = _next_cli_reminder_delay_seconds(cron, max_wait_seconds=300)
    delay_unbounded = _next_cli_reminder_delay_seconds(cron, max_wait_seconds=None)

    assert delay_short is None
    assert delay_unbounded is not None
    assert delay_unbounded > 300

    shutil.rmtree(store_path.parent, ignore_errors=True)


def test_strip_reminder_context_removes_history_suffix():
    message = "ingat makan\n\nRecent context:\n- User: halo\n- Assistant: ok"
    assert _strip_reminder_context(message) == "ingat makan"


def test_resolve_cron_delivery_content_falls_back_on_provider_error():
    message = "ingat minum air\n\nRecent context:\n- User: tadi rapat"
    assistant_error = "All models failed. Last error: RateLimitError"

    resolved = _resolve_cron_delivery_content(message, assistant_error)
    assert resolved == "ingat minum air"


def test_resolve_cron_delivery_content_uses_assistant_reply_when_valid():
    message = "ingat stretch"
    assistant_reply = "Siap, waktunya stretching sekarang."

    resolved = _resolve_cron_delivery_content(message, assistant_reply)
    assert resolved == assistant_reply


@pytest.mark.asyncio
async def test_render_cron_delivery_with_ai_returns_natural_response_and_strips_context():
    provider = MagicMock()
    provider.chat = AsyncMock(
        return_value=SimpleNamespace(
            content="Yuk, waktunya makan sekarang.",
            has_tool_calls=False,
        )
    )
    message = "ingat makan\n\nRecent context:\n- User: tadi meeting"

    result = await _render_cron_delivery_with_ai(
        provider=provider,
        model="openai-codex/gpt-5.3-codex",
        job_message=message,
    )

    assert result == "Yuk, waktunya makan sekarang."
    provider.chat.assert_awaited_once()
    call_kwargs = provider.chat.await_args.kwargs
    assert call_kwargs["model"] == "openai-codex/gpt-5.3-codex"
    assert "Recent context:" not in call_kwargs["messages"][1]["content"]
    assert "ingat makan" in call_kwargs["messages"][1]["content"]


@pytest.mark.asyncio
async def test_render_cron_delivery_with_ai_returns_none_on_provider_exception():
    provider = MagicMock()
    provider.chat = AsyncMock(side_effect=RuntimeError("provider down"))

    result = await _render_cron_delivery_with_ai(
        provider=provider,
        model="openai-codex/gpt-5.3-codex",
        job_message="ingat minum air",
    )

    assert result is None


@pytest.mark.asyncio
async def test_render_cron_delivery_with_ai_returns_none_for_tool_call_or_failure_marker():
    provider = MagicMock()
    provider.chat = AsyncMock(
        side_effect=[
            SimpleNamespace(content="", has_tool_calls=True),
            SimpleNamespace(content="All models failed. Last error: RateLimitError", has_tool_calls=False),
        ]
    )

    tool_call_result = await _render_cron_delivery_with_ai(
        provider=provider,
        model="openai-codex/gpt-5.3-codex",
        job_message="ingat jalan sebentar",
    )
    failure_result = await _render_cron_delivery_with_ai(
        provider=provider,
        model="openai-codex/gpt-5.3-codex",
        job_message="ingat jalan sebentar",
    )

    assert tool_call_result is None
    assert failure_result is None
