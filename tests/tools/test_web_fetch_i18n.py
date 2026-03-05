"""i18n regression tests for WebFetchTool deterministic error responses."""

import pytest

from kabot.agent.fallback_i18n import t as i18n_t
from kabot.agent.tools.web_fetch import WebFetchTool


@pytest.mark.asyncio
async def test_web_fetch_localizes_validation_error_for_blocked_target():
    tool = WebFetchTool()
    url = "http://127.0.0.1:8080/health"

    result = await tool.execute(url=url)

    assert result == i18n_t(
        "web_fetch.validation_error",
        url,
        error="Target blocked by network guard: 127.0.0.1",
    )


@pytest.mark.asyncio
async def test_web_fetch_localizes_timeout_error(monkeypatch):
    tool = WebFetchTool()
    url = "https://example.com"

    class _DummyClient:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return None

        async def request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            from kabot.agent.tools.web_fetch import httpx

            raise httpx.TimeoutException("timed out")

    monkeypatch.setattr("kabot.agent.tools.web_fetch.httpx.AsyncClient", lambda **kwargs: _DummyClient())

    result = await tool.execute(url=url)
    assert result == i18n_t("web_fetch.timeout", url, seconds=30)


@pytest.mark.asyncio
async def test_web_fetch_localizes_generic_request_error(monkeypatch):
    tool = WebFetchTool()
    url = "https://example.com"

    class _DummyClient:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return None

        async def request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    monkeypatch.setattr("kabot.agent.tools.web_fetch.httpx.AsyncClient", lambda **kwargs: _DummyClient())

    result = await tool.execute(url=url)
    assert result == i18n_t(
        "web_fetch.request_error",
        url,
        error_type="RuntimeError",
        error="boom",
    )
