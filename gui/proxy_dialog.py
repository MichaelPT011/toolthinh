"""Proxy editing dialog."""

from __future__ import annotations

import asyncio

import httpx
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from gui.base_worker import BaseWorker


class ProxyTestWorker(BaseWorker):
    """Verify that a proxy is reachable."""

    def __init__(self, proxy: str) -> None:
        super().__init__()
        self.proxy = proxy

    async def _run_async(self):
        async with httpx.AsyncClient(proxy=self.proxy, timeout=10) as client:
            response = await client.get("https://httpbin.org/ip")
            response.raise_for_status()
            await asyncio.sleep(0.1)
            return response.json()


class ProxyDialog(QDialog):
    """Edit and test a per-profile proxy configuration."""

    def __init__(self, current_proxy: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Thiết lập proxy")
        self.proxy_input = QLineEdit(current_proxy or "")
        self.status_label = QLabel("Proxy là tùy chọn.")
        self._worker: ProxyTestWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Địa chỉ proxy", self.proxy_input)
        layout.addLayout(form)
        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        test_btn = QPushButton("Kiểm tra")
        save_btn = QPushButton("Lưu")
        clear_btn = QPushButton("Xóa")
        cancel_btn = QPushButton("Hủy")
        test_btn.clicked.connect(self._test_proxy)
        save_btn.clicked.connect(self.accept)
        clear_btn.clicked.connect(self._clear)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(test_btn)
        buttons.addStretch(1)
        buttons.addWidget(clear_btn)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def _test_proxy(self) -> None:
        proxy = self.proxy_input.text().strip()
        if not proxy:
            QMessageBox.warning(self, "Proxy", "Hãy nhập địa chỉ proxy để kiểm tra.")
            return
        self.status_label.setText("Đang kiểm tra proxy...")
        self._worker = ProxyTestWorker(proxy)
        self._worker.completed.connect(self._on_test_ok)
        self._worker.error.connect(self._on_test_error)
        self._worker.start()

    def _on_test_ok(self, result: object) -> None:
        self.status_label.setText(f"Proxy hoạt động: {result}")

    def _on_test_error(self, message: str) -> None:
        self.status_label.setText(f"Proxy lỗi: {message}")

    def _clear(self) -> None:
        self.proxy_input.clear()
        self.status_label.setText("Đã xóa proxy.")

    def get_proxy(self) -> str | None:
        value = self.proxy_input.text().strip()
        return value or None
