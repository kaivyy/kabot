"""Cross-platform tests for BrowserTool path handling."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from kabot.agent.tools.browser import BrowserTool


@pytest.mark.asyncio
async def test_browser_screenshot_expands_tilde_and_creates_parent_dirs(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))

    tool = BrowserTool()
    tool.page = SimpleNamespace(screenshot=AsyncMock(return_value=None))

    result = await tool.execute(action="screenshot", path="~/Desktop/shots/kabot.png")

    expected_path = (fake_home / "Desktop" / "shots" / "kabot.png").resolve()
    tool.page.screenshot.assert_awaited_once_with(path=str(expected_path), full_page=True)
    assert expected_path.parent.exists()
    assert result == f"Screenshot saved to {expected_path}"


@pytest.mark.asyncio
async def test_browser_screenshot_resolves_relative_nested_path_from_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    tool = BrowserTool()
    tool.page = SimpleNamespace(screenshot=AsyncMock(return_value=None))

    result = await tool.execute(action="screenshot", path="./outputs/screenshots/report.png")

    expected_path = (tmp_path / "outputs" / "screenshots" / "report.png").resolve()
    tool.page.screenshot.assert_awaited_once_with(path=str(expected_path), full_page=True)
    assert expected_path.parent.exists()
    assert result == f"Screenshot saved to {expected_path}"
