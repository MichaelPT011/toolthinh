"""Helpers for launching the official Labs tools in a real browser and
watching the user's download folder for new files.
"""

from __future__ import annotations

import asyncio
import csv
import logging
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

from core.browser_installer import BrowserInstallError, BrowserInstaller
from core.config import (
    BUNDLED_CHROME_DIR,
    BUNDLED_CHROME_NESTED_DIR,
    FLOW_HOME_URL,
    FLOW_LOGIN_URL,
    MANAGED_BROWSER_DIR,
    MANAGED_BUNDLED_CHROME_DATA_DIR,
    MANAGED_CHROME_DATA_DIR,
    WHISK_TOOL_URL,
)

logger = logging.getLogger(__name__)


class BrowserAssist:
    """Open official Labs pages in Chrome and auto-import downloaded files."""

    TOOL_URLS = {
        "video": FLOW_HOME_URL,
        "flow": FLOW_HOME_URL,
        "whisk": WHISK_TOOL_URL,
    }

    def __init__(self, settings: dict) -> None:
        self.settings = dict(settings)
        self.browser_installer = BrowserInstaller()

    def update_settings(self, settings: dict) -> None:
        self.settings = dict(settings)

    def launch_tool(self, tool: str, prompt: str = "", image_paths: list[str] | None = None) -> None:
        url = self.TOOL_URLS[tool]
        del prompt
        browser_path = self._resolve_browser_path(allow_install=True)
        user_data_dir = self._effective_user_data_dir()
        profile_dir = self._effective_profile_dir()
        if browser_path:
            args = [browser_path]
            if user_data_dir:
                args.append(f"--user-data-dir={user_data_dir}")
            if profile_dir:
                args.append(f"--profile-directory={profile_dir}")
            args.extend(
                [
                    "--mute-audio",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-session-crashed-bubble",
                    "--new-tab",
                    url,
                ]
            )
            self._launch_browser(args)
        else:
            webbrowser.open(url)

        opened_parents: set[str] = set()
        for image_path in image_paths or []:
            parent = str(Path(image_path).resolve().parent)
            if parent in opened_parents:
                continue
            opened_parents.add(parent)
            try:
                if sys.platform == "win32":
                    subprocess.Popen(["explorer", parent])
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", parent])
                else:
                    subprocess.Popen(["xdg-open", parent])
            except OSError:
                logger.warning("Failed to open image folder: %s", parent)

    def launch_login_browser(self) -> None:
        """Open the managed browser profile to the official Flow page."""
        browser_path = self._resolve_browser_path(allow_install=True)
        user_data_dir = self._effective_user_data_dir()
        profile_dir = self._effective_profile_dir()
        if browser_path:
            self._close_existing_managed_browser(browser_path, user_data_dir)
            args = [browser_path]
            if user_data_dir:
                args.append(f"--user-data-dir={user_data_dir}")
            if profile_dir:
                args.append(f"--profile-directory={profile_dir}")
            args.extend(
                [
                    "--mute-audio",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-session-crashed-bubble",
                    "--new-window",
                    "--window-size=1280,900",
                    "--window-position=120,80",
                    FLOW_LOGIN_URL,
                ]
            )
            self._launch_browser(args, center_window=True, browser_path=browser_path)
            return
        webbrowser.open(FLOW_LOGIN_URL)

    def describe_environment(self) -> dict:
        return {
            "browser_path": self._resolve_browser_path() or "",
            "auto_download_browser": self.can_auto_install_browser(),
            "chrome_user_data_dir": self._effective_user_data_dir(),
            "chrome_profile_dir": self._effective_profile_dir(),
            "downloads_dir": str(Path(self.settings.get("downloads_dir") or Path.home() / "Downloads").expanduser()),
        }

    def has_browser_profile_data(self) -> bool:
        user_data_dir = Path(self._effective_user_data_dir()).expanduser()
        profile_dir = user_data_dir / self._effective_profile_dir()
        if not profile_dir.exists():
            return False
        markers = [
            profile_dir / "Preferences",
            profile_dir / "Cookies",
            profile_dir / "Network" / "Cookies",
            profile_dir / "Login Data",
            profile_dir / "Web Data",
        ]
        if any(marker.exists() for marker in markers):
            return True
        try:
            return any(profile_dir.iterdir())
        except OSError:
            return False

    def current_download_snapshot(self, extensions: set[str] | None = None) -> set[Path]:
        download_dir = Path(self.settings.get("downloads_dir") or Path.home() / "Downloads").expanduser()
        download_dir.mkdir(parents=True, exist_ok=True)
        snapshot: set[Path] = set()
        for item in download_dir.iterdir():
            if not item.is_file():
                continue
            if item.name.endswith(".crdownload") or item.name.endswith(".tmp"):
                continue
            if extensions and item.suffix.lower() not in extensions:
                continue
            snapshot.add(item.resolve())
        return snapshot

    async def wait_for_downloads(
        self,
        extensions: set[str],
        timeout_seconds: int,
        expected_count: int | None = None,
        baseline: set[Path] | None = None,
    ) -> list[Path] | None:
        download_dir = Path(self.settings.get("downloads_dir") or Path.home() / "Downloads").expanduser()
        download_dir.mkdir(parents=True, exist_ok=True)
        quiet_seconds = max(1, int(self.settings.get("watch_quiet_seconds", 4)))

        baseline = {path.resolve() for path in (baseline or self.current_download_snapshot())}
        previous_snapshot: dict[Path, tuple[int, float]] | None = None
        stable_for = 0
        stable: list[Path] = []
        elapsed = 0

        while elapsed < timeout_seconds:
            snapshot: dict[Path, tuple[int, float]] = {}
            for path in [item.resolve() for item in download_dir.iterdir() if item.is_file()]:
                if path in baseline:
                    continue
                if path.suffix.lower() not in extensions:
                    continue
                if path.name.endswith(".crdownload") or path.name.endswith(".tmp"):
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                snapshot[path] = (stat.st_size, stat.st_mtime)

            if snapshot:
                if snapshot == previous_snapshot:
                    stable_for += 1
                else:
                    stable_for = 0
                previous_snapshot = dict(snapshot)
                stable = sorted(snapshot, key=lambda item: snapshot[item][1])
                enough_files = expected_count is None or len(stable) >= expected_count
                if stable_for >= quiet_seconds and enough_files:
                    logger.info("Detected %s stable download(s) in %s", len(stable), download_dir)
                    return stable[:expected_count] if expected_count else stable
            else:
                previous_snapshot = None
                stable_for = 0

            await asyncio.sleep(1)
            elapsed += 1
        if expected_count and len(stable) >= expected_count:
            return stable[:expected_count]
        return stable or None

    def import_downloads(self, paths: list[Path], output_dir: Path, prefix: str) -> list[str]:
        output_dir.mkdir(parents=True, exist_ok=True)
        imported: list[str] = []
        for index, source in enumerate(paths):
            target = output_dir / f"{index + 1}-{prefix}{source.suffix.lower()}"
            counter = 1
            while target.exists():
                target = output_dir / f"{index + 1}-{prefix}_{counter}{source.suffix.lower()}"
                counter += 1
            shutil.copy2(source, target)
            imported.append(str(target))
        return imported

    def can_auto_install_browser(self) -> bool:
        return self.browser_installer.can_auto_install()

    def _resolve_browser_path(self, allow_install: bool = False) -> str | None:
        configured = self.settings.get("browser_path", "").strip()
        if configured and Path(configured).exists():
            return configured

        managed = self.browser_installer.installed_browser_path()
        if managed:
            return managed

        candidates = [
            Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
            Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
            Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            Path("/usr/bin/google-chrome"),
            Path("/usr/bin/google-chrome-stable"),
            BUNDLED_CHROME_DIR / "chrome.exe",
            BUNDLED_CHROME_NESTED_DIR / "chrome.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        found = shutil.which("chrome") or shutil.which("chrome.exe")
        if found:
            return found
        if allow_install and self.browser_installer.can_auto_install():
            try:
                return self.browser_installer.ensure_browser()
            except BrowserInstallError as exc:
                logger.error("Auto-install browser failed: %s", exc)
        return None

    def _effective_user_data_dir(self) -> str:
        configured = self.settings.get("chrome_user_data_dir", "").strip()
        if configured:
            return configured
        browser_path = self._resolve_browser_path() or ""
        browser_file = Path(browser_path).resolve() if browser_path else None
        bundled_paths = {
            (BUNDLED_CHROME_DIR / "chrome.exe").resolve(),
            (BUNDLED_CHROME_NESTED_DIR / "chrome.exe").resolve(),
        }
        managed_browser_root = MANAGED_BROWSER_DIR.resolve()
        if browser_file and (browser_file in bundled_paths or managed_browser_root in browser_file.parents):
            return str(MANAGED_BUNDLED_CHROME_DATA_DIR)
        return str(MANAGED_CHROME_DATA_DIR)

    def _effective_profile_dir(self) -> str:
        configured = self.settings.get("chrome_profile_dir", "").strip()
        return configured or "Default"

    def _close_existing_managed_browser(self, browser_path: str, user_data_dir: str) -> None:
        if sys.platform != "win32":
            return
        executable_name = Path(browser_path).name or "chrome.exe"
        escaped_dir = str(Path(user_data_dir).resolve()).replace("'", "''")
        script = (
            f"$needle = [regex]::Escape('{escaped_dir}'); "
            f"Get-CimInstance Win32_Process -Filter \"Name = '{executable_name}'\" | "
            "Where-Object { $_.CommandLine -and $_.CommandLine -match $needle } | "
            "ForEach-Object { "
            "try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} "
            "}"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            check=False,
        )
        time.sleep(0.8)

    def _launch_browser(
        self,
        args: list[str],
        *,
        center_window: bool = False,
        browser_path: str | None = None,
    ) -> None:
        existing_pids = self._list_browser_pids(browser_path or args[0]) if center_window else set()
        subprocess.Popen(args)
        if center_window:
            self._center_browser_windows(browser_path or args[0], existing_pids)

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

    def _center_browser_windows(self, browser_path: str, existing_pids: set[int]) -> None:
        if sys.platform != "win32":
            return

        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)
            current_pids = self._list_browser_pids(browser_path)
            target_pids = current_pids - existing_pids
            if not target_pids:
                target_pids = current_pids

            def collect_windows() -> list[int]:
                visible_windows: list[int] = []

                @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                def enum_windows(hwnd, _lparam):
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value not in target_pids:
                        return True
                    if not user32.IsWindow(hwnd):
                        return True
                    visible_windows.append(hwnd)
                    return True

                user32.EnumWindows(enum_windows, 0)
                return visible_windows

            windows: list[int] = []
            for _ in range(16):
                windows = collect_windows()
                if windows:
                    break
                time.sleep(0.25)

            for hwnd in windows:
                user32.ShowWindow(hwnd, 5)
                rect = wintypes.RECT()
                if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    continue
                width = max(1100, rect.right - rect.left)
                height = max(780, rect.bottom - rect.top)
                width = min(width, screen_width - 80)
                height = min(height, screen_height - 120)
                x = max(0, (screen_width - width) // 2)
                y = max(0, (screen_height - height) // 2)
                user32.MoveWindow(hwnd, x, y, width, height, True)
                user32.SetForegroundWindow(hwnd)
        except Exception:
            logger.exception("Could not center login browser window.")
