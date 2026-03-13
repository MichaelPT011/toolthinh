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

        hero = QLabel("📘 Hướng dẫn dùng nhanh")
        hero.setObjectName("heroNote")
        layout.addWidget(hero)

        cards = [
            (
                "🚀 Mở phần mềm",
                "Chỉ cần mở Tool Veo3's Thinh. App sẽ tự kiểm tra cập nhật từ repo chính thức của Thịnh và tự dùng browser đi kèm nếu máy chưa có Chrome.",
            ),
            (
                "🔐 Đăng nhập 1 lần",
                "Vào tab Tài khoản, bấm Mở trình duyệt đăng nhập Flow, rồi đăng nhập tài khoản của bạn. Từ lần sau app sẽ nhớ phiên này.",
            ),
            (
                "🎬 Tạo video",
                "Vào tab Video VEO3, nếu muốn ít lỗi nhất hãy bấm Preset an toàn trước. Sau đó nhập mô tả và bấm Tạo ngay bây giờ👍.",
            ),
            (
                "🖼️ Tạo ảnh",
                "Vào tab Ảnh Flow, nếu muốn ít lỗi nhất hãy bấm Preset an toàn trước. Nếu muốn bám theo bố cục có sẵn, hãy thêm ảnh tham chiếu.",
            ),
            (
                "⛓️ Tạo hàng loạt",
                "Bấm Tạo hàng loạt ⛓️ để nạp nhiều prompt. Nếu một dòng lỗi, bạn có thể sửa prompt trực tiếp rồi bấm Tạo lại ngay trên chính dòng đó.",
            ),
            (
                "🧪 Kiểm tra môi trường",
                "Nếu máy mới cài hoặc chạy hay lỗi, vào menu Công cụ rồi bấm Kiểm tra môi trường. App sẽ tự kiểm tra browser, thư mục và khả năng chạy automation.",
            ),
            (
                "💡 Mẹo để chạy ổn định hơn",
                "Video nên để song song thấp để tránh Flow nghẽn. Ảnh có thể chạy song song cao hơn. Khi cần tốc độ nhanh nhất, hãy ưu tiên 1080p.",
            ),
            (
                "⚠️ Khi thấy lỗi",
                "Nếu app báo lỗi đăng nhập hoặc Flow không phản hồi, hãy mở lại tab Tài khoản và đăng nhập Flow lại. App đã tự thử lại nhiều lần nhưng vẫn cần phiên đăng nhập còn sống.",
            ),
        ]

        for title, body in cards:
            layout.addWidget(self._card(title, body))

        support = QLabel("🤙Liên hệ Zalo: 0932694714 nếu cần hỗ trợ")
        support.setAlignment(Qt.AlignmentFlag.AlignCenter)
        support.setObjectName("batchTitle")
        layout.addWidget(support)

        zalo_btn = QPushButton("Mở Zalo hỗ trợ")
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
