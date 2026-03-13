"""Main application window."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QTabWidget

from core.config import APP_TITLE, OUTPUT_DIR
from core.environment_check import EnvironmentChecker
from core.updater import UpdateManager
from gui.base_worker import BaseWorker


class UpdateCheckWorker(BaseWorker):
    """Load and validate latest.json."""

    def __init__(self, manager: UpdateManager) -> None:
        super().__init__()
        self.manager = manager

    async def _run_async(self):
        return await self.manager.check_for_update()


class UpdatePrepareWorker(BaseWorker):
    """Download the update package and spawn the updater process."""

    def __init__(self, manager: UpdateManager, update_info: dict, app_pid: int) -> None:
        super().__init__()
        self.manager = manager
        self.update_info = dict(update_info)
        self.app_pid = app_pid

    async def _run_async(self):
        zip_path = await self.manager.download_package(self.update_info)
        self.manager.spawn_apply_update(zip_path, self.app_pid)
        return {"zip_path": str(zip_path), "remote_version": self.update_info["remote_version"]}


class EnvironmentCheckWorker(BaseWorker):
    """Run local diagnostics before production use."""

    def __init__(self, checker: EnvironmentChecker) -> None:
        super().__init__()
        self.checker = checker

    async def _run_async(self):
        return await self.checker.run()


class MainWindow(QMainWindow):
    """Top level application shell."""

    def __init__(self, auth, api_client, video_gen, flow_gen, concat_engine, project_mgr, batch_engine):
        super().__init__()
        self.auth = auth
        self.api_client = api_client
        self.video_gen = video_gen
        self.flow_gen = flow_gen
        self.concat_engine = concat_engine
        self.project_mgr = project_mgr
        self.batch_engine = batch_engine
        self._update_check_worker: UpdateCheckWorker | None = None
        self._update_prepare_worker: UpdatePrepareWorker | None = None
        self._environment_check_worker: EnvironmentCheckWorker | None = None
        self._auto_update_check_pending = False
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1280, 900)
        self._apply_theme()
        self._init_ui()
        self._init_menu()
        self.statusBar().showMessage("Sẵn sàng")
        QTimer.singleShot(1500, self._auto_check_updates)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f3f4f6;
            }
            QWidget {
                font-family: "Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Helvetica Neue", sans-serif;
                color: #111827;
                font-size: 13px;
            }
            QTabWidget::pane {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                top: -1px;
            }
            QTabBar::tab {
                background: transparent;
                color: #6b7280;
                padding: 12px 18px;
                margin-right: 6px;
                border: none;
                border-bottom: 2px solid transparent;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                color: #111827;
                border-bottom: 2px solid #111827;
            }
            QLabel {
                color: #111827;
            }
            QLabel#heroNote {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 14px;
                padding: 14px 16px;
                font-size: 15px;
                font-weight: 600;
                color: #0f172a;
            }
            QFrame#batchPanel, QWidget#batchPanel {
                background: #e7eaee;
                border: 1px solid #cbd5e1;
                border-radius: 16px;
            }
            QLabel#batchTitle {
                font-size: 14px;
                font-weight: 700;
                color: #111827;
            }
            QLabel[statValue="true"] {
                font-size: 22px;
                font-weight: 700;
                color: #111827;
            }
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background: #ffffff;
                color: #111827;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 9px 12px;
                selection-background-color: #cbd5e1;
            }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #64748b;
            }
            QPushButton {
                background: #111827;
                color: #ffffff;
                border: 1px solid #111827;
                border-radius: 10px;
                padding: 9px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #1f2937;
                border-color: #1f2937;
            }
            QPushButton:disabled {
                background: #e5e7eb;
                color: #9ca3af;
                border-color: #e5e7eb;
            }
            QTableWidget {
                background: #ffffff;
                color: #111827;
                alternate-background-color: #f9fafb;
                gridline-color: #eef2f7;
                border: 1px solid #e5e7eb;
                border-radius: 14px;
            }
            QTableWidget::item:selected {
                background: #e5e7eb;
                color: #111827;
            }
            QHeaderView::section {
                background: #f8fafc;
                color: #475569;
                border: none;
                border-bottom: 1px solid #e5e7eb;
                padding: 9px;
                font-weight: 700;
            }
            QProgressBar {
                background: #f3f4f6;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                text-align: center;
                color: #111827;
                min-height: 16px;
            }
            QProgressBar::chunk {
                border-radius: 8px;
                background: #16a34a;
            }
            QMenuBar {
                background: #ffffff;
                color: #111827;
                border-bottom: 1px solid #e5e7eb;
            }
            QMenuBar::item:selected {
                background: #f3f4f6;
                border-radius: 6px;
            }
            QMenu {
                background: #ffffff;
                color: #111827;
                border: 1px solid #e5e7eb;
            }
            QMenu::item:selected {
                background: #f3f4f6;
            }
            QStatusBar {
                background: #ffffff;
                color: #475569;
                border-top: 1px solid #e5e7eb;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            """
        )

    def _init_ui(self) -> None:
        from gui.account_tab import AccountTab
        from gui.concat_tab import ConcatTab
        from gui.flow_tab import FlowTab
        from gui.help_tab import HelpTab
        from gui.video_tab import VideoTab

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.video_tab = VideoTab(self.video_gen, self.auth, self.batch_engine)
        self.flow_tab = FlowTab(self.flow_gen, self.auth, self.batch_engine)
        self.concat_tab = ConcatTab(self.concat_engine)
        self.account_tab = AccountTab(self.auth, getattr(self.video_gen, "browser_assist", None))
        self.help_tab = HelpTab(self)
        self.tabs.addTab(self.video_tab, "Video VEO3")
        self.tabs.addTab(self.flow_tab, "Ảnh Flow")
        self.tabs.addTab(self.concat_tab, "Ghép video")
        self.tabs.addTab(self.account_tab, "Tài khoản")
        self.tabs.addTab(self.help_tab, "Hướng dẫn")
        self.setCentralWidget(self.tabs)

    def _init_menu(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&Tệp")
        projects_action = QAction("Dự án...", self)
        settings_action = QAction("Cài đặt...", self)
        exit_action = QAction("Thoát", self)
        projects_action.triggered.connect(self._show_projects)
        settings_action.triggered.connect(self._show_settings)
        exit_action.triggered.connect(QApplication.quit)
        file_menu.addAction(projects_action)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        tools_menu = menubar.addMenu("&Công cụ")
        login_browser_action = QAction("Mở trình duyệt đăng nhập Flow", self)
        update_action = QAction("Kiểm tra cập nhật", self)
        environment_action = QAction("Kiểm tra môi trường", self)
        output_action = QAction("Mở thư mục đầu ra", self)
        login_browser_action.triggered.connect(self._open_login_browser)
        update_action.triggered.connect(lambda: self._check_updates(manual=True))
        environment_action.triggered.connect(self._check_environment)
        output_action.triggered.connect(self._open_output)
        tools_menu.addAction(login_browser_action)
        tools_menu.addAction(environment_action)
        tools_menu.addAction(output_action)

    def _show_projects(self) -> None:
        from gui.project_dialog import ProjectDialog

        ProjectDialog(self.project_mgr, self).exec()

    def _show_settings(self) -> None:
        from gui.settings_dialog import SettingsDialog, load_settings

        dialog = SettingsDialog(self)
        if dialog.exec():
            settings = load_settings()
            self.video_gen.poll_interval = settings["video_delay_seconds"]
            self.flow_gen.poll_interval = settings["flow_delay_seconds"]
            output_base = Path(settings["output_dir"]).resolve()
            (output_base / "videos").mkdir(parents=True, exist_ok=True)
            (output_base / "images").mkdir(parents=True, exist_ok=True)
            self.video_gen.output_dir = output_base / "videos"
            self.flow_gen.output_dir = output_base / "images"
            if getattr(self.video_gen, "browser_assist", None):
                self.video_gen.browser_assist.update_settings(settings)
            if getattr(self.flow_gen, "browser_assist", None):
                self.flow_gen.browser_assist.update_settings(settings)
            if getattr(self.account_tab, "_refresh_browser_info", None):
                self.account_tab._refresh_browser_info()
            self.statusBar().showMessage("Đã cập nhật cài đặt", 4000)

    def _auto_check_updates(self) -> None:
        self._check_updates(manual=False)

    def _check_updates(self, manual: bool) -> None:
        if self._update_check_worker or self._update_prepare_worker:
            return

        from gui.settings_dialog import load_settings

        manager = UpdateManager(load_settings())
        self._auto_update_check_pending = not manual
        self.statusBar().showMessage("Đang kiểm tra cập nhật...", 4000)
        self._update_check_worker = UpdateCheckWorker(manager)
        self._update_check_worker.finished.connect(self._on_update_checked)
        self._update_check_worker.error.connect(self._on_update_check_error)
        self._update_check_worker.start()

    def _on_update_checked(self, result: object) -> None:
        self._update_check_worker = None
        if not isinstance(result, dict):
            return

        auto_mode = self._auto_update_check_pending
        self._auto_update_check_pending = False

        if not result.get("has_update"):
            return

        from gui.settings_dialog import load_settings

        manager = UpdateManager(load_settings())
        self.statusBar().showMessage("Đang tự cập nhật lên phiên bản mới...", 4000)
        self._update_prepare_worker = UpdatePrepareWorker(manager, result, os.getpid())
        self._update_prepare_worker.finished.connect(self._on_update_prepared)
        self._update_prepare_worker.error.connect(self._on_update_check_error)
        self._update_prepare_worker.start()
        return

        if not result.get("has_update"):
            if not auto_mode:
                QMessageBox.information(
                    self,
                    "Cập nhật",
                    f"Bạn đang ở bản mới nhất.\nPhiên bản hiện tại: {result.get('current_version', 'Không rõ')}",
                )
            return

        notes = str(result.get("notes") or "Không có ghi chú.")
        reply = QMessageBox.question(
            self,
            "Có bản cập nhật mới",
            "Đã tìm thấy bản mới.\n\n"
            f"Hiện tại: {result['current_version']}\n"
            f"Mới nhất: {result['remote_version']}\n\n"
            f"Ghi chú:\n{notes}\n\n"
            "Tải và cài ngay bây giờ?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        from gui.settings_dialog import load_settings

        manager = UpdateManager(load_settings())
        self.statusBar().showMessage("Đang tải bản cập nhật...", 4000)
        self._update_prepare_worker = UpdatePrepareWorker(manager, result, os.getpid())
        self._update_prepare_worker.finished.connect(self._on_update_prepared)
        self._update_prepare_worker.error.connect(self._on_update_check_error)
        self._update_prepare_worker.start()

    def _on_update_prepared(self, result: object) -> None:
        self._update_prepare_worker = None
        self.statusBar().showMessage("Đang cài bản cập nhật mới và tự mở lại...", 3000)
        QApplication.quit()
        return
        version = ""
        if isinstance(result, dict):
            version = str(result.get("remote_version") or "")
        QMessageBox.information(
            self,
            "Cập nhật",
            f"Đã tải xong bản {version}.\nỨng dụng sẽ đóng để cài cập nhật rồi tự mở lại.",
        )
        QApplication.quit()

    def _on_update_check_error(self, message: str) -> None:
        auto_mode = self._auto_update_check_pending
        self._auto_update_check_pending = False
        self._update_check_worker = None
        self._update_prepare_worker = None
        if auto_mode:
            self.statusBar().showMessage("Không kiểm tra được cập nhật tự động.", 4000)
            return
        QMessageBox.warning(self, "Cập nhật", message)

    def _open_output(self) -> None:
        from gui.settings_dialog import load_settings

        output_dir = Path(load_settings().get("output_dir", str(OUTPUT_DIR)))
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(output_dir)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(output_dir)])
        else:
            subprocess.Popen(["xdg-open", str(output_dir)])

    def _open_login_browser(self) -> None:
        browser_assist = getattr(self.video_gen, "browser_assist", None)
        if not browser_assist:
            QMessageBox.warning(self, "Trình duyệt", "Chưa cấu hình trình duyệt.")
            return
        try:
            browser_assist.launch_login_browser()
        except Exception as exc:
            QMessageBox.critical(self, "Đăng nhập Flow", f"Không mở được trình duyệt đăng nhập.\n\nChi tiết: {exc}")
            return
        self.statusBar().showMessage("Đã mở trình duyệt đăng nhập Flow", 4000)

    def _check_environment(self) -> None:
        from gui.settings_dialog import load_settings

        if self._environment_check_worker:
            return

        browser_assist = getattr(self.video_gen, "browser_assist", None)
        if not browser_assist:
            QMessageBox.warning(self, "Kiểm tra môi trường", "Không tìm thấy browser assistant để chạy kiểm tra.")
            return

        checker = EnvironmentChecker(load_settings(), browser_assist, self.auth)
        self.statusBar().showMessage("Đang kiểm tra môi trường...", 4000)
        self._environment_check_worker = EnvironmentCheckWorker(checker)
        self._environment_check_worker.finished.connect(self._on_environment_checked)
        self._environment_check_worker.error.connect(self._on_environment_check_error)
        self._environment_check_worker.start()

    def _on_environment_checked(self, result: object) -> None:
        self._environment_check_worker = None
        if not isinstance(result, dict):
            return
        from gui.environment_dialog import EnvironmentReportDialog

        dialog = EnvironmentReportDialog(result, self)
        dialog.exec()

    def _on_environment_check_error(self, message: str) -> None:
        self._environment_check_worker = None
        QMessageBox.warning(self, "Kiểm tra môi trường", message)
