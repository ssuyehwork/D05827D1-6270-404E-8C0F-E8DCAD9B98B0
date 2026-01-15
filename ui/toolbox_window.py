# ui/toolbox_window.py

from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsDropShadowEffect, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

class ToolboxWindow(QWidget):
    show_hotkey_settings_requested = pyqtSignal()
    show_time_paste_requested = pyqtSignal()
    show_password_generator_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.Window |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

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
        content_layout.setSpacing(15)

        # Hotkey settings button
        hotkey_button = QPushButton("快捷键设定")
        hotkey_button.setStyleSheet("""
            QPushButton {
                background-color: #4A4A4A;
                color: #E0E0E0;
                border: 1px solid #666;
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5A5A5A;
                border-color: #888;
            }
            QPushButton:pressed {
                background-color: #3A3A3A;
            }
        """)
        hotkey_button.clicked.connect(self.show_hotkey_settings_requested.emit)
        content_layout.addWidget(hotkey_button)

        # Time Paste button
        time_paste_button = QPushButton("时间输出")
        time_paste_button.setStyleSheet(hotkey_button.styleSheet()) # Reuse the same style
        time_paste_button.clicked.connect(self.show_time_paste_requested.emit)
        content_layout.addWidget(time_paste_button)

        # Password Generator button
        password_generator_button = QPushButton("密码生成器")
        password_generator_button.setStyleSheet(hotkey_button.styleSheet()) # Reuse the same style
        password_generator_button.clicked.connect(self.show_password_generator_requested.emit)
        content_layout.addWidget(password_generator_button)

        content_layout.addStretch()

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
