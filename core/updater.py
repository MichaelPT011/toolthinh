"""Simple app update checker and installer."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from core.config import (
    OFFICIAL_RELEASE_PREFIX,
    OFFICIAL_UPDATE_MANIFEST_URL,
    ROOT_DIR,
    UPDATE_CACHE_DIR,
    VERSION_FILE,
)


class UpdateError(Exception):
    """Raised when the update manifest or package is invalid."""


class UpdateManager:
    """Check the official latest.json manifest and stage an update."""

    def __init__(self, settings: dict) -> None:
        self.settings = dict(settings)

    def current_version(self) -> str:
        if not VERSION_FILE.exists():
            return "0.0.0"
        try:
            data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "0.0.0"
        return str(data.get("version") or "0.0.0")

    async def check_for_update(self) -> dict:
        manifest_url = OFFICIAL_UPDATE_MANIFEST_URL
        manifest = await self._read_json(manifest_url)
        remote_version = str(manifest.get("version") or "").strip()
        if not remote_version:
            raise UpdateError("latest.json thiếu trường version.")

        download_url = self._select_download_url(manifest)
        if not download_url:
            raise UpdateError("latest.json chưa có link tải phù hợp cho hệ điều hành hiện tại.")
        self._validate_download_url(download_url)

        current_version = self.current_version()
        return {
            "current_version": current_version,
            "remote_version": remote_version,
            "notes": str(manifest.get("notes") or "").strip(),
            "download_url": download_url,
            "manifest_url": manifest_url,
            "has_update": self._compare_versions(remote_version, current_version) > 0,
        }

    async def download_package(self, update_info: dict) -> Path:
        download_url = str(update_info.get("download_url") or "").strip()
        if not download_url:
            raise UpdateError("Không tìm thấy link tải bản cập nhật.")
        self._validate_download_url(download_url)

        UPDATE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        target = UPDATE_CACHE_DIR / f"update-{update_info['remote_version']}.zip"
        await self._download_file(download_url, target)
        return target

    def spawn_apply_update(self, zip_path: Path, app_pid: int) -> None:
        restart_target = self._restart_target()
        if getattr(sys, "frozen", False):
            command = [
                sys.executable,
                "--apply-update",
                "--pid",
                str(app_pid),
                "--zip",
                str(zip_path),
                "--target",
                str(ROOT_DIR),
                "--restart",
                str(restart_target),
            ]
        else:
            command = [
                sys.executable,
                str(ROOT_DIR / "bootstrap.py"),
                "--apply-update",
                "--pid",
                str(app_pid),
                "--zip",
                str(zip_path),
                "--target",
                str(ROOT_DIR),
                "--restart",
                str(restart_target),
            ]

        kwargs: dict = {"close_fds": True}
        if sys.platform == "win32":
            creationflags = 0x00000008 | 0x00000200
            kwargs["creationflags"] = creationflags
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen(command, **kwargs)

    async def _read_json(self, source: str) -> dict:
        text = await self._read_text(source)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise UpdateError(f"latest.json không hợp lệ: {exc}") from exc
        if not isinstance(data, dict):
            raise UpdateError("latest.json phải là một object JSON.")
        return data

    async def _read_text(self, source: str) -> str:
        if source.startswith(("http://", "https://")):
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
                    response = await client.get(source)
                    response.raise_for_status()
                    return response.text
            except httpx.HTTPStatusError as exc:
                raise UpdateError(
                    "Không đọc được nguồn cập nhật chính thức. "
                    "Hãy kiểm tra repo GitHub đã public chưa và file latest.json đã nằm đúng ở nhánh main chưa."
                ) from exc
            except httpx.HTTPError as exc:
                raise UpdateError(f"Không kết nối được nguồn cập nhật chính thức: {exc}") from exc
        return Path(self._local_path(source)).read_text(encoding="utf-8")

    async def _download_file(self, source: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.startswith(("http://", "https://")):
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
                    async with client.stream("GET", source) as response:
                        response.raise_for_status()
                        with open(destination, "wb") as handle:
                            async for chunk in response.aiter_bytes():
                                handle.write(chunk)
            except httpx.HTTPStatusError as exc:
                raise UpdateError("Không tải được gói cập nhật từ repo chính thức.") from exc
            except httpx.HTTPError as exc:
                raise UpdateError(f"Lỗi mạng khi tải gói cập nhật: {exc}") from exc
            return
        shutil.copy2(self._local_path(source), destination)

    def _select_download_url(self, manifest: dict) -> str:
        if sys.platform == "win32":
            return str(manifest.get("windows_url") or manifest.get("win_url") or manifest.get("zip_url") or "")
        if sys.platform == "darwin":
            return str(manifest.get("mac_url") or manifest.get("darwin_url") or manifest.get("zip_url") or "")
        return str(manifest.get("linux_url") or manifest.get("zip_url") or "")

    def _validate_download_url(self, download_url: str) -> None:
        normalized = str(download_url or "").strip()
        if not normalized.startswith(OFFICIAL_RELEASE_PREFIX):
            raise UpdateError("Nguồn cập nhật không hợp lệ. App chỉ nhận bản cập nhật từ repo chính thức của Thịnh.")

    def _restart_target(self) -> Path:
        if getattr(sys, "frozen", False):
            if sys.platform == "darwin":
                return Path(sys.executable).resolve().parents[2]
            return Path(sys.executable).resolve()
        if sys.platform == "win32":
            return ROOT_DIR / "Tool Veo3's Thinh.bat"
        if sys.platform == "darwin":
            return ROOT_DIR / "Tool Veo3's Thinh.command"
        return ROOT_DIR / "bootstrap.py"

    def _local_path(self, source: str) -> Path:
        if source.startswith("file://"):
            parsed = urlparse(source)
            path = unquote(parsed.path)
            if parsed.netloc:
                path = f"//{parsed.netloc}{path}"
            if sys.platform == "win32" and path.startswith("/") and len(path) > 3 and path[2] == ":":
                path = path[1:]
            return Path(path)
        return Path(source).expanduser()

    def _compare_versions(self, left: str, right: str) -> int:
        left_parts = self._version_parts(left)
        right_parts = self._version_parts(right)
        if left_parts > right_parts:
            return 1
        if left_parts < right_parts:
            return -1
        if left > right:
            return 1
        if left < right:
            return -1
        return 0

    def _version_parts(self, value: str) -> tuple[int, ...]:
        parts: list[int] = []
        current = ""
        for char in value:
            if char.isdigit():
                current += char
            elif current:
                parts.append(int(current))
                current = ""
        if current:
            parts.append(int(current))
        return tuple(parts or [0])


def apply_update(zip_path: Path, target_dir: Path, restart_path: Path, pid: int) -> None:
    _wait_for_process_exit(pid)
    extract_dir = Path(tempfile.mkdtemp(prefix="veo3-update-", dir=str(UPDATE_CACHE_DIR)))
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(extract_dir)
        source_root = _resolve_source_root(extract_dir)
        _copy_tree(source_root, target_dir)
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)
        try:
            zip_path.unlink(missing_ok=True)
        except OSError:
            pass
    _restart_application(restart_path)


def _wait_for_process_exit(pid: int) -> None:
    if pid <= 0:
        return
    while _is_process_alive(pid):
        time.sleep(1)


def _is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _resolve_source_root(extract_dir: Path) -> Path:
    children = [item for item in extract_dir.iterdir() if item.name != "__MACOSX"]
    if len(children) == 1 and children[0].is_dir():
        single = children[0]
        if (
            (single / "main.py").exists()
            or (single / "bootstrap.py").exists()
            or (single / "version.json").exists()
            or (single / "latest.json").exists()
            or any(path.suffix.lower() == ".exe" for path in single.iterdir())
            or any(path.suffix.lower() == ".app" for path in single.iterdir())
        ):
            return single
    return extract_dir


def _copy_tree(source: Path, target: Path) -> None:
    skip_names = {"data", "output", ".venv", "__pycache__", ".bootstrap_stamp"}
    for item in source.iterdir():
        if item.name in skip_names:
            continue
        destination = target / item.name
        if item.is_dir():
            if destination.exists():
                shutil.rmtree(destination, ignore_errors=True)
            shutil.copytree(item, destination)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, destination)


def _restart_application(restart_path: Path) -> None:
    if sys.platform == "win32" and restart_path.suffix.lower() == ".bat":
        subprocess.Popen(["cmd.exe", "/c", "start", "", str(restart_path)], close_fds=True)
        return
    if sys.platform == "darwin" and restart_path.suffix.lower() == ".command":
        subprocess.Popen(["open", str(restart_path)], close_fds=True)
        return
    if sys.platform == "darwin" and restart_path.suffix.lower() == ".app":
        subprocess.Popen(["open", str(restart_path)], close_fds=True)
        return
    if restart_path.suffix.lower() == ".py":
        subprocess.Popen([sys.executable, str(restart_path)], close_fds=True, start_new_session=True)
        return
    subprocess.Popen([str(restart_path)], close_fds=True, start_new_session=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--zip", dest="zip_path", default="")
    parser.add_argument("--target", dest="target_dir", default="")
    parser.add_argument("--restart", dest="restart_path", default="")
    args = parser.parse_args()

    if args.apply:
        apply_update(
            Path(args.zip_path),
            Path(args.target_dir),
            Path(args.restart_path),
            args.pid,
        )
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
