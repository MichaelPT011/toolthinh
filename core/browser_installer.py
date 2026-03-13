"""Download and manage an official Chrome for Testing browser when needed."""

from __future__ import annotations

import json
import platform
import shutil
import stat
import zipfile
from pathlib import Path

import httpx

from core.config import (
    CHROME_FOR_TESTING_JSON_URL,
    HTTP_TIMEOUT,
    MANAGED_BROWSER_DIR,
)


class BrowserInstallError(RuntimeError):
    """Raised when the fallback browser could not be prepared."""


class BrowserInstaller:
    """Install a managed Chrome for Testing browser outside the git repo."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = Path(base_dir or MANAGED_BROWSER_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.meta_file = self.base_dir / "browser.json"

    def can_auto_install(self) -> bool:
        return self._platform_key() is not None

    def installed_browser_path(self) -> str | None:
        meta = self._load_meta()
        if not meta:
            return None
        path = Path(str(meta.get("executable_path", "")))
        if path.exists():
            return str(path)
        return None

    def ensure_browser(self) -> str:
        existing = self.installed_browser_path()
        if existing:
            return existing

        platform_key = self._platform_key()
        if not platform_key:
            raise BrowserInstallError("May hien tai chua duoc ho tro auto-download browser.")

        version, download_url = self._resolve_download(platform_key)
        extract_root = self.base_dir / f"{platform_key}-{version}"
        executable_path = extract_root / self._executable_relative_path(platform_key)
        if executable_path.exists():
            self._write_meta(version, platform_key, executable_path)
            return str(executable_path)

        archive_path = self.base_dir / f"{platform_key}-{version}.zip"
        temp_dir = self.base_dir / f"{platform_key}-{version}.tmp"
        shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)
        self._download_file(download_url, archive_path)
        try:
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(temp_dir)
            shutil.rmtree(extract_root, ignore_errors=True)
            temp_dir.rename(extract_root)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        if not executable_path.exists():
            raise BrowserInstallError("Da tai browser nhung khong tim thay file thuc thi.")

        self._ensure_executable(executable_path)
        self._cleanup_old_versions(extract_root)
        self._write_meta(version, platform_key, executable_path)
        return str(executable_path)

    def _resolve_download(self, platform_key: str) -> tuple[str, str]:
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT * 2, follow_redirects=True) as client:
                response = client.get(CHROME_FOR_TESTING_JSON_URL)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise BrowserInstallError(f"Khong doc duoc thong tin browser chinh thuc: {exc}") from exc

        channels = payload.get("channels", {})
        stable = channels.get("Stable", {})
        version = str(stable.get("version") or "").strip()
        downloads = stable.get("downloads", {}).get("chrome", [])
        for item in downloads:
            if str(item.get("platform")) == platform_key and item.get("url"):
                return version, str(item["url"])
        raise BrowserInstallError("Khong tim thay goi browser phu hop voi may nay.")

    def _download_file(self, url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with httpx.stream("GET", url, timeout=None, follow_redirects=True) as response:
                response.raise_for_status()
                with open(destination, "wb") as handle:
                    for chunk in response.iter_bytes():
                        if chunk:
                            handle.write(chunk)
        except Exception as exc:
            raise BrowserInstallError(f"Tai browser that bai: {exc}") from exc

    def _cleanup_old_versions(self, keep_dir: Path) -> None:
        for item in self.base_dir.iterdir():
            if item == keep_dir or item == self.meta_file:
                continue
            if item.is_dir() and item.name.startswith(f"{keep_dir.name.split('-', 1)[0]}-"):
                shutil.rmtree(item, ignore_errors=True)
            if item.is_file() and item.suffix == ".zip":
                item.unlink(missing_ok=True)

    def _write_meta(self, version: str, platform_key: str, executable_path: Path) -> None:
        data = {
            "version": version,
            "platform": platform_key,
            "executable_path": str(executable_path),
        }
        self.meta_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load_meta(self) -> dict | None:
        if not self.meta_file.exists():
            return None
        try:
            return json.loads(self.meta_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _platform_key(self) -> str | None:
        machine = platform.machine().lower()
        if platform.system() == "Windows":
            return "win64" if "64" in machine or machine == "amd64" else "win32"
        if platform.system() == "Darwin":
            return "mac-arm64" if machine in {"arm64", "aarch64"} else "mac-x64"
        if platform.system() == "Linux":
            return "linux64"
        return None

    def _executable_relative_path(self, platform_key: str) -> Path:
        if platform_key == "win64":
            return Path("chrome-win64") / "chrome.exe"
        if platform_key == "win32":
            return Path("chrome-win32") / "chrome.exe"
        if platform_key == "mac-x64":
            return (
                Path("chrome-mac-x64")
                / "Google Chrome for Testing.app"
                / "Contents"
                / "MacOS"
                / "Google Chrome for Testing"
            )
        if platform_key == "mac-arm64":
            return (
                Path("chrome-mac-arm64")
                / "Google Chrome for Testing.app"
                / "Contents"
                / "MacOS"
                / "Google Chrome for Testing"
            )
        return Path("chrome-linux64") / "chrome"

    def _ensure_executable(self, executable_path: Path) -> None:
        if platform.system() == "Windows":
            return
        mode = executable_path.stat().st_mode
        executable_path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
