"""Simple in-app guide."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget


class HelpTab(QWidget):
    """Short guide and support information."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        hero = QLabel("Huong dan dung nhanh")
        hero.setObjectName("heroNote")
        layout.addWidget(hero)

        cards = [
            (
                "Mo phan mem",
                "Chi can mo Tool Veo3's Thinh. Moi lan mo len app se tu kiem tra ban cap nhat moi.",
            ),
            (
                "Dang nhap 1 lan",
                "Vao tab Tai khoan, bam mo trinh duyet dang nhap Flow roi dang nhap tai khoan cua ban. Tu lan sau app se nho phien nay.",
            ),
            (
                "Neu may chua co Chrome",
                "App se tu tai browser chinh thuc khi can. Ban khong can tu di tim browser de cai them.",
            ),
            (
                "Tao video",
                "Vao tab Video VEO3. Neu muon it loi nhat hay bam Preset an toan truoc, sau do nhap mo ta va bam Tao ngay bay gio.",
            ),
            (
                "Tao anh",
                "Vao tab Anh Flow. Neu muon on dinh nhat hay bam Preset an toan. Neu can bam theo bo cuc co san, hay them anh tham chieu.",
            ),
            (
                "Tao hang loat",
                "Bam Tao hang loat de nap nhieu prompt. Neu mot dong loi, ban co the sua prompt truc tiep va bam Tao lai ngay tren dong do.",
            ),
            (
                "Kiem tra moi truong",
                "Neu may moi cai hoac chay hay loi, vao menu Cong cu roi bam Kiem tra moi truong. App se tu kiem tra browser, thu muc va automation.",
            ),
            (
                "Meo de chay on dinh",
                "Video nen de song song thap de tranh Flow nghen. Anh co the de song song cao hon. Khi can nhanh nhat, uu tien 1080p.",
            ),
            (
                "Khi thay loi",
                "Neu app bao loi dang nhap hoac Flow khong phan hoi, hay dang nhap Flow lai trong tab Tai khoan roi thu lai.",
            ),
        ]

        for title, body in cards:
            layout.addWidget(self._card(title, body))

        support = QLabel("Lien he Zalo: 0932694714 neu can ho tro")
        support.setAlignment(Qt.AlignmentFlag.AlignCenter)
        support.setObjectName("batchTitle")
        layout.addWidget(support)

        zalo_btn = QPushButton("Mo Zalo ho tro")
        zalo_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://zalo.me/0932694714")))
        layout.addWidget(zalo_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)

        scroll.setWidget(container)
        root.addWidget(scroll)

    def _card(self, title: str, body: str) -> QWidget:
        wrapper = QWidget()
        wrapper.setObjectName("batchPanel")
        layout = QVBoxLayout(wrapper)
        heading = QLabel(title)
        heading.setObjectName("batchTitle")
        detail = QLabel(body)
        detail.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(detail)
        return wrapper
