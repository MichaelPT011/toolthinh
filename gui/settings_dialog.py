"""Settings dialog and helpers."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.config import DEFAULT_SETTINGS, OFFICIAL_UPDATE_MANIFEST_URL, OUTPUT_DIR, SETTINGS_FILE


def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    if SETTINGS_FILE.exists():
        try:
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                settings.update(saved)
        except (OSError, json.JSONDecodeError):
            pass
    return settings


def save_settings(settings: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")


class SettingsDialog(QDialog):
    """Edit application level settings."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cài đặt")
        self.setMinimumWidth(520)
        self._settings = load_settings()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(12)

        self.concurrent_spin = self._spin(1, 8, self._settings["max_concurrent"])
        self.batch_spin = self._spin(0, 120, self._settings["batch_interval"])
        self.watch_spin = self._spin(1, 30, self._settings.get("watch_quiet_seconds", 4))
        self.show_browser_checkbox = QCheckBox("Hiện cửa sổ Chrome khi chạy tự động")
        self.show_browser_checkbox.setChecked(bool(self._settings.get("show_browser_window", False)))

        self.output_edit = QLineEdit(self._settings.get("output_dir", str(OUTPUT_DIR)))
        output_widget = self._browse_row(self.output_edit, self._browse_output)

        self.downloads_edit = QLineEdit(self._settings.get("downloads_dir", ""))
        downloads_widget = self._browse_row(self.downloads_edit, self._browse_downloads)

        self.browser_edit = QLineEdit(self._settings.get("browser_path", ""))
        self.browser_edit.setPlaceholderText("Để trống để app tự dùng browser đi kèm hoặc Chrome hệ thống")
        browser_widget = self._browse_row(self.browser_edit, self._browse_browser_file)

        self.user_data_edit = QLineEdit(self._settings.get("chrome_user_data_dir", ""))
        self.user_data_edit.setPlaceholderText("Mặc định dùng hồ sơ sạch riêng của app")
        user_data_widget = self._browse_row(self.user_data_edit, self._browse_user_data_dir)

        self.profile_edit = QLineEdit(self._settings.get("chrome_profile_dir", "Default"))
        self.update_info_edit = QLineEdit(OFFICIAL_UPDATE_MANIFEST_URL)
        self.update_info_edit.setReadOnly(True)

        form.addRow("Chờ file ổn định (giây)", self.watch_spin)
        form.addRow("Tác vụ song song tối đa", self.concurrent_spin)
        form.addRow("Khoảng nghỉ batch (giây)", self.batch_spin)
        form.addRow("Thư mục đầu ra", output_widget)
        form.addRow("Thư mục tải xuống", downloads_widget)
        form.addRow("Đường dẫn browser", browser_widget)
        form.addRow("Thư mục dữ liệu browser", user_data_widget)
        form.addRow("Tên profile Chrome", self.profile_edit)
        form.addRow("Nguồn cập nhật", self.update_info_edit)
        form.addRow("Chế độ hiển thị", self.show_browser_checkbox)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Lưu")
        cancel_btn = QPushButton("Hủy")
        save_btn.clicked.connect(self._save)
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def _spin(self, min_value: int, max_value: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(min_value, max_value)
        spin.setValue(value)
        return spin

    def _browse_row(self, line_edit: QLineEdit, handler) -> QWidget:
        browse_btn = QPushButton("Chọn")
        browse_btn.clicked.connect(handler)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(line_edit)
        row.addWidget(browse_btn)
        widget = QWidget()
        widget.setLayout(row)
        return widget

    def _browse_output(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Chọn thư mục đầu ra",
            self.output_edit.text() or str(Path(OUTPUT_DIR)),
        )
        if selected:
            self.output_edit.setText(selected)

    def _browse_downloads(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Chọn thư mục tải xuống",
            self.downloads_edit.text() or str(Path.home() / "Downloads"),
        )
        if selected:
            self.downloads_edit.setText(selected)

    def _browse_user_data_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Chọn thư mục dữ liệu Chrome",
            self.user_data_edit.text() or str(Path.home()),
        )
        if selected:
            self.user_data_edit.setText(selected)

    def _browse_browser_file(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file Chrome",
            self.browser_edit.text() or str(Path.home()),
            "Tệp thực thi (*.exe);;Tất cả tệp (*)",
        )
        if selected:
            self.browser_edit.setText(selected)

    def _save(self) -> None:
        settings = {
            "video_delay_seconds": self._settings.get("video_delay_seconds", DEFAULT_SETTINGS["video_delay_seconds"]),
            "flow_delay_seconds": self._settings.get("flow_delay_seconds", DEFAULT_SETTINGS["flow_delay_seconds"]),
            "whisk_delay_seconds": self._settings.get("whisk_delay_seconds", DEFAULT_SETTINGS["whisk_delay_seconds"]),
            "output_dir": self.output_edit.text().strip() or str(OUTPUT_DIR),
            "downloads_dir": self.downloads_edit.text().strip() or str(Path.home() / "Downloads"),
            "browser_path": self.browser_edit.text().strip(),
            "chrome_user_data_dir": self.user_data_edit.text().strip(),
            "chrome_profile_dir": self.profile_edit.text().strip() or "Default",
            "show_browser_window": self.show_browser_checkbox.isChecked(),
            "watch_quiet_seconds": self.watch_spin.value(),
            "max_concurrent": self.concurrent_spin.value(),
            "batch_interval": self.batch_spin.value(),
            "update_manifest_url": OFFICIAL_UPDATE_MANIFEST_URL,
            "backend": "browser_assist",
        }
        save_settings(settings)
        self.accept()
