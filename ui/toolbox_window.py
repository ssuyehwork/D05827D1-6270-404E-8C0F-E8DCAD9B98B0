# ui/toolbox_window.py

from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

class ToolboxWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.Window |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("工具箱")
        self.resize(300, 400)

        # 根布局
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(15, 15, 15, 15)

        # 容器 (用于背景和圆角)
        container = QWidget()
        container.setObjectName("ToolboxContainer")
        container.setStyleSheet("""
            #ToolboxContainer {
                background-color: #2D2D2D;
                border-radius: 10px;
                border: 1px solid #444;
            }
        """)
        root_layout.addWidget(container)

        # 阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 120))
        container.setGraphicsEffect(shadow)

        # 内容布局
        content_layout = QVBoxLayout(container)
        content_layout.setContentsMargins(20, 20, 20, 20)

        # 占位符
        placeholder_label = QLabel("这是一个工具箱窗口")
        placeholder_label.setAlignment(Qt.AlignCenter)
        placeholder_label.setStyleSheet("color: #FFFFFF; font-size: 16px; border: none;")

        content_layout.addWidget(placeholder_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
