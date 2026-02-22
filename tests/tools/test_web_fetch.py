"""Tests for WebFetchTool."""

import pytest

from kabot.agent.tools.web_fetch import WebFetchTool


def test_tool_properties():
    """Test basic tool properties."""
    tool = WebFetchTool()
    assert tool.name == "web_fetch"
    assert "url" in tool.parameters["properties"]
    assert tool.parameters["required"] == ["url"]


@pytest.mark.asyncio
async def test_fetch_json_api():
    """Test fetching JSON from an API."""
    tool = WebFetchTool()
    result = await tool.execute(
        url="https://httpbin.org/json",
        extract_mode="json"
    )
    assert "slideshow" in result  # httpbin returns slideshow data
    assert "HTTP 200" in result


@pytest.mark.asyncio
async def test_fetch_with_headers():
    """Test fetching with custom headers."""
    tool = WebFetchTool()
    result = await tool.execute(
        url="https://httpbin.org/headers",
        headers={"X-Custom": "test"}
    )
    assert "X-Custom" in result


@pytest.mark.asyncio
async def test_max_chars_truncation():
    """Test content truncation with max_chars."""
    tool = WebFetchTool()
    result = await tool.execute(
        url="https://httpbin.org/json",
        max_chars=50
    )
    assert len(result) <= 100  # Some overhead for wrapper
    assert "[truncated]" in result


@pytest.mark.asyncio
async def test_post_request():
    """Test POST request with body."""
    tool = WebFetchTool()
    result = await tool.execute(
        url="https://httpbin.org/post",
        method="POST",
        body='{"key": "value"}',
        content_type="application/json"
    )
    assert "key" in result
    assert "HTTP 200" in result
