"""Tests for BrowserTool."""
import os

import pytest

from kabot.agent.tools.browser import BrowserTool


@pytest.mark.asyncio
async def test_browser_tool_lifecycle():
    """Test full lifecycle of browser tool."""
    tool = BrowserTool()

    # Launch
    result = await tool.execute(action="launch", headless=True)
    assert "launched" in result

    # Navigate
    # Use a reliable public site or local file
    result = await tool.execute(action="goto", url="https://example.com")
    assert "Successfully" in result

    # Get Content
    result = await tool.execute(action="get_content")
    assert isinstance(result, str)
    assert "Example Domain" in result

    # Screenshot
    test_path = "test_screenshot.png"
    result = await tool.execute(action="screenshot", path=test_path)
    assert "saved" in result
    assert os.path.exists(test_path)

    # Cleanup
    if os.path.exists(test_path):
        os.remove(test_path)

    # Close
    result = await tool.execute(action="close")
    assert "closed" in result
