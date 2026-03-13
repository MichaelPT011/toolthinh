"""Dialog to display environment diagnostics."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)


class EnvironmentReportDialog(QDialog):
    """Show a read-only environment report."""

    def __init__(self, result: dict, parent=None) -> None:
        super().__init__(parent)
        self.result = dict(result)
        self.setWindowTitle("Kiểm tra môi trường")
        self.setMinimumSize(720, 560)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        summary = QLabel(self._summary_text())
        summary.setWordWrap(True)
        summary.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(summary)

        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(str(self.result.get("report") or "Không có dữ liệu."))
        layout.addWidget(editor, 1)

        buttons = QHBoxLayout()
        copy_btn = QPushButton("Sao chép báo cáo")
        close_btn = QPushButton("Đóng")
        copy_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText(editor.toPlainText()))
        close_btn.clicked.connect(self.accept)
        buttons.addStretch(1)
        buttons.addWidget(copy_btn)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

    def _summary_text(self) -> str:
        overall = str(self.result.get("overall") or "ok")
        if overall == "error":
            lead = "Môi trường hiện còn lỗi cần xử lý trước khi scale lớn."
        elif overall == "warning":
            lead = "Môi trường chạy được nhưng có vài điểm nên chỉnh để ổn định hơn."
        else:
            lead = "Môi trường đang ở trạng thái tốt để chạy hằng ngày."
        return (
            f"{lead}\n"
            f"OK: {self.result.get('ok_count', 0)} | "
            f"Cảnh báo: {self.result.get('warning_count', 0)} | "
            f"Lỗi: {self.result.get('error_count', 0)}"
        )
