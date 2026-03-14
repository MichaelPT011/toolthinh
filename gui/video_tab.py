"""Video generation tab."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.config import SAFE_VIDEO_PRESET
from gui.base_worker import BaseWorker
from gui.batch_widgets import BatchWidget


class VideoWorker(BaseWorker):
    """Run one video generation job."""

    def __init__(self, generator, prompt: str, account_id: str, **kwargs: object) -> None:
        super().__init__()
        self.generator = generator
        self.prompt = prompt
        self.account_id = account_id
        self.kwargs = kwargs

    async def _run_async(self):
        return await self.generator.generate(
            self.prompt,
            self.account_id,
            cancel_event=self.cancel_event,
            progress_callback=self.progress.emit,
            status_callback=self.status.emit,
            **self.kwargs,
        )


class VideoTab(QWidget):
    """Prompt to video tab."""

    def __init__(self, video_gen, auth, batch_engine) -> None:
        super().__init__()
        self.video_gen = video_gen
        self.auth = auth
        self.batch_engine = batch_engine
        self.browser_assist = getattr(video_gen, "browser_assist", None)
        self.image_path: str | None = None
        self.start_image_path: str | None = None
        self.end_image_path: str | None = None
        self.ingredient_paths: list[str] = []
        self._worker: VideoWorker | None = None
        self._current_row: int | None = None
        self._init_ui()
        self.reload_accounts()

    def _init_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(12)

        account_row = QHBoxLayout()
        self.account_combo = QComboBox()
        refresh_btn = QPushButton("Tải lại")
        refresh_btn.clicked.connect(self.reload_accounts)
        account_row.addWidget(self.account_combo)
        account_row.addWidget(refresh_btn)
        account_widget = QWidget()
        account_widget.setLayout(account_row)
        form.addRow("Hồ sơ đang dùng", account_widget)

        self.prompt_input = QPlainTextEdit()
        self.prompt_input.setPlaceholderText("Mô tả video bạn muốn tạo")
        self.prompt_input.setMinimumHeight(120)
        form.addRow("Mô tả video", self.prompt_input)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Từ prompt", "text")
        self.mode_combo.addItem("Từ 1 ảnh", "image")
        self.mode_combo.addItem("Từ ảnh đầu và ảnh cuối", "start_end")
        self.mode_combo.addItem("Từ thành phần (nhiều ảnh)", "ingredients")
        self.mode_combo.addItem("Kéo dài video", "extend")
        self.mode_combo.currentIndexChanged.connect(self._update_mode_fields)
        form.addRow("Kiểu tạo video", self.mode_combo)

        self.output_count_spin = QSpinBox()
        self.output_count_spin.setRange(1, 4)
        self.output_count_spin.setValue(1)
        form.addRow("Số video tải về", self.output_count_spin)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["1080p", "2K", "4K"])
        form.addRow("Chất lượng tải", self.quality_combo)

        self.ratio_combo = QComboBox()
        self.ratio_combo.addItem("Ngang (16:9)", "16:9")
        self.ratio_combo.addItem("Dọc (9:16)", "9:16")
        form.addRow("Khung hình", self.ratio_combo)

        self.duration_combo = QComboBox()
        self.duration_combo.addItems(["4s", "8s"])
        self.duration_combo.setCurrentText("8s")
        form.addRow("Thời lượng", self.duration_combo)

        self.model_label = QLabel("Veo 3.1 - Fast")
        form.addRow("Model video", self.model_label)

        self.single_image_title = QLabel("Ảnh nguồn")
        self.image_label = QLabel("Chưa chọn ảnh")
        self.single_image_widget = self._build_file_row(
            self.image_label,
            self._browse_single_image,
            self._clear_single_image,
        )
        form.addRow(self.single_image_title, self.single_image_widget)

        self.start_image_title = QLabel("Ảnh đầu")
        self.start_image_label = QLabel("Chưa chọn ảnh đầu")
        self.start_image_widget = self._build_file_row(
            self.start_image_label,
            self._browse_start_image,
            self._clear_start_image,
        )
        form.addRow(self.start_image_title, self.start_image_widget)

        self.end_image_title = QLabel("Ảnh cuối")
        self.end_image_label = QLabel("Chưa chọn ảnh cuối")
        self.end_image_widget = self._build_file_row(
            self.end_image_label,
            self._browse_end_image,
            self._clear_end_image,
        )
        form.addRow(self.end_image_title, self.end_image_widget)

        self.ingredients_title = QLabel("Bộ ảnh thành phần")
        self.ingredients_label = QLabel("Chưa chọn ảnh thành phần")
        self.ingredients_widget = self._build_multi_file_row(
            self.ingredients_label,
            self._browse_ingredients,
            self._clear_ingredients,
        )
        form.addRow(self.ingredients_title, self.ingredients_widget)

        self.extend_info_title = QLabel("Chế độ kéo dài")
        self.extend_info_label = QLabel(
            "Chế độ này sẽ dùng cùng project Flow hiện tại. Prompt 1 tạo video gốc, prompt sau sẽ extend tiếp."
        )
        self.extend_info_label.setWordWrap(True)
        form.addRow(self.extend_info_title, self.extend_info_label)

        layout.addLayout(form)

        actions = QHBoxLayout()
        self.safe_preset_btn = QCheckBox("Dùng preset an toàn")
        self.batch_btn = QPushButton("Tạo hàng loạt ⛓️")
        self.gen_btn = QPushButton("Tạo ngay bây giờ 👍")
        self.stop_btn = QPushButton("Dừng")
        self.stop_btn.setEnabled(False)
        self.safe_preset_btn.setText("Dùng preset an toàn")
        self.batch_btn.setText("Tạo hàng loạt ⛓️")
        self.gen_btn.setText("Tạo ngay bây giờ 👍")
        self.stop_btn.setText("Dừng")
        self.safe_preset_btn.setChecked(False)
        self.safe_preset_btn.toggled.connect(self._on_safe_preset_toggled)
        self.batch_btn.clicked.connect(self._toggle_batch)
        self.gen_btn.clicked.connect(self._generate)
        self.stop_btn.clicked.connect(self._stop_current_job)
        actions.addStretch(1)
        actions.addWidget(self.safe_preset_btn)
        actions.addWidget(self.batch_btn)
        actions.addWidget(self.stop_btn)
        actions.addWidget(self.gen_btn)
        layout.addLayout(actions)

        self.batch_widget = BatchWidget(
            self.video_gen,
            self.auth,
            self.batch_engine,
            "video",
            self._build_batch_rows,
            self._describe_batch_logic,
            self,
        )
        self.batch_widget.setVisible(False)
        layout.addWidget(self.batch_widget)

        self.safe_hint = QLabel("Preset an toàn video: 1 video, 1080p, ngang, 8 giây, batch tuần tự 1 tác vụ.")
        self.safe_hint.setWordWrap(True)
        layout.addWidget(self.safe_hint)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.progress_label = QLabel("")
        self.progress_label.setWordWrap(True)
        layout.addWidget(self.progress_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["#", "Mô tả", "Trạng thái", "Tệp đầu ra", "Bắt đầu"])
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setMinimumHeight(220)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        layout.addStretch(1)

        self.scroll.setWidget(container)
        outer.addWidget(self.scroll)

        self._on_safe_preset_toggled(False)
        self._update_mode_fields()
        self._refresh_batch_button_style()

    def _build_file_row(self, label: QLabel, browse_handler, clear_handler) -> QWidget:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        browse_btn = QPushButton("Chọn")
        clear_btn = QPushButton("Xóa")
        browse_btn.clicked.connect(browse_handler)
        clear_btn.clicked.connect(clear_handler)
        row.addWidget(label, 1)
        row.addWidget(browse_btn)
        row.addWidget(clear_btn)
        widget = QWidget()
        widget.setLayout(row)
        return widget

    def _build_multi_file_row(self, label: QLabel, browse_handler, clear_handler) -> QWidget:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        browse_btn = QPushButton("Chọn nhiều ảnh")
        clear_btn = QPushButton("Xóa")
        browse_btn.clicked.connect(browse_handler)
        clear_btn.clicked.connect(clear_handler)
        row.addWidget(label, 1)
        row.addWidget(browse_btn)
        row.addWidget(clear_btn)
        widget = QWidget()
        widget.setLayout(row)
        return widget

    def reload_accounts(self) -> None:
        current = self.account_combo.currentData()
        if self.browser_assist and self.browser_assist.has_browser_profile_data() and not self.auth.get_active_accounts():
            self.auth.ensure_browser_profile_account()
        self.account_combo.clear()
        for account in self.auth.get_active_accounts():
            self.account_combo.addItem(account.get("nickname", "Hồ sơ"), account["account_id"])
        if self.account_combo.count() == 0:
            self.account_combo.addItem("Chưa đăng nhập Flow/VEO3", None)
        if current:
            index = self.account_combo.findData(current)
            if index >= 0:
                self.account_combo.setCurrentIndex(index)

    def _browse_single_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh nguồn", "", "Tệp ảnh (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.image_path = path
            self.image_label.setText(Path(path).name)

    def _clear_single_image(self) -> None:
        self.image_path = None
        self.image_label.setText("Chưa chọn ảnh")

    def _browse_start_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh đầu", "", "Tệp ảnh (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.start_image_path = path
            self.start_image_label.setText(Path(path).name)

    def _clear_start_image(self) -> None:
        self.start_image_path = None
        self.start_image_label.setText("Chưa chọn ảnh đầu")

    def _browse_end_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh cuối", "", "Tệp ảnh (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.end_image_path = path
            self.end_image_label.setText(Path(path).name)

    def _clear_end_image(self) -> None:
        self.end_image_path = None
        self.end_image_label.setText("Chưa chọn ảnh cuối")

    def _browse_ingredients(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn ảnh thành phần",
            "",
            "Tệp ảnh (*.png *.jpg *.jpeg *.webp)",
        )
        if paths:
            self.ingredient_paths = paths
            self.ingredients_label.setText(f"Đã chọn {len(paths)} ảnh thành phần")

    def _clear_ingredients(self) -> None:
        self.ingredient_paths = []
        self.ingredients_label.setText("Chưa chọn ảnh thành phần")

    def _selected_mode(self) -> str:
        return self.mode_combo.currentData() or "text"

    def _set_mode_row_visible(self, title: QLabel, widget: QWidget, visible: bool) -> None:
        title.setVisible(visible)
        widget.setVisible(visible)

    def _update_mode_fields(self) -> None:
        mode = self._selected_mode()
        self._set_mode_row_visible(self.single_image_title, self.single_image_widget, mode == "image")
        self._set_mode_row_visible(self.start_image_title, self.start_image_widget, mode == "start_end")
        self._set_mode_row_visible(self.end_image_title, self.end_image_widget, mode == "start_end")
        self._set_mode_row_visible(self.ingredients_title, self.ingredients_widget, mode == "ingredients")
        self._set_mode_row_visible(self.extend_info_title, self.extend_info_label, mode == "extend")

        extend_mode = mode == "extend"
        if extend_mode:
            self.output_count_spin.setValue(1)
            sequential_index = self.batch_widget.mode_combo.findData("sequential")
            if sequential_index >= 0:
                self.batch_widget.mode_combo.setCurrentIndex(sequential_index)
            self.batch_widget.concurrent_spin.setValue(1)

        lock_mode_controls = self.safe_preset_btn.isChecked() or extend_mode
        self.output_count_spin.setEnabled(not lock_mode_controls)
        self.duration_combo.setEnabled(not lock_mode_controls)
        self.batch_widget.mode_combo.setEnabled(not lock_mode_controls)
        self.batch_widget.concurrent_spin.setEnabled(not lock_mode_controls)
        if hasattr(self, "batch_widget"):
            self.batch_widget.refresh_from_parent()

    def _toggle_batch(self) -> None:
        visible = not self.batch_widget.isVisible()
        self.batch_widget.setVisible(visible)
        self.batch_btn.setText("Ẩn tạo hàng loạt" if visible else "Tạo hàng loạt ⛓️")
        self._refresh_batch_button_style()
        if visible:
            self.batch_widget.refresh_from_parent()
            QTimer.singleShot(0, lambda: self.scroll.ensureWidgetVisible(self.batch_widget))

    def _apply_safe_preset(self, startup: bool = False) -> None:
        self.output_count_spin.setValue(int(SAFE_VIDEO_PRESET["num_outputs"]))
        quality_index = self.quality_combo.findText(str(SAFE_VIDEO_PRESET["download_quality"]))
        if quality_index >= 0:
            self.quality_combo.setCurrentIndex(quality_index)
        ratio_index = self.ratio_combo.findData(SAFE_VIDEO_PRESET["aspect_ratio"])
        if ratio_index >= 0:
            self.ratio_combo.setCurrentIndex(ratio_index)
        duration_index = self.duration_combo.findText(str(SAFE_VIDEO_PRESET["duration"]))
        if duration_index >= 0:
            self.duration_combo.setCurrentIndex(duration_index)
        mode_index = self.batch_widget.mode_combo.findData(SAFE_VIDEO_PRESET["batch_mode"])
        if mode_index >= 0:
            self.batch_widget.mode_combo.setCurrentIndex(mode_index)
        self.batch_widget.concurrent_spin.setValue(int(SAFE_VIDEO_PRESET["batch_concurrent"]))
        if not startup:
            self.progress_label.setText("Đã áp dụng preset an toàn cho tab Video.")

    def _on_safe_preset_toggled(self, checked: bool) -> None:
        if checked:
            self._apply_safe_preset(startup=True)
            self.progress_label.setText("Đã bật preset an toàn cho tab Video.")
        mode = self._selected_mode()
        extend_mode = mode == "extend"
        self.output_count_spin.setEnabled(not checked and not extend_mode)
        self.quality_combo.setEnabled(not checked)
        self.ratio_combo.setEnabled(not checked)
        self.duration_combo.setEnabled(not checked and not extend_mode)
        self.batch_widget.mode_combo.setEnabled(not checked and not extend_mode)
        self.batch_widget.concurrent_spin.setEnabled(not checked and not extend_mode)
        self.safe_preset_btn.setText("Đang dùng preset an toàn" if checked else "Dùng preset an toàn")
        self._refresh_safe_preset_style()

    def _refresh_safe_preset_style(self) -> None:
        if self.safe_preset_btn.isChecked():
            self.safe_preset_btn.setStyleSheet(
                "QCheckBox { background: #ecfdf5; border: 1px solid #16a34a; "
                "border-radius: 10px; padding: 8px 12px; color: #166534; font-weight: 700; }"
            )
            return
        self.safe_preset_btn.setStyleSheet(
            "QCheckBox { background: #ffffff; border: 1px solid #cbd5e1; "
            "border-radius: 10px; padding: 8px 12px; color: #0f172a; font-weight: 600; }"
        )

    def _refresh_batch_button_style(self) -> None:
        if self.batch_widget.isVisible():
            self.batch_btn.setStyleSheet(
                "QPushButton { background: #64748b; border-color: #64748b; color: white; } "
                "QPushButton:hover { background: #475569; border-color: #475569; }"
            )
            return
        self.batch_btn.setStyleSheet("")

    def _generation_readiness_warning(self) -> str | None:
        if self.browser_assist and self.browser_assist.has_browser_profile_data():
            if not self.auth.get_active_accounts():
                self.auth.ensure_browser_profile_account()
                self.reload_accounts()
            return None
        if not self.auth.get_active_accounts() or not self.account_combo.currentData():
            return (
                "Bạn chưa đăng nhập Flow/VEO3.\n\n"
                "Hãy vào tab Tài khoản, bấm Mở trình duyệt đăng nhập Flow, "
                "đăng nhập xong rồi quay lại tạo."
            )
        if self.browser_assist and not self.browser_assist.has_browser_profile_data():
            return (
                "Bạn chưa đăng nhập Flow/VEO3 trong browser của app.\n\n"
                "Hãy vào tab Tài khoản, bấm Mở trình duyệt đăng nhập Flow, "
                "đăng nhập xong rồi quay lại tạo."
            )
        return None

    def _generate(self) -> None:
        prompt = self.prompt_input.toPlainText().strip()
        account_id = self.account_combo.currentData()
        readiness_warning = self._generation_readiness_warning()
        if readiness_warning:
            QMessageBox.warning(self, "Video Flow", readiness_warning)
            return
        if not prompt or not account_id:
            QMessageBox.warning(self, "Video Flow", "Hãy nhập mô tả video và chọn hồ sơ.")
            return

        mode = self._selected_mode()
        if mode == "image" and not self.image_path:
            QMessageBox.warning(self, "Video Flow", "Hãy chọn ảnh nguồn.")
            return
        if mode == "start_end" and (not self.start_image_path or not self.end_image_path):
            QMessageBox.warning(self, "Video Flow", "Hãy chọn đủ ảnh đầu và ảnh cuối.")
            return
        if mode == "ingredients" and not self.ingredient_paths:
            QMessageBox.warning(self, "Video Flow", "Hãy chọn ít nhất một ảnh thành phần.")
            return
        if mode == "extend":
            self.progress_label.setText(
                "App sẽ kéo dài video gần nhất đã tạo thành công trong Flow profile hiện tại."
            )

        QApplication.clipboard().setText(prompt)
        self.gen_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.progress_label.setText("Đang chuẩn bị gửi yêu cầu tạo video...")
        self._current_row = self._start_job_row(prompt)

        self._worker = VideoWorker(
            self.video_gen,
            prompt,
            account_id,
            aspect_ratio=self.ratio_combo.currentData(),
            duration=self.duration_combo.currentText(),
            image_path=self.image_path,
            num_outputs=self.output_count_spin.value(),
            download_quality=self.quality_combo.currentText(),
            mode=mode,
            start_image_path=self.start_image_path,
            end_image_path=self.end_image_path,
            ingredient_paths=self.ingredient_paths,
            extend_video_path=None,
            launch_browser=False,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.status.connect(self._on_status)
        self._worker.completed.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.start()

    def _stop_current_job(self) -> None:
        if self._worker:
            self.stop_btn.setEnabled(False)
            self.progress_label.setText("Đang dừng tác vụ video...")
            self._worker.request_cancel()

    def _on_progress(self, value: int) -> None:
        self.progress.setVisible(True)
        self.progress.setValue(max(0, min(100, value)))
        if self._current_row is not None:
            self._set_job_row_status(self._current_row, f"Đang chạy {max(0, min(100, value))}%")

    def _on_status(self, text: str) -> None:
        self.progress_label.setText(text)
        if self._current_row is not None:
            self._set_job_row_status(self._current_row, text)

    def _on_finished(self, job: object) -> None:
        self.gen_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if isinstance(job, dict):
            if job.get("status") == "completed":
                self.progress.setVisible(True)
                self.progress.setValue(100)
                outputs = len(job.get("output_paths", []))
                self.progress_label.setText(f"Đã tạo xong và tải về {outputs} video.")
            else:
                self.progress.setVisible(False)
                self.progress_label.setText(job.get("error", "") or f"Kết thúc với trạng thái: {job.get('status', '')}")
            self._finish_job_row(job)
        else:
            self.progress.setVisible(False)
            self.progress_label.setText("")
        self._current_row = None

    def _on_error(self, message: str) -> None:
        self.gen_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress.setVisible(False)
        self.progress_label.setText(message)
        if self._current_row is not None:
            self._set_job_row_status(self._current_row, "Thất bại")
            self._set_job_row_output(self._current_row, message)
        self._current_row = None
        QMessageBox.critical(self, "Video Flow", message)

    def _on_cancelled(self, message: str) -> None:
        self.gen_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress.setVisible(False)
        self.progress_label.setText(message)
        if self._current_row is not None:
            self._set_job_row_status(self._current_row, "Đã hủy")
            self._set_job_row_output(self._current_row, message)
        self._current_row = None

    def _start_job_row(self, prompt: str) -> int:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.table.setItem(row, 1, QTableWidgetItem(prompt))
        self.table.setItem(row, 2, QTableWidgetItem("Đang khởi tạo..."))
        self.table.setItem(row, 3, QTableWidgetItem(""))
        self.table.setItem(row, 4, QTableWidgetItem(""))
        return row

    def _set_job_row_status(self, row: int, status: str) -> None:
        item = self.table.item(row, 2)
        if item:
            item.setText(status)

    def _set_job_row_output(self, row: int, output: str) -> None:
        item = self.table.item(row, 3)
        if item:
            item.setText(output)

    def _finish_job_row(self, job: dict) -> None:
        if self._current_row is None:
            return
        self._set_job_row_status(self._current_row, self._humanize_job_status(job.get("status", "")))
        self._set_job_row_output(self._current_row, " | ".join(job.get("output_paths", [])) or job.get("error", ""))
        started_item = self.table.item(self._current_row, 4)
        if started_item:
            started_item.setText(job.get("started_at", ""))

    @staticmethod
    def _humanize_job_status(status: str) -> str:
        mapping = {
            "completed": "Hoàn tất",
            "failed": "Thất bại",
            "cancelled": "Đã hủy",
            "timeout": "Hết thời gian chờ",
            "pending": "Đang chờ",
        }
        return mapping.get(status, status)

    def _build_batch_rows(self, prompts: list[str], assets: dict) -> list[dict]:
        mode = self._selected_mode()
        sequence_files = list(assets.get("sequence_files") or [])
        root_folder = assets.get("root_folder")
        rows: list[dict] = []

        if mode == "extend":
            if len(prompts) < 2:
                raise ValueError(
                    "Batch kéo dài cần ít nhất 2 prompt. Prompt 1 tạo video gốc, prompt 2 trở đi là các lần kéo dài tiếp."
                )
            rows.append(self._batch_row(prompts[0], "Bước 1: tạo video gốc", {"mode": "text"}))
            for step_index, prompt in enumerate(prompts[1:], start=2):
                rows.append(
                    self._batch_row(
                        prompt,
                        f"Bước {step_index}: kéo dài tiếp chuỗi video đang có",
                        {"mode": "extend"},
                    )
                )
            return rows

        if mode == "text":
            for prompt in prompts:
                rows.append(self._batch_row(prompt, "Không dùng dữ liệu", {}))
            return rows

        if mode == "image":
            shared = self.image_path
            if sequence_files and len(sequence_files) not in {1, len(prompts)}:
                raise ValueError("Batch từ 1 ảnh cần dùng 1 ảnh dùng chung hoặc đúng bằng số prompt.")
            for index, prompt in enumerate(prompts):
                image_path = None
                if sequence_files:
                    image_path = sequence_files[0] if len(sequence_files) == 1 else sequence_files[index]
                elif shared:
                    image_path = shared
                else:
                    raise ValueError("Hãy chọn ảnh nguồn dùng chung hoặc nạp tệp dữ liệu batch.")
                rows.append(self._batch_row(prompt, Path(image_path).name, {"image_path": image_path}))
            return rows

        if mode == "start_end":
            if sequence_files:
                if len(sequence_files) < len(prompts) + 1:
                    raise ValueError("Batch ảnh đầu-cuối cần ít nhất số prompt + 1 ảnh.")
                for index, prompt in enumerate(prompts):
                    start_path = sequence_files[index]
                    end_path = sequence_files[index + 1]
                    rows.append(
                        self._batch_row(
                            prompt,
                            f"{Path(start_path).name} -> {Path(end_path).name}",
                            {
                                "start_image_path": start_path,
                                "end_image_path": end_path,
                            },
                        )
                    )
                return rows
            if not self.start_image_path or not self.end_image_path:
                raise ValueError("Hãy chọn cặp ảnh đầu-cuối dùng chung hoặc nạp chuỗi ảnh batch.")
            for prompt in prompts:
                rows.append(
                    self._batch_row(
                        prompt,
                        f"{Path(self.start_image_path).name} -> {Path(self.end_image_path).name}",
                        {
                            "start_image_path": self.start_image_path,
                            "end_image_path": self.end_image_path,
                        },
                    )
                )
            return rows

        if mode == "ingredients":
            if root_folder:
                subfolders = sorted(path for path in Path(root_folder).iterdir() if path.is_dir())
                if len(subfolders) < len(prompts):
                    raise ValueError(
                        "Mỗi prompt thành phần cần 1 thư mục con riêng trong thư mục dữ liệu batch."
                    )
                for index, prompt in enumerate(prompts):
                    files = sorted(
                        str(path)
                        for path in subfolders[index].iterdir()
                        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
                    )
                    if not files:
                        raise ValueError(f"Thư mục {subfolders[index].name} chưa có ảnh thành phần.")
                    rows.append(
                        self._batch_row(
                            prompt,
                            f"{subfolders[index].name} ({len(files)} ảnh)",
                            {"ingredient_paths": files[:4]},
                        )
                    )
                return rows
            if not self.ingredient_paths:
                raise ValueError("Hãy chọn ảnh thành phần dùng chung hoặc nạp thư mục dữ liệu batch.")
            label = f"Dùng chung {len(self.ingredient_paths)} ảnh"
            for prompt in prompts:
                rows.append(self._batch_row(prompt, label, {"ingredient_paths": self.ingredient_paths[:4]}))
            return rows

        return rows

    def _batch_row(self, prompt: str, source_label: str, extra_kwargs: dict) -> dict:
        kwargs = {
            "aspect_ratio": self.ratio_combo.currentData(),
            "duration": self.duration_combo.currentText(),
            "num_outputs": self.output_count_spin.value(),
            "download_quality": self.quality_combo.currentText(),
            "mode": self._selected_mode(),
            "launch_browser": False,
        }
        kwargs.update(extra_kwargs)
        return {
            "prompt": prompt,
            "kwargs": kwargs,
            "source_label": source_label,
            "gen_type": "video",
        }

    def _describe_batch_logic(self) -> str:
        mode = self._selected_mode()
        if mode == "text":
            return "Batch từ prompt: chỉ cần file prompt .txt, mỗi dòng là một prompt."
        if mode == "image":
            return (
                "Batch từ 1 ảnh: nạp 1 ảnh dùng chung cho tất cả prompt hoặc nạp nhiều ảnh, "
                "prompt thứ N đi với ảnh thứ N."
            )
        if mode == "start_end":
            return (
                "Batch ảnh đầu-cuối: nếu có N prompt thì nạp N+1 ảnh. Prompt 1 dùng ảnh 1->2, "
                "prompt 2 dùng ảnh 2->3, cứ tiếp tục như vậy."
            )
        if mode == "ingredients":
            return (
                "Batch thành phần: gọn nhất là nạp 1 thư mục gốc, mỗi prompt tương ứng 1 thư mục con "
                "chứa các ảnh thành phần của prompt đó."
            )
        return (
            "Batch kéo dài: prompt 1 tạo video gốc. Prompt 2 trở đi sẽ kéo dài tiếp trên cùng project "
            "Flow để tạo thành một chuỗi video dài hơn."
        )
