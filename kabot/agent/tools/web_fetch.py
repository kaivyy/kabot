"""Web fetch tool for calling HTTP APIs."""

import hashlib
import ipaddress
import json
import socket
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from kabot.agent.tools.base import Tool
from kabot.agent.tools.web_cache import TTLCache

MAX_CHARS_DEFAULT = 8000
MAX_CHARS_CAP = 50000
TIMEOUT_SECONDS = 30
USER_AGENT = "Kabot/1.0 (AI Assistant)"


class WebFetchTool(Tool):
    """Fetch content from HTTP URLs — web pages, APIs, files."""

    def __init__(
        self,
        http_guard: Any | None = None,
        firecrawl_api_key: str | None = None,
        firecrawl_base_url: str = "https://api.firecrawl.dev",
        cache_ttl_minutes: int = 5,
    ):
        import os
        deny_defaults = {
            "localhost",
            "127.0.0.1",
            "169.254.169.254",
            "metadata.google.internal",
        }
        self.guard_enabled = True
        self.block_private_networks = True
        self.allow_hosts: set[str] = set()
        self.deny_hosts: set[str] = set(deny_defaults)

        if http_guard is not None:
            self.guard_enabled = bool(getattr(http_guard, "enabled", True))
            self.block_private_networks = bool(
                getattr(http_guard, "block_private_networks", True)
            )
            self.allow_hosts = {
                str(host).strip().lower()
                for host in (getattr(http_guard, "allow_hosts", []) or [])
                if str(host).strip()
            }
            configured_deny_hosts = getattr(http_guard, "deny_hosts", None)
            custom_deny = {
                str(host).strip().lower()
                for host in (configured_deny_hosts or [])
                if str(host).strip()
            }
            if configured_deny_hosts is not None:
                self.deny_hosts = custom_deny

        self.firecrawl_api_key = firecrawl_api_key or os.environ.get("FIRECRAWL_API_KEY", "")
        self.firecrawl_base_url = firecrawl_base_url
        self._cache = TTLCache(default_ttl_seconds=cache_ttl_minutes * 60)

    def _wrap_external_content(self, text: str, source_url: str) -> str:
        """Wrap fetched content to mark it as untrusted external data."""
        return (
            "[EXTERNAL_CONTENT]\n"
            f"{text}\n"
            f"[/EXTERNAL_CONTENT]"
        )

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
                trunc_suffix = "\\n\\n[truncated]"
                keep = max(0, max_chars - len(trunc_suffix))
                md = md[:keep] + trunc_suffix
            return md if md else None
        except Exception as e:
            logger.warning(f"FireCrawl fallback failed: {e}")
            return None
    
    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return """Fetch content from an HTTP/HTTPS URL.

Supports:
- GET/POST/PUT/PATCH/DELETE methods
- JSON and HTML content (auto-extracts readable text from HTML)
- Custom headers (e.g. Authorization, API keys)
- Request body for POST/PUT
- Content truncation with max_chars

Use this for:
- Calling REST APIs (weather, stocks, EV car APIs, etc.)
- Reading web pages
- Checking webhook endpoints"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "HTTP or HTTPS URL to fetch"
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                    "description": "HTTP method (default: GET)"
                },
                "headers": {
                    "type": "object",
                    "description": "Custom HTTP headers (e.g. {\"Authorization\": \"Bearer ...\"})"
                },
                "body": {
                    "type": "string",
                    "description": "Request body (for POST/PUT/PATCH)"
                },
                "content_type": {
                    "type": "string",
                    "description": "Content-Type header for body (default: application/json)"
                },
                "extract_mode": {
                    "type": "string",
                    "enum": ["markdown", "text", "json", "raw", "auto"],
                    "description": "How to extract content (default: auto - markdown for HTML, json for APIs)"
                },
                "max_chars": {
                    "type": "integer",
                    "description": f"Max characters to return (default: {MAX_CHARS_DEFAULT})"
                },
            },
            "required": ["url"]
        }

    async def execute(
        self,
        url: str,
        method: str = "GET",
        headers: dict | None = None,
        body: str | None = None,
        content_type: str = "application/json",
        extract_mode: str = "auto",
        max_chars: int = MAX_CHARS_DEFAULT,
        **kwargs: Any,
    ) -> str:
        try:
            self._validate_target(url)
        except ValueError as e:
            return f"Error: {e}"

        max_chars = min(max_chars, MAX_CHARS_CAP)
        req_headers = {"User-Agent": USER_AGENT}
        if headers:
            req_headers.update(headers)
        if body and content_type:
            req_headers["Content-Type"] = content_type

        cache_payload = {
            "method": method,
            "url": url,
            "extract_mode": extract_mode,
            "max_chars": max_chars,
            "content_type": content_type,
            "headers": req_headers,
            "body": body or "",
        }
        cache_key = (
            f"{method}:{url}:"
            f"{hashlib.sha256(json.dumps(cache_payload, sort_keys=True).encode('utf-8')).hexdigest()}"
        )
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        try:
            async with httpx.AsyncClient(
                timeout=TIMEOUT_SECONDS, follow_redirects=True
            ) as client:
                resp = await client.request(
                    method, url, headers=req_headers,
                    content=body.encode() if body else None,
                )

                ct = resp.headers.get("content-type", "")
                raw_text = resp.text

                # Auto-detect extract mode
                if extract_mode == "auto":
                    if "json" in ct:
                        extract_mode = "json"
                    elif "html" in ct:
                        extract_mode = "markdown"
                    else:
                        extract_mode = "text"

                # Extract content
                if extract_mode == "json":
                    try:
                        data = resp.json()
                        text = json.dumps(data, indent=2, ensure_ascii=False)
                    except Exception:
                        text = raw_text
                elif extract_mode == "markdown":
                    text = self._html_to_markdown(raw_text)
                elif extract_mode == "raw":
                    text = raw_text
                else:
                    text = self._extract_text(raw_text)

                # Truncate
                if len(text) > max_chars:
                    trunc_suffix = "\n\n[truncated]"
                    keep = max(0, max_chars - len(trunc_suffix))
                    text = text[:keep] + trunc_suffix

                # After extraction, check if content is suspiciously empty
                if extract_mode == "markdown" and len(text.strip()) < 100 and self.firecrawl_api_key:
                    firecrawl_result = await self._fetch_firecrawl(url, max_chars)
                    if firecrawl_result:
                        text = firecrawl_result

                # Wrap external content to prevent prompt injection
                text = self._wrap_external_content(text, url)

                status_line = f"HTTP {resp.status_code}"
                result = f"{status_line}\n\n{text}"
                self._cache.set(cache_key, result)
                return result

        except httpx.TimeoutException:
            return f"Error: Request timed out after {TIMEOUT_SECONDS}s"
        except Exception as e:
            return f"Error: {type(e).__name__}: {str(e)}"

    def _validate_target(self, url: str) -> None:
        if not self.guard_enabled:
            return

        parsed = urlparse(url)
        scheme = (parsed.scheme or "").lower()
        if scheme not in {"http", "https"}:
            raise ValueError("Only HTTP/HTTPS URLs are supported")

        host = (parsed.hostname or "").strip().lower()
        if not host:
            raise ValueError("Missing URL host")

        if self.allow_hosts and host not in self.allow_hosts:
            raise ValueError(f"Host '{host}' is not in allowlist")

        if host in self.deny_hosts:
            raise ValueError(f"Target blocked by network guard: {host}")

        if self.block_private_networks and self._is_private_or_local_host(host):
            raise ValueError(f"Target blocked by network guard: {host}")

    def _is_private_or_local_host(self, host: str) -> bool:
        if host in {"localhost", "::1"}:
            return True

        if self._is_private_ip(host):
            return True

        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror:
            return False
        except Exception:
            return False

        for info in infos:
            addr = info[4][0]
            if self._is_private_ip(addr):
                return True
        return False

    def _is_private_ip(self, value: str) -> bool:
        try:
            ip = ipaddress.ip_address(value)
        except ValueError:
            return False

        return bool(
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )

    def _html_to_markdown(self, html: str) -> str:
        """Convert HTML to readable markdown-ish text."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            # Remove script/style
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            return soup.get_text(separator="\n", strip=True)
        except Exception:
            return html

    def _extract_text(self, content: str) -> str:
        """Extract plain text from content."""
        if "<" in content and ">" in content:
            return self._html_to_markdown(content)
        return content
