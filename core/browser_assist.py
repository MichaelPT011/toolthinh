"""Helpers for launching the official Labs tools in a real browser and
watching the user's download folder for new files.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

from core.browser_installer import BrowserInstallError, BrowserInstaller
from core.config import (
    BUNDLED_CHROME_DIR,
    BUNDLED_CHROME_NESTED_DIR,
    FLOW_HOME_URL,
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
            subprocess.Popen(args)
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
                    FLOW_HOME_URL,
                ]
            )
            subprocess.Popen(args)
            return
        webbrowser.open(FLOW_HOME_URL)

    def describe_environment(self) -> dict:
        return {
            "browser_path": self._resolve_browser_path() or "",
            "auto_download_browser": self.can_auto_install_browser(),
            "chrome_user_data_dir": self._effective_user_data_dir(),
            "chrome_profile_dir": self._effective_profile_dir(),
            "downloads_dir": str(Path(self.settings.get("downloads_dir") or Path.home() / "Downloads").expanduser()),
        }

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
