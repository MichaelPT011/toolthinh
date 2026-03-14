"""Huong dan su dung ngay trong ung dung."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget


class HelpTab(QWidget):
    """Tab huong dan ngan gon cho nguoi dung cuoi."""

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

        hero = QLabel("Hướng dẫn sử dụng nhanh")
        hero.setObjectName("heroNote")
        layout.addWidget(hero)

        cards = [
            (
                "1. Mở phần mềm",
                "Chỉ cần mở Tool Veo3's Thinh. Mỗi lần mở lên, app sẽ tự kiểm tra phiên bản mới.",
            ),
            (
                "2. Đăng nhập 1 lần",
                "Vào tab Tài khoản, bấm mở trình duyệt đăng nhập Flow rồi đăng nhập tài khoản của bạn. Từ lần sau app sẽ nhớ phiên này.",
            ),
            (
                "3. Nếu máy chưa có Chrome",
                "App có thể tự tải browser chính thức khi cần. Bạn không phải tự đi cài thêm Chrome.",
            ),
            (
                "4. Tạo video",
                "Vào tab Video VEO3. Nếu muốn ổn định nhất, hãy bật preset an toàn trước, sau đó nhập mô tả và bấm Tạo ngay bây giờ 👍.",
            ),
            (
                "5. Tạo ảnh",
                "Vào tab Ảnh Flow. Nếu muốn ít lỗi nhất, hãy bật preset an toàn. Nếu cần bám theo bố cục sẵn có, hãy thêm ảnh tham chiếu.",
            ),
            (
                "6. Tạo hàng loạt",
                "Bấm Tạo hàng loạt ⛓️ để nạp nhiều prompt. Nếu một dòng lỗi, bạn có thể sửa prompt trực tiếp rồi bấm Tạo lại ngay trên dòng đó.",
            ),
            (
                "7. Kiểm tra môi trường",
                "Nếu máy mới cài hoặc chạy hay lỗi, vào menu Công cụ rồi bấm Kiểm tra môi trường. App sẽ tự kiểm tra browser, thư mục và khả năng automation.",
            ),
            (
                "8. Mẹo để chạy ổn định",
                "Video nên để số tác vụ song song thấp để tránh Flow nghẽn. Ảnh có thể để song song cao hơn. Khi cần nhanh nhất, hãy ưu tiên 1080p.",
            ),
            (
                "9. Khi thấy lỗi",
                "Nếu app báo lỗi đăng nhập hoặc Flow không phản hồi, hãy đăng nhập Flow lại trong tab Tài khoản rồi thử lại.",
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
