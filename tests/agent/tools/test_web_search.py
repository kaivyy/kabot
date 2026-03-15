from __future__ import annotations

from typing import Any

import pytest

from kabot.agent.tools import web_search as web_search_module
from kabot.agent.tools.web_search import WebSearchTool
from kabot.agent.fallback_i18n import t as i18n_t


class _DummyResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self._payload


class _DummyAsyncClient:
    def __init__(self, payload: dict[str, Any], status_code: int = 200):
        self._payload = payload
        self._status_code = status_code

    async def __aenter__(self) -> "_DummyAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, *args: Any, **kwargs: Any) -> _DummyResponse:
        return _DummyResponse(self._payload, status_code=self._status_code)


class _DummyTextResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _DummyRSSAsyncClient:
    def __init__(self, xml_text: str, status_code: int = 200):
        self._xml_text = xml_text
        self._status_code = status_code

    async def __aenter__(self) -> "_DummyRSSAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, *args: Any, **kwargs: Any) -> _DummyTextResponse:
        return _DummyTextResponse(self._xml_text, status_code=self._status_code)


def test_web_search_provider_explicit_kimi():
    tool = WebSearchTool(provider="kimi", kimi_api_key="kimi-key-1")
    assert tool.provider == "kimi"


def test_web_search_provider_auto_uses_kimi_when_key_present():
    tool = WebSearchTool(provider="auto", kimi_api_key="kimi-key-1")
    assert tool.provider == "kimi"


def test_web_search_builds_priority_fallback_candidate_for_geopolitical_news():
    tool = WebSearchTool(provider="google_news_rss")
    candidates = tool._build_news_query_candidates(
        "Adakah gejolak politik sekarang? Saya dengar ada konflik Iran vs US/Israel. Jawab ringkas dan sertakan sumber jika ada."
    )

    assert len(candidates) >= 2
    assert any(
        "iran" in candidate.lower()
        and "israel" in candidate.lower()
        and "us" in candidate.lower()
        and "news" in candidate.lower()
        for candidate in candidates
    )
    assert all("ringkas" not in candidate.lower() for candidate in candidates[1:])


@pytest.mark.asyncio
async def test_web_search_kimi_parses_text_and_sources(monkeypatch):
    payload = {
        "choices": [
            {
                "message": {
                    "content": "Kimi answer",
                    "annotations": [
                        {"url": "https://example.com/a"},
                        {"uri": "https://example.com/b"},
                    ],
                }
            }
        ],
        "citations": ["https://example.com/c"],
    }
    monkeypatch.setattr(
        "kabot.agent.tools.web_search.httpx.AsyncClient",
        lambda: _DummyAsyncClient(payload),
    )

    tool = WebSearchTool(
        provider="kimi",
        kimi_api_key="kimi-key-1",
        kimi_model="kimi-k2.5",
    )
    result = await tool.execute("kimi parsing query")

    assert "[Kimi]" in result
    assert "Kimi answer" in result
    assert "https://example.com/a" in result
    assert "https://example.com/c" in result


@pytest.mark.asyncio
async def test_web_search_kimi_fallback_to_brave(monkeypatch):
    tool = WebSearchTool(
        provider="kimi",
        kimi_api_key="kimi-key-1",
        api_key="brave-key-1",
    )

    async def _boom(query: str) -> str:
        raise RuntimeError("kimi unavailable")

    async def _brave(query: str, count: int) -> str:
        return "brave-fallback-ok"

    monkeypatch.setattr(tool, "_search_kimi", _boom)
    monkeypatch.setattr(tool, "_search_brave", _brave)

    result = await tool.execute("fallback query")
    assert "brave-fallback-ok" in result


@pytest.mark.asyncio
async def test_web_search_no_keys_falls_back_to_google_news_rss(monkeypatch):
    web_search_module._SEARCH_CACHE.clear()
    tool = WebSearchTool(
        provider="brave",
        api_key="",
        perplexity_api_key="",
        xai_api_key="",
        kimi_api_key="",
    )

    async def _rss(query: str, count: int) -> str:
        return f"rss-fallback-ok:{query}:{count}"

    monkeypatch.setattr(tool, "_search_google_news_rss", _rss)

    result = await tool.execute("latest news 2026 now", count=5)
    assert "rss-fallback-ok:latest news 2026 now:5" in result


@pytest.mark.asyncio
async def test_web_search_no_keys_general_query_returns_setup_hint(monkeypatch):
    web_search_module._SEARCH_CACHE.clear()
    tool = WebSearchTool(
        provider="brave",
        api_key="",
        perplexity_api_key="",
        xai_api_key="",
        kimi_api_key="",
    )

    async def _rss_should_not_run(query: str, count: int) -> str:
        raise AssertionError("google news rss fallback should not run for general web search")

    monkeypatch.setattr(tool, "_search_google_news_rss", _rss_should_not_run)

    result = await tool.execute("who is the ceo of microsoft", count=5)
    assert result == i18n_t(
        "web_search.provider_missing",
        "who is the ceo of microsoft",
        provider="brave",
    )


@pytest.mark.asyncio
async def test_web_search_google_news_rss_filters_irrelevant_items(monkeypatch):
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss><channel>
  <item>
    <title>US-Iran war risk rises after new strikes</title>
    <link>https://example.com/relevant</link>
    <pubDate>Wed, 04 Mar 2026 16:24:17 GMT</pubDate>
  </item>
  <item>
    <title>100 Lagu tentang Persahabatan Bahasa Inggris</title>
    <link>https://example.com/irrelevant</link>
    <pubDate>Tue, 24 Jun 2025 07:00:00 GMT</pubDate>
  </item>
</channel></rss>"""

    monkeypatch.setattr(
        "kabot.agent.tools.web_search.httpx.AsyncClient",
        lambda: _DummyRSSAsyncClient(xml),
    )

    tool = WebSearchTool(
        provider="google_news_rss",
        api_key="",
        perplexity_api_key="",
        xai_api_key="",
        kimi_api_key="",
    )

    result = await tool._search_google_news_rss("find news about iran war", count=5)
    assert "US-Iran war risk rises after new strikes" in result
    assert "100 Lagu tentang Persahabatan Bahasa Inggris" not in result


@pytest.mark.asyncio
async def test_web_search_google_news_rss_compacts_conversational_geopolitical_query(monkeypatch):
    requested_urls: list[str] = []
    raw_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss><channel>
  <item>
    <title>Unrelated lifestyle article</title>
    <link>https://example.com/irrelevant</link>
    <pubDate>Wed, 04 Mar 2026 16:24:17 GMT</pubDate>
  </item>
</channel></rss>"""
    compact_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss><channel>
  <item>
    <title>Iran war live: US and Israeli strikes widen conflict</title>
    <link>https://example.com/relevant</link>
    <pubDate>Fri, 06 Mar 2026 06:33:10 GMT</pubDate>
  </item>
</channel></rss>"""

    class _CapturingClient:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return None

        async def get(self, url, timeout=10.0):  # type: ignore[no-untyped-def]
            requested_urls.append(str(url))
            lowered = str(url).lower()
            if "iran" in lowered and "israel" in lowered and "conflict" in lowered and "please" not in lowered:
                return _DummyTextResponse(compact_xml)
            return _DummyTextResponse(raw_xml)

    monkeypatch.setattr(
        "kabot.agent.tools.web_search.httpx.AsyncClient",
        lambda: _CapturingClient(),
    )

    tool = WebSearchTool(
        provider="google_news_rss",
        api_key="",
        perplexity_api_key="",
        xai_api_key="",
        kimi_api_key="",
    )

    result = await tool._search_google_news_rss(
        "Is there political turmoil right now? I heard there is conflict between Iran and the US/Israel, please answer briefly and naturally.",
        count=5,
    )

    assert "Iran war live: US and Israeli strikes widen conflict" in result
    assert any("please" in item.lower() for item in requested_urls)
    assert any("conflict" in item.lower() and "please" not in item.lower() for item in requested_urls)
