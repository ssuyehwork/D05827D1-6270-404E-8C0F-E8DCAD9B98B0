# -*- coding: utf-8 -*-
# ui/main_window_parts/header_bar.py

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QLineEdit, QApplication, QMenu, QAction
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIntValidator, QIcon, QPalette
from core.config import STYLES, COLORS
from ui.utils import create_svg_icon, create_clear_button_icon
from ui.components.search_line_edit import SearchLineEdit

class HeaderBar(QWidget):
    # 定义信号，对外暴露交互事件
    search_changed = pyqtSignal(str)
    search_history_added = pyqtSignal(str)
    page_changed = pyqtSignal(int)
    
    window_minimized = pyqtSignal()
    window_maximized = pyqtSignal()
    window_closed = pyqtSignal()
    
    toggle_filter = pyqtSignal()
    toggle_metadata = pyqtSignal(bool)
    new_idea_requested = pyqtSignal()
    refresh_requested = pyqtSignal()
    toolbox_requested = pyqtSignal()
    global_hotkeys_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hotkeys_enabled = True
        self.setFixedHeight(40)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_mid']};
                border-bottom: 1px solid {COLORS['bg_light']};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(0)

        # 1. Logo & Title
        self.app_logo = QLabel()
        self.app_logo.setFixedSize(18, 18)
        self.app_logo.setScaledContents(True)
        # 默认占位图标
        self.app_logo.setPixmap(create_svg_icon('coffee.svg', COLORS['primary']).pixmap(18, 18))
        layout.addWidget(self.app_logo)
        layout.addSpacing(6)

        self.title_label = QLabel('快速笔记')
        self.title_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {COLORS['primary']}; border: none; background: transparent;")
        layout.addWidget(self.title_label)
        layout.addSpacing(15)

        # 2. Search Box
        self.search = SearchLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText('搜索灵感 (双击查看历史)')
        self.search.setFixedWidth(280)
        self.search.setFixedHeight(28)
        
        _clear_icon_path = create_clear_button_icon()
        self.search.setStyleSheet(STYLES['input'] + f"""
            QLineEdit {{ border-radius: 14px; padding-right: 25px; }} 
            QLineEdit::clear-button {{ image: url({_clear_icon_path}); border: 0; margin-right: 5px; }}
        """)
        
        self.search.textChanged.connect(lambda t: self.search_changed.emit(t))
        self.search.returnPressed.connect(lambda: self.search_history_added.emit(self.search.text().strip()))
        layout.addWidget(self.search)
        layout.addSpacing(15)

        # 3. Pagination Controls
        page_btn_style = """
            QPushButton {
                background-color: transparent;
                border: 1px solid #555;
                border-radius: 12px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
                padding: 0px;
            }
            QPushButton:hover { background-color: #333; border-color: #777; }
            QPushButton:disabled { border-color: #333; }
        """
        
        self.btn_first = self._create_btn('nav_first.svg', "第一页", page_btn_style)
        self.btn_prev = self._create_btn('nav_prev.svg', "上一页", page_btn_style)
        self.btn_next = self._create_btn('nav_next.svg', "下一页", page_btn_style)
        self.btn_last = self._create_btn('nav_last.svg', "最后一页", page_btn_style)

        self.page_input = QLineEdit()
        self.page_input.setFixedWidth(40)
        self.page_input.setFixedHeight(24)
        self.page_input.setAlignment(Qt.AlignCenter)
        self.page_input.setValidator(QIntValidator(1, 9999))
        self.page_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #2D2D2D;
                border: 1px solid #555;
                border-radius: 12px;
                color: #eee;
                font-size: 11px;
                padding: 0px;
            }}
            QLineEdit:focus {{ border: 1px solid {COLORS['primary']}; }}
        """)
        self.page_input.returnPressed.connect(self._on_page_input_return)

        self.total_page_label = QLabel("/ 1")
        self.total_page_label.setStyleSheet("color: #888; font-size: 12px; margin-left: 2px; margin-right: 5px; border: none; background: transparent;")

        layout.addWidget(self.btn_first); layout.addSpacing(6)
        layout.addWidget(self.btn_prev); layout.addSpacing(8)
        layout.addWidget(self.page_input); layout.addSpacing(6)
        layout.addWidget(self.total_page_label); layout.addSpacing(10)
        layout.addWidget(self.btn_next); layout.addSpacing(6)
        layout.addWidget(self.btn_last)
        layout.addSpacing(10)

        # Refresh button
        refresh_btn = self._create_btn('action_restore.svg', "刷新 (F5)", page_btn_style)
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        layout.addWidget(refresh_btn)

        layout.addStretch()

        # 4. Functional Buttons (Filter, Add, Metadata Toggle)
        func_btn_style = """
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 5px;
                width: 26px;
                height: 26px;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }
            QPushButton:pressed { background-color: rgba(255, 255, 255, 0.2); }
        """
        
        self.filter_btn = self._create_btn('select.svg', "高级筛选 (Ctrl+G)", func_btn_style, checkable=True)
        self.filter_btn.clicked.connect(self.toggle_filter.emit)
        
        new_btn = self._create_btn('action_add.svg', "新建笔记 (Ctrl+N)", func_btn_style)
        new_btn.clicked.connect(self.new_idea_requested.emit)
        
        self.toggle_meta_btn = self._create_btn('sidebar_right.svg', "元数据面板 (Ctrl+I)", func_btn_style + f" QPushButton:checked {{ background-color: {COLORS['primary']}; }}", checkable=True)
        self.toggle_meta_btn.toggled.connect(self.toggle_metadata.emit)

        self.toolbox_btn = self._create_btn('toolbox.svg', "工具箱", func_btn_style)
        self.toolbox_btn.clicked.connect(self.toolbox_requested.emit)
        self.toolbox_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.toolbox_btn.customContextMenuRequested.connect(self._show_toolbox_menu)


        layout.addWidget(self.filter_btn); layout.addSpacing(4)
        layout.addWidget(new_btn); layout.addSpacing(4)
        layout.addWidget(self.toggle_meta_btn); layout.addSpacing(4)
        layout.addWidget(self.toolbox_btn); layout.addSpacing(12)


        # 5. Window Controls
        min_btn = self._create_btn('win_min.svg', "最小化", func_btn_style)
        min_btn.clicked.connect(self.window_minimized.emit)
        
        self.max_btn = self._create_btn('win_max.svg', "最大化", func_btn_style)
        self.max_btn.clicked.connect(self.window_maximized.emit)
        
        close_btn = self._create_btn('win_close.svg', "关闭", func_btn_style + " QPushButton:hover { background-color: #e74c3c; }")
        close_btn.clicked.connect(self.window_closed.emit)

        layout.addWidget(min_btn); layout.addSpacing(2)
        layout.addWidget(self.max_btn); layout.addSpacing(2)
        layout.addWidget(close_btn)

    def _create_btn(self, icon, tip, style, checkable=False):
        btn = QPushButton()
        # 对于 select.svg 和 action_add.svg 使用白色，其他使用灰色，保持原有视觉
        color = '#FFF' if icon in ['select.svg', 'action_add.svg'] else '#aaa'
        btn.setIcon(create_svg_icon(icon, color))
        btn.setToolTip(tip)
        btn.setStyleSheet(style)
        if checkable:
            btn.setCheckable(True)
        return btn

    def _on_page_input_return(self):
        text = self.page_input.text().strip()
        if text.isdigit():
            self.page_changed.emit(int(text))

    def update_pagination(self, current, total):
        """外部调用：更新分页显示状态"""
        self.page_input.setText(str(current))
        self.total_page_label.setText(f"/ {total}")
        self.btn_first.setDisabled(current <= 1)
        self.btn_prev.setDisabled(current <= 1)
        self.btn_next.setDisabled(current >= total)
        self.btn_last.setDisabled(current >= total)
        
        # 断开旧连接防止重复触发
        try: self.btn_first.disconnect(); self.btn_prev.disconnect(); self.btn_next.disconnect(); self.btn_last.disconnect() 
        except: pass
        
        self.btn_first.clicked.connect(lambda: self.page_changed.emit(1))
        self.btn_prev.clicked.connect(lambda: self.page_changed.emit(current - 1))
        self.btn_next.clicked.connect(lambda: self.page_changed.emit(current + 1))
        self.btn_last.clicked.connect(lambda: self.page_changed.emit(total))

    def set_maximized_state(self, is_max):
        """外部调用：更新最大化按钮图标"""
        icon = 'win_restore.svg' if is_max else 'win_max.svg'
        self.max_btn.setIcon(create_svg_icon(icon, "#aaa"))
        
        # 更新圆角样式 (最大化时无圆角，还原时有圆角)
        if is_max:
            self.setStyleSheet(f"QWidget {{ background-color: {COLORS['bg_mid']}; border-radius: 0px; border-bottom: 1px solid {COLORS['bg_light']}; }}")
        else:
            self.setStyleSheet(f"QWidget {{ background-color: {COLORS['bg_mid']}; border-bottom: 1px solid {COLORS['bg_light']}; border-top-left-radius: 8px; border-top-right-radius: 8px; }}")

    def set_filter_active(self, active):
        """外部调用：同步筛选按钮状态"""
        self.filter_btn.setChecked(active)
        
    def set_metadata_active(self, active):
        """外部调用：同步元数据按钮状态"""
        self.toggle_meta_btn.setChecked(active)

    def refresh_logo(self):
        """外部调用：刷新 Logo"""
        icon = QApplication.windowIcon()
        if not icon.isNull():
            self.app_logo.setPixmap(icon.pixmap(20, 20))

    def _show_toolbox_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ background-color: #2D2D2D; color: #EEE; border: 1px solid #444; }} QMenu::item {{ padding: 6px 24px; }} QMenu::item:selected {{ background-color: #4a90e2; }}")

        action = QAction("快捷键设置", self, checkable=True)
        action.setChecked(self.hotkeys_enabled)
        action.toggled.connect(self.global_hotkeys_toggled.emit)

        menu.addAction(action)
        menu.exec_(self.toolbox_btn.mapToGlobal(pos))

    def set_hotkeys_enabled_state(self, enabled):
        self.hotkeys_enabled = enabled