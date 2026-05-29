"""Chrome DevTools Protocol (CDP) browser controller for autonomous browsing."""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from nexus import config

logger = logging.getLogger(__name__)


class CDPBrowserController:
    """Controls an existing Chrome instance via Chrome DevTools Protocol."""

    def __init__(self, debug_port: int = None):
        self.debug_port = debug_port or config.CHROME_DEBUG_PORT
        self.host = "127.0.0.1"
        self._ws = None
        self._target_id = None
        self._session_id = None
        self._msg_id = 0
        self._client = httpx.Client(timeout=10.0)

    def _cdp_url(self, path: str) -> str:
        return f"http://{self.host}:{self.debug_port}{path}"

    def is_connected(self) -> bool:
        """Check if Chrome is running with remote debugging."""
        try:
            resp = self._client.get(self._cdp_url("/json/version"))
            return resp.status_code == 200
        except Exception:
            return False

    def get_targets(self) -> List[Dict]:
        """Get list of browser targets (tabs/pages)."""
        try:
            resp = self._client.get(self._cdp_url("/json/list"))
            return resp.json()
        except Exception:
            return []

    def _get_or_create_target(self) -> Optional[str]:
        """Get the first page target or create a new one."""
        targets = self.get_targets()
        # Find existing page target
        for t in targets:
            if t.get("type") == "page":
                return t["id"]

        # Create new tab
        try:
            resp = self._client.get(self._cdp_url("/json/new?"))
            data = resp.json()
            return data.get("id")
        except Exception:
            return None

    async def _send_cdp_command(self, method: str, params: Dict = None) -> Dict:
        """Send a CDP command via WebSocket and return the result."""
        import websockets

        if not self._target_id:
            self._target_id = self._get_or_create_target()
            if not self._target_id:
                return {"error": "No Chrome target available. Start Chrome with --remote-debugging-port=9222"}

        # Connect to target's WebSocket
        ws_url = f"ws://{self.host}:{self.debug_port}/devtools/page/{self._target_id}"

        try:
            async with websockets.connect(ws_url, max_size=10 * 1024 * 1024) as ws:
                self._msg_id += 1
                msg = {"id": self._msg_id, "method": method, "params": params or {}}
                await ws.send(json.dumps(msg))

                # Read responses until we get our answer
                while True:
                    response = await asyncio.wait_for(ws.recv(), timeout=15)
                    data = json.loads(response)
                    if data.get("id") == self._msg_id:
                        return data

        except asyncio.TimeoutError:
            return {"error": f"Timeout executing {method}"}
        except Exception as e:
            return {"error": f"CDP connection failed: {str(e)}"}

    async def navigate(self, url: str) -> str:
        """Navigate to a URL."""
        result = await self._send_cdp_command("Page.navigate", {"url": url})
        if "error" in result:
            return f"Error navigating: {result['error']}"
        frame_id = result.get("result", {}).get("frameId", "")
        await asyncio.sleep(2)  # Wait for page load
        return f"Navigated to {url}"

    async def evaluate_js(self, expression: str) -> Any:
        """Evaluate JavaScript in the page and return the result."""
        result = await self._send_cdp_command("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True
        })
        if "error" in result:
            return f"Error: {result['error']}"
        return result.get("result", {}).get("result", {}).get("value")

    async def click_element(self, selector: str) -> str:
        """Click an element matching a CSS selector."""
        js = f"""
        (function() {{
            const el = document.querySelector('{selector}');
            if (!el) return 'Element not found: {selector}';
            el.click();
            return 'Clicked: {selector}';
        }})()
        """
        result = await self.evaluate_js(js)
        return str(result) if result else f"Clicked: {selector}"

    async def type_text(self, selector: str, text: str, submit: bool = False) -> str:
        """Type text into an element, optionally pressing Enter."""
        js_code = f"""
        (function() {{
            const el = document.querySelector('{selector}');
            if (!el) return 'Element not found: {selector}';
            el.focus();
            el.value = '{text.replace("'", "\\'")}';
            el.dispatchEvent(new Event('input', {{bubbles: true}}));
            el.dispatchEvent(new Event('change', {{bubbles: true}}));
            {'el.form?.submit();' if submit else ''}
            return 'Typed into {selector}';
        }})()
        """
        result = await self.evaluate_js(js_code)
        return str(result) if result else f"Typed '{text}' into {selector}"

    async def extract_text(self) -> str:
        """Extract visible text from the current page."""
        js = "document.body.innerText.substring(0, 5000)"
        result = await self.evaluate_js(js)
        return str(result)[:5000] if result else "No text found"

    async def extract_links(self) -> str:
        """Extract all links from the page."""
        js = """
        (function() {
            const links = Array.from(document.querySelectorAll('a[href]'));
            return links.slice(0, 20).map(a => a.href + ' | ' + (a.textContent || '').trim().substring(0, 50)).join('\\n');
        })()
        """
        result = await self.evaluate_js(js)
        return str(result) if result else "No links found"

    async def get_page_title(self) -> str:
        """Get the current page title."""
        result = await self.evaluate_js("document.title")
        return str(result) if result else "No title"

    async def get_current_url(self) -> str:
        """Get the current page URL."""
        result = await self.evaluate_js("window.location.href")
        return str(result) if result else "No URL"

    async def scroll_page(self, direction: str = "down", amount: int = 500) -> str:
        """Scroll the page."""
        if direction == "up":
            js = f"window.scrollBy(0, -{amount})"
        else:
            js = f"window.scrollBy(0, {amount})"
        await self.evaluate_js(js)
        return f"Scrolled {direction} by {amount}px"

    async def take_screenshot(self) -> str:
        """Take a screenshot and return base64 data."""
        result = await self._send_cdp_command("Page.captureScreenshot", {
            "format": "jpeg",
            "quality": 50
        })
        if "error" in result:
            return f"Error: {result['error']}"
        data = result.get("result", {}).get("data", "")
        return f"data:image/jpeg;base64,{data}" if data else "Screenshot failed"

    async def search_google(self, query: str) -> str:
        """Search Google and extract results."""
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        await self.navigate(search_url)
        await asyncio.sleep(2)

        js = """
        (function() {
            const results = [];
            document.querySelectorAll('div.g, div[data-ved]').forEach(el => {
                const h3 = el.querySelector('h3');
                const a = el.querySelector('a[href]');
                if (h3 && a && a.href && !a.href.includes('google.com/search')) {
                    results.push(h3.innerText + ' | ' + a.href);
                }
            });
            return results.slice(0, 8).join('\\n');
        })()
        """
        result = await self.evaluate_js(js)
        return str(result) if result else "No results found"

    async def search_youtube(self, query: str) -> str:
        """Search YouTube and return top video links."""
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        await self.navigate(search_url)
        await asyncio.sleep(3)

        js = """
        (function() {
            const videos = [];
            document.querySelectorAll('a#video-title, ytd-video-renderer a#video-title').forEach(el => {
                if (el.href && el.href.includes('watch')) {
                    videos.push(el.innerText.trim() + ' | ' + el.href);
                }
            });
            return videos.slice(0, 5).join('\\n');
        })()
        """
        result = await self.evaluate_js(js)
        return str(result) if result else "No videos found"

    async def play_youtube_video(self, query: str) -> str:
        """Search YouTube and click the first video to play it."""
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        await self.navigate(search_url)
        await asyncio.sleep(3)

        # Click first video
        js = """
        (function() {
            const video = document.querySelector('a#video-title, ytd-video-renderer a#video-title');
            if (video && video.href) {
                window.location.href = video.href;
                return 'Playing: ' + video.innerText.trim();
            }
            return 'No video found to play';
        })()
        """
        result = await self.evaluate_js(js)
        return str(result) if result else "Could not play video"

    async def get_page_source(self) -> str:
        """Get the page HTML source."""
        result = await self.evaluate_js("document.documentElement.outerHTML.substring(0, 10000)")
        return str(result)[:10000] if result else "No source available"

    def close(self):
        """Close the HTTP client."""
        self._client.close()


# Singleton instance
_browser: Optional[CDPBrowserController] = None


def get_browser() -> CDPBrowserController:
    """Get or create the browser controller singleton."""
    global _browser
    if _browser is None:
        _browser = CDPBrowserController()
    return _browser
