"""Reusable inline batch widget."""

from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.batch import BatchJob, BatchMode
from gui.base_worker import BaseWorker


class BatchRunWorker(BaseWorker):
    """Execute one batch run and forward row updates."""

    row_update = Signal(object)

    def __init__(
        self,
        engine,
        generators: dict,
        auth,
        row_indices: list[int],
        rows_payload: list[dict],
        mode: BatchMode,
        max_concurrent: int,
        interval: int,
    ) -> None:
        super().__init__()
        self.engine = engine
        self.generators = generators
        self.auth = auth
        self.row_indices = row_indices
        self.rows_payload = rows_payload
        self.mode = mode
        self.max_concurrent = max_concurrent
        self.interval = interval

    async def _run_async(self):
        self.engine.clear()
        for payload in self.rows_payload:
            self.engine.add_job(BatchJob(payload["prompt"], payload["gen_type"], **payload["kwargs"]))

        def on_status(index, status, output) -> None:
            self.row_update.emit(
                {
                    "row": self.row_indices[index],
                    "status": status,
                    "output": output,
                    "error": "",
                    "final": False,
                }
            )

        def on_progress(index, job) -> None:
            output = ""
            if job.result and job.result.get("output_paths"):
                output = " | ".join(job.result["output_paths"])
            error = job.error or (job.result or {}).get("error", "")
            self.row_update.emit(
                {
                    "row": self.row_indices[index],
                    "status": job.status,
                    "output": output,
                    "error": error,
                    "final": True,
                }
            )

        await self.engine.run(
            self.generators,
            self.auth,
            mode=self.mode,
            max_concurrent=self.max_concurrent,
            interval=self.interval,
            on_progress=on_progress,
            on_status=on_status,
            cancel_event=self.cancel_event,
        )
        return list(self.engine.queue)


class BatchWidget(QFrame):
    """Inline batch controls displayed inside the main tabs."""

    TABLE_COLUMNS = [
        "#",
        "Prompt",
        "Dữ liệu",
        "Trạng thái",
        "Mã",
        "Lần thử",
        "Tệp đầu ra",
        "Lỗi",
        "Tác vụ",
    ]

    def __init__(self, generator, auth, batch_engine, gen_type: str, build_rows, describe_logic, parent=None) -> None:
        super().__init__(parent)
        self.generator = generator
        self.auth = auth
        self.batch_engine = batch_engine
        self.gen_type = gen_type
        self.build_rows = build_rows
        self.describe_logic = describe_logic
        self.prompts: list[str] = []
        self.sequence_files: list[str] = []
        self.root_folder: str | None = None
        self.rows: list[dict] = []
        self._worker: BatchRunWorker | None = None
        self._table_sync = False
        self._success_count = 0
        self._failure_count = 0
        self.setObjectName("batchPanel")
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel("Tạo hàng loạt")
        title.setObjectName("batchTitle")
        layout.addWidget(title)

        self.logic_label = QLabel("")
        self.logic_label.setWordWrap(True)
        layout.addWidget(self.logic_label)

        stats_grid = QGridLayout()
        total_card, self.total_label = self._stat_card("Tổng")
        success_card, self.success_label = self._stat_card("Thành công")
        failed_card, self.failed_label = self._stat_card("Lỗi")
        running_card, self.running_label = self._stat_card("Đang chạy")
        stats_grid.addWidget(total_card, 0, 0)
        stats_grid.addWidget(success_card, 0, 1)
        stats_grid.addWidget(failed_card, 0, 2)
        stats_grid.addWidget(running_card, 0, 3)
        layout.addLayout(stats_grid)

        controls = QFormLayout()
        controls.setSpacing(12)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Tuần tự an toàn", BatchMode.SEQUENTIAL.value)
        self.mode_combo.addItem("Song song thông minh (1 browser)", BatchMode.PARALLEL.value)
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 8)
        self.concurrent_spin.setValue(2)
        controls.addRow("Kiểu chạy", self.mode_combo)
        controls.addRow("Số tác vụ song song", self.concurrent_spin)
        layout.addLayout(controls)

        source_grid = QGridLayout()
        source_grid.setHorizontalSpacing(10)
        source_grid.setVerticalSpacing(10)
        buttons = [
            ("Nạp prompt .txt", self._load_prompts),
            ("Thêm prompt", self._add_prompt),
            ("Nạp tệp dữ liệu", self._load_sequence_files),
            ("Nạp thư mục dữ liệu", self._load_root_folder),
            ("Xóa nguồn batch", self._clear_sources),
        ]
        for index, (label, handler) in enumerate(buttons):
            button = QPushButton(label)
            button.clicked.connect(handler)
            source_grid.addWidget(button, index // 3, index % 3)
        source_grid.setColumnStretch(0, 1)
        source_grid.setColumnStretch(1, 1)
        source_grid.setColumnStretch(2, 1)
        layout.addLayout(source_grid)

        self.source_label = QLabel("")
        self.source_label.setWordWrap(True)
        layout.addWidget(self.source_label)

        filter_row = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Tất cả", "Chỉ lỗi", "Chỉ thành công", "Đang chạy"])
        self.filter_combo.currentTextChanged.connect(self._apply_filter)
        clear_btn = QPushButton("Xóa danh sách")
        clear_btn.clicked.connect(self._clear_everything)
        filter_row.addWidget(QLabel("Lọc danh sách"))
        filter_row.addWidget(self.filter_combo)
        filter_row.addStretch(1)
        filter_row.addWidget(clear_btn)
        layout.addLayout(filter_row)

        retry_row = QHBoxLayout()
        self.export_errors_btn = QPushButton("Xuất danh sách lỗi")
        self.export_errors_btn.clicked.connect(self._export_errors)
        self.retry_failed_btn = QPushButton("Tạo lại toàn bộ lỗi")
        self.retry_failed_btn.clicked.connect(self._retry_failed_rows)
        retry_row.addStretch(1)
        retry_row.addWidget(self.export_errors_btn)
        retry_row.addWidget(self.retry_failed_btn)
        layout.addLayout(retry_row)

        self.table = QTableWidget(0, len(self.TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels(self.TABLE_COLUMNS)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setMinimumHeight(340)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table)

        action_row = QHBoxLayout()
        self.run_btn = QPushButton("Chạy batch")
        self.cancel_btn = QPushButton("Dừng batch")
        self.cancel_btn.setEnabled(False)
        self.run_btn.clicked.connect(self._run_batch)
        self.cancel_btn.clicked.connect(self._cancel)
        action_row.addStretch(1)
        action_row.addWidget(self.cancel_btn)
        action_row.addWidget(self.run_btn)
        layout.addLayout(action_row)

        self.refresh_from_parent()

    def _stat_card(self, title: str) -> tuple[QWidget, QLabel]:
        wrapper = QWidget()
        wrapper.setObjectName("batchPanel")
        inner = QVBoxLayout(wrapper)
        inner.setContentsMargins(12, 10, 12, 10)
        heading = QLabel(title)
        heading.setObjectName("batchTitle")
        value = QLabel("0")
        value.setProperty("statValue", True)
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(heading, alignment=Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(value, alignment=Qt.AlignmentFlag.AlignCenter)
        return wrapper, value

    def refresh_from_parent(self) -> None:
        self.logic_label.setText(self.describe_logic())
        self._refresh_source_label()
        self._rebuild_rows(preserve_state=True)

    def _refresh_source_label(self) -> None:
        file_count = len(self.sequence_files)
        folder_text = self.root_folder or "Chưa chọn"
        self.source_label.setText(
            f"Tệp dữ liệu batch: {file_count} | Thư mục dữ liệu: {folder_text}"
        )

    def _load_prompts(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Nạp file prompt", "", "Tệp văn bản (*.txt);;Mọi tệp (*)")
        if not file_path:
            return
        with open(file_path, "r", encoding="utf-8") as handle:
            self.prompts = [line.strip() for line in handle if line.strip()]
        self._rebuild_rows()

    def _add_prompt(self) -> None:
        prompt, ok = QInputDialog.getMultiLineText(self, "Thêm prompt", "Nhập mỗi prompt một đoạn:")
        if not ok or not prompt.strip():
            return
        self.prompts.append(prompt.strip())
        self._rebuild_rows()

    def _load_sequence_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn tệp dữ liệu batch",
            "",
            "Ảnh / video (*.png *.jpg *.jpeg *.webp *.mp4 *.mov *.mkv *.webm);;Mọi tệp (*)",
        )
        if not paths:
            return
        self.sequence_files = paths
        self._refresh_source_label()
        self._rebuild_rows(preserve_state=True)

    def _load_root_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục dữ liệu batch", "")
        if not folder:
            return
        self.root_folder = folder
        self._refresh_source_label()
        self._rebuild_rows(preserve_state=True)

    def _clear_sources(self) -> None:
        self.sequence_files = []
        self.root_folder = None
        self._refresh_source_label()
        self._rebuild_rows(preserve_state=True)

    def _clear_everything(self) -> None:
        self.prompts.clear()
        self.sequence_files = []
        self.root_folder = None
        self.rows.clear()
        self._success_count = 0
        self._failure_count = 0
        self._refresh_source_label()
        self._refresh_table()
        self._refresh_summary()

    def _rebuild_rows(self, preserve_state: bool = False) -> None:
        previous = list(self.rows) if preserve_state else []
        if not self.prompts:
            self.rows = []
            self._refresh_table()
            self._refresh_summary()
            return

        try:
            built_rows = self.build_rows(
                self.prompts,
                {
                    "sequence_files": list(self.sequence_files),
                    "root_folder": self.root_folder,
                },
            )
        except Exception as exc:
            if not preserve_state:
                QMessageBox.warning(self, "Tạo hàng loạt", str(exc))
            built_rows = [
                {
                    "prompt": prompt,
                    "kwargs": {},
                    "source_label": str(exc),
                    "gen_type": self.gen_type,
                }
                for prompt in self.prompts
            ]

        self.rows = []
        for index, built in enumerate(built_rows):
            old = previous[index] if index < len(previous) else {}
            self.rows.append(
                {
                    "prompt": built["prompt"],
                    "kwargs": built["kwargs"],
                    "source_label": built.get("source_label", ""),
                    "gen_type": built.get("gen_type", self.gen_type),
                    "status": old.get("status", "pending"),
                    "output": old.get("output", ""),
                    "error": old.get("error", ""),
                    "attempts": old.get("attempts", 0),
                    "code": old.get("code", ""),
                }
            )
        self._refresh_table()
        self._refresh_summary()

    def _refresh_table(self) -> None:
        self._table_sync = True
        self.table.setRowCount(len(self.rows))
        for row_index, row in enumerate(self.rows):
            values = [
                str(row_index + 1),
                row.get("prompt", ""),
                row.get("source_label", ""),
                row.get("status", ""),
                row.get("code", ""),
                str(row.get("attempts", 0)),
                row.get("output", ""),
                row.get("error", ""),
            ]
            for column, value in enumerate(values):
                item = self.table.item(row_index, column)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(row_index, column, item)
                item.setText(value)
                if column != 1:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                else:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self._apply_row_style(row_index)
            self._set_row_actions(row_index)
        self._table_sync = False
        self._apply_filter()

    def _apply_row_style(self, row_index: int) -> None:
        status = (self.rows[row_index].get("status") or "").lower()
        if "completed" in status or "thành công" in status:
            color = QColor("#166534")
        elif "failed" in status or "timeout" in status or "error" in status or "lỗi" in status:
            color = QColor("#b91c1c")
        elif "running" in status or "đang" in status:
            color = QColor("#92400e")
        else:
            color = QColor("#475569")
        item = self.table.item(row_index, 3)
        if item:
            item.setForeground(color)

    def _set_row_actions(self, row_index: int) -> None:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        retry_btn = QPushButton("Tạo lại")
        retry_btn.setEnabled(self.rows[row_index].get("status") in {"failed", "timeout", "cancelled"})
        retry_btn.clicked.connect(lambda _checked=False, index=row_index: self._retry_rows([index]))
        layout.addWidget(retry_btn)
        self.table.setCellWidget(row_index, 8, wrapper)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._table_sync or item.column() != 1:
            return
        row = item.row()
        if 0 <= row < len(self.rows):
            self.rows[row]["prompt"] = item.text().strip()
            self.prompts[row] = self.rows[row]["prompt"]

    def _refresh_summary(self) -> None:
        total = len(self.rows)
        success = sum(1 for row in self.rows if row.get("status") == "completed")
        failed = sum(1 for row in self.rows if row.get("status") in {"failed", "timeout", "cancelled"})
        running = sum(
            1
            for row in self.rows
            if "đang" in str(row.get("status", "")).lower() or row.get("status") == "running"
        )
        self.total_label.setText(str(total))
        self.success_label.setText(str(success))
        self.failed_label.setText(str(failed))
        self.running_label.setText(str(running))
        self.retry_failed_btn.setEnabled(failed > 0)
        self.export_errors_btn.setEnabled(failed > 0)

    def _apply_filter(self) -> None:
        mode = self.filter_combo.currentText()
        for row_index, row in enumerate(self.rows):
            status = row.get("status", "")
            hide = False
            if mode == "Chỉ lỗi":
                hide = status not in {"failed", "timeout", "cancelled"}
            elif mode == "Chỉ thành công":
                hide = status != "completed"
            elif mode == "Đang chạy":
                hide = not ("đang" in str(status).lower() or status == "running")
            self.table.setRowHidden(row_index, hide)

    def _build_payloads(self, row_indices: list[int]) -> list[dict]:
        built_rows = self.build_rows(
            self.prompts,
            {
                "sequence_files": list(self.sequence_files),
                "root_folder": self.root_folder,
            },
        )
        for index, built in enumerate(built_rows):
            if index >= len(self.rows):
                continue
            self.rows[index]["prompt"] = built["prompt"]
            self.rows[index]["kwargs"] = built["kwargs"]
            self.rows[index]["source_label"] = built.get("source_label", "")
            self.rows[index]["gen_type"] = built.get("gen_type", self.gen_type)
        self._refresh_table()
        return [
            {
                "prompt": self.rows[row_index]["prompt"],
                "kwargs": self.rows[row_index]["kwargs"],
                "gen_type": self.rows[row_index]["gen_type"],
            }
            for row_index in row_indices
        ]

    def _run_batch(self) -> None:
        if not self.prompts:
            QMessageBox.information(self, "Tạo hàng loạt", "Hãy thêm ít nhất một prompt.")
            return
        if not self.auth.get_active_accounts():
            QMessageBox.warning(self, "Tạo hàng loạt", "Hãy có ít nhất một hồ sơ đang hoạt động.")
            return
        preflight_check = getattr(self.parent(), "_generation_readiness_warning", None)
        if callable(preflight_check):
            message = preflight_check()
            if message:
                QMessageBox.warning(self, "Batch", message)
                return
        self._retry_rows(list(range(len(self.prompts))), reset_codes=True)

    def _retry_failed_rows(self) -> None:
        failed_rows = [
            index
            for index, row in enumerate(self.rows)
            if row.get("status") in {"failed", "timeout", "cancelled"}
        ]
        if not failed_rows:
            QMessageBox.information(self, "Tạo hàng loạt", "Hiện không có prompt lỗi để tạo lại.")
            return
        self._retry_rows(failed_rows)

    def _retry_rows(self, row_indices: list[int], reset_codes: bool = False) -> None:
        if self._worker:
            QMessageBox.information(self, "Tạo hàng loạt", "Batch đang chạy. Hãy chờ xong hoặc bấm Dừng batch.")
            return

        try:
            payloads = self._build_payloads(row_indices)
        except Exception as exc:
            QMessageBox.warning(self, "Tạo hàng loạt", str(exc))
            return

        if reset_codes:
            self._success_count = 0
            self._failure_count = 0

        for row_index in row_indices:
            self.rows[row_index]["status"] = "Đang khởi tạo..."
            self.rows[row_index]["output"] = ""
            self.rows[row_index]["error"] = ""
            self.rows[row_index]["attempts"] = int(self.rows[row_index].get("attempts", 0)) + 1
        self._refresh_table()
        self._refresh_summary()

        from gui.settings_dialog import load_settings

        settings = load_settings()
        mode = BatchMode(self.mode_combo.currentData())
        generators = {self.gen_type: self.generator}
        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        self._worker = BatchRunWorker(
            self.batch_engine,
            generators,
            self.auth,
            row_indices,
            payloads,
            mode,
            self.concurrent_spin.value(),
            settings.get("batch_interval", 2),
        )
        self._worker.row_update.connect(self._on_row_update)
        self._worker.finished.connect(self._on_batch_finished)
        self._worker.error.connect(self._on_batch_error)
        self._worker.cancelled.connect(self._on_batch_cancelled)
        self._worker.start()

    def _cancel(self) -> None:
        self.batch_engine.cancel()
        if self._worker:
            self._worker.request_cancel()
        self.cancel_btn.setEnabled(False)

    def _on_row_update(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        row_index = int(payload["row"])
        row = self.rows[row_index]
        row["status"] = payload["status"]
        if payload.get("output"):
            row["output"] = payload["output"]
        if payload.get("error"):
            row["error"] = payload["error"]

        if payload.get("final"):
            if row["status"] == "completed":
                self._success_count += 1
                row["code"] = f"OK-{self._success_count:04d}"
                row["error"] = ""
            elif row["status"] in {"failed", "timeout", "cancelled"}:
                self._failure_count += 1
                row["code"] = f"ERR-{self._failure_count:04d}"
        self._refresh_table()
        self._refresh_summary()

    def _on_batch_finished(self, _result: object) -> None:
        self._worker = None
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._refresh_summary()

    def _on_batch_error(self, message: str) -> None:
        self._worker = None
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        QMessageBox.critical(self, "Tạo hàng loạt", message)

    def _on_batch_cancelled(self, message: str) -> None:
        self._worker = None
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        QMessageBox.information(self, "Tạo hàng loạt", message)
        self._refresh_summary()

    def _export_errors(self) -> None:
        failed_rows = [row for row in self.rows if row.get("status") in {"failed", "timeout", "cancelled"}]
        if not failed_rows:
            QMessageBox.information(self, "Tạo hàng loạt", "Hiện không có dòng lỗi để xuất.")
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Xuất danh sách lỗi",
            str(Path.home() / "batch_errors.csv"),
            "CSV (*.csv)",
        )
        if not output_path:
            return

        with open(output_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["code", "prompt", "status", "error", "source"])
            for row in failed_rows:
                writer.writerow(
                    [
                        row.get("code", ""),
                        row.get("prompt", ""),
                        row.get("status", ""),
                        row.get("error", ""),
                        row.get("source_label", ""),
                    ]
                )
        QMessageBox.information(self, "Tạo hàng loạt", f"Đã xuất danh sách lỗi ra:\n{output_path}")
