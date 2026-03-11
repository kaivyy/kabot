from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from kabot.agent.fallback_i18n import t as i18n_t
from kabot.agent.tools.filesystem import ReadFileTool
from kabot.agent.tools.message import MessageTool
from kabot.agent.tools.speedtest import SpeedtestTool


@pytest.mark.asyncio
async def test_read_file_tool_localizes_file_not_found(tmp_path: Path):
    tool = ReadFileTool()
    missing = tmp_path / "tidak-ada.txt"

    result = await tool.execute(str(missing))

    assert result == i18n_t("filesystem.file_not_found", str(missing), path=str(missing))


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
async def test_speedtest_tool_localizes_runtime_error(monkeypatch):
    tool = SpeedtestTool()
    prompt = "cek speed internet sekarang"

    def _boom() -> str:
        raise RuntimeError("network down")

    monkeypatch.setattr(tool, "_run_speedtest", _boom)

    result = await tool.execute(context_text=prompt)

    assert result == i18n_t("speedtest.failed", prompt, error="network down")
