"""Browser automation tool using Playwright."""

from pathlib import Path
from typing import Any, Optional

from loguru import logger
try:
    from playwright.async_api import async_playwright as _async_playwright
except ModuleNotFoundError:  # pragma: no cover - environment-dependent
    _async_playwright = None

from kabot.agent.tools.base import Tool


class BrowserTool(Tool):
    """Tool for web browsing and screenshots using Playwright."""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return (
            "Advanced Web Explorer using Playwright. "
            "Supported actions: launch, goto, screenshot, get_content, get_dom_snapshot, click, fill, close. "
            "Use get_dom_snapshot to see what elements are clickable on the screen along with their CSS selectors."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform: launch, goto, screenshot, get_content, get_dom_snapshot, click, fill, close",
                    "enum": ["launch", "goto", "screenshot", "get_content", "get_dom_snapshot", "click", "fill", "close"]
                },
                "url": {
                    "type": "string",
                    "description": "URL to navigate to (required for goto)"
                },
                "path": {
                    "type": "string",
                    "description": "File path to save screenshot (default: screenshot.png)"
                },
                "headless": {
                    "type": "boolean",
                    "description": "Whether to run browser in headless mode (default: true)"
                },
                "selector": {
                    "type": "string",
                    "description": "CSS Selector to target (required for click, fill)"
                },
                "text": {
                    "type": "string",
                    "description": "Text to input into a field (required for fill)"
                }
            },
            "required": ["action"]
        }

    async def execute(self, action: str, url: Optional[str] = None, **kwargs) -> Any:
        """Execute browser actions."""
        try:
            if action == "launch":
                return await self._launch(**kwargs)

            if not self.page:
                await self._launch()

            if action == "goto":
                if not url:
                    return "Error: URL is required for goto action."
                await self.page.goto(url, wait_until="networkidle")
                return f"Successfully navigated to {url}"

            elif action == "screenshot":
                output_path = self._resolve_output_path(kwargs.get("path", "screenshot.png"))
                await self.page.screenshot(path=str(output_path), full_page=True)
                return f"Screenshot saved to {output_path}"

            elif action == "get_content":
                # Simple extraction of text
                text = await self.page.evaluate("document.body.innerText")
                return f"URL: {self.page.url}\nTitle: {await self.page.title()}\nContent:\n{text[:5000]}"

            elif action == "get_dom_snapshot":
                # Inject JS to extract interactive elements and their selectors
                script = """
                () => {
                    const elements = Array.from(document.querySelectorAll('a, button, input, select, textarea, [role="button"]'));
                    let result = [];
                    for(let el of elements) {
                        let text = el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '';
                        text = text.trim();
                        // simplistic selector generation
                        let selector = el.tagName.toLowerCase();
                        if (el.id) { selector += '#' + el.id; }
                        else if (el.className && typeof el.className === 'string') { selector += '.' + el.className.split(' ').join('.'); }
                        if (text && text.length > 0) {
                            result.push(`[${selector}] -> ${text.substring(0, 50)}`);
                        }
                    }
                    return result.join('\\n');
                }
                """
                dom_tree = await self.page.evaluate(script)
                return f"URL: {self.page.url}\\nInteractive Elements:\\n{dom_tree}"

            elif action == "click":
                selector = kwargs.get("selector")
                if not selector:
                    return "Error: 'selector' is required for click action."
                await self.page.click(selector, timeout=5000)
                await self.page.wait_for_load_state("networkidle", timeout=5000)
                return f"Successfully clicked {selector}"

            elif action == "fill":
                selector = kwargs.get("selector")
                text_input = kwargs.get("text")
                if not selector or not text_input:
                    return "Error: 'selector' and 'text' are required for fill action."
                await self.page.fill(selector, str(text_input), timeout=5000)
                return f"Successfully filled {selector} with '{text_input}'"

            elif action == "close":
                await self._cleanup()
                return "Browser closed."

            else:
                return f"Unknown action: {action}"

        except Exception as e:
            logger.error(f"Browser error: {e}")
            return f"Error during browser action '{action}': {str(e)}"

    async def _launch(self, headless: bool = True, **kwargs):
        """Lazy initialization of browser."""
        if not self.playwright:
            if _async_playwright is None:
                raise RuntimeError(
                    "Playwright is not installed. Install with `pip install playwright` "
                    "and run `playwright install` before using browser tool."
                )
            self.playwright = await _async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=headless)
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
        return "Browser launched."

    @staticmethod
    def _resolve_output_path(value: str) -> Path:
        raw = str(value or "screenshot.png").strip() or "screenshot.png"
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path)
        path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    async def _cleanup(self):
        """Close browser resources."""
        if self.page:
            await self.page.close()
            self.page = None
        if self.context:
            await self.context.close()
            self.context = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
