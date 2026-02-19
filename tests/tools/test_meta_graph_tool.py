"""Tests for MetaGraphTool."""

import pytest

from kabot.agent.tools.meta_graph import MetaGraphTool


@pytest.mark.asyncio
async def test_meta_graph_threads_create_uses_expected_endpoint():
    sent = {}

    class FakeClient:
        async def request(self, method, path, payload):  # noqa: ANN001
            sent["method"] = method
            sent["path"] = path
            sent["payload"] = payload
            return {"id": "creation-1"}

    tool = MetaGraphTool(client=FakeClient())
    await tool.execute(action="threads_create", text="hello world")
    assert sent["method"] == "POST"
    assert sent["path"].endswith("/threads")

