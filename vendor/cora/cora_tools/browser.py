r"""
# ================================================================
#   ____   ___   ____      _
#  / ___| / _ \ |  _ \    / \
# | |    | | | || |_) |  / _ \
# | |___ | |_| ||  _ <  / ___ \
#  \____| \___/ |_| \_\/_/   \_\
#
# C.O.R.A Browser Control Module
# ================================================================
# Version: 1.0.0
# Unity AI Lab
# Website: https://www.unityailab.com
# GitHub: https://github.com/Unity-Lab-AI
# Contact: unityailabcontact@gmail.com
# Creators: Hackall360, Sponge, GFourteen, Alfreddo
# ================================================================
#
# Browser automation using Playwright for web interaction.
# Navigate, click, type, screenshot - full browser control.
#
# ================================================================
"""

import asyncio
from typing import Optional
from pathlib import Path
import os


# Playwright for browser control
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class BrowserController:
    """Browser control using Playwright."""

    def __init__(self, headless: bool = False):
        """
        Args:
            headless: If True, browser runs invisibly. If False, visible.
        """
        self.headless = headless
        self.browser = None
        self.page = None
        self.playwright = None

    async def start(self):
        """Start the browser."""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright not installed. Run: pip install playwright && playwright install")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.page = await self.browser.new_page()
        return self

    async def goto(self, url: str) -> str:
        """Navigate to a URL. Returns page title."""
        await self.page.goto(url)
        return await self.page.title()

    async def click(self, selector_or_text: str):
        """Click an element by selector or visible text."""
        try:
            await self.page.click(selector_or_text)
        except Exception:
            await self.page.get_by_text(selector_or_text).click()

    async def type_text(self, selector: str, text: str):
        """Type text into an input field."""
        await self.page.fill(selector, text)

    async def press_key(self, key: str):
        """Press a key (e.g., 'Enter', 'Tab')."""
        await self.page.keyboard.press(key)

    async def screenshot(self, path: str = "screenshot.png") -> str:
        """Take a screenshot. Returns path."""
        await self.page.screenshot(path=path)
        return path

    async def get_text(self, selector: str = "body") -> str:
        """Get text content of an element."""
        return await self.page.inner_text(selector)

    async def get_html(self) -> str:
        """Get page HTML."""
        return await self.page.content()

    async def wait(self, seconds: float):
        """Wait for a number of seconds."""
        await asyncio.sleep(seconds)

    async def close(self):
        """Close the browser."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


def browse_sync(url: str, screenshot_path: str = None) -> dict:
    """
    Synchronous wrapper to open a URL and optionally screenshot.

    Args:
        url: URL to navigate to
        screenshot_path: Optional path to save screenshot

    Returns:
        dict with title, url, screenshot_path
    """
    async def _browse():
        if not PLAYWRIGHT_AVAILABLE:
            return {'success': False, 'error': 'Playwright not installed. Run: pip install playwright'}

        browser = BrowserController(headless=True)
        try:
            await browser.start()
            title = await browser.goto(url)

            result = {
                'success': True,
                'title': title,
                'url': url
            }

            if screenshot_path:
                await browser.screenshot(screenshot_path)
                result['screenshot'] = screenshot_path

            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            await browser.close()

    return asyncio.run(_browse())


def search_and_screenshot(query: str, save_path: str = None) -> dict:
    """
    Search DuckDuckGo and take a screenshot of results.

    Args:
        query: Search query
        save_path: Path to save screenshot

    Returns:
        dict with screenshot path
    """
    from urllib.parse import quote_plus

    if save_path is None:
        import tempfile
        save_path = os.path.join(tempfile.gettempdir(), 'search_results.png')

    url = f"https://duckduckgo.com/?q={quote_plus(query)}"
    return browse_sync(url, save_path)


# Module test
if __name__ == "__main__":
    print("=" * 50)
    print("  C.O.R.A Browser Module Test")
    print("  Unity AI Lab")
    print("=" * 50)

    if PLAYWRIGHT_AVAILABLE:
        result = browse_sync("https://example.com", "test_browser.png")
        print(f"Result: {result}")
    else:
        print("Playwright not installed.")
        print("Run: pip install playwright && playwright install")
