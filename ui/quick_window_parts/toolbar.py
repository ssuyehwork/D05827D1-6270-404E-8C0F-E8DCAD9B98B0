# -*- coding: utf-8 -*-
# ui/quick_window_parts/toolbar.py

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLineEdit, QLabel, QMenu, QAction)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QTransform, QIntValidator

from ui.utils import create_svg_icon
from core.config import COLORS

class Toolbar(QWidget):
    close_requested = pyqtSignal()
    minimize_requested = pyqtSignal()
    open_full_requested = pyqtSignal()
    toggle_stay_on_top_requested = pyqtSignal(bool)
    toggle_sidebar_requested = pyqtSignal()
    prev_page_requested = pyqtSignal()
    next_page_requested = pyqtSignal()
    jump_to_page_requested = pyqtSignal(int)
    refresh_requested = pyqtSignal()
    toolbox_requested = pyqtSignal()
    global_hotkeys_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hotkeys_enabled = True
        self.setObjectName("RightToolbar")
        self.setFixedWidth(40)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignHCenter)

        btn_size = 28

        # 1. 窗口控制
        self.btn_close = self._create_button('win_close.svg', '#aaa', "CloseButton", "关闭", self.close_requested.emit)
        layout.addWidget(self.btn_close)

        self.btn_open_full = self._create_button('win_max.svg', '#aaa', "MaxButton", "切换主程序界面", self.open_full_requested.emit)
        layout.addWidget(self.btn_open_full)

        self.btn_minimize = self._create_button('win_min.svg', '#aaa', "MinButton", "最小化", self.minimize_requested.emit)
        layout.addWidget(self.btn_minimize)
        
        # 2. 功能按钮
        self.btn_stay_top = self._create_button('pin_tilted.svg', '#aaa', "PinButton", "保持置顶", None, is_checkable=True)
        self.btn_stay_top.clicked.connect(lambda checked: self.toggle_stay_on_top_requested.emit(checked))
        layout.addWidget(self.btn_stay_top)

        self.btn_toggle_side = self._create_button('action_eye.svg', '#aaa', "ToolButton", "显示/隐藏侧边栏", self.toggle_sidebar_requested.emit)
        layout.addWidget(self.btn_toggle_side)

        # Add refresh button
        self.btn_refresh = self._create_button('action_restore.svg', '#aaa', "ToolButton", "刷新 (F5)", self.refresh_requested.emit)
        layout.addWidget(self.btn_refresh)

        # Add toolbox button
        self.btn_toolbox = self._create_button('toolbox.svg', '#aaa', "ToolButton", "工具箱", self.toolbox_requested.emit)
        self.btn_toolbox.setContextMenuPolicy(Qt.CustomContextMenu)
        self.btn_toolbox.customContextMenuRequested.connect(self._show_toolbox_menu)
        layout.addWidget(self.btn_toolbox)

        layout.addSpacing(10)

        # 3. 翻页区域
        self.btn_prev_page = self._create_button("nav_prev.svg", "#aaa", "PageButton", "上一页", self.prev_page_requested.emit, rotated_icon=90)
        self.btn_prev_page.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.btn_prev_page)

        self.txt_page_input = QLineEdit("1")
        self.txt_page_input.setObjectName("PageInput")
        self.txt_page_input.setAlignment(Qt.AlignCenter)
        self.txt_page_input.setFixedWidth(28)
        self.txt_page_input.setValidator(QIntValidator(1, 9999))
        self.txt_page_input.returnPressed.connect(self._on_jump_to_page)
        layout.addWidget(self.txt_page_input)
        
        self.lbl_total_pages = QLabel("1")
        self.lbl_total_pages.setObjectName("TotalPageLabel")
        self.lbl_total_pages.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_total_pages)

        self.btn_next_page = self._create_button("nav_next.svg", "#aaa", "PageButton", "下一页", self.next_page_requested.emit, rotated_icon=90)
        self.btn_next_page.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.btn_next_page)

        layout.addStretch()

        # 4. 垂直标题
        lbl_vertical_title = QLabel("快\n速\n笔\n记")
        lbl_vertical_title.setObjectName("VerticalTitle")
        lbl_vertical_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_vertical_title)

        layout.addStretch()

        # 5. Logo
        title_icon = QLabel()
        title_icon.setPixmap(create_svg_icon("zap.svg", COLORS['primary']).pixmap(20, 20))
        title_icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_icon)

    def _create_button(self, icon_name, color, obj_name, tooltip, on_click=None, is_checkable=False, rotated_icon=None):
        btn = QPushButton()
        
        if rotated_icon is not None:
            icon = create_svg_icon(icon_name, color)
            pixmap = icon.pixmap(24, 24)
            transform = QTransform().rotate(rotated_icon)
            rotated_pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)
            btn.setIcon(QIcon(rotated_pixmap))
        else:
            btn.setIcon(create_svg_icon(icon_name, color))
            
        btn.setObjectName(obj_name)
        btn.setToolTip(tooltip)
        btn.setFixedSize(28, 28)
        if on_click:
            btn.clicked.connect(on_click)
        if is_checkable:
            btn.setCheckable(True)
        return btn

    def _on_jump_to_page(self):
        text = self.txt_page_input.text()
        if text.isdigit():
            page = int(text)
            self.jump_to_page_requested.emit(page)

    def set_stay_on_top(self, is_on_top):
        self.btn_stay_top.setChecked(is_on_top)

    def update_pagination(self, current_page, total_pages):
        self.txt_page_input.setText(str(current_page))
        self.lbl_total_pages.setText(str(total_pages))
        self.btn_prev_page.setDisabled(current_page <= 1)
        self.btn_next_page.setDisabled(current_page >= total_pages)

    def _show_toolbox_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ background-color: #2D2D2D; color: #EEE; border: 1px solid #444; }} QMenu::item {{ padding: 6px 24px; }} QMenu::item:selected {{ background-color: #4a90e2; }}")

        action = QAction("快捷键设置", self, checkable=True)
        action.setChecked(self.hotkeys_enabled)
        action.toggled.connect(self.global_hotkeys_toggled.emit)

        menu.addAction(action)
        menu.exec_(self.btn_toolbox.mapToGlobal(pos))

    def set_hotkeys_enabled_state(self, enabled):
        self.hotkeys_enabled = enabled
