# -*- coding: utf-8 -*-
# ui/quick_window.py

import sys
import os
import ctypes
from ctypes import wintypes
import time
import datetime
import subprocess

from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QListWidget, QLineEdit, 
                             QListWidgetItem, QHBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QPushButton, QStyle, QAction, QSplitter, QGraphicsDropShadowEffect, 
                             QLabel, QTreeWidgetItemIterator, QShortcut, QAbstractItemView, QMenu,
                             QColorDialog, QInputDialog, QMessageBox)
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QSettings, QUrl, QMimeData, pyqtSignal, QObject, QSize, QByteArray
from PyQt5.QtGui import QImage, QColor, QCursor, QPixmap, QPainter, QIcon, QKeySequence, QDrag

from services.preview_service import PreviewService
from ui.dialogs import EditDialog
from ui.advanced_tag_selector import AdvancedTagSelector
from ui.components.search_line_edit import SearchLineEdit
from core.config import COLORS
from core.settings import load_setting, save_setting
from ui.utils import create_svg_icon, create_clear_button_icon

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
        if event.source() == self:
            super().dragEnterEvent(event)
            event.accept()
        elif event.mimeData().hasFormat('application/x-idea-id'):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.source() == self:
            super().dragMoveEvent(event)
        elif event.mimeData().hasFormat('application/x-idea-id'):
            item = self.itemAt(event.pos())
            if item:
                data = item.data(0, Qt.UserRole)
                if data and data.get('type') in ['partition', 'favorite']:
                    self.setCurrentItem(item)
                    event.accept()
                    return
            event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasFormat('application/x-idea-id'):
            try:
                idea_id = int(event.mimeData().data('application/x-idea-id'))
                item = self.itemAt(event.pos())
                if item:
                    data = item.data(0, Qt.UserRole)
                    if data and data.get('type') in ['partition', 'favorite']:
                        cat_id = data.get('id')
                        self.item_dropped.emit(idea_id, cat_id)
                        event.acceptProposedAction()
            except Exception as e:
                pass
        elif event.source() == self:
            super().dropEvent(event)
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
QListWidget::item { padding: 8px; border: none; }
QListWidget::item:selected, QTreeWidget::item:selected {
    background-color: #4a90e2; color: #FFFFFF;
}
QListWidget::item:hover { background-color: #444444; }
QSplitter::handle { background-color: #333333; width: 2px; }
QSplitter::handle:hover { background-color: #4a90e2; }
QLineEdit {
    background-color: #252526;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 6px;
    font-size: 16px;
}
QPushButton#ToolButton, QPushButton#MinButton, QPushButton#CloseButton, QPushButton#PinButton, QPushButton#MaxButton { 
    background-color: transparent; 
    border-radius: 4px; 
    padding: 0px;  
    font-size: 16px;
    font-weight: bold;
    text-align: center;
}
QPushButton#ToolButton:hover, QPushButton#MinButton:hover, QPushButton#MaxButton:hover { background-color: #444; }
QPushButton#ToolButton:checked, QPushButton#MaxButton:checked { background-color: #555; border: 1px solid #666; }
QPushButton#CloseButton:hover { background-color: #E81123; color: white; }
QPushButton#PinButton:hover { background-color: #444; }
QPushButton#PinButton:checked { background-color: #0078D4; color: white; border: 1px solid #005A9E; }

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
        # 保持监控频率，但移除了内部的危险操作
        if user32: self.monitor_timer.start(200)
        
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._update_list)
        
        self.search_box.textChanged.connect(self._on_search_text_changed)
        self.search_box.returnPressed.connect(self._add_search_to_history)
        self.list_widget.itemActivated.connect(self._on_item_activated)
        
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_list_context_menu)
        
        self.partition_tree.currentItemChanged.connect(self._on_partition_selection_changed)
        self.partition_tree.item_dropped.connect(self._handle_category_drop)
        self.partition_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.partition_tree.customContextMenuRequested.connect(self._show_partition_context_menu)
        self.partition_tree.order_changed.connect(self._save_partition_order)
        
        self.btn_stay_top.clicked.connect(self._toggle_stay_on_top)
        self.btn_toggle_side.clicked.connect(self._toggle_partition_panel)
        self.btn_open_full.clicked.connect(self.toggle_main_window_requested)
        self.btn_minimize.clicked.connect(self.showMinimized) 
        self.btn_close.clicked.connect(self.close)
        
        self._update_partition_tree()
        self._update_list()
        self.partition_tree.currentItemChanged.connect(self._update_partition_status_display)

    def _init_ui(self):
        self.setWindowTitle("快速笔记")
        self.resize(830, 630)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(15, 15, 15, 15) 
        
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
        
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        
        title_bar_layout = QHBoxLayout()
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        title_bar_layout.setSpacing(5)
        
        self.title_label = QLabel("⚡️ 快速笔记")
        self.title_label.setObjectName("TitleLabel")
        title_bar_layout.addWidget(self.title_label)
        
        title_bar_layout.addStretch()
        
        self.btn_stay_top = QPushButton(self)
        self.btn_stay_top.setIcon(create_svg_icon('pin_tilted.svg', '#aaa'))
        self.btn_stay_top.setObjectName("PinButton")
        self.btn_stay_top.setToolTip("保持置顶")
        self.btn_stay_top.setCheckable(True)
        self.btn_stay_top.setFixedSize(32, 32)
        
        self.btn_toggle_side = QPushButton(self)
        self.btn_toggle_side.setIcon(create_svg_icon('action_eye.svg', '#aaa'))
        self.btn_toggle_side.setObjectName("ToolButton")
        self.btn_toggle_side.setToolTip("显示/隐藏侧边栏")
        self.btn_toggle_side.setFixedSize(32, 32)
        
        self.btn_open_full = QPushButton(self)
        self.btn_open_full.setIcon(create_svg_icon('win_max.svg', '#aaa'))
        self.btn_open_full.setObjectName("MaxButton")
        self.btn_open_full.setToolTip("切换主程序界面")
        self.btn_open_full.setFixedSize(32, 32)
        
        self.btn_minimize = QPushButton(self)
        self.btn_minimize.setIcon(create_svg_icon('win_min.svg', '#aaa'))
        self.btn_minimize.setObjectName("MinButton")
        self.btn_minimize.setToolTip("最小化")
        self.btn_minimize.setFixedSize(32, 32)
        
        self.btn_close = QPushButton(self)
        self.btn_close.setIcon(create_svg_icon('win_close.svg', '#aaa'))
        self.btn_close.setObjectName("CloseButton")
        self.btn_close.setToolTip("关闭")
        self.btn_close.setFixedSize(32, 32)
        
        title_bar_layout.addWidget(self.btn_stay_top)
        title_bar_layout.addWidget(self.btn_toggle_side)
        title_bar_layout.addWidget(self.btn_open_full) 
        title_bar_layout.addWidget(self.btn_minimize)
        title_bar_layout.addWidget(self.btn_close)
        
        self.main_layout.addLayout(title_bar_layout)
        
        self.search_box = SearchLineEdit(self)
        self.search_box.setPlaceholderText("🔍 搜索灵感 (双击查看历史)")
        self.search_box.setClearButtonEnabled(True)

        _clear_icon_path = create_clear_button_icon()
        clear_button_style = f"""
        QLineEdit::clear-button {{
            image: url({_clear_icon_path});
            border: 0;
            margin-right: 5px;
        }}
        QLineEdit::clear-button:hover {{
            background-color: #444;
            border-radius: 8px;
        }}
        """
        # Apply the style directly to the search box for better encapsulation
        self.search_box.setStyleSheet(self.search_box.styleSheet() + clear_button_style)

        self.main_layout.addWidget(self.search_box)
        
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(4)
        
        self.list_widget = DraggableListWidget()
        self.list_widget.setFocusPolicy(Qt.StrongFocus)
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setIconSize(QSize(120, 90))
        
        self.partition_tree = DropTreeWidget()
        self.partition_tree.setHeaderHidden(True)
        self.partition_tree.setFocusPolicy(Qt.NoFocus)
        self.partition_tree.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.partition_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.splitter.addWidget(self.list_widget)
        self.splitter.addWidget(self.partition_tree)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([550, 150])
        
        content_layout.addWidget(self.splitter)
        self.main_layout.addWidget(content_widget, 1)
        
        self.partition_status_label = QLabel("当前分区: 全部数据")
        self.partition_status_label.setObjectName("PartitionStatusLabel")
        self.partition_status_label.setStyleSheet("font-size: 11px; color: #888; padding-left: 5px;")
        self.main_layout.addWidget(self.partition_status_label)
        self.partition_status_label.hide()

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
            
            # --- 菜单样式优化 ---
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
            item.setText(self._get_content_display(new_data))
    
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
                item.setText(self._get_content_display(new_data))

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
        elif target_type == 'uncategorized': self.db.move_category(idea_id, None)
        elif target_type == 'partition': self.db.move_category(idea_id, cat_id)
        
        self._update_list(); self._update_partition_tree()

    def _save_partition_order(self):
        update_list = []
        def iterate_items(parent_item, parent_id):
            for i in range(parent_item.childCount()):
                item = parent_item.child(i)
                data = item.data(0, Qt.UserRole)
                if data and data.get('type') == 'partition':
                    cat_id = data.get('id')
                    update_list.append((cat_id, parent_id, i))
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
        self.partition_tree.setHidden(is_hidden)
        self._update_partition_status_display()
        
        is_pinned = load_setting("quick_window_pinned", False)
        self.btn_stay_top.setChecked(is_pinned)
        self._toggle_stay_on_top()

    def save_state(self):
        save_setting("quick_window_geometry_hex", self.saveGeometry().toHex().data().decode())
        save_setting("quick_window_splitter_hex", self.splitter.saveState().toHex().data().decode())
        save_setting("partition_panel_hidden", self.partition_tree.isHidden())
        save_setting("quick_window_pinned", self.btn_stay_top.isChecked())

    def closeEvent(self, event):
        self.save_state()
        self.hide()
        event.ignore()

    def _get_resize_area(self, pos):
        x, y = pos.x(), pos.y(); w, h = self.width(), self.height(); m = self.RESIZE_MARGIN
        areas = []
        if x < m: areas.append('left')
        elif x > w - m: areas.append('right')
        if y < m: areas.append('top')
        elif y > h - m: areas.append('bottom')
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
        """
        修正后的监控方法：
        仅记录前台窗口句柄，移除了导致系统卡顿的 AttachThreadInput 逻辑。
        """
        if not user32: return 
        current_hwnd = user32.GetForegroundWindow()
        if current_hwnd == 0 or current_hwnd == self.my_hwnd: return
        
        if current_hwnd != self.last_active_hwnd:
            self.last_active_hwnd = current_hwnd
            self.last_thread_id = user32.GetWindowThreadProcessId(current_hwnd, None)
            self.last_focus_hwnd = None # 移除焦点控件记录，由系统自动处理

    def _on_search_text_changed(self): self.search_timer.start(300)

    def _update_list(self):
        search_text = self.search_box.text()
        current_partition = self.partition_tree.currentItem()
        f_type, f_val = 'all', None
        
        if current_partition:
            partition_data = current_partition.data(0, Qt.UserRole)
            if partition_data:
                p_type = partition_data.get('type')
                if p_type == 'partition': f_type, f_val = 'category', partition_data.get('id')
                elif p_type in ['all', 'today', 'uncategorized', 'untagged', 'bookmark', 'trash']: f_type, f_val = p_type, None

        items = self.db.get_ideas(search=search_text, f_type=f_type, f_val=f_val)
        self.list_widget.clear()
        categories = {c[0]: c[1] for c in self.db.get_categories()}
        
        for item_tuple in items:
            list_item = QListWidgetItem()
            list_item.setData(Qt.UserRole, item_tuple)
            
            item_type = item_tuple['item_type'] or 'text'
            if item_type == 'image':
                blob_data = item_tuple['data_blob']
                if blob_data:
                    pixmap = QPixmap(); pixmap.loadFromData(blob_data)
                    if not pixmap.isNull(): list_item.setIcon(QIcon(pixmap))
            
            display_text = self._get_content_display(item_tuple)
            list_item.setText(display_text)
            
            idea_id = item_tuple['id']; category_id = item_tuple['category_id']
            cat_name = categories.get(category_id, "未分类")
            tags = self.db.get_tags(idea_id); tags_str = " ".join([f"#{t}" for t in tags]) if tags else "无"
            
            list_item.setToolTip(f"📂 分区: {cat_name}\n🏷️ 标签: {tags_str}")
            self.list_widget.addItem(list_item)
            
        if self.list_widget.count() > 0: self.list_widget.setCurrentRow(0)

    def _get_content_display(self, item_tuple):
        title = item_tuple['title']; content = item_tuple['content']; prefix = ""
        rating = item_tuple['rating'] or 0
        
        if rating > 0: prefix += f"{'★'*rating} "
        if item_tuple['is_locked']: prefix += "🔒 "
        if item_tuple['is_pinned']: prefix += "📌 "
        if item_tuple['is_favorite']: prefix += "🔖 "
        
        item_type = item_tuple['item_type'] or 'text'
        text_part = title if item_type != 'text' else (content if content else "")
        text_part = text_part.replace('\n', ' ').replace('\r', '').strip()[:150]
        return prefix + text_part

    def _create_color_icon(self, color_str):
        pixmap = QPixmap(16, 16); pixmap.fill(Qt.transparent); painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing); painter.setBrush(QColor(color_str or "#808080"))
        painter.setPen(Qt.NoPen); painter.drawRoundedRect(2, 2, 12, 12, 4, 4); painter.end()
        return QIcon(pixmap)

    def _update_partition_tree(self):
        current_selection_data = None
        if self.partition_tree.currentItem(): current_selection_data = self.partition_tree.currentItem().data(0, Qt.UserRole)
        
        self.partition_tree.clear()
        counts = self.db.get_counts(); partition_counts = counts.get('categories', {})
        static_items = [("全部数据", 'all', 'all_data.svg'), ("今日数据", 'today', 'today.svg'), ("未分类", 'uncategorized', 'uncategorized.svg'), ("未标签", 'untagged', 'untagged.svg'), ("书签", 'bookmark', 'bookmark.svg'), ("回收站", 'trash', 'trash.svg')]
        id_map = {'all': -1, 'today': -5, 'uncategorized': -15, 'untagged': -16, 'bookmark': -20, 'trash': -30}
        
        for name, key, icon_filename in static_items:
            data = {'type': key, 'id': id_map.get(key)}
            item = QTreeWidgetItem(self.partition_tree, [f"{name} ({counts.get(key, 0)})"])
            item.setData(0, Qt.UserRole, data)
            item.setIcon(0, create_svg_icon(icon_filename))
            
        self._add_partition_recursive(self.db.get_partitions_tree(), self.partition_tree, partition_counts)
        self.partition_tree.expandAll()
        
        if current_selection_data:
            it = QTreeWidgetItemIterator(self.partition_tree)
            while it.value():
                item = it.value(); item_data = item.data(0, Qt.UserRole)
                if item_data and item_data.get('id') == current_selection_data.get('id') and item_data.get('type') == current_selection_data.get('type'):
                    self.partition_tree.setCurrentItem(item); break
                it += 1
        else:
            if self.partition_tree.topLevelItemCount() > 0: self.partition_tree.setCurrentItem(self.partition_tree.topLevelItem(0))

    def _add_partition_recursive(self, partitions, parent_item, partition_counts):
        for partition in partitions:
            count = partition_counts.get(partition.id, 0)
            item = QTreeWidgetItem(parent_item, [f"{partition.name} ({count})"])
            item.setData(0, Qt.UserRole, {'type': 'partition', 'id': partition.id, 'color': partition.color})
            item.setIcon(0, self._create_color_icon(partition.color))
            if partition.children: self._add_partition_recursive(partition.children, item, partition_counts)

    def _update_partition_status_display(self):
        if self.partition_tree.isHidden():
            current_item = self.partition_tree.currentItem()
            text = current_item.text(0).split(' (')[0] if current_item else "N/A"
            self.partition_status_label.setText(f"当前分区: {text}")
            self.partition_status_label.show()
        else: self.partition_status_label.hide()

    def _on_partition_selection_changed(self, c, p): self._update_list(); self._update_partition_status_display()
        
    def _toggle_partition_panel(self):
        is_visible = self.partition_tree.isVisible()
        self.partition_tree.setVisible(not is_visible)
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
                # 任何非 Image 非 Text 的都视为文件类型处理
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
        # 仅在需要粘贴的一瞬间进行挂靠
        if target_thread and curr_thread != target_thread: attached = user32.AttachThreadInput(curr_thread, target_thread, True)
        
        try:
            if user32.IsIconic(target_win): user32.ShowWindow(target_win, 9)
            user32.SetForegroundWindow(target_win)
            
            # 如果之前有记录焦点控件，尝试恢复；如果没有，SetForegroundWindow通常已足够
            if target_focus and user32.IsWindow(target_focus): user32.SetFocus(target_focus)
            
            time.sleep(0.1)
            user32.keybd_event(VK_CONTROL, 0, 0, 0); user32.keybd_event(VK_V, 0, 0, 0)
            user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0); user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        except Exception as e: log(f"❌ 粘贴异常: {e}")
        finally:
            if attached: user32.AttachThreadInput(curr_thread, target_thread, False)

    def on_clipboard_changed(self):
        if self._processing_clipboard: return
        self._processing_clipboard = True
        try:
            mime = self.clipboard.mimeData()
            self.cm.process_clipboard(mime, None)
        finally: self._processing_clipboard = False

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape: self.close()
        elif key in (Qt.Key_Up, Qt.Key_Down):
            if not self.list_widget.hasFocus(): self.list_widget.setFocus(); QApplication.sendEvent(self.list_widget, event)
        else: super().keyPressEvent(event)

    def _show_partition_context_menu(self, pos):
        import logging
        try:
            item = self.partition_tree.itemAt(pos)
            menu = QMenu(self)
            menu.setStyleSheet(f"background-color: {COLORS.get('bg_dark', '#2d2d2d')}; color: white; border: 1px solid #444;")
            
            if not item:
                menu.addAction('➕ 新建分组', self._new_group); menu.exec_(self.partition_tree.mapToGlobal(pos)); return
                
            data = item.data(0, Qt.UserRole)
            if data and data.get('type') == 'partition':
                cat_id = data.get('id'); raw_text = item.text(0); current_name = raw_text.split(' (')[0]
                
                menu.addAction('➕ 新建数据', lambda: self._request_new_data(cat_id))
                menu.addSeparator()
                menu.addAction('🎨 设置颜色', lambda: self._change_color(cat_id))
                menu.addAction('🏷️ 设置预设标签', lambda: self._set_preset_tags(cat_id))
                menu.addSeparator()
                menu.addAction('➕ 新建分组', self._new_group)
                menu.addAction('➕ 新建分区', lambda: self._new_zone(cat_id))
                menu.addAction('✏️ 重命名', lambda: self._rename_category(cat_id, current_name))
                menu.addAction('🗑️ 删除', lambda: self._del_category(cat_id))
                
                menu.exec_(self.partition_tree.mapToGlobal(pos))
            else:
                 if not item: menu.addAction('➕ 新建分组', self._new_group); menu.exec_(self.partition_tree.mapToGlobal(pos))
        except Exception as e: logging.critical(f"Critical error in _show_partition_context_menu: {e}", exc_info=True)

    def _request_new_data(self, cat_id):
        dialog = EditDialog(self.db, category_id_for_new=cat_id, parent=None)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.data_saved.connect(self._update_list); dialog.data_saved.connect(self._update_partition_tree)
        dialog.finished.connect(lambda: self.open_dialogs.remove(dialog) if dialog in self.open_dialogs else None)
        self.open_dialogs.append(dialog); dialog.show(); dialog.activateWindow()

    def _new_group(self):
        text, ok = QInputDialog.getText(self, '新建组', '组名称:')
        if ok and text: self.db.add_category(text, parent_id=None); self._update_partition_tree()
            
    def _new_zone(self, parent_id):
        text, ok = QInputDialog.getText(self, '新建区', '区名称:')
        if ok and text: self.db.add_category(text, parent_id=parent_id); self._update_partition_tree()

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
        dlg = QDialog(self); dlg.setWindowTitle("🏷️ 设置预设标签"); dlg.setStyleSheet(f"background-color: {COLORS.get('bg_dark', '#2d2d2d')}; color: #EEE;"); dlg.setFixedSize(350, 150)
        
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

