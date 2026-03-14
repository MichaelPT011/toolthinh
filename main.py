"""Application entry point."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


os.chdir(_runtime_root())

_log_dir = _runtime_root() / "data" / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)
_log_file = _log_dir / "app.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(_log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def _handle_update_cli(argv: list[str]) -> int | None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--apply-update", action="store_true")
    parser.add_argument("--smoke-login-browser", action="store_true")
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--zip", dest="zip_path", default="")
    parser.add_argument("--target", dest="target_dir", default="")
    parser.add_argument("--restart", dest="restart_path", default="")
    args, _unknown = parser.parse_known_args(argv)
    if args.apply_update:
        from core.updater import apply_update

        apply_update(
            Path(args.zip_path),
            Path(args.target_dir),
            Path(args.restart_path),
            args.pid,
        )
        return 0

    if args.smoke_login_browser:
        from core.browser_assist import BrowserAssist
        from core.config import ensure_dirs
        from gui.settings_dialog import load_settings

        ensure_dirs()
        browser_assist = BrowserAssist(load_settings())
        browser_assist.launch_login_browser()
        logger.info("Smoke login browser launched successfully")
        return 0

    return None


def _run_startup_update_check(app, settings: dict) -> int | None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

    from core.updater import UpdateManager

    class StartupUpdateDialog(QDialog):
        def __init__(self) -> None:
            super().__init__(None)
            self.setWindowTitle("Khởi động")
            self.setModal(True)
            self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
            self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
            self.setMinimumWidth(420)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(24, 24, 24, 24)
            self.label = QLabel("Vui lòng chờ để kiểm tra cập nhật...")
            self.label.setWordWrap(True)
            layout.addWidget(self.label)

        def set_message(self, text: str) -> None:
            self.label.setText(text)

    dialog = None
    if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
        dialog = StartupUpdateDialog()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        app.processEvents()

    manager = UpdateManager(settings)
    try:
        info = asyncio.run(manager.check_for_update())
        logger.info("Startup update info: %r", info)
        if info.get("has_update"):
            if dialog:
                dialog.set_message(
                    f"Đang tải và cài đặt bản mới {info['remote_version']}...\n"
                    "Tool sẽ tự mở lại sau khi xong."
                )
                app.processEvents()
            zip_path = asyncio.run(manager.download_package(info))
            manager.spawn_apply_update(zip_path, os.getpid())
            logger.info("Startup update prepared; exiting for apply")
            return 0
    except Exception as exc:
        logger.exception("Startup update check failed: %s", exc)
    finally:
        if dialog:
            dialog.close()
            dialog.deleteLater()
            app.processEvents()
    return None


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    logger.info("App start argv=%s frozen=%s root=%s", argv, getattr(sys, "frozen", False), _runtime_root())
    handled = _handle_update_cli(argv)
    if handled is not None:
        logger.info("Handled startup CLI and exiting rc=%s", handled)
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
    logger.info("Loaded settings: %s", settings)
    output_base = Path(settings["output_dir"]).resolve()
    (output_base / "videos").mkdir(parents=True, exist_ok=True)
    (output_base / "images").mkdir(parents=True, exist_ok=True)

    auth = GoogleAuth()

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
    app.aboutToQuit.connect(lambda: logger.info("QApplication.aboutToQuit emitted"))
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

    handled = _run_startup_update_check(app, settings)
    if handled is not None:
        logger.info("Handled startup update flow; exiting rc=%s", handled)
        return handled

    window = MainWindow(auth, api_client, video_gen, flow_gen, concat, project_mgr, batch)
    logger.info("MainWindow created; showing UI")
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    rc = app.exec()
    logger.info("App event loop exited rc=%s", rc)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
