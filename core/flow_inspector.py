"""Read lightweight account information from the logged-in Flow page."""

from __future__ import annotations

from core.config import FLOW_HOME_URL
from core.flow_automation import FlowAutomation
from core.flow_runtime import FlowBrowserRuntime


class FlowInspector:
    """Inspect the logged-in Flow browser profile."""

    def __init__(self, browser_assist) -> None:
        self.browser_assist = browser_assist
        self._automation = FlowAutomation(browser_assist)

    async def inspect_membership(self) -> dict:
        async with FlowBrowserRuntime(self.browser_assist, self._automation._load_playwright, max_pages=1) as runtime:
            async with runtime.page() as page:
                await page.goto(FLOW_HOME_URL, wait_until="domcontentloaded", timeout=120000)
                await page.wait_for_timeout(5000)
                body = await page.locator("body").inner_text()
                return {
                    "plan": self._detect_plan(body),
                    "logged_in": "NEW PROJECT" in body.upper() or "PROJECT" in body.upper(),
                }

    def _detect_plan(self, body: str) -> str:
        body_upper = body.upper()
        if "ULTRA" in body_upper:
            return "Google AI Ultra"
        if "PRO" in body_upper:
            return "Google AI Pro"
        if "FREE" in body_upper:
            return "Miễn phí"
        return "Không rõ"
