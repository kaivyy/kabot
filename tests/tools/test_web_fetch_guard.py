"""Tests for WebFetchTool target guard behavior."""

import pytest

from kabot.agent.tools.web_fetch import WebFetchTool


@pytest.mark.asyncio
async def test_web_fetch_blocks_private_host_by_default():
    tool = WebFetchTool()
    result = await tool.execute(url="http://127.0.0.1:8080/health")
    assert "blocked by network guard" in result.lower()


def test_web_fetch_guard_can_be_disabled_for_trusted_mode():
    class Guard:
        enabled = False
        block_private_networks = True
        allow_hosts = []
        deny_hosts = ["localhost", "127.0.0.1"]

    tool = WebFetchTool(http_guard=Guard())
    tool._validate_target("http://127.0.0.1:8080/health")


def test_web_fetch_allows_empty_denylist_when_private_blocking_disabled():
    class Guard:
        enabled = True
        block_private_networks = False
        allow_hosts = []
        deny_hosts = []

    tool = WebFetchTool(http_guard=Guard())
    tool._validate_target("http://localhost:8080/health")
