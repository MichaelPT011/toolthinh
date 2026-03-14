"""Account/profile management tab."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.base_worker import BaseWorker
from gui.proxy_dialog import ProxyDialog


class ValidateWorker(BaseWorker):
    """Validate a single profile."""

    def __init__(self, auth, account_id: str) -> None:
        super().__init__()
        self.auth = auth
        self.account_id = account_id

    async def _run_async(self):
        return await self.auth.validate_session(self.account_id)


class AddProfileDialog(QDialog):
    """Create a local backend profile."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Thêm hồ sơ")
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.nickname_input = QLineEdit()
        self.api_key_input = QLineEdit()
        self.email_input = QLineEdit()
        self.user_name_input = QLineEdit()
        self.notes_input = QLineEdit()
        form.addRow("Tên hiển thị", self.nickname_input)
        form.addRow("API key", self.api_key_input)
        form.addRow("Email", self.email_input)
        form.addRow("Tên người dùng", self.user_name_input)
        form.addRow("Ghi chú", self.notes_input)
        layout.addLayout(form)

        info = QLabel(
            "Hồ sơ ở đây là hồ sơ cục bộ của app. Browser profile Flow được quản lý riêng ở phần đăng nhập."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        buttons = QHBoxLayout()
        add_btn = QPushButton("Thêm")
        cancel_btn = QPushButton("Hủy")
        add_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(add_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def get_data(self) -> dict:
        return {
            "nickname": self.nickname_input.text().strip(),
            "api_key": self.api_key_input.text().strip(),
            "email": self.email_input.text().strip(),
            "user_name": self.user_name_input.text().strip(),
            "notes": self.notes_input.text().strip(),
        }


class AccountTab(QWidget):
    """Display and edit profiles used by the app backend."""

    def __init__(self, auth, browser_assist=None) -> None:
        super().__init__()
        self.auth = auth
        self.browser_assist = browser_assist
        self._workers: list[ValidateWorker] = []
        self._identity_timer = QTimer(self)
        self._identity_timer.setInterval(3000)
        self._identity_timer.timeout.connect(self._poll_browser_identity)
        self._identity_timer_loops_left = 0
        self._init_ui()
        self._refresh_table()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        actions = QHBoxLayout()
        add_btn = QPushButton("Thêm hồ sơ")
        import_btn = QPushButton("Nhập hồ sơ")
        validate_btn = QPushButton("Kiểm tra tất cả")
        self.login_btn = QPushButton("Mở trình duyệt đăng nhập Flow")
        add_btn.clicked.connect(self._add_profile)
        import_btn.clicked.connect(self._import_from_file)
        validate_btn.clicked.connect(self._validate_all)
        self.login_btn.clicked.connect(self._open_login_browser)
        actions.addWidget(add_btn)
        actions.addWidget(import_btn)
        actions.addWidget(validate_btn)
        actions.addWidget(self.login_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.browser_info = QLabel()
        self.browser_info.setWordWrap(True)
        layout.addWidget(self.browser_info)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Tên", "Email", "Người dùng", "Trạng thái", "Proxy", "Tác vụ"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        self._refresh_browser_info()

    def _add_profile(self) -> None:
        dialog = AddProfileDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.auth.add_account(**dialog.get_data())
        self._refresh_table()

    def _import_from_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Nhập hồ sơ", "", "Tệp JSON (*.json);;Mọi tệp (*)")
        if not file_path:
            return
        try:
            self.auth.import_account_from_file(file_path)
        except Exception as exc:
            QMessageBox.critical(self, "Nhập hồ sơ", str(exc))
            return
        self._refresh_table()

    def _validate_all(self) -> None:
        self._workers.clear()
        for account in self.auth.get_accounts():
            worker = ValidateWorker(self.auth, account["account_id"])
            worker.completed.connect(lambda _result, self=self: self._refresh_table())
            worker.error.connect(lambda message, self=self: QMessageBox.warning(self, "Kiểm tra", message))
            worker.start()
            self._workers.append(worker)

    def _set_proxy(self, account_id: str) -> None:
        account = self.auth.get_account(account_id)
        if not account:
            return
        dialog = ProxyDialog(account.get("proxy"), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.auth.set_proxy(account_id, dialog.get_proxy())
        self._refresh_table()

    def _remove_account(self, account_id: str) -> None:
        account = self.auth.get_account(account_id)
        if not account:
            return
        reply = QMessageBox.question(
            self,
            "Xóa hồ sơ",
            f"Xóa hồ sơ '{account.get('nickname', account_id)}'?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.auth.remove_account(account_id)
        self._refresh_table()

    def _validate_one(self, account_id: str) -> None:
        worker = ValidateWorker(self.auth, account_id)
        worker.completed.connect(lambda _result, self=self: self._refresh_table())
        worker.error.connect(lambda message, self=self: QMessageBox.warning(self, "Kiểm tra", message))
        worker.start()
        self._workers.append(worker)

    def _open_login_browser(self) -> None:
        if not self.browser_assist:
            QMessageBox.warning(self, "Trình duyệt", "Chưa cấu hình trình duyệt.")
            return
        self.login_btn.setEnabled(False)
        self.browser_info.setText(
            self.browser_info.text()
            + "\n\nDang chuan bi trinh duyet dang nhap Flow..."
            + "\nLan dau co the mat 1-3 phut de tai trinh duyet rieng cua tool."
        )
        try:
            self.browser_assist.spawn_login_browser_helper()
        except Exception as exc:
            self.login_btn.setEnabled(True)
            QMessageBox.critical(
                self,
                "Dang nhap Flow",
                f"Khong mo duoc trinh duyet dang nhap.\n\nChi tiet: {exc}",
            )
            return

        QTimer.singleShot(3000, lambda: self.login_btn.setEnabled(True))
        self._identity_timer_loops_left = 40
        self._identity_timer.start()
        self.browser_info.setText(
            self.browser_info.text()
            + "\n\nDa gui lenh mo cua so dang nhap Flow."
            + "\nSau khi dang nhap xong, app se tu doc email va cap nhat bang ho so."
        )

    def _refresh_browser_info(self) -> None:
        if not self.browser_assist:
            self.browser_info.setText("Chưa cấu hình trình duyệt.")
            return
        env = self.browser_assist.describe_environment()
        email = env.get("email") or "Chưa phát hiện"
        user_name = env.get("user_name") or "Chưa phát hiện"
        self.browser_info.setText(
            "Profile trình duyệt đang dùng:\n"
            f"Đường dẫn Chrome: {env['browser_path'] or '(tự nhận diện)'}\n"
            f"Thư mục dữ liệu Chrome: {env['chrome_user_data_dir']}\n"
            f"Tên profile Chrome: {env['chrome_profile_dir']}\n"
            f"Thư mục tải xuống: {env['downloads_dir']}\n"
            f"Email đăng nhập hiện tại: {email}\n"
            f"Tên người dùng: {user_name}"
        )

    def _refresh_table(self) -> None:
        self._sync_browser_identity()
        accounts = self.auth.get_accounts()
        self.table.setRowCount(len(accounts))
        for row, account in enumerate(accounts):
            self.table.setItem(row, 0, QTableWidgetItem(account.get("nickname", "")))
            self.table.setItem(row, 1, QTableWidgetItem(account.get("email") or ""))
            self.table.setItem(row, 2, QTableWidgetItem(account.get("user_name") or ""))
            self.table.setItem(row, 3, QTableWidgetItem(account.get("status") or ""))
            self.table.setItem(row, 4, QTableWidgetItem(account.get("proxy") or ""))

            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)
            validate_btn = QPushButton("Kiểm tra")
            proxy_btn = QPushButton("Proxy")
            remove_btn = QPushButton("Xóa")
            validate_btn.clicked.connect(lambda _checked=False, aid=account["account_id"]: self._validate_one(aid))
            proxy_btn.clicked.connect(lambda _checked=False, aid=account["account_id"]: self._set_proxy(aid))
            remove_btn.clicked.connect(lambda _checked=False, aid=account["account_id"]: self._remove_account(aid))
            action_layout.addWidget(validate_btn)
            action_layout.addWidget(proxy_btn)
            action_layout.addWidget(remove_btn)
            self.table.setCellWidget(row, 5, action_widget)
        self._refresh_browser_info()

    def _poll_browser_identity(self) -> None:
        self._identity_timer_loops_left -= 1
        identity = self._sync_browser_identity()
        if identity:
            self._refresh_table()
        if identity.get("email") or self._identity_timer_loops_left <= 0:
            self._identity_timer.stop()

    def _sync_browser_identity(self) -> dict:
        if not self.browser_assist or not hasattr(self.auth, "sync_browser_profile_account"):
            return {}
        identity = self.browser_assist.read_profile_identity()
        if not identity:
            return {}
        nickname = str(identity.get("profile_name") or "Flow mac dinh").strip() or "Flow mac dinh"
        self.auth.sync_browser_profile_account(
            nickname=nickname,
            email=str(identity.get("email") or "").strip(),
            user_name=str(identity.get("user_name") or "").strip(),
        )
        return identity
