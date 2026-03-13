"""Project dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class ProjectDialog(QDialog):
    """Create, inspect, and delete local projects."""

    def __init__(self, project_mgr, parent=None) -> None:
        super().__init__(parent)
        self.project_mgr = project_mgr
        self.setWindowTitle("Dự án")
        self.setMinimumSize(640, 420)
        self._init_ui()
        self._refresh()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.name_input = QLineEdit()
        self.description_input = QLineEdit()
        form.addRow("Tên dự án", self.name_input)
        form.addRow("Mô tả", self.description_input)
        layout.addLayout(form)

        create_row = QHBoxLayout()
        create_btn = QPushButton("Tạo dự án")
        create_btn.clicked.connect(self._create_project)
        create_row.addStretch(1)
        create_row.addWidget(create_btn)
        layout.addLayout(create_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Tên", "Mô tả", "Ngày tạo"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        open_btn = QPushButton("Mở")
        delete_btn = QPushButton("Xóa")
        close_btn = QPushButton("Đóng")
        open_btn.clicked.connect(self._open_project)
        delete_btn.clicked.connect(self._delete_project)
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(open_btn)
        buttons.addWidget(delete_btn)
        buttons.addStretch(1)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

    def _refresh(self) -> None:
        projects = self.project_mgr.list_projects()
        self.table.setRowCount(len(projects))
        for row, project in enumerate(projects):
            self.table.setItem(row, 0, QTableWidgetItem(project.get("name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(project.get("description", "")))
            self.table.setItem(row, 2, QTableWidgetItem(project.get("created_at", "")))

    def _create_project(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Dự án", "Hãy nhập tên dự án.")
            return
        self.project_mgr.create_project(name, self.description_input.text().strip())
        self.name_input.clear()
        self.description_input.clear()
        self._refresh()

    def _selected_name(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.text() if item else None

    def _open_project(self) -> None:
        name = self._selected_name()
        if not name:
            QMessageBox.information(self, "Dự án", "Hãy chọn một dự án trước.")
            return
        project = self.project_mgr.load_project(name)
        QMessageBox.information(self, "Chi tiết dự án", str(project))

    def _delete_project(self) -> None:
        name = self._selected_name()
        if not name:
            QMessageBox.information(self, "Dự án", "Hãy chọn một dự án trước.")
            return
        if QMessageBox.question(self, "Xóa dự án", f"Xóa dự án '{name}'?") != QMessageBox.StandardButton.Yes:
            return
        self.project_mgr.delete_project(name)
        self._refresh()
