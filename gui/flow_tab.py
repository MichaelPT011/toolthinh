"""Image generation tab."""

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

from core.config import SAFE_IMAGE_PRESET
from gui.base_worker import BaseWorker
from gui.batch_widgets import BatchWidget


class FlowWorker(BaseWorker):
    """Run one image generation job."""

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


class FlowTab(QWidget):
    """Prompt to image tab."""

    def __init__(self, flow_gen, auth, batch_engine) -> None:
        super().__init__()
        self.flow_gen = flow_gen
        self.auth = auth
        self.batch_engine = batch_engine
        self.browser_assist = getattr(flow_gen, "browser_assist", None)
        self.reference_image_path: str | None = None
        self._worker: FlowWorker | None = None
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
        refresh_btn = QPushButton("Tai lai")
        refresh_btn.clicked.connect(self.reload_accounts)
        account_row.addWidget(self.account_combo)
        account_row.addWidget(refresh_btn)
        account_widget = QWidget()
        account_widget.setLayout(account_row)
        form.addRow("Ho so dang dung", account_widget)

        self.prompt_input = QPlainTextEdit()
        self.prompt_input.setPlaceholderText("Mo ta anh ban muon tao")
        self.prompt_input.setMinimumHeight(120)
        form.addRow("Mo ta anh", self.prompt_input)

        self.num_images_spin = QSpinBox()
        self.num_images_spin.setRange(1, 4)
        self.num_images_spin.setValue(1)
        form.addRow("So anh tai ve", self.num_images_spin)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["1080p", "2K", "4K"])
        form.addRow("Chat luong tai", self.quality_combo)

        self.orientation_combo = QComboBox()
        self.orientation_combo.addItem("Ngang (16:9)", "landscape")
        self.orientation_combo.addItem("Doc (9:16)", "portrait")
        form.addRow("Khung hinh", self.orientation_combo)

        self.reference_label = QLabel("Chua chon anh tham chieu")
        ref_row = QHBoxLayout()
        ref_row.setContentsMargins(0, 0, 0, 0)
        ref_row.addWidget(self.reference_label, 1)
        ref_browse = QPushButton("Chon anh")
        ref_clear = QPushButton("Xoa")
        ref_browse.clicked.connect(self._browse_reference_image)
        ref_clear.clicked.connect(self._clear_reference_image)
        ref_row.addWidget(ref_browse)
        ref_row.addWidget(ref_clear)
        ref_widget = QWidget()
        ref_widget.setLayout(ref_row)
        form.addRow("Anh tham chieu", ref_widget)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self.safe_preset_btn = QCheckBox("Dang dung preset an toan")
        self.batch_btn = QPushButton("Tao hang loat ⛓️")
        self.gen_btn = QPushButton("Tao ngay bay gio👍")
        self.stop_btn = QPushButton("Dung")
        self.stop_btn.setEnabled(False)
        self.safe_preset_btn.setChecked(True)
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
            self.flow_gen,
            self.auth,
            self.batch_engine,
            "flow",
            self._build_batch_rows,
            self._describe_batch_logic,
            self,
        )
        self.batch_widget.setVisible(False)
        layout.addWidget(self.batch_widget)

        self.safe_hint = QLabel("Preset an toan anh: 1 anh, 1080p, ngang, batch song song 2.")
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
        self.table.setHorizontalHeaderLabels(["#", "Mo ta", "Trang thai", "Tep dau ra", "Bat dau"])
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

        self._on_safe_preset_toggled(True)
        self._refresh_batch_button_style()

    def reload_accounts(self) -> None:
        current = self.account_combo.currentData()
        if self.browser_assist and self.browser_assist.has_browser_profile_data() and not self.auth.get_active_accounts():
            self.auth.ensure_browser_profile_account()
        self.account_combo.clear()
        for account in self.auth.get_active_accounts():
            self.account_combo.addItem(account.get("nickname", "Ho so"), account["account_id"])
        if self.account_combo.count() == 0:
            self.account_combo.addItem("Chua dang nhap Flow/VEO3", None)
        if current:
            index = self.account_combo.findData(current)
            if index >= 0:
                self.account_combo.setCurrentIndex(index)

    def _browse_reference_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Chon anh tham chieu", "", "Tep anh (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.reference_image_path = path
            self.reference_label.setText(Path(path).name)

    def _clear_reference_image(self) -> None:
        self.reference_image_path = None
        self.reference_label.setText("Chua chon anh tham chieu")

    def _toggle_batch(self) -> None:
        visible = not self.batch_widget.isVisible()
        self.batch_widget.setVisible(visible)
        self.batch_btn.setText("An tao hang loat" if visible else "Tao hang loat ⛓️")
        self._refresh_batch_button_style()
        if visible:
            self.batch_widget.refresh_from_parent()
            QTimer.singleShot(0, lambda: self.scroll.ensureWidgetVisible(self.batch_widget))

    def _apply_safe_preset(self, startup: bool = False) -> None:
        self.num_images_spin.setValue(int(SAFE_IMAGE_PRESET["num_images"]))
        quality_index = self.quality_combo.findText(str(SAFE_IMAGE_PRESET["download_quality"]))
        if quality_index >= 0:
            self.quality_combo.setCurrentIndex(quality_index)
        orientation_index = self.orientation_combo.findData(SAFE_IMAGE_PRESET["orientation"])
        if orientation_index >= 0:
            self.orientation_combo.setCurrentIndex(orientation_index)
        mode_index = self.batch_widget.mode_combo.findData(SAFE_IMAGE_PRESET["batch_mode"])
        if mode_index >= 0:
            self.batch_widget.mode_combo.setCurrentIndex(mode_index)
        self.batch_widget.concurrent_spin.setValue(int(SAFE_IMAGE_PRESET["batch_concurrent"]))
        if not startup:
            self.progress_label.setText("Da ap dung preset an toan cho tab Anh.")

    def _on_safe_preset_toggled(self, checked: bool) -> None:
        if checked:
            self._apply_safe_preset(startup=True)
            self.progress_label.setText("Dang dung preset an toan cho tab Anh.")
        self.num_images_spin.setEnabled(not checked)
        self.quality_combo.setEnabled(not checked)
        self.orientation_combo.setEnabled(not checked)
        self.batch_widget.mode_combo.setEnabled(not checked)
        self.batch_widget.concurrent_spin.setEnabled(not checked)
        self.safe_preset_btn.setText("Dang dung preset an toan" if checked else "Dung preset an toan")
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
                "Ban chua dang nhap Flow/VEO3.\n\n"
                "Hay vao tab Tai khoan, bam Mo trinh duyet dang nhap Flow, "
                "dang nhap xong roi quay lai tao."
            )
        if self.browser_assist and not self.browser_assist.has_browser_profile_data():
            return (
                "Ban chua dang nhap Flow/VEO3 trong browser cua app.\n\n"
                "Hay vao tab Tai khoan, bam Mo trinh duyet dang nhap Flow, "
                "dang nhap xong roi quay lai tao."
            )
        return None

    def _generate(self) -> None:
        prompt = self.prompt_input.toPlainText().strip()
        account_id = self.account_combo.currentData()
        readiness_warning = self._generation_readiness_warning()
        if readiness_warning:
            QMessageBox.warning(self, "Anh Flow", readiness_warning)
            return
        if not prompt or not account_id:
            QMessageBox.warning(self, "Anh Flow", "Hay nhap mo ta anh va chon ho so.")
            return

        if not getattr(self.flow_gen, "flow_automation", None):
            QApplication.clipboard().setText(prompt)

        self.gen_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress_label.setText("Dang chuan bi gui yeu cau tao anh...")
        self._current_row = self._start_job_row(prompt)

        self._worker = FlowWorker(
            self.flow_gen,
            prompt,
            account_id,
            image_path=self.reference_image_path,
            num_images=self.num_images_spin.value(),
            download_quality=self.quality_combo.currentText(),
            orientation=self.orientation_combo.currentData(),
            launch_browser=not getattr(self.flow_gen, "flow_automation", None),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.status.connect(self._on_status)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.start()

    def _stop_current_job(self) -> None:
        if self._worker:
            self.stop_btn.setEnabled(False)
            self.progress_label.setText("Dang dung tac vu anh...")
            self._worker.request_cancel()

    def _on_progress(self, value: int) -> None:
        self.progress.setVisible(True)
        self.progress.setValue(max(0, min(100, value)))
        if self._current_row is not None:
            self._set_job_row_status(self._current_row, f"Dang chay {max(0, min(100, value))}%")

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
                self.progress_label.setText(f"Da tao xong va tai ve {len(job.get('output_paths', []))} anh.")
            else:
                self.progress.setVisible(False)
                self.progress_label.setText(job.get("error", "") or f"Ket thuc voi trang thai: {job.get('status', '')}")
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
            self._set_job_row_status(self._current_row, "failed")
            self._set_job_row_output(self._current_row, message)
        self._current_row = None
        QMessageBox.critical(self, "Anh Flow", message)

    def _on_cancelled(self, message: str) -> None:
        self.gen_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress.setVisible(False)
        self.progress_label.setText(message)
        if self._current_row is not None:
            self._set_job_row_status(self._current_row, "cancelled")
            self._set_job_row_output(self._current_row, message)
        self._current_row = None

    def _start_job_row(self, prompt: str) -> int:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.table.setItem(row, 1, QTableWidgetItem(prompt))
        self.table.setItem(row, 2, QTableWidgetItem("Dang khoi tao..."))
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
        self._set_job_row_status(self._current_row, job.get("status", ""))
        self._set_job_row_output(self._current_row, " | ".join(job.get("output_paths", [])) or job.get("error", ""))
        started_item = self.table.item(self._current_row, 4)
        if started_item:
            started_item.setText(job.get("started_at", ""))

    def _build_batch_rows(self, prompts: list[str], assets: dict) -> list[dict]:
        sequence_files = list(assets.get("sequence_files") or [])
        shared_reference = self.reference_image_path
        rows: list[dict] = []

        if sequence_files and len(sequence_files) not in {1, len(prompts)}:
            raise ValueError("Batch anh tham chieu can dung 1 anh dung chung hoac dung bang so prompt.")

        for index, prompt in enumerate(prompts):
            image_path = None
            if sequence_files:
                image_path = sequence_files[0] if len(sequence_files) == 1 else sequence_files[index]
            elif shared_reference:
                image_path = shared_reference

            rows.append(
                {
                    "prompt": prompt,
                    "kwargs": {
                        "image_path": image_path,
                        "num_images": self.num_images_spin.value(),
                        "download_quality": self.quality_combo.currentText(),
                        "orientation": self.orientation_combo.currentData(),
                    },
                    "source_label": Path(image_path).name if image_path else "Khong dung anh tham chieu",
                    "gen_type": "flow",
                }
            )
        return rows

    def _describe_batch_logic(self) -> str:
        return (
            "Anh hang loat: neu ban nap 1 anh thi toan bo prompt dung chung anh do. "
            "Neu nap nhieu anh thi prompt thu N se di voi anh thu N."
        )
