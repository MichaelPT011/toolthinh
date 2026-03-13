"""Build a macOS onedir release with PyInstaller.

Run this on macOS only, or via the bundled GitHub Actions workflow.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT_DIR = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT_DIR / "build"
DIST_DIR = BUILD_DIR / "dist"
WORK_DIR = BUILD_DIR / "work"
SPEC_DIR = BUILD_DIR / "spec"
RELEASE_DIR = ROOT_DIR / "release"
APP_NAME = "Tool Veo3's Thinh"
BUILD_NAME = "Tool_Veo3s_Thinh"
ZIP_NAME = "Tool-Veo3s-Thinh-mac.zip"


def _optional_add_data(command: list[str], source: Path, target: str) -> None:
    if source.exists():
        command.extend(["--add-data", f"{source}:{target}"])


def _run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT_DIR)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _version() -> str:
    data = json.loads((ROOT_DIR / "version.json").read_text(encoding="utf-8"))
    return str(data.get("version") or "0.0.0")


def _zip_dir(source_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in source_dir.rglob("*"):
            archive.write(path, path.relative_to(source_dir.parent))


def main() -> int:
    if sys.platform != "darwin":
        raise SystemExit("build_macos.py must be run on macOS.")

    _run([sys.executable, str(ROOT_DIR / "release_tools" / "generate_icon_assets.py")])

    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    shutil.rmtree(RELEASE_DIR, ignore_errors=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    SPEC_DIR.mkdir(parents=True, exist_ok=True)
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    icon_path = ROOT_DIR / "assets" / "build" / "app_icon_1024.png"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        BUILD_NAME,
        "--icon",
        str(icon_path),
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(WORK_DIR),
        "--specpath",
        str(SPEC_DIR),
        "--collect-all",
        "playwright",
        str(ROOT_DIR / "main.py"),
    ]
    _optional_add_data(command, ROOT_DIR / "assets", "assets")
    _optional_add_data(command, ROOT_DIR / "version.json", ".")
    _optional_add_data(command, ROOT_DIR / "latest.json", ".")
    _optional_add_data(command, ROOT_DIR / "chrome-mac", "chrome-mac")
    _run(command)

    built_dir = DIST_DIR / f"{BUILD_NAME}.app"
    app_dir = DIST_DIR / f"{APP_NAME}.app"
    if app_dir.exists():
        shutil.rmtree(app_dir, ignore_errors=True)
    built_dir.rename(app_dir)
    zip_path = RELEASE_DIR / ZIP_NAME
    _zip_dir(app_dir, zip_path)
    print(f"Built macOS release {zip_path} (version {_version()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
