from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from kabot.agent.fallback_i18n import t as i18n_t
from kabot.agent.tools.filesystem import ListDirTool, ReadFileTool
from kabot.agent.tools.message import MessageTool
from kabot.agent.tools.speedtest import SpeedtestTool


@pytest.mark.asyncio
async def test_read_file_tool_localizes_file_not_found(tmp_path: Path):
    tool = ReadFileTool()
    missing = tmp_path / "tidak-ada.txt"

    result = await tool.execute(str(missing))

    assert result == i18n_t("filesystem.file_not_found", str(missing), path=str(missing))


@pytest.mark.asyncio
async def test_list_dir_tool_localizes_missing_directory_with_friendly_copy(tmp_path: Path):
    tool = ListDirTool()
    missing = tmp_path / "folder-yang-tidak-ada"

    result = await tool.execute(str(missing))

    assert result == i18n_t("filesystem.directory_not_found", str(missing), path=str(missing))
    assert "belum" in result.lower() or "couldn't" in result.lower()


@pytest.mark.asyncio
async def test_message_tool_localizes_missing_target():
    tool = MessageTool()
    prompt = "tolong kirim pesan"

    result = await tool.execute(prompt)

    assert result == i18n_t("message.no_target", prompt)


@pytest.mark.asyncio
async def test_message_tool_localizes_missing_sender_callback():
    tool = MessageTool(default_channel="telegram", default_chat_id="123")
    prompt = "tolong kirim pesan"

    result = await tool.execute(prompt)

    assert result == i18n_t("message.not_configured", prompt)


@pytest.mark.asyncio
async def test_message_tool_can_send_file_to_current_chat_context():
    send_callback = AsyncMock(return_value=None)
    tool = MessageTool(
        send_callback=send_callback,
        default_channel="telegram",
        default_chat_id="chat-99",
    )

    result = await tool.execute("Ini file yang diminta.", files=["docs/report.pdf"])

    assert result == "Message sent to telegram:chat-99"
    outbound = send_callback.await_args.args[0]
    assert outbound.channel == "telegram"
    assert outbound.chat_id == "chat-99"
    assert outbound.content == "Ini file yang diminta."
    assert outbound.media == ["docs/report.pdf"]


@pytest.mark.asyncio
async def test_message_tool_merges_delivery_route_metadata_into_outbound_message():
    send_callback = AsyncMock(return_value=None)
    tool = MessageTool(
        send_callback=send_callback,
        default_channel="slack",
        default_chat_id="C123",
    )
    tool.set_context(
        "slack",
        "C123",
        delivery_route={
            "channel": "slack",
            "chat_id": "C123",
            "team_id": "T9",
            "thread_id": "171717.0001",
        },
    )

    result = await tool.execute("Sending the file now.", files=["docs/report.pdf"])

    assert result == "Message sent to slack:C123"
    outbound = send_callback.await_args.args[0]
    assert outbound.metadata["delivery_route"] == {
        "channel": "slack",
        "chat_id": "C123",
        "team_id": "T9",
        "thread_id": "171717.0001",
    }
    assert outbound.metadata["team_id"] == "T9"
    assert outbound.metadata["thread_id"] == "171717.0001"
    assert outbound.metadata["thread_ts"] == "171717.0001"


@pytest.mark.asyncio
async def test_speedtest_tool_localizes_runtime_error(monkeypatch):
    tool = SpeedtestTool()
    prompt = "cek speed internet sekarang"

    def _boom() -> str:
        raise RuntimeError("network down")

    monkeypatch.setattr(tool, "_run_speedtest", _boom)

    result = await tool.execute(context_text=prompt)

    assert result == i18n_t("speedtest.failed", prompt, error="network down")
