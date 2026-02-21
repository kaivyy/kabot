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
    assert sent["payload"]["media_type"] == "TEXT"


@pytest.mark.asyncio
async def test_meta_graph_can_use_inline_access_token_without_saved_config(monkeypatch):
    created = {}
    sent = {}

    class FakeMetaGraphClient:
        def __init__(self, access_token, api_base="https://graph.facebook.com/v21.0", timeout=30.0):  # noqa: ANN001
            created["access_token"] = access_token
            created["api_base"] = api_base
            created["timeout"] = timeout

        async def request(self, method, path, payload):  # noqa: ANN001
            sent["method"] = method
            sent["path"] = path
            sent["payload"] = payload
            return {"id": "creation-2"}

    monkeypatch.setattr("kabot.agent.tools.meta_graph.MetaGraphClient", FakeMetaGraphClient)

    tool = MetaGraphTool(meta_config=None, client=None)
    out = await tool.execute(
        action="threads_create",
        text="hello inline token",
        access_token="token-inline-123",
        threads_user_id="26179670184998096",
    )

    assert "creation-2" in out
    assert created["access_token"] == "token-inline-123"
    assert sent["path"] == "/26179670184998096/threads"


@pytest.mark.asyncio
async def test_meta_graph_uses_env_token_when_config_missing(monkeypatch):
    created = {}

    class FakeMetaGraphClient:
        def __init__(self, access_token, api_base="https://graph.facebook.com/v21.0", timeout=30.0):  # noqa: ANN001
            created["access_token"] = access_token

        async def request(self, method, path, payload):  # noqa: ANN001
            return {"id": "creation-3"}

    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "token-from-env")
    monkeypatch.setattr("kabot.agent.tools.meta_graph.MetaGraphClient", FakeMetaGraphClient)

    tool = MetaGraphTool(meta_config=None, client=None)
    out = await tool.execute(action="threads_create", text="hello from env")

    assert "creation-3" in out
    assert created["access_token"] == "token-from-env"


@pytest.mark.asyncio
async def test_meta_graph_uses_configured_env_token_name(monkeypatch):
    created = {}

    class FakeMetaGraphClient:
        def __init__(self, access_token, api_base="https://graph.facebook.com/v21.0", timeout=30.0):  # noqa: ANN001
            created["access_token"] = access_token

        async def request(self, method, path, payload):  # noqa: ANN001
            return {"id": "creation-4"}

    class MetaCfg:
        enabled = True
        access_token = ""
        access_token_env = "MY_THREADS_TOKEN"
        threads_user_id = "26179670184998096"
        instagram_user_id = ""

    monkeypatch.setenv("MY_THREADS_TOKEN", "token-from-custom-env")
    monkeypatch.setattr("kabot.agent.tools.meta_graph.MetaGraphClient", FakeMetaGraphClient)

    tool = MetaGraphTool(meta_config=MetaCfg(), client=None)
    out = await tool.execute(action="threads_create", text="hello from configured env")

    assert "creation-4" in out
    assert created["access_token"] == "token-from-custom-env"
