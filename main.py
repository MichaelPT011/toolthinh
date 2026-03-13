"""Application entry point."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


os.chdir(_runtime_root())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


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
    handled = _handle_update_cli(argv)
    if handled is not None:
        return handled

    from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPalette
    from PySide6.QtWidgets import QApplication

    from core.batch import BatchEngine
    from core.browser_assist import BrowserAssist
    from core.concat import ConcatEngine
    from core.config import ensure_dirs
    from core.flow_automation import FlowAutomation
    from core.flow_gen import FlowGenerator
    from core.google_auth import GoogleAuth
    from core.labs_api import LabsAPIClient
    from core.project import ProjectManager
    from core.video_automation import VideoAutomation
    from core.video_gen import VideoGenerator
    from gui.main_window import MainWindow
    from gui.settings_dialog import load_settings

    ensure_dirs()
    settings = load_settings()
    output_base = Path(settings["output_dir"]).resolve()
    (output_base / "videos").mkdir(parents=True, exist_ok=True)
    (output_base / "images").mkdir(parents=True, exist_ok=True)

    auth = GoogleAuth()
    if not auth.get_accounts():
        auth.add_account("Default profile")

    api_client = LabsAPIClient(auth)
    browser_assist = BrowserAssist(settings)
    flow_automation = FlowAutomation(browser_assist)
    video_automation = VideoAutomation(browser_assist)
    video_gen = VideoGenerator(
        api_client,
        settings["video_delay_seconds"],
        browser_assist=browser_assist,
        video_automation=video_automation,
    )
    flow_gen = FlowGenerator(
        api_client,
        settings["flow_delay_seconds"],
        browser_assist=browser_assist,
        flow_automation=flow_automation,
    )
    video_gen.output_dir = output_base / "videos"
    flow_gen.output_dir = output_base / "images"
    concat = ConcatEngine()
    project_mgr = ProjectManager()
    batch = BatchEngine()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f3f4f6"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f9fafb"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    available_fonts = set(QFontDatabase.families())
    preferred_font = next(
        (
            family
            for family in [
                "Segoe UI Variable Text",
                "Segoe UI Variable",
                "Bahnschrift",
                "Segoe UI",
                "Tahoma",
            ]
            if family in available_fonts
        ),
        app.font().family(),
    )
    app.setFont(QFont(preferred_font, 10))
    icon_path = _runtime_root() / "assets" / "app_icon.svg"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow(auth, api_client, video_gen, flow_gen, concat, project_mgr, batch)
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
