"""Tests for Discord typing keepalive behavior with status updates."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from kabot.bus.events import OutboundMessage
from kabot.bus.queue import MessageBus
from kabot.channels.discord import DiscordChannel
from kabot.config.schema import DiscordConfig


@pytest.mark.asyncio
async def test_discord_send_keeps_typing_for_status_updates():
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._http = SimpleNamespace(
        post=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {"id": "status-1"})),
        patch=AsyncMock(return_value=SimpleNamespace(status_code=200)),
        delete=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    )
    channel._stop_typing = AsyncMock()

    msg = OutboundMessage(
        channel="discord",
        chat_id="1234567890",
        content="Queued. Preparing your request...",
        metadata={"type": "status_update", "phase": "queued"},
    )

    await channel.send(msg)

    channel._stop_typing.assert_not_awaited()
    channel._http.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_discord_status_update_ensures_typing_when_running():
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._running = True
    channel._ensure_typing = AsyncMock()
    channel._http = SimpleNamespace(
        post=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {"id": "status-1"})),
        patch=AsyncMock(return_value=SimpleNamespace(status_code=200)),
        delete=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    )
    channel._stop_typing = AsyncMock()

    msg = OutboundMessage(
        channel="discord",
        chat_id="1234567890",
        content="Queued. Preparing your request...",
        metadata={"type": "status_update", "phase": "queued"},
    )

    await channel.send(msg)

    channel._ensure_typing.assert_awaited_once_with("1234567890")
    channel._stop_typing.assert_not_awaited()


@pytest.mark.asyncio
async def test_discord_send_stops_typing_for_regular_messages():
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._http = SimpleNamespace(
        post=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {})),
        patch=AsyncMock(return_value=SimpleNamespace(status_code=200)),
        delete=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    )
    channel._stop_typing = AsyncMock()

    msg = OutboundMessage(
        channel="discord",
        chat_id="1234567890",
        content="Final answer",
    )

    await channel.send(msg)

    channel._stop_typing.assert_awaited_once_with("1234567890")
    channel._http.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_discord_status_update_edits_existing_status_message():
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._http = SimpleNamespace(
        post=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {"id": "status-1"})),
        patch=AsyncMock(return_value=SimpleNamespace(status_code=200)),
        delete=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    )
    channel._stop_typing = AsyncMock()

    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Queued...",
            metadata={"type": "status_update", "phase": "queued"},
        )
    )
    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Thinking...",
            metadata={"type": "status_update", "phase": "thinking"},
        )
    )

    channel._http.post.assert_awaited_once()
    channel._http.patch.assert_awaited_once()
    channel._stop_typing.assert_not_awaited()


@pytest.mark.asyncio
async def test_discord_draft_update_edits_existing_progress_message():
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._http = SimpleNamespace(
        post=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {"id": "status-1"})),
        patch=AsyncMock(return_value=SimpleNamespace(status_code=200)),
        delete=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    )
    channel._stop_typing = AsyncMock()

    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Draft awal",
            metadata={"type": "draft_update", "phase": "thinking"},
        )
    )
    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Draft awal",
            metadata={"type": "draft_update", "phase": "thinking"},
        )
    )
    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Draft revisi",
            metadata={"type": "draft_update", "phase": "thinking"},
        )
    )

    channel._http.post.assert_awaited_once()
    channel._http.patch.assert_awaited_once()
    channel._stop_typing.assert_not_awaited()


@pytest.mark.asyncio
async def test_discord_regular_message_clears_status_message():
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._http = SimpleNamespace(
        post=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {})),
        patch=AsyncMock(return_value=SimpleNamespace(status_code=200)),
        delete=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    )
    channel._stop_typing = AsyncMock()
    channel._status_message_ids["1234567890"] = "status-99"

    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Final answer",
        )
    )

    channel._http.delete.assert_awaited_once()
    channel._stop_typing.assert_awaited_once_with("1234567890")


@pytest.mark.asyncio
async def test_discord_status_update_transient_patch_keeps_existing_status_message():
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._http = SimpleNamespace(
        post=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {"id": "status-2"})),
        patch=AsyncMock(return_value=SimpleNamespace(status_code=429)),
        delete=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    )
    channel._status_message_ids["1234567890"] = "status-1"
    channel._stop_typing = AsyncMock()

    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Still working...",
            metadata={"type": "status_update", "phase": "thinking", "keepalive": True},
        )
    )

    channel._http.patch.assert_awaited_once()
    channel._http.post.assert_not_awaited()
    assert channel._status_message_ids["1234567890"] == "status-1"


@pytest.mark.asyncio
async def test_discord_regular_message_transient_delete_keeps_status_message_for_retry():
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._http = SimpleNamespace(
        post=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {})),
        patch=AsyncMock(return_value=SimpleNamespace(status_code=200)),
        delete=AsyncMock(return_value=SimpleNamespace(status_code=429)),
    )
    channel._status_message_ids["1234567890"] = "status-1"
    channel._stop_typing = AsyncMock()

    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Final answer",
        )
    )

    channel._http.delete.assert_awaited_once()
    channel._http.post.assert_awaited_once()
    assert channel._status_message_ids["1234567890"] == "status-1"


@pytest.mark.asyncio
async def test_discord_typing_loop_stops_after_repeated_failures(monkeypatch):
    import kabot.channels.discord as discord_module

    monkeypatch.setattr(discord_module, "_DISCORD_TYPING_RETRY_DELAY_SECONDS", 0.01)
    monkeypatch.setattr(discord_module, "_DISCORD_TYPING_MAX_CONSECUTIVE_FAILURES", 2)

    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._running = True
    channel._http = SimpleNamespace(post=AsyncMock(side_effect=RuntimeError("boom")))

    await channel._start_typing("1234567890")
    task = channel._typing_tasks["1234567890"]
    await asyncio.wait_for(task, timeout=1.0)
    channel._running = False

    assert "1234567890" not in channel._typing_tasks


@pytest.mark.asyncio
async def test_discord_final_message_cleans_stale_status_bubbles_after_patch_failure():
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._http = SimpleNamespace(
        post=AsyncMock(
            side_effect=[
                SimpleNamespace(status_code=200, json=lambda: {"id": "status-1"}),
                SimpleNamespace(status_code=200, json=lambda: {"id": "status-2"}),
                SimpleNamespace(status_code=200, json=lambda: {}),
            ]
        ),
        patch=AsyncMock(return_value=SimpleNamespace(status_code=400)),
        delete=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    )
    channel._stop_typing = AsyncMock()

    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Queued...",
            metadata={"type": "status_update", "phase": "queued"},
        )
    )
    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Thinking...",
            metadata={"type": "status_update", "phase": "thinking"},
        )
    )
    await channel.send(
        OutboundMessage(
            channel="discord",
            chat_id="1234567890",
            content="Final answer",
        )
    )

    deleted_ids = {str(call.args[0]).rsplit("/", 1)[-1] for call in channel._http.delete.await_args_list}
    assert deleted_ids == {"status-1", "status-2"}


@pytest.mark.asyncio
async def test_discord_attachment_download_sanitizes_windows_style_filename(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    monkeypatch.setattr("kabot.channels.discord.Path.home", lambda: fake_home)

    response = SimpleNamespace(
        raise_for_status=lambda: None,
        content=b"hello",
    )
    channel = DiscordChannel(DiscordConfig(enabled=True, token="test-token"), MessageBus())
    channel._http = SimpleNamespace(get=AsyncMock(return_value=response))
    channel._start_typing = AsyncMock()
    channel._handle_message = AsyncMock()

    payload = {
        "id": "message-1",
        "channel_id": "123456",
        "content": "",
        "author": {"id": "555", "username": "tester"},
        "attachments": [
            {
                "id": "att-1",
                "filename": r"reports\\daily\\report.txt",
                "url": "https://cdn.example.test/report.txt",
                "size": 5,
            }
        ],
    }

    await channel._handle_message_create(payload)

    channel._handle_message.assert_awaited_once()
    kwargs = channel._handle_message.await_args.kwargs
    assert kwargs["sender_id"] == "555"
    assert kwargs["chat_id"] == "123456"
    assert kwargs["media"]
    saved_path = Path(kwargs["media"][0])
    assert saved_path.exists()
    assert saved_path.name == "att-1_report.txt"
    assert "[attachment: " in kwargs["content"]
    assert "download failed" not in kwargs["content"]
