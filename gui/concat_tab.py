"""Concat tab."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QCheckBox,
    QDoubleSpinBox,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.concat import ConcatClip, ConcatJob
from gui.base_worker import BaseWorker


class ConcatWorker(BaseWorker):
    """Run one concat job."""

    def __init__(self, engine, job: ConcatJob) -> None:
        super().__init__()
        self.engine = engine
        self.job = job

    async def _run_async(self):
        return self.engine.run_concat_job(self.job)


class ConcatTab(QWidget):
    """Video concat and trim tab."""

    def __init__(self, concat_engine) -> None:
        super().__init__()
        self.concat_engine = concat_engine
        self._worker: ConcatWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.warning_label = QLabel()
        if self.concat_engine.is_available():
            self.warning_label.setText("Đã phát hiện ffmpeg và sẵn sàng ghép video.")
        else:
            self.warning_label.setText("Không tìm thấy ffmpeg. Chức năng ghép video đang bị tắt.")
        layout.addWidget(self.warning_label)

        row = QHBoxLayout()
        add_btn = QPushButton("Thêm video")
        remove_btn = QPushButton("Xóa dòng")
        add_btn.clicked.connect(self._add_videos)
        remove_btn.clicked.connect(self._remove_selected)
        row.addWidget(add_btn)
        row.addWidget(remove_btn)
        row.addStretch(1)
        layout.addLayout(row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Tệp", "Cắt từ giây", "Cắt đến giây", "Thời lượng"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        form = QFormLayout()
        self.sync_checkbox = QCheckBox("Đồng bộ thời lượng")
        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(0.0, 600.0)
        self.target_spin.setValue(8.0)
        self.output_edit = QLineEdit()
        output_row = QHBoxLayout()
        output_browse = QPushButton("Chọn")
        output_browse.clicked.connect(self._browse_output)
        output_row.addWidget(self.output_edit)
        output_row.addWidget(output_browse)
        output_widget = QWidget()
        output_widget.setLayout(output_row)
        form.addRow(self.sync_checkbox)
        form.addRow("Thời lượng mục tiêu", self.target_spin)
        form.addRow("Tệp đầu ra", output_widget)
        layout.addLayout(form)

        action_row = QHBoxLayout()
        self.run_btn = QPushButton("Ghép video")
        self.run_btn.setEnabled(self.concat_engine.is_available())
        self.run_btn.clicked.connect(self._run_concat)
        action_row.addStretch(1)
        action_row.addWidget(self.run_btn)
        layout.addLayout(action_row)

    def _add_videos(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Chọn video", "", "Tệp video (*.mp4 *.mov *.mkv);;Mọi tệp (*)")
        for path in paths:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(path))
            self.table.setItem(row, 1, QTableWidgetItem("0"))
            self.table.setItem(row, 2, QTableWidgetItem("0"))
            duration = ""
            if self.concat_engine.is_available():
                try:
                    duration = f"{self.concat_engine.get_duration(path):.2f}"
                except Exception:
                    duration = ""
            self.table.setItem(row, 3, QTableWidgetItem(duration))

    def _remove_selected(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Lưu video đầu ra", "", "Tệp video (*.mp4)")
        if path:
            self.output_edit.setText(path)

    def _run_concat(self) -> None:
        if self.table.rowCount() < 2:
            QMessageBox.warning(self, "Ghép video", "Hãy thêm ít nhất hai video.")
            return
        output_path = self.output_edit.text().strip()
        if not output_path:
            QMessageBox.warning(self, "Ghép video", "Hãy chọn nơi lưu video đầu ra.")
            return

        clips: list[ConcatClip] = []
        for row in range(self.table.rowCount()):
            path_item = self.table.item(row, 0)
            start_item = self.table.item(row, 1)
            end_item = self.table.item(row, 2)
            if not path_item:
                continue
            clips.append(
                ConcatClip(
                    path=path_item.text(),
                    order=row,
                    trim_start=float(start_item.text() if start_item else 0),
                    trim_end=float(end_item.text() if end_item else 0),
                )
            )

        job = ConcatJob(
            clips=clips,
            output_path=output_path,
            sync_duration=self.sync_checkbox.isChecked(),
            target_duration=self.target_spin.value(),
        )
        self.run_btn.setEnabled(False)
        self._worker = ConcatWorker(self.concat_engine, job)
        self._worker.completed.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, result: object) -> None:
        self.run_btn.setEnabled(True)
        QMessageBox.information(self, "Ghép video", f"Đã lưu: {result}")

    def _on_error(self, message: str) -> None:
        self.run_btn.setEnabled(True)
        QMessageBox.critical(self, "Ghép video", message)
