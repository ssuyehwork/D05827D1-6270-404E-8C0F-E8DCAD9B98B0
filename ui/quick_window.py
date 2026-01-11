# -*- coding: utf-8 -*-
# ui/quick_window.py

import sys
import os
import ctypes
from ctypes import wintypes
import time
import datetime
import subprocess
import logging
import math

from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QListWidget, QLineEdit, 
                             QListWidgetItem, QHBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QPushButton, QStyle, QAction, QSplitter, QGraphicsDropShadowEffect, 
                             QLabel, QTreeWidgetItemIterator, QShortcut, QAbstractItemView, QMenu,
                             QColorDialog, QInputDialog, QMessageBox, QFrame)
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QSettings, QUrl, QMimeData, pyqtSignal, QObject, QSize, QByteArray, QBuffer, QIODevice
from PyQt5.QtGui import QImage, QColor, QCursor, QPixmap, QPainter, QIcon, QKeySequence, QDrag, QIntValidator, QTransform

from services.preview_service import PreviewService
from ui.dialogs import EditDialog
from ui.advanced_tag_selector import AdvancedTagSelector
from ui.components.search_line_edit import SearchLineEdit
from core.config import COLORS
from core.settings import load_setting, save_setting
from ui.utils import create_svg_icon, create_clear_button_icon

# ... (Platform specific imports) ...
if sys.platform == "win32":
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    
    KEYEVENTF_KEYUP = 0x0002
    VK_CONTROL = 0x11
    VK_V = 0x56
    
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010
    SWP_FLAGS = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE

    class GUITHREADINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("hwndActive", wintypes.HWND),
            ("hwndFocus", wintypes.HWND),      
            ("hwndCapture", wintypes.HWND),
            ("hwndMenuOwner", wintypes.HWND),
            ("hwndMoveSize", wintypes.HWND),
            ("hwndCaret", wintypes.HWND),
            ("rcCaret", wintypes.RECT)
        ]
    
    user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
    user32.GetGUIThreadInfo.restype = wintypes.BOOL
    user32.SetFocus.argtypes = [wintypes.HWND]
    user32.SetFocus.restype = wintypes.HWND
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
else:
    user32 = None
    kernel32 = None

def log(message): pass

try:
    from data.db_manager import DatabaseManager as DBManager
    from services.clipboard import ClipboardManager
except ImportError:
    class DBManager:
        def get_items(self, **kwargs): return []
        def get_partitions_tree(self): return []
        def get_partition_item_counts(self): return {}
        def get_ideas_count(self, **kwargs): return 0
    class ClipboardManager(QObject):
        data_captured = pyqtSignal()
        def __init__(self, db_manager):
            super().__init__()
            self.db = db_manager
        def process_clipboard(self, mime_data, cat_id=None): pass

class DraggableListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item: return
        data = item.data(Qt.UserRole)
        if not data: return
        idea_id = data['id']
        
        mime = QMimeData()
        mime.setData('application/x-idea-id', str(idea_id).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec_(Qt.MoveAction)

class DropTreeWidget(QTreeWidget):
    item_dropped = pyqtSignal(int, int)
    order_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDropIndicatorShown(True)

    def dragEnterEvent(self, event):
        # 优先允许自身拖拽（排序）
        if event.source() == self:
            super().dragEnterEvent(event)
            event.accept()
        elif event.mimeData().hasFormat('application/x-idea-id'):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        # 自身拖拽（排序）：必须调用 super() 且 accept()，否则不显示插入线
        if event.source() == self:
            super().dragMoveEvent(event)
            event.accept()
            return
            
        # 外部拖拽（归档笔记）
        if event.mimeData().hasFormat('application/x-idea-id'):
            item = self.itemAt(event.pos())
            if item:
                data = item.data(0, Qt.UserRole)
                # 只有具备 drop 权限的节点才允许放入
                if item.flags() & Qt.ItemIsDropEnabled:
                    # 额外检查：如果是 user root 或者是具体分类
                    if data and data.get('type') in ['partition', 'favorite', 'trash', 'uncategorized']:
                        self.setCurrentItem(item)
                        event.accept()
                        return
            event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        # 情况1：拖入笔记 -> 归档
        if event.mimeData().hasFormat('application/x-idea-id'):
            try:
                idea_id = int(event.mimeData().data('application/x-idea-id'))
                item = self.itemAt(event.pos())
                if item:
                    data = item.data(0, Qt.UserRole)
                    # 允许拖入各类容器
                    if data and data.get('type') in ['partition', 'favorite', 'trash', 'uncategorized']:
                        cat_id = data.get('id')
                        self.item_dropped.emit(idea_id, cat_id)
                        event.acceptProposedAction()
            except Exception as e:
                pass
        # 情况2：自身拖拽 -> 排序
        elif event.source() == self:
            # 调用父类完成树节点的移动
            super().dropEvent(event)
            # 发出信号保存顺序
            self.order_changed.emit()
            event.accept()

DARK_STYLESHEET = """
QWidget#Container {
    background-color: #1e1e1e;
    border: 1px solid #333333; 
    border-radius: 8px;    
}
QWidget {
    color: #cccccc;
    font-family: "Microsoft YaHei", "Segoe UI Emoji";
    font-size: 14px;
}
QToolTip {
    color: #ffffff;
    background-color: #2b2b2b;
    border: 1px solid #444;
    padding: 2px;
    border-radius: 4px;
    opacity: 240; 
}
QLabel#TitleLabel {
    color: #858585;
    font-weight: bold;
    font-size: 15px;
    padding-left: 5px;
}
QListWidget, QTreeWidget {
    border: none;
    background-color: #1e1e1e;
    alternate-background-color: #252526;
    outline: none;
}
QListWidget::item { 
    padding: 6px; 
    border: none; 
    border-bottom: 1px solid #2A2A2A; 
}
QTreeWidget::item {
    height: 25px;
}
QListWidget::item:selected, QTreeWidget::item:selected {
    background-color: #4a90e2; color: #FFFFFF;
}
QListWidget::item:hover { background-color: #333333; }
QSplitter::handle { background-color: #333333; width: 2px; }
QSplitter::handle:hover { background-color: #4a90e2; }
QLineEdit {
    background-color: #252526;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 6px;
    font-size: 16px;
}

/* --- 右侧垂直工具栏样式 --- */

/* 垂直工具栏容器 - 黑色背景 */
QWidget#RightToolbar {
    background-color: #252526;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    border-left: 1px solid #333;
}

/* 通用图标按钮 - 统一尺寸和悬停 */
QPushButton#ToolButton, QPushButton#MinButton, QPushButton#CloseButton, QPushButton#PinButton, QPushButton#MaxButton, QPushButton#PageButton { 
    background-color: transparent; 
    border-radius: 4px; 
    padding: 0px;
    border: none;
    margin: 0px; /* 消除外边距 */
}
QPushButton#ToolButton:hover, QPushButton#MinButton:hover, QPushButton#MaxButton:hover, QPushButton#PageButton:hover, QPushButton#PinButton:hover { 
    background-color: rgba(255, 255, 255, 0.1); 
}
QPushButton#CloseButton:hover { 
    background-color: #E81123; 
}
/* 选中状态 */
QPushButton#PinButton:checked, QPushButton#ToolButton:checked { 
    background-color: #4a90e2; 
    border: 1px solid #357abd; 
}

/* 页码输入框 - 极简风格 */
QLineEdit#PageInput {
    background: transparent;
    border: 1px solid #444;
    border-radius: 4px;
    color: #ddd;
    font-size: 11px;
    font-weight: bold;
    selection-background-color: #4a90e2;
    padding: 0px;
}
QLineEdit#PageInput:focus {
    border-color: #4a90e2;
}

/* 总页数标签 */
QLabel#TotalPageLabel {
    background: transparent;
    border: none;
    color: #777;
    font-size: 10px;
}

/* 垂直标题文字 */
QLabel#VerticalTitle {
    color: #666;
    font-weight: bold;
    font-size: 14px;
    font-family: "Microsoft YaHei";
    padding-top: 10px;
    padding-bottom: 10px;
}

QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0px; }
QScrollBar::handle:vertical { background: #444; border-radius: 3px; min-height: 20px; }
QScrollBar::handle:vertical:hover { background: #555; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
"""

class ClickableLineEdit(QLineEdit):
    doubleClicked = pyqtSignal()
    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)

class QuickWindow(QWidget):
    RESIZE_MARGIN = 18 
    toggle_main_window_requested = pyqtSignal()

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.settings = QSettings("MyTools", "RapidNotes")
        
        self.m_drag = False
        self.m_DragPosition = QPoint()
        self.resize_area = None
        self._is_pinned = False
        
        # [分页] 初始化状态
        self.current_page = 1
        self.page_size = 100
        self.total_pages = 1
        
        self._icon_html_cache = {}
        
        self.last_active_hwnd = None
        self.last_focus_hwnd = None
        self.last_thread_id = None
        self.my_hwnd = None
        
        self.cm = ClipboardManager(self.db)
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_changed)
        self.cm.data_captured.connect(self._update_list)
        self._processing_clipboard = False
        
        self.open_dialogs = []
        self.preview_service = PreviewService(self.db, self)
        
        self._init_ui()
        self._setup_shortcuts()
        self._restore_window_state()
        
        self.setMouseTracking(True)
        self.container.setMouseTracking(True)
        
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._monitor_foreground_window)
        if user32: self.monitor_timer.start(200)
        
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._update_list)
        
        self.search_box.textChanged.connect(self._on_search_text_changed)
        self.search_box.returnPressed.connect(self._add_search_to_history)
        self.list_widget.itemActivated.connect(self._on_item_activated)
        
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_list_context_menu)
        
        # 修复关键：连接信号
        self.partition_tree.currentItemChanged.connect(self._on_partition_selection_changed)
        self.partition_tree.item_dropped.connect(self._handle_category_drop)
        self.partition_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.partition_tree.customContextMenuRequested.connect(self._show_partition_context_menu)
        self.partition_tree.order_changed.connect(self._save_partition_order)
        
        self.system_tree.currentItemChanged.connect(self._on_system_selection_changed)
        self.system_tree.item_dropped.connect(self._handle_category_drop)
        self.system_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.system_tree.customContextMenuRequested.connect(self._show_partition_context_menu)

        # 翻页按钮连接
        self.btn_prev_page.clicked.connect(self._prev_page)
        self.btn_next_page.clicked.connect(self._next_page)
        self.txt_page_input.returnPressed.connect(self._jump_to_page)
        
        self.btn_stay_top.clicked.connect(self._toggle_stay_on_top)
        self.btn_toggle_side.clicked.connect(self._toggle_partition_panel)
        self.btn_open_full.clicked.connect(self.toggle_main_window_requested)
        self.btn_minimize.clicked.connect(self.showMinimized) 
        self.btn_close.clicked.connect(self.close)
        
        self._update_partition_tree()
        self._update_list()
        self._update_partition_status_display()

    def on_clipboard_changed(self):
        if self._processing_clipboard: return
        self._processing_clipboard = True
        try:
            mime = self.clipboard.mimeData()
            self.cm.process_clipboard(mime, None)
        finally: 
            self._processing_clipboard = False

    def _create_rotated_icon(self, icon_name, color, angle):
        icon = create_svg_icon(icon_name, color)
        pixmap = icon.pixmap(24, 24)
        transform = QTransform().rotate(angle)
        rotated_pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)
        return QIcon(rotated_pixmap)

    def _init_ui(self):
        self.setWindowTitle("快速笔记")
        self.resize(830, 630)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        
        self.root_layout = QHBoxLayout(self)
        self.root_layout.setContentsMargins(15, 15, 15, 15) 
        self.root_layout.setSpacing(0)
        
        self.container = QWidget()
        self.container.setObjectName("Container")
        self.root_layout.addWidget(self.container)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 100))
        self.container.setGraphicsEffect(shadow)
        
        self.setStyleSheet(DARK_STYLESHEET)
        
        self.main_container_layout = QHBoxLayout(self.container)
        self.main_container_layout.setContentsMargins(0, 0, 0, 0)
        self.main_container_layout.setSpacing(0)

        # === 左侧内容区 ===
        self.left_content_widget = QWidget()
        self.left_layout = QVBoxLayout(self.left_content_widget)
        self.left_layout.setContentsMargins(10, 10, 10, 5) 
        self.left_layout.setSpacing(8)

        self.search_box = SearchLineEdit(self)
        self.search_box.setPlaceholderText("搜索灵感 (双击查看历史)")
        self.search_box.setClearButtonEnabled(True)
        _clear_icon_path = create_clear_button_icon()
        clear_button_style = f"""
        QLineEdit::clear-button {{ image: url({_clear_icon_path}); border: 0; margin-right: 5px; }}
        QLineEdit::clear-button:hover {{ background-color: #444; border-radius: 8px; }}
        """
        self.search_box.setStyleSheet(self.search_box.styleSheet() + clear_button_style)
        self.left_layout.addWidget(self.search_box)
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(4)
        
        self.list_widget = DraggableListWidget()
        self.list_widget.setFocusPolicy(Qt.StrongFocus)
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setIconSize(QSize(28, 28))
        
        self.right_sidebar_widget = QWidget()
        self.right_sidebar_layout = QVBoxLayout(self.right_sidebar_widget)
        self.right_sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.right_sidebar_layout.setSpacing(0)
        
        self.system_tree = DropTreeWidget()
        self.system_tree.setHeaderHidden(True)
        self.system_tree.setFocusPolicy(Qt.NoFocus)
        self.system_tree.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.system_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.system_tree.setFixedHeight(150) 
        
        self.partition_tree = DropTreeWidget()
        self.partition_tree.setHeaderHidden(True)
        self.partition_tree.setFocusPolicy(Qt.NoFocus)
        self.partition_tree.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.partition_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.right_sidebar_layout.addWidget(self.system_tree)
        self.right_sidebar_layout.addWidget(self.partition_tree)
        
        self.splitter.addWidget(self.list_widget)
        self.splitter.addWidget(self.right_sidebar_widget)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([550, 150])
        
        self.left_layout.addWidget(self.splitter)
        
        self.partition_status_label = QLabel("当前分区: 全部数据")
        self.partition_status_label.setObjectName("PartitionStatusLabel")
        self.partition_status_label.setStyleSheet("font-size: 11px; color: #888; padding-left: 2px;")
        self.left_layout.addWidget(self.partition_status_label)
        self.partition_status_label.hide()

        self.main_container_layout.addWidget(self.left_content_widget)

        # === 右侧垂直工具栏 ===
        self.right_bar = QWidget()
        self.right_bar.setObjectName("RightToolbar")
        self.right_bar.setFixedWidth(40) 
        
        self.right_bar_layout = QVBoxLayout(self.right_bar)
        self.right_bar_layout.setContentsMargins(0, 8, 0, 8)
        self.right_bar_layout.setSpacing(0)
        self.right_bar_layout.setAlignment(Qt.AlignHCenter)

        btn_size = 28

        # 1. 窗口控制
        self.btn_close = QPushButton()
        self.btn_close.setIcon(create_svg_icon('win_close.svg', '#aaa'))
        self.btn_close.setObjectName("CloseButton")
        self.btn_close.setToolTip("关闭")
        self.btn_close.setFixedSize(btn_size, btn_size)
        self.right_bar_layout.addWidget(self.btn_close)

        self.btn_open_full = QPushButton()
        self.btn_open_full.setIcon(create_svg_icon('win_max.svg', '#aaa'))
        self.btn_open_full.setObjectName("MaxButton")
        self.btn_open_full.setToolTip("切换主程序界面")
        self.btn_open_full.setFixedSize(btn_size, btn_size)
        self.right_bar_layout.addWidget(self.btn_open_full)

        self.btn_minimize = QPushButton()
        self.btn_minimize.setIcon(create_svg_icon('win_min.svg', '#aaa'))
        self.btn_minimize.setObjectName("MinButton")
        self.btn_minimize.setToolTip("最小化")
        self.btn_minimize.setFixedSize(btn_size, btn_size)
        self.right_bar_layout.addWidget(self.btn_minimize)
        
        # 2. 功能按钮
        self.btn_stay_top = QPushButton()
        self.btn_stay_top.setIcon(create_svg_icon('pin_tilted.svg', '#aaa'))
        self.btn_stay_top.setObjectName("PinButton")
        self.btn_stay_top.setToolTip("保持置顶")
        self.btn_stay_top.setCheckable(True)
        self.btn_stay_top.setFixedSize(btn_size, btn_size)
        self.right_bar_layout.addWidget(self.btn_stay_top)

        self.btn_toggle_side = QPushButton()
        self.btn_toggle_side.setIcon(create_svg_icon('action_eye.svg', '#aaa'))
        self.btn_toggle_side.setObjectName("ToolButton")
        self.btn_toggle_side.setToolTip("显示/隐藏侧边栏")
        self.btn_toggle_side.setFixedSize(btn_size, btn_size)
        self.right_bar_layout.addWidget(self.btn_toggle_side)

        self.right_bar_layout.addSpacing(10)

        # 3. 翻页区域
        self.btn_prev_page = QPushButton()
        self.btn_prev_page.setObjectName("PageButton")
        self.btn_prev_page.setIcon(self._create_rotated_icon("nav_prev.svg", "#aaa", 90))
        self.btn_prev_page.setFixedSize(btn_size, btn_size)
        self.btn_prev_page.setToolTip("上一页")
        self.btn_prev_page.setCursor(Qt.PointingHandCursor)
        self.right_bar_layout.addWidget(self.btn_prev_page)

        self.txt_page_input = QLineEdit("1")
        self.txt_page_input.setObjectName("PageInput")
        self.txt_page_input.setAlignment(Qt.AlignCenter)
        self.txt_page_input.setFixedWidth(28)
        self.txt_page_input.setValidator(QIntValidator(1, 9999))
        self.right_bar_layout.addWidget(self.txt_page_input)
        
        self.lbl_total_pages = QLabel("1")
        self.lbl_total_pages.setObjectName("TotalPageLabel")
        self.lbl_total_pages.setAlignment(Qt.AlignCenter)
        self.right_bar_layout.addWidget(self.lbl_total_pages)

        self.btn_next_page = QPushButton()
        self.btn_next_page.setObjectName("PageButton")
        self.btn_next_page.setIcon(self._create_rotated_icon("nav_next.svg", "#aaa", 90))
        self.btn_next_page.setFixedSize(btn_size, btn_size)
        self.btn_next_page.setToolTip("下一页")
        self.btn_next_page.setCursor(Qt.PointingHandCursor)
        self.right_bar_layout.addWidget(self.btn_next_page)

        self.right_bar_layout.addStretch()

        # 4. 垂直标题
        self.lbl_vertical_title = QLabel("快\n速\n笔\n记")
        self.lbl_vertical_title.setObjectName("VerticalTitle")
        self.lbl_vertical_title.setAlignment(Qt.AlignCenter)
        self.right_bar_layout.addWidget(self.lbl_vertical_title)

        self.right_bar_layout.addStretch()

        # 5. Logo
        title_icon = QLabel()
        title_icon.setPixmap(create_svg_icon("zap.svg", COLORS['primary']).pixmap(20, 20))
        title_icon.setAlignment(Qt.AlignCenter)
        self.right_bar_layout.addWidget(title_icon)
        
        self.main_container_layout.addWidget(self.right_bar)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+F"), self, self.search_box.setFocus)
        QShortcut(QKeySequence("Delete"), self, self._do_delete_selected)
        QShortcut(QKeySequence("Ctrl+E"), self, self._do_toggle_favorite)
        QShortcut(QKeySequence("Ctrl+P"), self, self._do_toggle_pin)
        QShortcut(QKeySequence("Ctrl+W"), self, self.close)
        QShortcut(QKeySequence("Ctrl+S"), self, self._do_lock_selected)
        QShortcut(QKeySequence("Ctrl+N"), self, self._do_new_idea)
        QShortcut(QKeySequence("Ctrl+A"), self, self._do_select_all)
        QShortcut(QKeySequence("Ctrl+T"), self, self._do_extract_content)
        for i in range(6):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, lambda r=i: self._do_set_rating(r))
        self.space_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.space_shortcut.setContext(Qt.WindowShortcut)
        self.space_shortcut.activated.connect(self._do_preview)

    def _do_preview(self):
        iid = self._get_selected_id()
        if iid: self.preview_service.toggle_preview({iid})

    def _do_new_idea(self):
        dialog = EditDialog(self.db, parent=None)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.data_saved.connect(self._update_list)
        dialog.data_saved.connect(self._update_partition_tree)
        dialog.show()
        self.open_dialogs.append(dialog)

    def _do_select_all(self):
        self.list_widget.selectAll()

    def _do_extract_content(self):
        item = self.list_widget.currentItem()
        if item:
            data = item.data(Qt.UserRole)
            if data:
                self._copy_item_content(data)

    def _add_search_to_history(self):
        search_text = self.search_box.text().strip()
        if search_text:
            self.search_box.add_history_entry(search_text)

    def _show_list_context_menu(self, pos):
        import logging
        try:
            item = self.list_widget.itemAt(pos)
            if not item: return
            data = item.data(Qt.UserRole)
            if not data: return
            
            idea_id = data['id']
            is_pinned = data['is_pinned']
            is_fav = data['is_favorite']
            is_locked = data['is_locked']
            rating = data['rating']
            
            menu = QMenu(self)
            menu.setStyleSheet("""
                QMenu { background-color: #2D2D2D; color: #EEE; border: 1px solid #444; border-radius: 4px; padding: 4px; }
                QMenu::item { padding: 6px 10px 6px 28px; border-radius: 3px; }
                QMenu::item:selected { background-color: #4a90e2; color: white; }
                QMenu::separator { background-color: #444; height: 1px; margin: 4px 0px; }
                QMenu::icon { position: absolute; left: 6px; top: 6px; }
            """)
            
            menu.addAction(create_svg_icon('action_eye.svg', '#1abc9c'), "预览 (Space)", self._do_preview)
            menu.addAction(create_svg_icon('action_export.svg', '#1abc9c'), "复制内容", lambda: self._copy_item_content(data))
            menu.addSeparator()
            
            menu.addAction(create_svg_icon('action_edit.svg', '#4a90e2'), "编辑", self._do_edit_selected)
            menu.addSeparator()

            from PyQt5.QtWidgets import QAction, QActionGroup
            rating_menu = menu.addMenu(create_svg_icon('star.svg', '#f39c12'), "设置星级")
            star_group = QActionGroup(self)
            star_group.setExclusive(True)
            for i in range(1, 6):
                action = QAction(f"{'★'*i}", self, checkable=True)
                action.triggered.connect(lambda _, r=i: self._do_set_rating(r))
                if rating == i: action.setChecked(True)
                rating_menu.addAction(action)
                star_group.addAction(action)
            rating_menu.addSeparator()
            rating_menu.addAction("清除评级").triggered.connect(lambda: self._do_set_rating(0))

            if is_locked:
                menu.addAction(create_svg_icon('lock.svg', COLORS['success']), "解锁", self._do_lock_selected)
            else:
                menu.addAction(create_svg_icon('lock.svg', '#aaaaaa'), "锁定 (Ctrl+S)", self._do_lock_selected)
            
            menu.addSeparator()

            if is_pinned:
                menu.addAction(create_svg_icon('pin_vertical.svg', '#e74c3c'), "取消置顶", self._do_toggle_pin)
            else:
                menu.addAction(create_svg_icon('pin_tilted.svg', '#aaaaaa'), "置顶", self._do_toggle_pin)
            
            menu.addAction(create_svg_icon('bookmark.svg', '#ff6b81'), "取消书签" if is_fav else "添加书签", self._do_toggle_favorite)
            
            menu.addSeparator()
            
            cat_menu = menu.addMenu(create_svg_icon('branch.svg', '#cccccc'), '移动到分类')

            recent_cats = load_setting('recent_categories', [])
            all_cats = {c['id']: c for c in self.db.get_categories()}
            
            action_uncategorized = cat_menu.addAction('⚠️ 未分类')
            action_uncategorized.triggered.connect(lambda: self._move_to_category(None))

            count = 0
            for cat_id in recent_cats:
                if count >= 15: break
                if cat_id in all_cats:
                    cat = all_cats[cat_id]
                    action = cat_menu.addAction(create_svg_icon('branch.svg', cat['color']), f"{cat['name']}")
                    action.triggered.connect(lambda _, cid=cat['id']: self._move_to_category(cid))
                    count += 1
            
            menu.addSeparator()
            
            if not is_locked:
                menu.addAction(create_svg_icon('action_delete.svg', '#e74c3c'), "删除", self._do_delete_selected)
            else:
                del_action = menu.addAction(create_svg_icon('action_delete.svg', '#555555'), "删除 (已锁定)")
                del_action.setEnabled(False)
            
            menu.exec_(self.list_widget.mapToGlobal(pos))
        except Exception as e:
            logging.critical(f"Critical error in _show_list_context_menu: {e}", exc_info=True)

    def _do_set_rating(self, rating):
        item = self.list_widget.currentItem()
        idea_id = self._get_selected_id()
        if item and idea_id:
            self.db.set_rating(idea_id, rating)
            new_data = self.db.get_idea(idea_id)
            if new_data:
                item.setData(Qt.UserRole, new_data)
                item.setText(self._get_content_display(new_data))
                self._update_list_item_tooltip(item, new_data)

    def _move_to_category(self, cat_id):
        iid = self._get_selected_id()
        if iid:
            if cat_id is not None:
                recent_cats = load_setting('recent_categories', [])
                if cat_id in recent_cats: recent_cats.remove(cat_id)
                recent_cats.insert(0, cat_id)
                save_setting('recent_categories', recent_cats)

            self.db.move_category(iid, cat_id)
            self._update_list()
            self._update_partition_tree()

    def _copy_item_content(self, data):
        item_type = data['item_type'] or 'text'
        content = data['content']
        if item_type == 'text' and content: QApplication.clipboard().setText(content)

    def _get_selected_id(self):
        item = self.list_widget.currentItem()
        if not item: return None
        data = item.data(Qt.UserRole)
        if data: return data['id'] 
        return None
    
    def _do_lock_selected(self):
        item = self.list_widget.currentItem()
        iid = self._get_selected_id()
        if not iid or not item: return
        status = self.db.get_lock_status([iid])
        current_state = status.get(iid, 0)
        new_state = 0 if current_state else 1
        self.db.set_locked([iid], new_state)
        new_data = self.db.get_idea(iid)
        if new_data:
            item.setData(Qt.UserRole, new_data)
            self._update_list_item_tooltip(item, new_data)
    
    def _do_edit_selected(self):
        iid = self._get_selected_id()
        if iid:
            for dialog in self.open_dialogs:
                if hasattr(dialog, 'idea_id') and dialog.idea_id == iid: dialog.activateWindow(); return
            dialog = EditDialog(self.db, idea_id=iid, parent=None)
            dialog.setAttribute(Qt.WA_DeleteOnClose)
            dialog.data_saved.connect(self._update_list)
            dialog.data_saved.connect(self._update_partition_tree)
            dialog.finished.connect(lambda: self.open_dialogs.remove(dialog) if dialog in self.open_dialogs else None)
            self.open_dialogs.append(dialog)
            dialog.show(); dialog.activateWindow()

    def _do_delete_selected(self):
        iid = self._get_selected_id()
        if iid:
            status = self.db.get_lock_status([iid])
            if status.get(iid, 0): return
            self.db.set_deleted(iid, True)
            self._update_list()
            self._update_partition_tree()

    def _do_toggle_favorite(self):
        item = self.list_widget.currentItem()
        iid = self._get_selected_id()
        if iid and item:
            self.db.toggle_field(iid, 'is_favorite')
            new_data = self.db.get_idea(iid)
            if new_data:
                item.setData(Qt.UserRole, new_data)
                self._update_list_item_tooltip(item, new_data)

    def _do_toggle_pin(self):
        iid = self._get_selected_id()
        if iid:
            self.db.toggle_field(iid, 'is_pinned')
            self._update_list()

    def _handle_category_drop(self, idea_id, cat_id):
        target_item = None
        it = QTreeWidgetItemIterator(self.partition_tree)
        while it.value():
            item = it.value()
            data = item.data(0, Qt.UserRole)
            if data and data.get('id') == cat_id:
                target_item = item; break
            it += 1
        
        if not target_item: return
        target_data = target_item.data(0, Qt.UserRole)
        target_type = target_data.get('type')
        
        if target_type == 'trash':
            status = self.db.get_lock_status([idea_id])
            if status.get(idea_id, 0): return

        if target_type == 'bookmark': self.db.set_favorite(idea_id, True)
        elif target_type == 'trash': self.db.set_deleted(idea_id, True)
        elif target_type == 'uncategorized': 
            self.db.move_category(idea_id, None)
        elif target_type == 'partition': 
            self.db.move_category(idea_id, cat_id)
            if cat_id is not None:
                recent_cats = load_setting('recent_categories', [])
                if cat_id in recent_cats: recent_cats.remove(cat_id)
                recent_cats.insert(0, cat_id)
                save_setting('recent_categories', recent_cats)

        QTimer.singleShot(10, self._update_list)
        QTimer.singleShot(10, self._update_partition_tree)

    def _save_partition_order(self):
        update_list = []
        def iterate_items(parent_item, parent_id):
            for i in range(parent_item.childCount()):
                item = parent_item.child(i)
                data = item.data(0, Qt.UserRole)
                if data and data.get('type') == 'partition':
                    cat_id = data.get('id')
                    update_list.append({'id': cat_id, 'parent_id': parent_id, 'sort_order': i})
                    if item.childCount() > 0: iterate_items(item, cat_id)
        iterate_items(self.partition_tree.invisibleRootItem(), None)
        if update_list: self.db.save_category_order(update_list)

    def _restore_window_state(self):
        geo_hex = load_setting("quick_window_geometry_hex")
        if geo_hex:
            try: self.restoreGeometry(QByteArray.fromHex(geo_hex.encode()))
            except: pass
        else:
            screen_geo = QApplication.desktop().screenGeometry()
            win_geo = self.geometry()
            self.move((screen_geo.width() - win_geo.width()) // 2, (screen_geo.height() - win_geo.height()) // 2)
            
        splitter_hex = load_setting("quick_window_splitter_hex")
        if splitter_hex:
            try: self.splitter.restoreState(QByteArray.fromHex(splitter_hex.encode()))
            except: pass
            
        is_hidden = load_setting("partition_panel_hidden", False)
        self.right_sidebar_widget.setHidden(is_hidden) # 修改为隐藏整个右侧容器
        self._update_partition_status_display()
        
        is_pinned = load_setting("quick_window_pinned", False)
        self.btn_stay_top.setChecked(is_pinned)
        self._toggle_stay_on_top()

    def save_state(self):
        save_setting("quick_window_geometry_hex", self.saveGeometry().toHex().data().decode())
        save_setting("quick_window_splitter_hex", self.splitter.saveState().toHex().data().decode())
        save_setting("partition_panel_hidden", self.right_sidebar_widget.isHidden())
        save_setting("quick_window_pinned", self.btn_stay_top.isChecked())

    def closeEvent(self, event):
        self.save_state()
        self.hide()
        event.ignore()

    def _get_resize_area(self, pos):
        # 修正：工具栏在右侧，调整区域需要避开
        rect = self.rect()
        right_margin = 40 # 工具栏宽度
        
        x, y = pos.x(), pos.y()
        w, h = rect.width(), rect.height()
        m = self.RESIZE_MARGIN
        
        areas = []
        if x < m: areas.append('left')
        elif x > w - m: areas.append('right') # 注意：这可能会和工具栏点击冲突，通常工具栏应处理自己的事件
        
        if y < m: areas.append('top')
        elif y > h - m: areas.append('bottom')
        
        # 如果点击在右侧工具栏区域内，且不是边缘拖拽，则返回空
        if x > w - right_margin and y > m and y < h - m:
            return []
            
        return areas

    def _set_cursor_shape(self, areas):
        if not areas: self.setCursor(Qt.ArrowCursor); return
        if 'left' in areas and 'top' in areas: self.setCursor(Qt.SizeFDiagCursor)
        elif 'right' in areas and 'bottom' in areas: self.setCursor(Qt.SizeFDiagCursor)
        elif 'left' in areas and 'bottom' in areas: self.setCursor(Qt.SizeBDiagCursor)
        elif 'right' in areas and 'top' in areas: self.setCursor(Qt.SizeBDiagCursor)
        elif 'left' in areas or 'right' in areas: self.setCursor(Qt.SizeHorCursor)
        elif 'top' in areas or 'bottom' in areas: self.setCursor(Qt.SizeVerCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            areas = self._get_resize_area(event.pos())
            if areas: self.resize_area = areas; self.m_drag = False
            else: self.resize_area = None; self.m_drag = True; self.m_DragPosition = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.NoButton:
            self._set_cursor_shape(self._get_resize_area(event.pos()))
            event.accept(); return
        
        if event.buttons() == Qt.LeftButton:
            if self.resize_area:
                global_pos = event.globalPos()
                rect = self.geometry()
                
                if 'left' in self.resize_area:
                    new_w = rect.right() - global_pos.x()
                    if new_w > 100: rect.setLeft(global_pos.x())
                elif 'right' in self.resize_area:
                    new_w = global_pos.x() - rect.left()
                    if new_w > 100: rect.setWidth(new_w)
                    
                if 'top' in self.resize_area:
                    new_h = rect.bottom() - global_pos.y()
                    if new_h > 100: rect.setTop(global_pos.y())
                elif 'bottom' in self.resize_area:
                    new_h = global_pos.y() - rect.top()
                    if new_h > 100: rect.setHeight(new_h)
                
                self.setGeometry(rect)
                event.accept()
            elif self.m_drag:
                self.move(event.globalPos() - self.m_DragPosition)
                event.accept()

    def mouseReleaseEvent(self, event):
        self.m_drag = False; self.resize_area = None; self.setCursor(Qt.ArrowCursor)

    def showEvent(self, event):
        if not self.my_hwnd and user32: self.my_hwnd = int(self.winId())
        super().showEvent(event)

    def _monitor_foreground_window(self):
        if not user32: return 
        current_hwnd = user32.GetForegroundWindow()
        if current_hwnd == 0 or current_hwnd == self.my_hwnd: return
        
        if current_hwnd != self.last_active_hwnd:
            self.last_active_hwnd = current_hwnd
            self.last_thread_id = user32.GetWindowThreadProcessId(current_hwnd, None)
            self.last_focus_hwnd = None 

    def _on_search_text_changed(self):
        # 搜索变更时，重置为第一页
        self.current_page = 1
        self.search_timer.start(300)

    # [新增] 翻页控制槽函数
    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._update_list()

    def _next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._update_list()

    # [新增] 页码跳转逻辑
    def _jump_to_page(self):
        text = self.txt_page_input.text()
        if text.isdigit():
            page = int(text)
            if 1 <= page <= self.total_pages:
                self.current_page = page
                self._update_list()
            else:
                self.txt_page_input.setText(str(self.current_page))
        else:
            self.txt_page_input.setText(str(self.current_page))

    # [核心修改] 动态主题：奇/偶行都使用分类颜色，只是深浅不同
    def _apply_list_theme(self, color_hex):
        if color_hex:
            c = QColor(color_hex)
            
            # 偶数行（Base Background）：分类颜色的深色版 (350% darker)
            bg_color = c.darker(350).name()
            
            # 奇数行（Alternate Background）：分类颜色的更深色版 (450% darker) -> 也就是"调暗一点"
            alt_bg_color = c.darker(450).name()
            
            # 选中行：分类颜色的稍亮版 (110% darker，接近原色)
            sel_color = c.darker(110).name()

            style = f"""
                QListWidget {{
                    border: none;
                    outline: none;
                    /* 偶数行背景 */
                    background-color: {bg_color};
                    /* 奇数行背景 (交替色) - 更暗一点 */
                    alternate-background-color: {alt_bg_color};
                }}
                QListWidget::item {{
                    padding: 6px;
                    border: none;
                    border-bottom: 1px solid rgba(0,0,0, 0.3); /* 增加微弱的分割线提升层次感 */
                }}
                QListWidget::item:selected {{
                    background-color: {sel_color};
                    color: #FFFFFF;
                }}
                QListWidget::item:hover {{
                    background-color: rgba(255, 255, 255, 0.1);
                }}
            """
        else:
            # 默认深色主题 (未选中分类时)
            style = """
                QListWidget {
                    border: none;
                    outline: none;
                    background-color: #1e1e1e;
                    alternate-background-color: #151515;
                }
                QListWidget::item {
                    padding: 6px;
                    border: none;
                    border-bottom: 1px solid #2A2A2A;
                }
                QListWidget::item:selected {
                    background-color: #4a90e2;
                    color: #FFFFFF;
                }
                QListWidget::item:hover {
                    background-color: #333333;
                }
            """
        self.list_widget.setStyleSheet(style)

    def _update_list(self):
        search_text = self.search_box.text()
        
        # [双树逻辑] 检查谁被选中了
        current_partition_sys = self.system_tree.currentItem()
        current_partition_user = self.partition_tree.currentItem()
        
        f_type, f_val = 'all', None
        current_color = None
        
        # 优先判断是否有选中项
        active_item = None
        
        # [双树逻辑修复] 只要有 currentItem 且不为 None，就认为是激活项
        if current_partition_sys:
            active_item = current_partition_sys
        elif current_partition_user:
            active_item = current_partition_user
        
        if active_item:
            partition_data = active_item.data(0, Qt.UserRole)
            if partition_data:
                p_type = partition_data.get('type')
                if p_type == 'partition': 
                    f_type, f_val = 'category', partition_data.get('id')
                    current_color = partition_data.get('color') 
                elif p_type == 'uncategorized':
                    f_type, f_val = 'category', None
                elif p_type in ['all', 'today', 'untagged', 'bookmark', 'trash']: 
                    f_type, f_val = p_type, None

        # [新增] 应用动态列表颜色
        self._apply_list_theme(current_color)

        total_items = self.db.get_ideas_count(search=search_text, f_type=f_type, f_val=f_val)
        
        if total_items > 0:
            self.total_pages = math.ceil(total_items / self.page_size)
        else:
            self.total_pages = 1
            
        if self.current_page > self.total_pages:
            self.current_page = self.total_pages
        if self.current_page < 1:
            self.current_page = 1
            
        self.txt_page_input.setText(str(self.current_page))
        self.lbl_total_pages.setText(f"{self.total_pages}") # [修改] 移除 "/"
        
        self.btn_prev_page.setDisabled(self.current_page <= 1)
        self.btn_next_page.setDisabled(self.current_page >= self.total_pages)

        items = self.db.get_ideas(
            search=search_text, 
            f_type=f_type, 
            f_val=f_val, 
            page=self.current_page, 
            page_size=self.page_size
        )
        
        self.list_widget.clear()
        
        for item_tuple in items:
            list_item = QListWidgetItem()
            list_item.setData(Qt.UserRole, item_tuple)
            
            text_part = self._get_content_display(item_tuple)
            list_item.setText(text_part)
            
            item_type = item_tuple['item_type'] or 'text'
            icon = QIcon()
            
            if item_type == 'image' and item_tuple['data_blob']:
                pixmap = QPixmap()
                pixmap.loadFromData(item_tuple['data_blob'])
                if not pixmap.isNull():
                    icon = QIcon(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                icon_name = 'folder.svg' if item_type == 'folder' else 'all_data.svg'
                icon = create_svg_icon(icon_name, "#888")
            
            list_item.setIcon(icon)
            
            self._update_list_item_tooltip(list_item, item_tuple)
            
            self.list_widget.addItem(list_item)
            
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    # [双树逻辑修复] 强制清除另一个树的 currentItem，确保下次点击能触发 changed 信号
    def _on_system_selection_changed(self, current, previous):
        if current:
            # 清除下方分区的选中
            self.partition_tree.blockSignals(True)
            self.partition_tree.clearSelection()
            self.partition_tree.setCurrentItem(None) # [核心修复] 强制置空
            self.partition_tree.blockSignals(False)
            
            self.current_page = 1
            self._update_list()
            self._update_partition_status_display()

    # [双树逻辑修复] 强制清除另一个树的 currentItem，确保下次点击能触发 changed 信号
    def _on_partition_selection_changed(self, current, previous):
        if current:
            # 清除上方系统项的选中
            self.system_tree.blockSignals(True)
            self.system_tree.clearSelection()
            self.system_tree.setCurrentItem(None) # [核心修复] 强制置空
            self.system_tree.blockSignals(False)
            
            self.current_page = 1
            self._update_list()
            self._update_partition_status_display()

    def _get_icon_html(self, icon_name, color):
        cache_key = (icon_name, color)
        if cache_key in self._icon_html_cache:
            return self._icon_html_cache[cache_key]

        icon = create_svg_icon(icon_name, color)
        pixmap = icon.pixmap(14, 14) 
        ba = QByteArray()
        buffer = QBuffer(ba)
        buffer.open(QIODevice.WriteOnly)
        pixmap.save(buffer, "PNG")
        base64_str = ba.toBase64().data().decode()
        
        html = f'<img src="data:image/png;base64,{base64_str}" width="14" height="14" style="vertical-align:middle;">'
        self._icon_html_cache[cache_key] = html
        return html

    def _update_list_item_tooltip(self, list_item, item_data):
        category_id = item_data['category_id']
        all_cats = self.db.get_categories() 
        cat_name = "未分类"
        for c in all_cats:
            if c['id'] == category_id:
                cat_name = c['name']; break
        
        tags = self.db.get_tags(item_data['id'])
        tags_str = ", ".join(tags) if tags else "无"
        
        full_content = item_data['content'] or ""
        preview_limit = 400 
        content_preview = full_content[:preview_limit].strip().replace('\n', '<br>')
        if len(full_content) > preview_limit: content_preview += "..."
        if not content_preview and item_data['title']:
            content_preview = item_data['title'] 
            
        flags = []
        if item_data['is_pinned']: flags.append(f"{self._get_icon_html('pin_vertical.svg', '#e74c3c')} 置顶")
        if item_data['is_locked']: flags.append(f"{self._get_icon_html('lock.svg', COLORS['success'])} 锁定")
        if item_data['is_favorite']: flags.append(f"{self._get_icon_html('bookmark.svg', '#ff6b81')} 书签")
        flags_str = "&nbsp;&nbsp;".join(flags) if flags else "无"
        
        rating_val = item_data['rating'] or 0
        if rating_val > 0:
            star_icon = self._get_icon_html('star_filled.svg', '#f39c12')
            rating_str = (star_icon + " ") * rating_val
        else:
            rating_str = "无"
            
        icon_folder = self._get_icon_html("branch.svg", COLORS['primary'])
        icon_tag = self._get_icon_html("tag.svg", "#FFAB91")
        icon_star = self._get_icon_html("star.svg", "#f39c12")
        icon_flag = self._get_icon_html("pin_tilted.svg", "#aaaaaa")
        
        tooltip_html = f"""
        <html><body>
        <table border="0" cellpadding="1" cellspacing="0" style="color: #ddd;">
            <tr>
                <td width="20">{icon_folder}</td>
                <td><b>分区:</b> {cat_name}</td>
            </tr>
            <tr>
                <td width="20">{icon_tag}</td>
                <td><b>标签:</b> {tags_str}</td>
            </tr>
            <tr>
                <td width="20">{icon_star}</td>
                <td><b>评级:</b> {rating_str}</td>
            </tr>
            <tr>
                <td width="20">{icon_flag}</td>
                <td><b>状态:</b> {flags_str}</td>
            </tr>
        </table>
        <hr style="border: 0; border-top: 1px solid #555; margin: 5px 0;">
        <div style="color: #ccc; font-size: 12px; line-height: 1.4;">
            {content_preview}
        </div>
        </body></html>
        """
        list_item.setToolTip(tooltip_html)

    def _get_content_display(self, item_tuple):
        title = item_tuple['title']; content = item_tuple['content']
        item_type = item_tuple['item_type'] or 'text'
        text_part = title if item_type != 'text' else (content if content else "")
        text_part = text_part.replace('\n', ' ').replace('\r', '').strip()[:150]
        return text_part

    def _create_color_icon(self, color_str):
        pixmap = QPixmap(16, 16); pixmap.fill(Qt.transparent); painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing); painter.setBrush(QColor(color_str or "#808080"))
        painter.setPen(Qt.NoPen); painter.drawRoundedRect(2, 2, 12, 12, 4, 4); painter.end()
        return QIcon(pixmap)

    def _update_partition_tree(self):
        # [双树逻辑] 分别更新上下两棵树
        
        # 1. 更新上部系统树
        self.system_tree.clear()
        counts = self.db.get_counts()
        
        static_items = [
            ("全部数据", 'all', 'all_data.svg'), 
            ("今日数据", 'today', 'today.svg'), 
            ("未分类", 'uncategorized', 'uncategorized.svg'), 
            ("未标签", 'untagged', 'untagged.svg'), 
            ("书签", 'bookmark', 'bookmark.svg'), 
            ("回收站", 'trash', 'trash.svg')
        ]
        
        for name, key, icon_filename in static_items:
            data = {'type': key, 'id': None} # ID for system items is None usually
            # 修正 uncategorized 等的 ID 映射
            id_map = {'all': -1, 'today': -5, 'uncategorized': -15, 'untagged': -16, 'bookmark': -20, 'trash': -30}
            if key in id_map: data['id'] = id_map[key]
            
            item = QTreeWidgetItem(self.system_tree, [f"{name} ({counts.get(key, 0)})"])
            item.setData(0, Qt.UserRole, data)
            item.setIcon(0, create_svg_icon(icon_filename))
            item.setFlags(item.flags() & ~Qt.ItemIsDragEnabled) # 禁止系统项拖拽，但允许Drop
            item.setFlags(item.flags() | Qt.ItemIsDropEnabled) # 允许拖入

        # 默认选中“全部数据”
        if self.system_tree.topLevelItemCount() > 0 and not self.partition_tree.currentItem():
            self.system_tree.setCurrentItem(self.system_tree.topLevelItem(0))

        # 2. 更新下部分区树
        current_selection_data = None
        if self.partition_tree.currentItem(): 
            current_selection_data = self.partition_tree.currentItem().data(0, Qt.UserRole)
        
        self.partition_tree.clear()
        partition_counts = counts.get('categories', {})
        
        user_partitions_root = QTreeWidgetItem(self.partition_tree, ["我的分区"])
        user_partitions_root.setIcon(0, create_svg_icon("branch.svg", "white"))
        user_partitions_root.setFlags(Qt.ItemIsEnabled | Qt.ItemIsDropEnabled) # 仅允许Drop
        font = user_partitions_root.font(0); font.setBold(True); user_partitions_root.setFont(0, font)
        user_partitions_root.setForeground(0, QColor("#FFFFFF"))
            
        self._add_partition_recursive(self.db.get_partitions_tree(), user_partitions_root, partition_counts)
        self.partition_tree.expandAll()
        
        if current_selection_data:
            it = QTreeWidgetItemIterator(self.partition_tree)
            while it.value():
                item = it.value(); item_data = item.data(0, Qt.UserRole)
                if item_data and item_data.get('id') == current_selection_data.get('id') and item_data.get('type') == current_selection_data.get('type'):
                    self.partition_tree.setCurrentItem(item); break
                it += 1

    def _add_partition_recursive(self, partitions, parent_item, partition_counts):
        for partition in partitions:
            count = partition_counts.get(partition.id, 0)
            item = QTreeWidgetItem(parent_item, [f"{partition.name} ({count})"])
            item.setData(0, Qt.UserRole, {'type': 'partition', 'id': partition.id, 'color': partition.color})
            item.setIcon(0, self._create_color_icon(partition.color))
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
            if partition.children: self._add_partition_recursive(partition.children, item, partition_counts)

    def _update_partition_status_display(self):
        # [修改] 检查整个右侧容器的可见性
        if self.right_sidebar_widget.isHidden():
            current_sys = self.system_tree.currentItem()
            current_user = self.partition_tree.currentItem()
            
            text = "N/A"
            if current_sys:
                text = current_sys.text(0).split(' (')[0]
            elif current_user:
                text = current_user.text(0).split(' (')[0]
                
            self.partition_status_label.setText(f"当前分区: {text}")
            self.partition_status_label.show()
        else: self.partition_status_label.hide()
        
    def _toggle_partition_panel(self):
        is_visible = self.right_sidebar_widget.isVisible()
        self.right_sidebar_widget.setVisible(not is_visible)
        self.settings.setValue("partition_panel_hidden", not is_visible)
        self._update_partition_status_display()
    
    def _toggle_stay_on_top(self):
        if not user32: return
        self._is_pinned = self.btn_stay_top.isChecked()
        hwnd = int(self.winId())
        user32.SetWindowPos(hwnd, HWND_TOPMOST if self._is_pinned else HWND_NOTOPMOST, 0, 0, 0, 0, SWP_FLAGS)

    def _on_item_activated(self, item):
        item_tuple = item.data(Qt.UserRole)
        if not item_tuple: return
        try:
            clipboard = QApplication.clipboard(); item_type = item_tuple['item_type'] or 'text'
            if item_type == 'image':
                if item_tuple['data_blob']:
                    image = QImage(); image.loadFromData(item_tuple['data_blob']); clipboard.setImage(image)
            elif item_type != 'text':
                if item_tuple['content']:
                    mime_data = QMimeData(); mime_data.setUrls([QUrl.fromLocalFile(p) for p in item_tuple['content'].split(';') if p])
                    clipboard.setMimeData(mime_data)
            else:
                if item_tuple['content']: clipboard.setText(item_tuple['content'])
            self._paste_ditto_style()
        except Exception as e: log(f"❌ 粘贴操作失败: {e}")

    def _paste_ditto_style(self):
        if not user32: return
        target_win = self.last_active_hwnd; target_focus = self.last_focus_hwnd; target_thread = self.last_thread_id
        if not target_win or not user32.IsWindow(target_win): return
        
        curr_thread = kernel32.GetCurrentThreadId(); attached = False
        if target_thread and curr_thread != target_thread: attached = user32.AttachThreadInput(curr_thread, target_thread, True)
        
        try:
            if user32.IsIconic(target_win): user32.ShowWindow(target_win, 9)
            user32.SetForegroundWindow(target_win)
            
            if target_focus and user32.IsWindow(target_focus): user32.SetFocus(target_focus)
            
            time.sleep(0.1)
            user32.keybd_event(VK_CONTROL, 0, 0, 0); user32.keybd_event(VK_V, 0, 0, 0)
            user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0); user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        except Exception as e: log(f"❌ 粘贴异常: {e}")
        finally:
            if attached: user32.AttachThreadInput(curr_thread, target_thread, False)

    def _draw_book_mocha(self, p):
        w, h = 56, 76
        p.setBrush(QColor(245, 240, 225)); p.drawRoundedRect(QRectF(-w/2+6, -h/2+6, w, h), 3, 3)
        grad = QLinearGradient(-w, -h, w, h)
        grad.setColorAt(0, QColor(90, 60, 50)); grad.setColorAt(1, QColor(50, 30, 25))
        p.setBrush(grad); p.drawRoundedRect(QRectF(-w/2, -h/2, w, h), 3, 3)
        p.setBrush(QColor(120, 20, 30)); p.drawRect(QRectF(w/2 - 15, -h/2, 8, h))

    def _draw_universal_pen(self, p):
        w_pen, h_pen = 12, 46
        c_light, c_mid, c_dark = QColor(180, 60, 70), QColor(140, 20, 30), QColor(60, 5, 10)
        body_grad = QLinearGradient(-w_pen/2, 0, w_pen/2, 0)
        body_grad.setColorAt(0.0, c_light); body_grad.setColorAt(0.5, c_mid); body_grad.setColorAt(1.0, c_dark)
        path_body = QPainterPath()
        path_body.addRoundedRect(QRectF(-w_pen/2, -h_pen/2, w_pen, h_pen), 5, 5)
        p.setPen(Qt.NoPen); p.setBrush(body_grad); p.drawPath(path_body)
        path_tip = QPainterPath(); tip_h = 14
        path_tip.moveTo(-w_pen/2 + 3, h_pen/2); path_tip.lineTo(w_pen/2 - 3, h_pen/2); path_tip.lineTo(0, h_pen/2 + tip_h); path_tip.closeSubpath()
        tip_grad = QLinearGradient(-5, 0, 5, 0)
        tip_grad.setColorAt(0, QColor(240, 230, 180)); tip_grad.setColorAt(1, QColor(190, 170, 100))
        p.setBrush(tip_grad); p.drawPath(path_tip)
        p.setBrush(QColor(220, 200, 140)); p.drawRect(QRectF(-w_pen/2, h_pen/2 - 4, w_pen, 4))
        p.setBrush(QColor(210, 190, 130)); p.drawRoundedRect(QRectF(-1.5, -h_pen/2 + 6, 3, 24), 1.5, 1.5)

    # [已补全] 右键菜单功能
    def _show_partition_context_menu(self, pos):
        import logging
        try:
            # 判断点击的是哪个 TreeWidget
            sender = self.sender()
            if not sender: return
            
            item = sender.itemAt(pos)
            menu = QMenu(self)
            menu.setStyleSheet(f"background-color: {COLORS.get('bg_dark', '#2d2d2d')}; color: white; border: 1px solid #444;")
            
            # 点击的是“我的分区”根节点或空白处 -> 允许新建
            if not item or item.text(0) == "我的分区":
                menu.addAction('➕ 新建分组', self._new_group)
                menu.exec_(sender.mapToGlobal(pos))
                return
                
            data = item.data(0, Qt.UserRole)
            if data and data.get('type') == 'partition':
                cat_id = data.get('id'); raw_text = item.text(0); current_name = raw_text.split(' (')[0]
                
                menu.addAction('新建数据', lambda: self._request_new_data(cat_id))
                menu.addSeparator()
                menu.addAction('设置颜色', lambda: self._change_color(cat_id))
                menu.addAction('设置预设标签', lambda: self._set_preset_tags(cat_id))
                menu.addSeparator()
                menu.addAction('新建分组', self._new_group)
                menu.addAction('新建分区', lambda: self._new_zone(cat_id))
                menu.addAction('重命名', lambda: self._rename_category(cat_id, current_name))
                menu.addAction('删除', lambda: self._del_category(cat_id))
                
                menu.exec_(sender.mapToGlobal(pos))
            elif data and data.get('type') == 'trash':
                menu.addAction('清空回收站', self._empty_trash)
                menu.exec_(sender.mapToGlobal(pos))

        except Exception as e: logging.critical(f"Critical error in _show_partition_context_menu: {e}", exc_info=True)
    
    # [补充缺失] 清空回收站
    def _empty_trash(self):
        if QMessageBox.Yes == QMessageBox.warning(self, '清空回收站', '确定要清空回收站吗？\n此操作将永久删除所有内容，不可恢复！', QMessageBox.Yes | QMessageBox.No):
            self.db.empty_trash()
            self._update_list()
            self._update_partition_tree()

    def _request_new_data(self, cat_id):
        dialog = EditDialog(self.db, category_id_for_new=cat_id, parent=None)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.data_saved.connect(self._update_list); dialog.data_saved.connect(self._update_partition_tree)
        dialog.finished.connect(lambda: self.open_dialogs.remove(dialog) if dialog in self.open_dialogs else None)
        self.open_dialogs.append(dialog); dialog.show(); dialog.activateWindow()

    def _new_group(self):
        text, ok = QInputDialog.getText(self, '新建组', '组名称:')
        if ok and text: 
            new_cat_id = self.db.add_category(text, parent_id=None)
            if new_cat_id:
                recent_cats = load_setting('recent_categories', [])
                if new_cat_id in recent_cats: recent_cats.remove(new_cat_id)
                recent_cats.insert(0, new_cat_id)
                save_setting('recent_categories', recent_cats)
            self._update_partition_tree()
            
    def _new_zone(self, parent_id):
        text, ok = QInputDialog.getText(self, '新建区', '区名称:')
        if ok and text: 
            new_cat_id = self.db.add_category(text, parent_id=parent_id)
            if new_cat_id:
                recent_cats = load_setting('recent_categories', [])
                if new_cat_id in recent_cats: recent_cats.remove(new_cat_id)
                recent_cats.insert(0, new_cat_id)
                save_setting('recent_categories', recent_cats)
            self._update_partition_tree()

    def _rename_category(self, cat_id, old_name):
        text, ok = QInputDialog.getText(self, '重命名', '新名称:', text=old_name)
        if ok and text and text.strip(): self.db.rename_category(cat_id, text.strip()); self._update_partition_tree(); self._update_list() 

    def _del_category(self, cid):
        c = self.db.conn.cursor() 
        c.execute("SELECT COUNT(*) FROM categories WHERE parent_id = ?", (cid,))
        child_count = c.fetchone()[0]
        msg = '确认删除此分类? (其中的内容将移至未分类)'
        if child_count > 0: msg = f'此组包含 {child_count} 个区，确认一并删除?\n(所有内容都将移至未分类)'
        
        if QMessageBox.Yes == QMessageBox.question(self, '确认删除', msg):
            c.execute("SELECT id FROM categories WHERE parent_id = ?", (cid,))
            child_ids = [row[0] for row in c.fetchall()]
            for child_id in child_ids: self.db.delete_category(child_id)
            self.db.delete_category(cid); self._update_partition_tree(); self._update_list()

    def _change_color(self, cat_id):
        color = QColorDialog.getColor(Qt.gray, self, "选择分类颜色")
        if color.isValid(): self.db.set_category_color(cat_id, color.name()); self._update_partition_tree()

    def _set_preset_tags(self, cat_id):
        current_tags = self.db.get_category_preset_tags(cat_id)
        dlg = QDialog(self); dlg.setWindowTitle("设置预设标签"); dlg.setStyleSheet(f"background-color: {COLORS.get('bg_dark', '#2d2d2d')}; color: #EEE;"); dlg.setFixedSize(350, 150)
        
        layout = QVBoxLayout(dlg); layout.setContentsMargins(20, 20, 20, 20)
        info = QLabel("拖入该分类时自动绑定以下标签：\n(双击输入框选择历史标签)"); info.setStyleSheet("color: #888; font-size: 12px; margin-bottom: 5px;"); layout.addWidget(info)
        
        inp = ClickableLineEdit(); inp.setText(current_tags); inp.setPlaceholderText("例如: 工作, 重要 (逗号分隔)"); inp.setStyleSheet(f"background-color: {COLORS.get('bg_mid', '#333')}; border: 1px solid #444; padding: 6px; border-radius: 4px; color: white;"); layout.addWidget(inp)
        
        def open_tag_selector():
            initial_list = [t.strip() for t in inp.text().split(',') if t.strip()]
            selector = AdvancedTagSelector(self.db, idea_id=None, initial_tags=initial_list)
            def on_confirmed(tags): inp.setText(', '.join(tags))
            selector.tags_confirmed.connect(on_confirmed); selector.show_at_cursor()
            
        inp.doubleClicked.connect(open_tag_selector)
        
        btns = QHBoxLayout(); btns.addStretch(); btn_ok = QPushButton("完成"); btn_ok.setStyleSheet(f"background-color: {COLORS.get('primary', '#0078D4')}; border:none; padding: 5px 15px; border-radius: 4px; font-weight:bold; color: white;"); btn_ok.clicked.connect(dlg.accept); btns.addWidget(btn_ok); layout.addLayout(btns)
        
        if dlg.exec_() == QDialog.Accepted:
            new_tags = inp.text().strip(); self.db.set_category_preset_tags(cat_id, new_tags)
            tags_list = [t.strip() for t in new_tags.split(',') if t.strip()]
            if tags_list: self.db.apply_preset_tags_to_category_items(cat_id, tags_list)
            self.data_changed.emit()