"""Web search tool with multi-provider support (Brave, Perplexity, Grok)."""

import json
import os
from typing import Any

import httpx
from loguru import logger

from kabot.agent.tools.base import Tool
from kabot.agent.tools.web_cache import TTLCache

# Shared cache across searches
_SEARCH_CACHE = TTLCache(default_ttl_seconds=300)

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
PERPLEXITY_ENDPOINT = "https://api.perplexity.ai/chat/completions"
XAI_ENDPOINT = "https://api.x.ai/v1/responses"


class WebSearchTool(Tool):
    """Search the web using Brave, Perplexity, or Grok."""

    name = "web_search"
    description = "Search the web. Returns titles, URLs, and snippets."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "count": {"type": "integer", "description": "Results (1-10)", "minimum": 1, "maximum": 10}
        },
        "required": ["query"]
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
        cache_ttl_minutes: int = 5,
    ):
        self.brave_api_key = api_key or os.environ.get("BRAVE_API_KEY", "")
        self.max_results = max_results
        self.perplexity_api_key = perplexity_api_key or os.environ.get("PERPLEXITY_API_KEY", "")
        self.perplexity_model = perplexity_model
        self.xai_api_key = xai_api_key or os.environ.get("XAI_API_KEY", "")
        self.xai_model = xai_model
        self.cache_ttl = cache_ttl_minutes * 60

        # Auto-detect best available provider
        if provider == "brave":
            self.provider = provider
        elif provider == "perplexity" and self.perplexity_api_key:
            self.provider = "perplexity"
        elif provider == "grok" and self.xai_api_key:
            self.provider = "grok"
        else:
            # Fallback chain: configured → perplexity → grok → brave
            if self.perplexity_api_key:
                self.provider = "perplexity"
            elif self.xai_api_key:
                self.provider = "grok"
            else:
                self.provider = "brave"

    async def execute(self, query: str, count: int | None = None, **kwargs: Any) -> str:
        n = min(max(count or self.max_results, 1), 10)

        # Check cache
        cache_key = f"{self.provider}:{query}:{n}"
        cached = _SEARCH_CACHE.get(cache_key)
        if cached:
            return f"[cached] {cached}"

        try:
            if self.provider == "perplexity":
                result = await self._search_perplexity(query)
            elif self.provider == "grok":
                result = await self._search_grok(query)
            else:
                result = await self._search_brave(query, n)

            _SEARCH_CACHE.set(cache_key, result, self.cache_ttl)
            return result

        except Exception as e:
            logger.warning(f"Search failed with {self.provider}: {e}")
            # Fallback to Brave if premium provider fails
            if self.provider != "brave" and self.brave_api_key:
                try:
                    result = await self._search_brave(query, n)
                    _SEARCH_CACHE.set(cache_key, result, self.cache_ttl)
                    return result
                except Exception as e2:
                    return f"Error: All search providers failed. Last: {e2}"
            return f"Error: {e}"

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
        # Parse xAI Responses API format
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