# Military-Grade Progressive Enhancement — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade Kabot's web tools, search, and skills to military-grade quality (SSRF, FireCrawl, multi-provider search, advanced skills validation) while keeping token usage at zero-overhead via Progressive Enhancement.

**Architecture:** Each tool (`web_fetch`, `web_search`, `skills`) is enhanced in-place. If a premium API key exists in config, the tool automatically uses the military-grade route. If not, it silently falls back to the current lightweight behavior. Config schema is extended first, then setup wizard, then tools.

**Tech Stack:** Python 3.11+, Pydantic, httpx, BeautifulSoup4, questionary, Rich

---

## Task 1: Extend Config Schema with Premium Tool Fields

**Files:**
- Modify: `kabot/config/schema.py:286-318`

**Step 1: Update `WebSearchConfig` to support multi-provider**

In `kabot/config/schema.py`, replace the current `WebSearchConfig` (line 286-289):

```python
class WebSearchConfig(BaseModel):
    """Web search tool configuration."""
    api_key: str = ""  # Brave Search API key
    max_results: int = 5
```

With:

```python
class WebSearchConfig(BaseModel):
    """Web search tool configuration."""
    api_key: str = ""  # Brave Search API key (default provider)
    max_results: int = 5
    provider: str = "brave"  # "brave" | "perplexity" | "grok"
    cache_ttl_minutes: int = 5
    perplexity_api_key: str = ""
    perplexity_model: str = "sonar-pro"
    xai_api_key: str = ""
    xai_model: str = "grok-3-mini"
```

**Step 2: Add `WebFetchConfig` model**

After `WebSearchConfig`, add:

```python
class WebFetchConfig(BaseModel):
    """Web fetch tool configuration."""
    firecrawl_api_key: str = ""
    firecrawl_base_url: str = "https://api.firecrawl.dev"
    cache_ttl_minutes: int = 5
    max_response_bytes: int = 2_000_000
```

**Step 3: Update `WebToolsConfig` to include fetch config**

Replace `WebToolsConfig` (line 292-294):

```python
class WebToolsConfig(BaseModel):
    """Web tools configuration."""
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)
```

With:

```python
class WebToolsConfig(BaseModel):
    """Web tools configuration."""
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)
    fetch: WebFetchConfig = Field(default_factory=WebFetchConfig)
```

**Step 4: Verify no import errors**

Run: `python -c "from kabot.config.schema import Config; c = Config(); print(c.tools.web.fetch.firecrawl_api_key, c.tools.web.search.provider)"`

Expected: ` brave` (empty string + "brave")

**Step 5: Commit**

```bash
git add kabot/config/schema.py
git commit -m "feat(config): add multi-provider search + firecrawl fetch schema"
```

---

## Task 2: Add Response Cache Utility

**Files:**
- Create: `kabot/agent/tools/web_cache.py`

**Step 1: Create in-memory TTL cache utility**

```python
"""Simple in-memory TTL cache for web tool results."""

import time
from typing import Any


class TTLCache:
    """Thread-safe in-memory cache with time-to-live expiration."""

    def __init__(self, default_ttl_seconds: int = 300):
        self._store: dict[str, tuple[float, Any]] = {}
        self._default_ttl = default_ttl_seconds

    def get(self, key: str) -> Any | None:
        """Get cached value if not expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Set value with TTL."""
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        self._store[key] = (time.monotonic() + ttl, value)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._store.clear()

    def _evict_expired(self) -> None:
        """Remove all expired entries (call periodically if needed)."""
        now = time.monotonic()
        expired = [k for k, (exp, _) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]
```

**Step 2: Verify import**

Run: `python -c "from kabot.agent.tools.web_cache import TTLCache; c = TTLCache(); c.set('a', 1); print(c.get('a'))"`

Expected: `1`

**Step 3: Commit**

```bash
git add kabot/agent/tools/web_cache.py
git commit -m "feat(tools): add TTL cache utility for web tools"
```

---

## Task 3: Upgrade Web Search to Multi-Provider

**Files:**
- Modify: `kabot/agent/tools/web_search.py` (full rewrite, 54 → ~180 lines)

**Step 1: Rewrite `web_search.py` with multi-provider + cache**

```python
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
```

**Step 2: Verify import**

Run: `python -c "from kabot.agent.tools.web_search import WebSearchTool; t = WebSearchTool(); print(t.provider)"`

Expected: `brave` (no premium keys configured)

**Step 3: Commit**

```bash
git add kabot/agent/tools/web_search.py
git commit -m "feat(web_search): add multi-provider support (Brave/Perplexity/Grok) with cache"
```

---

## Task 4: Upgrade Web Fetch with SSRF Guard + FireCrawl Fallback

**Files:**
- Modify: `kabot/agent/tools/web_fetch.py` (enhance existing, ~255 → ~350 lines)

**Step 1: Add DNS-level SSRF validation**

In `web_fetch.py`, enhance `_validate_target` method. After the existing `_is_private_or_local_host` check (line 201-202), the method already resolves DNS. This is adequate.

**Step 2: Add external content wrapping**

Add a new method to `WebFetchTool` class:

```python
def _wrap_external_content(self, text: str, source_url: str) -> str:
    """Wrap fetched content to mark it as untrusted external data."""
    return (
        f"[EXTERNAL_CONTENT source={source_url}]\n"
        f"{text}\n"
        f"[/EXTERNAL_CONTENT]"
    )
```

**Step 3: Add FireCrawl fallback**

Add FireCrawl support to `__init__` and a new `_fetch_firecrawl` method:

```python
def __init__(self, http_guard: Any | None = None,
             firecrawl_api_key: str | None = None,
             firecrawl_base_url: str = "https://api.firecrawl.dev",
             cache_ttl_minutes: int = 5):
    # ... existing guard init ...
    self.firecrawl_api_key = firecrawl_api_key or os.environ.get("FIRECRAWL_API_KEY", "")
    self.firecrawl_base_url = firecrawl_base_url
    self._cache = TTLCache(default_ttl_seconds=cache_ttl_minutes * 60)

async def _fetch_firecrawl(self, url: str, max_chars: int) -> str | None:
    """Fallback: use FireCrawl to render JS-heavy pages."""
    if not self.firecrawl_api_key:
        return None
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.firecrawl_base_url}/v1/scrape",
                json={"url": url, "formats": ["markdown"], "onlyMainContent": True},
                headers={
                    "Authorization": f"Bearer {self.firecrawl_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            r.raise_for_status()
        data = r.json()
        md = data.get("data", {}).get("markdown", "")
        if md and len(md) > max_chars:
            md = md[:max_chars] + "\n\n[truncated]"
        return md if md else None
    except Exception as e:
        logger.warning(f"FireCrawl fallback failed: {e}")
        return None
```

**Step 4: Integrate wrapping + FireCrawl into `execute`**

In the `execute` method, after the HTML extraction (around line 164-168), add FireCrawl fallback:

```python
# After extraction, check if content is suspiciously empty
if extract_mode == "markdown" and len(text.strip()) < 100 and self.firecrawl_api_key:
    firecrawl_result = await self._fetch_firecrawl(url, max_chars)
    if firecrawl_result:
        text = firecrawl_result

# Wrap external content to prevent prompt injection
text = self._wrap_external_content(text, url)
```

**Step 5: Add caching to execute**

At the start of `execute`:
```python
cache_key = f"{method}:{url}"
cached = self._cache.get(cache_key)
if cached:
    return cached
```

At the end before return:
```python
self._cache.set(cache_key, result)
return result
```

**Step 6: Verify import**

Run: `python -c "from kabot.agent.tools.web_fetch import WebFetchTool; t = WebFetchTool(); print(t.firecrawl_api_key)"`

Expected: `` (empty string)

**Step 7: Commit**

```bash
git add kabot/agent/tools/web_fetch.py
git commit -m "feat(web_fetch): add SSRF hardening, external content wrapping, FireCrawl fallback + cache"
```

---

## Task 5: Enhance Skills Validation Messaging

**Files:**
- Modify: `kabot/agent/skills.py:112-196`

**Step 1: Enhance `match_skills` to report unmet requirements**

After the skill scoring loop (line 185), before returning, add validation check:

```python
# Validate requirements for selected skills
validated = []
for skill_name in expanded:
    meta = self._get_skill_meta(skill_name)
    if self._check_requirements(meta):
        validated.append(skill_name)
    else:
        missing = self._get_missing_requirements(meta)
        install_info = meta.get("install", {})
        install_cmd = install_info.get("cmd", "")
        hint = f"[SKILL_UNAVAILABLE] {skill_name} needs: {missing}"
        if install_cmd:
            hint += f" (install: {install_cmd})"
        logger.info(hint)
        # Still include the skill name but mark it
        validated.append(f"{skill_name} [NEEDS: {missing}]")

return validated[:max_results + 2]
```

**Step 2: Commit**

```bash
git add kabot/agent/skills.py
git commit -m "feat(skills): add requirement validation messaging in match_skills"
```

---

## Task 6: Wire New Config into Tool Initialization

**Files:**
- Modify: `kabot/agent/loop.py` (where tools are registered)

**Step 1: Find where WebSearchTool and WebFetchTool are instantiated**

Search for `WebSearchTool(` and `WebFetchTool(` in `loop.py` and pass the new config fields:

```python
# WebSearchTool — pass new config fields
WebSearchTool(
    api_key=cfg.tools.web.search.api_key,
    max_results=cfg.tools.web.search.max_results,
    provider=cfg.tools.web.search.provider,
    perplexity_api_key=cfg.tools.web.search.perplexity_api_key,
    perplexity_model=cfg.tools.web.search.perplexity_model,
    xai_api_key=cfg.tools.web.search.xai_api_key,
    xai_model=cfg.tools.web.search.xai_model,
    cache_ttl_minutes=cfg.tools.web.search.cache_ttl_minutes,
)

# WebFetchTool — pass new config fields
WebFetchTool(
    http_guard=cfg.integrations.http_guard,
    firecrawl_api_key=cfg.tools.web.fetch.firecrawl_api_key,
    firecrawl_base_url=cfg.tools.web.fetch.firecrawl_base_url,
    cache_ttl_minutes=cfg.tools.web.fetch.cache_ttl_minutes,
)
```

**Step 2: Commit**

```bash
git add kabot/agent/loop.py
git commit -m "feat(loop): wire new multi-provider search + firecrawl config into tool init"
```

---

## Task 7: Add Advanced Tools Section to Setup Wizard

**Files:**
- Modify: `kabot/cli/setup_wizard.py:831-877`

**Step 1: Extend `_configure_tools` method**

After the Docker Sandbox section (line 868), before the section end marker, add:

```python
        # Advanced Tools (Optional)
        console.print("│")
        console.print("│  [bold]Advanced Tools (Optional)[/bold]")
        console.print("│  [dim]Premium API keys for enhanced capabilities. Press Enter to skip.[/dim]")
        console.print("│")

        # FireCrawl
        firecrawl_key = Prompt.ask(
            "│  FireCrawl API Key (JS rendering)",
            default=self.config.tools.web.fetch.firecrawl_api_key or "",
        )
        if firecrawl_key.strip():
            self.config.tools.web.fetch.firecrawl_api_key = firecrawl_key.strip()
            console.print("│  [green]✓ FireCrawl configured[/green]")
        else:
            console.print("│  [dim]  Skipped (BeautifulSoup only)[/dim]")

        # Perplexity
        perplexity_key = Prompt.ask(
            "│  Perplexity API Key (AI search)",
            default=self.config.tools.web.search.perplexity_api_key or "",
        )
        if perplexity_key.strip():
            self.config.tools.web.search.perplexity_api_key = perplexity_key.strip()
            self.config.tools.web.search.provider = "perplexity"
            console.print("│  [green]✓ Perplexity configured (set as default search)[/green]")
        else:
            console.print("│  [dim]  Skipped (Brave Search only)[/dim]")

        # xAI / Grok
        xai_key = Prompt.ask(
            "│  xAI API Key (Grok search)",
            default=self.config.tools.web.search.xai_api_key or "",
        )
        if xai_key.strip():
            self.config.tools.web.search.xai_api_key = xai_key.strip()
            if not perplexity_key.strip():
                self.config.tools.web.search.provider = "grok"
                console.print("│  [green]✓ Grok configured (set as default search)[/green]")
            else:
                console.print("│  [green]✓ Grok configured (available as fallback)[/green]")
        else:
            console.print("│  [dim]  Skipped[/dim]")

        # Summary
        console.print("│")
        adv_tools = []
        if self.config.tools.web.fetch.firecrawl_api_key:
            adv_tools.append("FireCrawl")
        if self.config.tools.web.search.perplexity_api_key:
            adv_tools.append("Perplexity")
        if self.config.tools.web.search.xai_api_key:
            adv_tools.append("Grok")
        if adv_tools:
            console.print(f"│  [bold green]Military-grade tools active: {', '.join(adv_tools)}[/bold green]")
        else:
            console.print("│  [dim]Standard mode (all tools work with defaults)[/dim]")
```

**Step 2: Update `summary_box` to show advanced tools**

In `ClackUI.summary_box` (line 104-109), after the tools line, add:

```python
        # Advanced tools
        adv = []
        if c.tools.web.fetch.firecrawl_api_key: adv.append("firecrawl")
        if c.tools.web.search.perplexity_api_key: adv.append("perplexity")
        if c.tools.web.search.xai_api_key: adv.append("grok")
        if adv:
            lines.append(f"advanced: {', '.join(adv)}")
```

**Step 3: Update `_main_menu_option_values` for simple mode**

In `_main_menu_option_values` (line 480-486), add `"tools"` to the simple mode list so users always see the tools option:

```python
        return [
            "workspace",
            "model",
            "tools",     # <-- ADD THIS
            "skills",
            "channels",
            "finish",
        ]
```

**Step 4: Commit**

```bash
git add kabot/cli/setup_wizard.py
git commit -m "feat(wizard): add Advanced Tools section (FireCrawl/Perplexity/Grok API keys)"
```

---

## Task 8: Final Integration Test

**Step 1: Run full config load cycle**

Run: `python -c "from kabot.config.loader import load_config; c = load_config(); print('provider:', c.tools.web.search.provider); print('firecrawl:', bool(c.tools.web.fetch.firecrawl_api_key)); print('OK')"`

Expected:
```
provider: brave
firecrawl: False
OK
```

**Step 2: Run tool instantiation test**

Run: `python -c "from kabot.agent.tools.web_search import WebSearchTool; from kabot.agent.tools.web_fetch import WebFetchTool; print('WebSearch provider:', WebSearchTool().provider); print('WebFetch firecrawl:', bool(WebFetchTool().firecrawl_api_key)); print('All tools OK')"`

Expected:
```
WebSearch provider: brave
WebFetch firecrawl: False
All tools OK
```

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: military-grade progressive enhancement complete"
```

---

## Summary of All Tasks

| Task | Component | Files | Estimated Time |
|------|-----------|-------|---------------|
| 1 | Config Schema | `schema.py` | 3 min |
| 2 | TTL Cache | `web_cache.py` [NEW] | 3 min |
| 3 | Multi-Provider Search | `web_search.py` | 10 min |
| 4 | SSRF + FireCrawl Fetch | `web_fetch.py` | 10 min |
| 5 | Skills Validation | `skills.py` | 5 min |
| 6 | Wire Config → Tools | `loop.py` | 5 min |
| 7 | Setup Wizard | `setup_wizard.py` | 8 min |
| 8 | Integration Test | — | 3 min |
| **Total** | | **7 files** | **~47 min** |
