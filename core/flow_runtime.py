"""Shared hidden Chrome runtime for Flow automation."""

from __future__ import annotations

import asyncio
import csv
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path


class FlowBrowserRuntime:
    """Manage one hidden Chrome instance and hand out tabs to concurrent jobs."""

    def __init__(self, browser_assist, playwright_loader, max_pages: int = 1) -> None:
        self.browser_assist = browser_assist
        self.playwright_loader = playwright_loader
        self.max_pages = max(1, int(max_pages or 1))
        self.context = None
        self._playwright_manager = None
        self._playwright = None
        self._semaphore = asyncio.Semaphore(self.max_pages)
        self._download_lock = asyncio.Lock()
        self._parking_page = None
        self._parking_page_in_use = False

    async def __aenter__(self):
        _playwright_error, _playwright_timeout_error, async_playwright = self.playwright_loader()
        browser_path = self.browser_assist._resolve_browser_path()
        if not browser_path:
            raise RuntimeError("Chrome executable was not found. Set Chrome path in Settings first.")

        user_data_dir = self.browser_assist._effective_user_data_dir()
        profile_dir = self.browser_assist._effective_profile_dir()
        headless = bool(self.browser_assist.settings.get("headless_automation", False))
        existing_pids = self._list_browser_pids(browser_path)
        self._playwright_manager = async_playwright()
        self._playwright = await self._playwright_manager.__aenter__()
        self.context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir,
            executable_path=browser_path,
            headless=headless,
            args=[
                f"--profile-directory={profile_dir}",
                "--window-position=-2000,0",
                "--window-size=1600,1200",
                "--mute-audio",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-session-crashed-bubble",
            ],
            viewport={"width": 1600, "height": 1200},
            accept_downloads=True,
        )
        if not headless and not bool(self.browser_assist.settings.get("show_browser_window", False)):
            await asyncio.sleep(1.2)
            self._hide_new_browser_windows(browser_path, existing_pids)
        pages = list(self.context.pages)
        if pages:
            self._parking_page = pages[0]
            await self._parking_page.goto("about:blank", wait_until="domcontentloaded")
            for page in pages[1:]:
                await page.close()
        else:
            self._parking_page = await self.context.new_page()
            await self._parking_page.goto("about:blank", wait_until="domcontentloaded")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.context is not None:
            try:
                await self.context.close()
            except Exception:
                pass
            self.context = None
            self._parking_page = None
            self._parking_page_in_use = False
        if self._playwright_manager is not None:
            await self._playwright_manager.__aexit__(exc_type, exc, tb)
            self._playwright_manager = None
            self._playwright = None

    @asynccontextmanager
    async def page(self):
        if self.context is None:
            raise RuntimeError("Flow browser runtime is not started.")

        await self._semaphore.acquire()
        reused_parking_page = False
        if self._parking_page is not None and not self._parking_page_in_use:
            page = self._parking_page
            self._parking_page_in_use = True
            reused_parking_page = True
        else:
            page = await self.context.new_page()
        try:
            yield page
        finally:
            try:
                if reused_parking_page:
                    try:
                        await page.goto("about:blank", wait_until="domcontentloaded")
                    except Exception:
                        pass
                    self._parking_page_in_use = False
                else:
                    await page.close()
            finally:
                self._semaphore.release()

    @asynccontextmanager
    async def download_slot(self):
        await self._download_lock.acquire()
        try:
            yield
        finally:
            self._download_lock.release()

    def _list_browser_pids(self, browser_path: str) -> set[int]:
        if sys.platform != "win32":
            return set()

        executable_name = Path(browser_path).name or "chrome.exe"
        result = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh", "/fi", f"IMAGENAME eq {executable_name}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return set()

        pids: set[int] = set()
        for row in csv.reader(result.stdout.splitlines()):
            if len(row) < 2 or row[0].startswith("INFO:"):
                continue
            try:
                pids.add(int(row[1]))
            except ValueError:
                continue
        return pids

    def _hide_new_browser_windows(self, browser_path: str, existing_pids: set[int]) -> None:
        if sys.platform != "win32":
            return

        current_pids = self._list_browser_pids(browser_path)
        target_pids = current_pids - existing_pids
        if not target_pids:
            return

        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            visible_windows: list[int] = []

            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def enum_windows(hwnd, _lparam):
                if not user32.IsWindowVisible(hwnd):
                    return True
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value in target_pids:
                    visible_windows.append(hwnd)
                return True

            for _ in range(12):
                visible_windows.clear()
                user32.EnumWindows(enum_windows, 0)
                if visible_windows:
                    break
                time.sleep(0.25)

            for hwnd in visible_windows:
                user32.ShowWindow(hwnd, 0)
        except Exception:
            return
