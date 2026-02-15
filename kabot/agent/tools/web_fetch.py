"""Web fetch tool for calling HTTP APIs."""

from typing import Any
import httpx
from bs4 import BeautifulSoup
from kabot.agent.tools.base import Tool

MAX_CHARS_DEFAULT = 8000
MAX_CHARS_CAP = 50000
TIMEOUT_SECONDS = 30
USER_AGENT = "Kabot/1.0 (AI Assistant)"


class WebFetchTool(Tool):
    """Fetch content from HTTP URLs — web pages, APIs, files."""

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
        max_chars = min(max_chars, MAX_CHARS_CAP)
        req_headers = {"User-Agent": USER_AGENT}
        if headers:
            req_headers.update(headers)
        if body and content_type:
            req_headers["Content-Type"] = content_type

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
                    import json
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
                    text = text[:max_chars] + "\n\n[truncated]"

                status_line = f"HTTP {resp.status_code}"
                return f"{status_line}\n\n{text}"

        except httpx.TimeoutException:
            return f"Error: Request timed out after {TIMEOUT_SECONDS}s"
        except Exception as e:
            return f"Error: {type(e).__name__}: {str(e)}"

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
