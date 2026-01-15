# core/time_paste_helper.py

import pyperclip
import time
import keyboard
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import QPainter, QColor, QPainterPath

class TimePasteWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.mode = "退"
        self.drag_position = QPoint()
        self.hotkey_hook = None
        self._init_ui()
        self._setup_timer()

    def _init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("时间输出工具")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        title_bar = self._create_title_bar()
        main_layout.addWidget(title_bar)

        content = self._create_content()
        main_layout.addWidget(content)

        self.setLayout(main_layout)
        self.setFixedSize(320, 270)
        self.update_datetime()

    def _create_title_bar(self):
        title_bar = QWidget()
        title_bar.setFixedHeight(35)
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(15, 5, 10, 5)

        title_label = QLabel("时间输出工具")
        title_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        btn_min = QPushButton("—")
        btn_min.setFixedSize(30, 25)
        btn_min.setStyleSheet("QPushButton { background: transparent; color: #B0B0B0; border: none; font-size: 16px; font-weight: bold; } QPushButton:hover { background: #404040; color: #FFFFFF; border-radius: 3px; }")
        btn_min.clicked.connect(self.showMinimized)
        title_layout.addWidget(btn_min)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(30, 25)
        btn_close.setStyleSheet("QPushButton { background: transparent; color: #B0B0B0; border: none; font-size: 16px; } QPushButton:hover { background: #E81123; color: #FFFFFF; border-radius: 3px; }")
        btn_close.clicked.connect(self.hide)
        title_layout.addWidget(btn_close)

        title_bar.setLayout(title_layout)
        return title_bar

    def _create_content(self):
        content = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 10, 20, 20)
        layout.setSpacing(10)

        self.date_label = QLabel()
        self.date_label.setAlignment(Qt.AlignCenter)
        self.date_label.setStyleSheet("color: #B0B0B0; font-size: 16px; padding: 5px;")
        layout.addWidget(self.date_label)

        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("color: #E0E0E0; font-size: 28px; font-weight: bold; padding: 5px; font-family: 'Consolas', 'Monaco', monospace;")
        layout.addWidget(self.time_label)

        sep = QLabel()
        sep.setFixedHeight(2)
        sep.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 transparent, stop:0.5 #555555, stop:1 transparent);")
        layout.addWidget(sep)

        self.button_group = QButtonGroup(self)

        self.radio_prev = QRadioButton("退 (往前 N 分钟)")
        self.radio_prev.setChecked(True)
        self.radio_prev.setStyleSheet(self._get_radio_style())
        self.button_group.addButton(self.radio_prev, 0)
        layout.addWidget(self.radio_prev)

        self.radio_next = QRadioButton("进 (往后 N 分钟)")
        self.radio_next.setStyleSheet(self._get_radio_style())
        self.button_group.addButton(self.radio_next, 1)
        layout.addWidget(self.radio_next)

        self.radio_prev.toggled.connect(self._handle_mode_change)

        tip = QLabel("按主键盘数字键 0-9 输出时间")
        tip.setAlignment(Qt.AlignCenter)
        tip.setStyleSheet("color: #666666; font-size: 11px; padding: 5px;")
        layout.addWidget(tip)

        content.setLayout(layout)
        return content

    def _get_radio_style(self):
        return "QRadioButton { color: #E0E0E0; font-size: 14px; padding: 6px; spacing: 8px; } QRadioButton::indicator { width: 18px; height: 18px; border-radius: 9px; border: 2px solid #555555; background: #2A2A2A; } QRadioButton::indicator:checked { background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #4A9EFF, stop:0.7 #4A9EFF, stop:1 #2A2A2A); border: 2px solid #4A9EFF; } QRadioButton::indicator:hover { border: 2px solid #4A9EFF; }"

    def _handle_mode_change(self):
        if self.radio_prev.isChecked():
            self.mode = "退"
        else:
            self.mode = "进"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 15, 15)
        painter.fillPath(path, QColor(30, 30, 30, 250))
        painter.setPen(QColor(60, 60, 60))
        painter.drawPath(path)

    def _setup_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_datetime)
        self.timer.start(100)

    def update_datetime(self):
        now = datetime.now()
        self.date_label.setText(now.strftime("%Y-%m-%d"))
        self.time_label.setText(now.strftime("%H:%M:%S"))

    def _start_hotkeys(self):
        if self.hotkey_hook is not None:
            return
        main_keyboard_scancodes = {'0': 11, '1': 2, '2': 3, '3': 4, '4': 5, '5': 6, '6': 7, '7': 8, '8': 9, '9': 10}

        def key_handler(event):
            for num, scancode in main_keyboard_scancodes.items():
                if event.scan_code == scancode:
                    if event.event_type == 'down':
                        self._on_number_press(num)
                    return False
            return True

        self.hotkey_hook = keyboard.hook(key_handler, suppress=True)

    def _stop_hotkeys(self):
        if self.hotkey_hook:
            keyboard.unhook(self.hotkey_hook)
            self.hotkey_hook = None

    def _on_number_press(self, key):
        try:
            minutes = int(key)
            now = datetime.now()

            if self.mode == "退":
                target = now - timedelta(minutes=minutes)
            else:
                target = now + timedelta(minutes=minutes)

            time_str = target.strftime("%H:%M")

            pyperclip.copy(time_str)
            time.sleep(0.05)
            keyboard.send('ctrl+v')
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.pos().y() <= 35:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPos() - self.drag_position)

    def mouseReleaseEvent(self, event):
        self.drag_position = QPoint()

    def showEvent(self, event):
        self._start_hotkeys()
        super().showEvent(event)

    def hideEvent(self, event):
        self._stop_hotkeys()
        super().hideEvent(event)
