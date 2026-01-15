# core/password_generator.py

import string
import secrets
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QLineEdit, QSlider, QCheckBox, QProgressBar, QApplication, QToolTip)
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QPainter, QColor, QPainterPath

def generate_secure_password(length, use_upper, use_lower, use_digits, use_symbols, exclude_ambiguous=False):
    char_pool = ""
    required_chars = []

    symbols = "!@#$%^&*()-_=+[]{}|;:,.<>?/~`"
    ambiguous = "0O1lI"

    if use_upper:
        upper_chars = string.ascii_uppercase
        if exclude_ambiguous:
            upper_chars = ''.join(c for c in upper_chars if c not in ambiguous)
        if upper_chars:
            char_pool += upper_chars
            required_chars.append(secrets.choice(upper_chars))

    if use_lower:
        lower_chars = string.ascii_lowercase
        if exclude_ambiguous:
            lower_chars = ''.join(c for c in lower_chars if c not in ambiguous)
        if lower_chars:
            char_pool += lower_chars
            required_chars.append(secrets.choice(lower_chars))

    if use_digits:
        digit_chars = string.digits
        if exclude_ambiguous:
            digit_chars = ''.join(c for c in digit_chars if c not in ambiguous)
        if digit_chars:
            char_pool += digit_chars
            required_chars.append(secrets.choice(digit_chars))

    if use_symbols:
        char_pool += symbols
        required_chars.append(secrets.choice(symbols))

    if not char_pool:
        return ""

    if length <= len(required_chars):
        pwd_chars = required_chars[:length]
    else:
        remaining_length = length - len(required_chars)
        pwd_chars = required_chars + [secrets.choice(char_pool) for _ in range(remaining_length)]

    secrets.SystemRandom().shuffle(pwd_chars)

    return ''.join(pwd_chars)

class PasswordGeneratorWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.drag_position = QPoint()
        self._init_ui()

    def _init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("Secure Pass Pro")
        self.setFixedSize(540, 370)

        # Main container for rounded corners and border
        self.container = QWidget(self)
        self.container.setGeometry(0, 0, self.width(), self.height())
        self.container.setStyleSheet("""
            QWidget { font-family: 'Microsoft YaHei UI'; }
            #Container {
                background-color: #1e1e1e;
                border: 2px solid #606060;
                border-radius: 16px;
            }
        """)
        self.container.setObjectName("Container")

        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title Bar
        title_bar = self._create_title_bar()
        main_layout.addWidget(title_bar)

        # --- Content Area ---
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 0, 20, 20)
        content_layout.setSpacing(8)

        self.usage_entry = QLineEdit()
        self.usage_entry.setPlaceholderText("Account / Usage (e.g. GitHub, Gmail...)")
        self.usage_entry.setFixedHeight(36)
        self.usage_entry.setStyleSheet("QLineEdit { background-color: #252525; border: 1px solid #333333; border-radius: 8px; color: #cccccc; font-size: 13px; padding-left: 10px; } QLineEdit:focus { border-color: #3b8ed0; }")
        content_layout.addWidget(self.usage_entry)

        display_frame, self.pass_entry, self.strength_bar = self._create_display_area()
        content_layout.addWidget(display_frame)

        controls_frame, self.length_label, self.length_slider, self.check_upper, self.check_lower, self.check_digits, self.check_symbols, self.exclude_ambiguous_check = self._create_controls_area()
        content_layout.addWidget(controls_frame)

        self.generate_btn = QPushButton("Generate Password")
        self.generate_btn.setFixedHeight(40)
        self.generate_btn.setStyleSheet("QPushButton { background-color: #2cc985; color: white; border: none; border-radius: 20px; font-size: 13px; font-weight: bold; } QPushButton:hover { background-color: #229c67; }")
        self.generate_btn.clicked.connect(self._generate_password)
        content_layout.addWidget(self.generate_btn)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: gray; font-size: 9px;")
        content_layout.addWidget(self.status_label)

        main_layout.addLayout(content_layout)

    def _create_title_bar(self):
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(20, 0, 10, 0)

        title_label = QLabel("SECURE PASS PRO")
        title_label.setStyleSheet("color: #555555; font-size: 12px; font-weight: bold;")
        title_layout.addWidget(title_label, alignment=Qt.AlignLeft)

        close_btn = QPushButton("×")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("QPushButton { color: #888888; font-size: 20px; border: none; background: transparent; } QPushButton:hover { background: #c42b1c; color: white; border-radius: 5px; }")
        close_btn.clicked.connect(self.hide)
        title_layout.addWidget(close_btn, alignment=Qt.AlignRight)

        title_bar.mousePressEvent = self.title_bar_press
        title_bar.mouseMoveEvent = self.title_bar_move
        return title_bar

    def _create_display_area(self):
        frame = QWidget()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        pass_entry = QLineEdit()
        pass_entry.setFixedHeight(44)
        pass_entry.setAlignment(Qt.AlignCenter)
        pass_entry.setReadOnly(True)
        pass_entry.setStyleSheet("QLineEdit { background-color: #2b2b2b; border: none; border-radius: 10px; color: #e0e0e0; font-family: Consolas; font-size: 15px; }")

        strength_bar = QProgressBar()
        strength_bar.setFixedHeight(3)
        strength_bar.setTextVisible(False)
        strength_bar.setStyleSheet("QProgressBar { border: none; background-color: #2b2b2b; border-radius: 1.5px; } QProgressBar::chunk { background-color: #4ade80; border-radius: 1.5px; }")
        strength_bar.setRange(0, 100)
        strength_bar.setValue(0)

        layout.addWidget(pass_entry)
        layout.addWidget(strength_bar)
        return frame, pass_entry, strength_bar

    def _create_controls_area(self):
        frame = QWidget()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)

        length_label = QLabel("Length: 16")
        length_label.setStyleSheet("font-size: 12px; font-weight: bold;")

        length_slider = QSlider(Qt.Horizontal)
        length_slider.setRange(8, 64)
        length_slider.setValue(16)
        length_slider.valueChanged.connect(lambda v: length_label.setText(f"Length: {v}"))

        checks_frame = QWidget()
        checks_layout = QHBoxLayout(checks_frame)
        checks_layout.setContentsMargins(0, 0, 0, 0)

        cb_style = "QCheckBox { spacing: 5px; font-size: 12px; font-weight: bold; } QCheckBox::indicator { width: 20px; height: 20px; border: 2px solid #444; border-radius: 6px; } QCheckBox::indicator:checked { background-color: #2cc985; border-color: #2cc985; } "
        check_upper = QCheckBox("A-Z"); check_upper.setChecked(True); check_upper.setStyleSheet(cb_style)
        check_lower = QCheckBox("a-z"); check_lower.setChecked(True); check_lower.setStyleSheet(cb_style)
        check_digits = QCheckBox("0-9"); check_digits.setChecked(True); check_digits.setStyleSheet(cb_style)
        check_symbols = QCheckBox("@#$"); check_symbols.setChecked(True); check_symbols.setStyleSheet(cb_style)

        checks_layout.addWidget(check_upper)
        checks_layout.addWidget(check_lower)
        checks_layout.addWidget(check_digits)
        checks_layout.addWidget(check_symbols)

        exclude_ambiguous_check = QCheckBox("排除相似字符 (0O1lI)")
        exclude_ambiguous_check.setStyleSheet("QCheckBox { spacing: 5px; font-size: 11px; } QCheckBox::indicator { width: 18px; height: 18px; border: 2px solid #444; border-radius: 6px; } QCheckBox::indicator:checked { background-color: #3b8ed0; border-color: #3b8ed0; }")

        layout.addWidget(length_label)
        layout.addWidget(length_slider)
        layout.addWidget(checks_frame)
        layout.addWidget(exclude_ambiguous_check)

        return frame, length_label, length_slider, check_upper, check_lower, check_digits, check_symbols, exclude_ambiguous_check

    def _generate_password(self):
        usage_text = self.usage_entry.text().strip()
        if not usage_text:
            self.usage_entry.setStyleSheet(self.usage_entry.styleSheet().replace("border: 1px solid #333333;", "border: 1px solid #ef4444;"))
            QToolTip.showText(self.usage_entry.mapToGlobal(QPoint(0,0)), "⚠️ 请输入账号备注信息！", self.usage_entry)
            QTimer.singleShot(1500, lambda: self.usage_entry.setStyleSheet(self.usage_entry.styleSheet().replace("border: 1px solid #ef4444;", "border: 1px solid #333333;")))
            return

        if not any([self.check_upper.isChecked(), self.check_lower.isChecked(), self.check_digits.isChecked(), self.check_symbols.isChecked()]):
            QToolTip.showText(self.generate_btn.mapToGlobal(QPoint(0,0)), "⚠️ 至少选择一种字符类型！", self.generate_btn)
            return

        length = self.length_slider.value()
        pwd = generate_secure_password(
            length=length,
            use_upper=self.check_upper.isChecked(),
            use_lower=self.check_lower.isChecked(),
            use_digits=self.check_digits.isChecked(),
            use_symbols=self.check_symbols.isChecked(),
            exclude_ambiguous=self.exclude_ambiguous_check.isChecked()
        )

        self.pass_entry.setText(pwd)

        clipboard_content = f"{usage_text}\n{pwd}"
        QApplication.clipboard().setText(clipboard_content)

        self.status_label.setText(f"✓ 已复制到剪贴板！[{usage_text}]")
        self.status_label.setStyleSheet("color: #4ade80; font-size: 9px;")

        # Update strength bar
        if length < 10:
            self.strength_bar.setStyleSheet(self.strength_bar.styleSheet().replace("#4ade80", "#ef4444"))
            self.strength_bar.setValue(30)
        elif length < 16:
            self.strength_bar.setStyleSheet(self.strength_bar.styleSheet().replace("#ef4444", "#f59e0b").replace("#2cc985", "#f59e0b"))
            self.strength_bar.setValue(60)
        else:
            self.strength_bar.setStyleSheet(self.strength_bar.styleSheet().replace("#f59e0b", "#2cc985").replace("#ef4444", "#2cc985"))
            self.strength_bar.setValue(100)

    def title_bar_press(self, event):
        self.drag_position = event.globalPos() - self.frameGeometry().topLeft()

    def title_bar_move(self, event):
        self.move(event.globalPos() - self.drag_position)
