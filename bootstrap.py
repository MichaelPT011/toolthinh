"""Bootstrap launcher for Windows and macOS.

Creates a local .venv on first run, installs the requirements when needed,
then starts the desktop app with that interpreter.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
REQUIREMENTS_FILE = ROOT_DIR / "requirements.txt"
STAMP_FILE = ROOT_DIR / ".bootstrap_stamp"
IS_WINDOWS = sys.platform.startswith("win")
VENV_DIR = ROOT_DIR / ".venv"
VENV_PYTHON = VENV_DIR / ("Scripts/python.exe" if IS_WINDOWS else "bin/python3")


def _requirements_hash() -> str:
    return hashlib.sha256(REQUIREMENTS_FILE.read_bytes()).hexdigest()


def _venv_needs_install() -> bool:
    if not VENV_PYTHON.exists():
        return True
    if not STAMP_FILE.exists():
        return True
    try:
        return STAMP_FILE.read_text(encoding="utf-8").strip() != _requirements_hash()
    except OSError:
        return True


def _run(command: list[str], *, check: bool = True) -> int:
    process = subprocess.run(command, cwd=ROOT_DIR)
    if check and process.returncode != 0:
        raise SystemExit(process.returncode)
    return process.returncode


def _ensure_venv() -> None:
    if not VENV_DIR.exists() or not VENV_PYTHON.exists():
        print("Dang tao moi truong chay lan dau...")
        _run([sys.executable, "-m", "venv", str(VENV_DIR)])

    if _venv_needs_install():
        print("Dang cai dat thu vien can thiet...")
        _run([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"])
        _run([str(VENV_PYTHON), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])
        STAMP_FILE.write_text(_requirements_hash(), encoding="utf-8")


def _handle_update_cli(argv: list[str]) -> int | None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--apply-update", action="store_true")
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--zip", dest="zip_path", default="")
    parser.add_argument("--target", dest="target_dir", default="")
    parser.add_argument("--restart", dest="restart_path", default="")
    args, _unknown = parser.parse_known_args(argv)
    if not args.apply_update:
        return None

    from core.updater import apply_update

    apply_update(
        Path(args.zip_path),
        Path(args.target_dir),
        Path(args.restart_path),
        args.pid,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    os.chdir(ROOT_DIR)
    handled = _handle_update_cli(argv)
    if handled is not None:
        return handled
    _ensure_venv()
    process = subprocess.run([str(VENV_PYTHON), "main.py"], cwd=ROOT_DIR)
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
