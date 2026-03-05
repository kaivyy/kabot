"""Web search tool with multi-provider support (Brave, Perplexity, Grok, Kimi)."""

from __future__ import annotations

import os
import re
from html import unescape
from typing import Any
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import httpx
from loguru import logger

from kabot.agent.tools.base import Tool
from kabot.agent.tools.web_cache import TTLCache

# Shared cache across searches
_SEARCH_CACHE = TTLCache(default_ttl_seconds=300)

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
PERPLEXITY_ENDPOINT = "https://api.perplexity.ai/chat/completions"
XAI_ENDPOINT = "https://api.x.ai/v1/responses"
KIMI_ENDPOINT = "https://api.moonshot.ai/v1/chat/completions"
GOOGLE_NEWS_RSS_ENDPOINT = "https://news.google.com/rss/search"
_NEWS_QUERY_STOPWORDS = {
    "news",
    "latest",
    "breaking",
    "headline",
    "headlines",
    "berita",
    "terbaru",
    "terkini",
    "cari",
    "carikan",
    "search",
    "find",
    "cek",
    "check",
    "update",
    "now",
    "sekarang",
    "today",
}


class WebSearchTool(Tool):
    """Search the web using Brave, Perplexity, Grok, or Kimi."""

    name = "web_search"
    description = "Search the web. Returns titles, URLs, and snippets."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "count": {"type": "integer", "description": "Results (1-10)", "minimum": 1, "maximum": 10},
        },
        "required": ["query"],
    }

    def __init__(
        self,
        api_key: str | None = None,
        max_results: int = 5,
        provider: str = "brave",
        perplexity_api_key: str | None = None,
        perplexity_model: str = "sonar-pro",
        xai_api_key: str | None = None,
        xai_model: str = "grok-3-mini",
        kimi_api_key: str | None = None,
        kimi_model: str = "moonshot-v1-8k",
        cache_ttl_minutes: int = 5,
    ):
        self.brave_api_key = api_key or os.environ.get("BRAVE_API_KEY", "")
        self.max_results = max_results

        self.perplexity_api_key = perplexity_api_key or os.environ.get("PERPLEXITY_API_KEY", "")
        self.perplexity_model = perplexity_model

        self.xai_api_key = xai_api_key or os.environ.get("XAI_API_KEY", "")
        self.xai_model = xai_model

        self.kimi_api_key = (
            kimi_api_key
            or os.environ.get("KIMI_API_KEY", "")
            or os.environ.get("MOONSHOT_API_KEY", "")
        )
        self.kimi_model = kimi_model

        self.cache_ttl = cache_ttl_minutes * 60

        requested = (provider or "brave").strip().lower()
        if requested in {"auto", "default"}:
            self.provider = self._pick_provider()
        else:
            self.provider = self._pick_provider(preferred=requested)

    def _pick_provider(self, preferred: str | None = None) -> str:
        has_keys = {
            "perplexity": bool(self.perplexity_api_key),
            "grok": bool(self.xai_api_key),
            "kimi": bool(self.kimi_api_key),
            "brave": bool(self.brave_api_key),
        }

        if preferred == "brave":
            return "brave"
        if preferred == "perplexity" and has_keys["perplexity"]:
            return "perplexity"
        if preferred == "grok" and has_keys["grok"]:
            return "grok"
        if preferred == "kimi" and has_keys["kimi"]:
            return "kimi"
        if preferred == "google_news_rss":
            return "google_news_rss"

        if preferred and preferred not in {"brave", "perplexity", "grok", "kimi"}:
            logger.warning(f"Unknown web_search provider '{preferred}', using best available provider")

        for candidate in ("perplexity", "grok", "kimi"):
            if has_keys[candidate]:
                return candidate

        return "brave"

    def _fallback_candidates(self, exclude: str) -> list[str]:
        candidates: list[str] = []
        if self.perplexity_api_key:
            candidates.append("perplexity")
        if self.xai_api_key:
            candidates.append("grok")
        if self.kimi_api_key:
            candidates.append("kimi")
        if self.brave_api_key:
            candidates.append("brave")
        # No-key fallback for news/search queries.
        candidates.append("google_news_rss")

        return [name for name in candidates if name != exclude]

    async def _run_provider(self, provider: str, query: str, count: int) -> str:
        if provider == "perplexity":
            return await self._search_perplexity(query)
        if provider == "grok":
            return await self._search_grok(query)
        if provider == "kimi":
            return await self._search_kimi(query)
        if provider == "google_news_rss":
            return await self._search_google_news_rss(query, count)
        return await self._search_brave(query, count)

    async def execute(self, query: str, count: int | None = None, **kwargs: Any) -> str:
        n = min(max(count or self.max_results, 1), 10)

        cache_key = f"{self.provider}:{query}:{n}"
        cached = _SEARCH_CACHE.get(cache_key)
        if cached:
            return f"[cached] {cached}"

        try:
            result = await self._run_provider(self.provider, query, n)
            if isinstance(result, str) and result.strip().lower().startswith("error:"):
                raise RuntimeError(result)
            _SEARCH_CACHE.set(cache_key, result, self.cache_ttl)
            return result
        except Exception as e:
            logger.warning(f"Search failed with {self.provider}: {e}")
            last_error: Exception = e
            for fallback_provider in self._fallback_candidates(exclude=self.provider):
                try:
                    logger.info(f"Trying web_search fallback provider: {fallback_provider}")
                    result = await self._run_provider(fallback_provider, query, n)
                    if isinstance(result, str) and result.strip().lower().startswith("error:"):
                        raise RuntimeError(result)
                    _SEARCH_CACHE.set(cache_key, result, self.cache_ttl)
                    return result
                except Exception as fallback_error:
                    last_error = fallback_error
                    logger.warning(
                        f"Search fallback failed with {fallback_provider}: {fallback_error}"
                    )
            return f"Error: All search providers failed. Last: {last_error}"

    async def _search_brave(self, query: str, count: int) -> str:
        if not self.brave_api_key:
            return "Error: BRAVE_API_KEY not configured"

        async with httpx.AsyncClient() as client:
            r = await client.get(
                BRAVE_ENDPOINT,
                params={"q": query, "count": count},
                headers={"Accept": "application/json", "X-Subscription-Token": self.brave_api_key},
                timeout=10.0,
            )
            r.raise_for_status()

        results = r.json().get("web", {}).get("results", [])
        if not results:
            return f"No results for: {query}"

        lines = [f"Results for: {query}\n"]
        for i, item in enumerate(results[:count], 1):
            lines.append(f"{i}. {item.get('title', '')}\n   {item.get('url', '')}")
            if desc := item.get("description"):
                lines.append(f"   {desc}")
        return "\n".join(lines)

    async def _search_perplexity(self, query: str) -> str:
        if not self.perplexity_api_key:
            return "Error: PERPLEXITY_API_KEY not configured"

        async with httpx.AsyncClient() as client:
            r = await client.post(
                PERPLEXITY_ENDPOINT,
                json={
                    "model": self.perplexity_model,
                    "messages": [{"role": "user", "content": query}],
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.perplexity_api_key}",
                },
                timeout=30.0,
            )
            r.raise_for_status()

        data = r.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "No response")
        citations = data.get("citations", [])

        result = f"[Perplexity] {content}"
        if citations:
            result += "\n\nSources:\n" + "\n".join(f"- {url}" for url in citations[:5])
        return result

    async def _search_grok(self, query: str) -> str:
        if not self.xai_api_key:
            return "Error: XAI_API_KEY not configured"

        async with httpx.AsyncClient() as client:
            r = await client.post(
                XAI_ENDPOINT,
                json={
                    "model": self.xai_model,
                    "input": [{"role": "user", "content": query}],
                    "tools": [{"type": "web_search"}],
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.xai_api_key}",
                },
                timeout=30.0,
            )
            r.raise_for_status()

        data = r.json()
        text = ""
        for output in data.get("output", []):
            if output.get("type") == "message":
                for block in output.get("content", []):
                    if block.get("type") == "output_text":
                        text = block.get("text", "")
                        break
        if not text:
            text = data.get("output_text", "No response")

        citations = data.get("citations", [])
        result = f"[Grok] {text}"
        if citations:
            result += "\n\nSources:\n" + "\n".join(f"- {url}" for url in citations[:5])
        return result

    async def _search_kimi(self, query: str) -> str:
        if not self.kimi_api_key:
            return "Error: KIMI_API_KEY or MOONSHOT_API_KEY not configured"

        async with httpx.AsyncClient() as client:
            r = await client.post(
                KIMI_ENDPOINT,
                json={
                    "model": self.kimi_model,
                    "messages": [{"role": "user", "content": query}],
                    "tools": [{"type": "web_search"}],
                    "tool_choice": "auto",
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.kimi_api_key}",
                },
                timeout=30.0,
            )
            r.raise_for_status()

        data = r.json()
        message = data.get("choices", [{}])[0].get("message", {}) or {}
        content = self._extract_text_content(message.get("content"))
        if not content:
            content = self._extract_text_content(data.get("output_text")) or "No response"

        sources = self._extract_sources(data, message)
        result = f"[Kimi] {content}"
        if sources:
            result += "\n\nSources:\n" + "\n".join(f"- {url}" for url in sources[:5])
        return result

    def _extract_text_content(self, value: Any) -> str:
        if isinstance(value, str):
            return value.strip()

        if isinstance(value, dict):
            for key in ("text", "content", "output_text"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
            return ""

        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                extracted = self._extract_text_content(item)
                if extracted:
                    parts.append(extracted)
            return "\n".join(parts).strip()

        return ""

    def _extract_sources(self, payload: dict[str, Any], message: dict[str, Any]) -> list[str]:
        raw_sources: list[Any] = []
        raw_sources.extend(payload.get("citations", []) or [])
        raw_sources.extend(message.get("citations", []) or [])
        raw_sources.extend(message.get("annotations", []) or [])

        normalized: list[str] = []
        for item in raw_sources:
            if isinstance(item, str):
                candidate = item.strip()
            elif isinstance(item, dict):
                candidate = str(
                    item.get("url")
                    or item.get("uri")
                    or item.get("link")
                    or ""
                ).strip()
            else:
                candidate = ""

            if candidate:
                normalized.append(candidate)

        deduped: list[str] = []
        seen: set[str] = set()
        for url in normalized:
            if url in seen:
                continue
            seen.add(url)
            deduped.append(url)
        return deduped

    def _extract_relevance_terms(self, query: str) -> list[str]:
        terms: list[str] = []
        seen: set[str] = set()
        for token in re.findall(r"[^\W_]+", str(query or "").lower(), flags=re.UNICODE):
            cleaned = token.strip()
            if len(cleaned) < 3:
                continue
            if cleaned in _NEWS_QUERY_STOPWORDS:
                continue
            if cleaned in seen:
                continue
            seen.add(cleaned)
            terms.append(cleaned)
        return terms

    def _score_news_item(self, title: str, description: str, query_terms: list[str]) -> int:
        if not query_terms:
            return 0
        haystack = f"{title} {description}".lower()
        return sum(1 for term in query_terms if term in haystack)

    async def _search_google_news_rss(self, query: str, count: int) -> str:
        """Fallback search provider that works without API keys."""
        encoded_query = quote_plus(query)
        url = (
            f"{GOOGLE_NEWS_RSS_ENDPOINT}?q={encoded_query}"
            "&hl=en-US&gl=US&ceid=US:en"
        )
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10.0)
            r.raise_for_status()

        root = ET.fromstring(r.text)
        items = root.findall(".//item")
        if not items:
            return f"No results for: {query}"

        query_terms = self._extract_relevance_terms(query)
        ranked_items: list[tuple[int, int, str, str, str]] = []
        for item_index, item in enumerate(items):
            title = unescape((item.findtext("title") or "").strip())
            description = unescape((item.findtext("description") or "").strip())
            score = self._score_news_item(title, description, query_terms)
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            ranked_items.append((score, item_index, title, link, pub_date))

        if query_terms:
            relevant = [entry for entry in ranked_items if entry[0] > 0]
            if relevant:
                ranked_items = relevant
                ranked_items.sort(key=lambda item: (-item[0], item[1]))

        lines = [f"Results for: {query}\n"]
        for index, (_score, _item_index, title, link, pub_date) in enumerate(ranked_items[:count], 1):
            if title:
                lines.append(f"{index}. {title}")
            if link:
                lines.append(f"   {link}")
            if pub_date:
                lines.append(f"   Published: {pub_date}")
        return "\n".join(lines)
