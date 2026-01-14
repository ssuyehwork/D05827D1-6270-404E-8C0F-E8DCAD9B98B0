# -*- coding: utf-8 -*-
# ui/quick_window.py

import sys
import os
import ctypes
from ctypes import wintypes
import time
import math

from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QSplitter, QGraphicsDropShadowEffect, QShortcut, QToolTip,
                             QListWidgetItem, QMenu, QColorDialog, QInputDialog, 
                             QMessageBox, QFrame, QAbstractItemView)
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QSettings, QUrl, QMimeData, pyqtSignal, QObject, QSize, QByteArray, QBuffer, QIODevice
from PyQt5.QtGui import QImage, QColor, QCursor, QPixmap, QKeySequence, QIcon, QPainter, QTransform

from services.preview_service import PreviewService
from ui.dialogs import EditDialog
from ui.components.search_line_edit import SearchLineEdit
from core.config import COLORS
from core.settings import load_setting, save_setting
from ui.utils import create_svg_icon, create_clear_button_icon
from .quick_window_parts.widgets import DraggableListWidget
from .quick_window_parts.toolbar import Toolbar
from .quick_window_parts.quick_sidebar import Sidebar

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

try:
    from services.clipboard import ClipboardManager
except ImportError:
    class ClipboardManager(QObject):
        data_captured = pyqtSignal()
        def __init__(self, db_manager):
            super().__init__()
            self.db = db_manager
        def process_clipboard(self, mime_data, cat_id=None): pass

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
/* Toolbar Styles */
QWidget#RightToolbar {
    background-color: #252526;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    border-left: 1px solid #333;
}
QPushButton#ToolButton, QPushButton#MinButton, QPushButton#CloseButton, QPushButton#PinButton, QPushButton#MaxButton, QPushButton#PageButton { 
    background-color: transparent; 
    border-radius: 4px; 
    padding: 0px;
    border: none;
    margin: 0px;
}
QPushButton#ToolButton:hover, QPushButton#MinButton:hover, QPushButton#MaxButton:hover, QPushButton#PageButton:hover, QPushButton#PinButton:hover { 
    background-color: rgba(255, 255, 255, 0.1); 
}
QPushButton#CloseButton:hover { 
    background-color: #E81123; 
}
QPushButton#PinButton:checked, QPushButton#ToolButton:checked { 
    background-color: #4a90e2; 
    border: 1px solid #357abd; 
}
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
QLineEdit#PageInput:focus { border-color: #4a90e2; }
QLabel#TotalPageLabel { background: transparent; border: none; color: #777; font-size: 10px; }
QLabel#VerticalTitle { color: #666; font-weight: bold; font-size: 14px; font-family: "Microsoft YaHei"; padding-top: 10px; padding-bottom: 10px; }
QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0px; }
QScrollBar::handle:vertical { background: #444; border-radius: 3px; min-height: 20px; }
QScrollBar::handle:vertical:hover { background: #555; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
"""

class QuickWindow(QWidget):
    RESIZE_MARGIN = 8 
    toggle_main_window_requested = pyqtSignal()

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.settings = QSettings("MyTools", "RapidNotes")
        
        self.m_drag = False
        self.m_DragPosition = QPoint()
        self.resize_area = None
        self.resize_start_pos = None
        self.resize_start_geometry = None
        self._is_pinned = False
        
        self.current_filter_type = 'all'
        self.current_filter_value = None
        
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
        
        self.sidebar.selection_changed.connect(self._on_sidebar_selection_changed)
        self.sidebar.item_dropped_on_category.connect(self._handle_category_drop)
        self.sidebar.new_data_requested.connect(self._request_new_data_from_sidebar)
        self.sidebar.data_changed.connect(self._on_sidebar_data_changed)

        self.toolbar.close_requested.connect(self.close)
        self.toolbar.minimize_requested.connect(self.showMinimized)
        self.toolbar.open_full_requested.connect(self.toggle_main_window_requested)
        self.toolbar.toggle_stay_on_top_requested.connect(self._toggle_stay_on_top)
        self.toolbar.toggle_sidebar_requested.connect(self._toggle_partition_panel)
        self.toolbar.prev_page_requested.connect(self._prev_page)
        self.toolbar.next_page_requested.connect(self._next_page)
        self.toolbar.jump_to_page_requested.connect(self._jump_to_page_from_toolbar)
        self.toolbar.refresh_requested.connect(self.sidebar.refresh_ui)

        self.sidebar.refresh_ui()
        self._update_list()
        self._update_partition_status_display()

    def _get_resize_area(self, pos):
        check_widgets = [self.list_widget, self.sidebar, self.search_box, self.toolbar]
        
        for widget in check_widgets:
            if widget and widget.isVisible():
                origin = widget.mapTo(self, QPoint(0, 0))
                rect = QRect(origin, widget.size())
                if rect.contains(pos):
                    return [] 

        rect = self.container.geometry()
        x, y = pos.x(), pos.y()
        win_w, win_h = self.width(), self.height()
        m = self.RESIZE_MARGIN
        
        areas = []
        if x < m: areas.append('left')
        elif x > win_w - m: areas.append('right')
        
        if y < m: areas.append('top')
        elif y > win_h - m: areas.append('bottom')
        
        return areas

    def _set_cursor_shape(self, areas):
        if not areas:
            self.setCursor(Qt.ArrowCursor)
            return
            
        if 'left' in areas and 'top' in areas: self.setCursor(Qt.SizeFDiagCursor)
        elif 'right' in areas and 'bottom' in areas: self.setCursor(Qt.SizeFDiagCursor)
        elif 'left' in areas and 'bottom' in areas: self.setCursor(Qt.SizeBDiagCursor)
        elif 'right' in areas and 'top' in areas: self.setCursor(Qt.SizeBDiagCursor)
        elif 'left' in areas or 'right' in areas: self.setCursor(Qt.SizeHorCursor)
        elif 'top' in areas or 'bottom' in areas: self.setCursor(Qt.SizeVerCursor)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.NoButton:
            self._set_cursor_shape(self._get_resize_area(event.pos()))
            event.accept()
            return

        if event.buttons() == Qt.LeftButton:
            if self.resize_area:
                delta = event.globalPos() - self.resize_start_pos
                start_rect = self.resize_start_geometry
                
                x, y, w, h = start_rect.x(), start_rect.y(), start_rect.width(), start_rect.height()
                min_w, min_h = 400, 300

                if 'left' in self.resize_area:
                    new_x = start_rect.left() + delta.x()
                    new_w = start_rect.right() - new_x
                    if new_w > min_w:
                        x = new_x
                        w = new_w
                
                if 'right' in self.resize_area:
                    new_w = start_rect.width() + delta.x()
                    if new_w > min_w:
                        w = new_w
                
                if 'top' in self.resize_area:
                    new_y = start_rect.top() + delta.y()
                    new_h = start_rect.bottom() - new_y
                    if new_h > min_h:
                        y = new_y
                        h = new_h
                
                if 'bottom' in self.resize_area:
                    new_h = start_rect.height() + delta.y()
                    if new_h > min_h:
                        h = new_h

                self.setGeometry(x, y, w, h)
                event.accept()
            elif self.m_drag:
                self.move(event.globalPos() - self.m_DragPosition)
                event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            areas = self._get_resize_area(event.pos())
            if areas:
                self.resize_area = areas
                self.resize_start_pos = event.globalPos()
                self.resize_start_geometry = self.geometry()
                self.m_drag = False
            else:
                self.resize_area = None
                self.m_drag = True
                self.m_DragPosition = event.globalPos() - self.pos()
            event.accept()

    def mouseReleaseEvent(self, event):
        self.m_drag = False; self.resize_area = None; self.setCursor(Qt.ArrowCursor)

    def refresh_sidebar(self): self.sidebar.refresh_ui()
    def on_clipboard_changed(self):
        if self._processing_clipboard: return
        self._processing_clipboard = True
        try: self.cm.process_clipboard(self.clipboard.mimeData(), None)
        finally: self._processing_clipboard = False

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

        self.left_content_widget = QWidget()
        self.left_layout = QVBoxLayout(self.left_content_widget)
        self.left_layout.setContentsMargins(10, 10, 10, 5) 
        self.left_layout.setSpacing(8)

        self.search_box = SearchLineEdit(self)
        self.search_box.setPlaceholderText("搜索灵感 (双击查看历史)")
        self.search_box.setClearButtonEnabled(True)
        _clear_icon_path = create_clear_button_icon()
        self.search_box.setStyleSheet(self.search_box.styleSheet() + f"QLineEdit::clear-button {{ image: url({_clear_icon_path}); border: 0; margin-right: 5px; }} QLineEdit::clear-button:hover {{ background-color: #444; border-radius: 8px; }}")
        self.left_layout.addWidget(self.search_box)
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(4)
        
        self.list_widget = DraggableListWidget()
        self.list_widget.setFocusPolicy(Qt.StrongFocus)
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setIconSize(QSize(28, 28))
        
        # [修改] 开启多选模式
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        self.sidebar = Sidebar(self.db, self)
        
        self.splitter.addWidget(self.list_widget)
        self.splitter.addWidget(self.sidebar)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([550, 150])
        
        self.left_layout.addWidget(self.splitter)
        
        self.partition_status_label = QLabel("当前分区: 全部数据")
        self.partition_status_label.setObjectName("PartitionStatusLabel")
        self.partition_status_label.setStyleSheet("font-size: 11px; color: #888; padding-left: 2px;")
        self.partition_status_label.setFixedHeight(32)
        self.left_layout.addWidget(self.partition_status_label)
        self.partition_status_label.hide()

        self.main_container_layout.addWidget(self.left_content_widget)
        self.toolbar = Toolbar(self)
        self.main_container_layout.addWidget(self.toolbar)

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
        QShortcut(QKeySequence("Alt+D"), self, self._toggle_stay_on_top)
        QShortcut(QKeySequence("Alt+W"), self, self.toggle_main_window_requested.emit)
        QShortcut(QKeySequence("Ctrl+B"), self, self._do_edit_selected)
        QShortcut(QKeySequence("Ctrl+Q"), self, self._toggle_partition_panel)
        QShortcut(QKeySequence("Alt+S"), self, self._prev_page)
        QShortcut(QKeySequence("Alt+X"), self, self._next_page)
        for i in range(6): QShortcut(QKeySequence(f"Ctrl+{i}"), self, lambda r=i: self._do_set_rating(r))
        self.space_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.space_shortcut.setContext(Qt.WindowShortcut)
        self.space_shortcut.activated.connect(self._do_preview)

    def _do_preview(self):
        # 预览暂时只支持第一个选中项
        iid = self._get_first_selected_id()
        if iid: self.preview_service.toggle_preview({iid})

    def _do_new_idea(self):
        dialog = EditDialog(self.db, parent=None)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.data_saved.connect(self._update_list)
        dialog.data_saved.connect(self.sidebar.refresh_ui)
        dialog.show()
        self.open_dialogs.append(dialog)

    def _do_select_all(self): self.list_widget.selectAll()

    def _do_extract_content(self):
        # 复制所有选中的内容，用换行符合并
        selected_items = self.list_widget.selectedItems()
        if not selected_items: return
        
        texts = []
        for item in selected_items:
            data = item.data(Qt.UserRole)
            if data:
                item_type = data['item_type'] or 'text'
                content = data['content']
                if item_type == 'text' and content:
                    texts.append(content)
        
        if texts:
            full_text = "\n---\n".join(texts)
            QApplication.clipboard().setText(full_text)

    def _add_search_to_history(self):
        search_text = self.search_box.text().strip()
        if search_text: self.search_box.add_history_entry(search_text)

    def _show_list_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item: return
        
        # 确保右键点击的项目被选中（如果它还未被选中的话）
        if not item.isSelected():
            self.list_widget.setCurrentItem(item)
            
        data = item.data(Qt.UserRole)
        if not data: return
        
        is_locked = data['is_locked']
        is_pinned = data['is_pinned']
        is_fav = data['is_favorite']
        rating = data['rating']
        
        # 获取选中数量
        sel_count = len(self.list_widget.selectedItems())
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2D2D2D; color: #EEE; border: 1px solid #444; border-radius: 4px; padding: 4px; }
            QMenu::item { padding: 6px 10px 6px 28px; border-radius: 3px; }
            QMenu::item:selected { background-color: #4a90e2; color: white; }
            QMenu::separator { background-color: #444; height: 1px; margin: 4px 0px; }
            QMenu::icon { position: absolute; left: 6px; top: 6px; }
        """)
        
        if sel_count == 1:
            menu.addAction(create_svg_icon('action_eye.svg', '#1abc9c'), "预览 (Space)", self._do_preview)
            
        menu.addAction(create_svg_icon('action_export.svg', '#1abc9c'), f"复制内容 ({sel_count})", self._do_extract_content)
        menu.addSeparator()
        
        if sel_count == 1:
            menu.addAction(create_svg_icon('action_edit.svg', '#4a90e2'), "编辑", self._do_edit_selected)
            menu.addSeparator()
        
        from PyQt5.QtWidgets import QAction, QActionGroup
        rating_menu = menu.addMenu(create_svg_icon('star.svg', '#f39c12'), f"设置星级 ({sel_count})")
        star_group = QActionGroup(self); star_group.setExclusive(True)
        for i in range(1, 6):
            action = QAction(f"{'★'*i}", self, checkable=True); action.triggered.connect(lambda _, r=i: self._do_set_rating(r))
            if sel_count == 1 and rating == i: action.setChecked(True)
            rating_menu.addAction(action); star_group.addAction(action)
        rating_menu.addSeparator()
        rating_menu.addAction("清除评级").triggered.connect(lambda: self._do_set_rating(0))

        # 锁定状态是混合的，这里只根据当前右键的项目显示文字，但操作是批量的
        menu.addAction(create_svg_icon('lock.svg', COLORS['success'] if is_locked else '#aaaaaa'), 
                       "解锁选中项" if is_locked else "锁定选中项 (Ctrl+S)", self._do_lock_selected)
        
        menu.addSeparator()
        menu.addAction(create_svg_icon('pin_vertical.svg', '#e74c3c') if is_pinned else create_svg_icon('pin_tilted.svg', '#aaaaaa'), 
                       "取消置顶" if is_pinned else "置顶选中项", self._do_toggle_pin)
        
        menu.addAction(create_svg_icon('bookmark.svg', '#ff6b81'), 
                       "取消书签" if is_fav else "添加书签", self._do_toggle_favorite)
        menu.addSeparator()
        
        cat_menu = menu.addMenu(create_svg_icon('branch.svg', '#cccccc'), f'移动选中项到分类')
        recent_cats = load_setting('recent_categories', []); all_cats = {c['id']: c for c in self.db.get_categories()}
        action_uncategorized = cat_menu.addAction('⚠️ 未分类'); action_uncategorized.triggered.connect(lambda: self._move_to_category(None))
        count = 0
        for cat_id in recent_cats:
            if count >= 15: break
            if cat_id in all_cats:
                cat = all_cats[cat_id]
                action = cat_menu.addAction(create_svg_icon('branch.svg', cat['color']), f"{cat['name']}")
                action.triggered.connect(lambda _, cid=cat['id']: self._move_to_category(cid))
                count += 1
        
        menu.addSeparator()
        if not is_locked: menu.addAction(create_svg_icon('action_delete.svg', '#e74c3c'), f"删除 ({sel_count})", self._do_delete_selected)
        else: del_action = menu.addAction(create_svg_icon('action_delete.svg', '#555555'), "删除 (已锁定)"); del_action.setEnabled(False)
        menu.exec_(self.list_widget.mapToGlobal(pos))

    def _do_set_rating(self, rating):
        ids = self._get_selected_ids()
        for iid in ids:
            self.db.set_rating(iid, rating)

    def _move_to_category(self, cat_id):
        ids = self._get_selected_ids()
        if not ids: return
        
        if cat_id is not None:
            recent_cats = load_setting('recent_categories', [])
            if cat_id in recent_cats: recent_cats.remove(cat_id)
            recent_cats.insert(0, cat_id)
            save_setting('recent_categories', recent_cats)
            
        for iid in ids:
            self.db.move_category(iid, cat_id)

    def _copy_item_content(self, data):
        item_type = data['item_type'] or 'text'; content = data['content']
        if item_type == 'text' and content: QApplication.clipboard().setText(content)

    def _get_first_selected_id(self):
        item = self.list_widget.currentItem()
        if not item: return None
        data = item.data(Qt.UserRole)
        return data['id'] if data else None

    # [新增] 获取所有选中的 ID
    def _get_selected_ids(self):
        ids = []
        for item in self.list_widget.selectedItems():
            data = item.data(Qt.UserRole)
            if data:
                ids.append(data['id'])
        return ids
    
    def _do_lock_selected(self):
        ids = self._get_selected_ids()
        if not ids: return
        
        # 简单逻辑：根据第一个选中项的状态决定是全部锁定还是全部解锁
        first_id = ids[0]
        status = self.db.get_lock_status([first_id])
        current_state = status.get(first_id, 0)
        target_state = 0 if current_state else 1
        
        self.db.set_locked(ids, target_state)
    
    def _do_edit_selected(self):
        # 编辑只支持单选
        iid = self._get_first_selected_id()
        if iid:
            for dialog in self.open_dialogs:
                if hasattr(dialog, 'idea_id') and dialog.idea_id == iid: dialog.activateWindow(); return
            dialog = EditDialog(self.db, idea_id=iid, parent=None)
            dialog.setAttribute(Qt.WA_DeleteOnClose)
            dialog.data_saved.connect(self._update_list); dialog.data_saved.connect(self.sidebar.refresh_ui)
            dialog.finished.connect(lambda: self.open_dialogs.remove(dialog) if dialog in self.open_dialogs else None)
            self.open_dialogs.append(dialog); dialog.show(); dialog.activateWindow()

    def _do_delete_selected(self):
        ids = self._get_selected_ids()
        if not ids: return
        
        # 过滤掉锁定的
        status_map = self.db.get_lock_status(ids)
        to_delete = [iid for iid in ids if not status_map.get(iid, 0)]
        
        for iid in to_delete:
            self.db.set_deleted(iid, True)

    def _do_toggle_favorite(self):
        ids = self._get_selected_ids()
        for iid in ids:
            self.db.toggle_field(iid, 'is_favorite')

    def _do_toggle_pin(self):
        ids = self._get_selected_ids()
        for iid in ids:
            self.db.toggle_field(iid, 'is_pinned')

    def _handle_category_drop(self, idea_id, cat_id):
        # 这里的 idea_id 参数实际上来自 DropTreeWidget 的信号
        # 如果是多选拖拽，逻辑其实已经被 QuickSidebar 接管了
        # 但如果是从列表单个拖动到侧边栏，这个函数仍有效
        # 为了保险，我们不在这里处理多选逻辑，DropTreeWidget 会循环触发
        
        if cat_id == -30: 
            status = self.db.get_lock_status([idea_id])
            if status.get(idea_id, 0): return
        
        if cat_id == -20: self.db.set_favorite(idea_id, True, emit_signal=False)
        elif cat_id == -30: self.db.set_deleted(idea_id, True, emit_signal=False)
        elif cat_id == -15: self.db.move_category(idea_id, None, emit_signal=False)
        else: 
            self.db.move_category(idea_id, cat_id, emit_signal=False)
            if cat_id is not None:
                recent_cats = load_setting('recent_categories', []); 
                if cat_id in recent_cats: recent_cats.remove(cat_id)
                recent_cats.insert(0, cat_id); save_setting('recent_categories', recent_cats)

        # 手动、仅刷新侧边栏
        self.sidebar.refresh_ui()

    def _restore_window_state(self):
        geo_hex = load_setting("quick_window_geometry_hex")
        if geo_hex:
            try: self.restoreGeometry(QByteArray.fromHex(geo_hex.encode()))
            except: pass
        else:
            screen_geo = QApplication.desktop().screenGeometry(); win_geo = self.geometry()
            self.move((screen_geo.width() - win_geo.width()) // 2, (screen_geo.height() - win_geo.height()) // 2)
        splitter_hex = load_setting("quick_window_splitter_hex")
        if splitter_hex:
            try: self.splitter.restoreState(QByteArray.fromHex(splitter_hex.encode()))
            except: pass
        is_hidden = load_setting("partition_panel_hidden", False)
        self.sidebar.setHidden(is_hidden); self._update_partition_status_display()
        is_pinned = load_setting("quick_window_pinned", False)
        self.toolbar.set_stay_on_top(is_pinned); self._toggle_stay_on_top(is_pinned)

    def save_state(self):
        save_setting("quick_window_geometry_hex", self.saveGeometry().toHex().data().decode())
        save_setting("quick_window_splitter_hex", self.splitter.saveState().toHex().data().decode())
        save_setting("partition_panel_hidden", self.sidebar.isHidden())
        save_setting("quick_window_pinned", self.toolbar.btn_stay_top.isChecked())

    def closeEvent(self, event):
        self.save_state(); self.hide(); event.ignore()

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
        self.current_page = 1; self.search_timer.start(300)

    def _prev_page(self):
        if self.current_page > 1: self.current_page -= 1; self._update_list()

    def _next_page(self):
        if self.current_page < self.total_pages: self.current_page += 1; self._update_list()

    def _jump_to_page_from_toolbar(self, page):
        if 1 <= page <= self.total_pages: self.current_page = page; self._update_list()
        else: self.toolbar.update_pagination(self.current_page, self.total_pages)

    def _apply_list_theme(self, color_hex):
        if color_hex:
            c = QColor(color_hex)
            bg_color = c.darker(350).name(); alt_bg_color = c.darker(450).name(); sel_color = c.darker(110).name()
            style = f"QListWidget {{ border: none; outline: none; background-color: {bg_color}; alternate-background-color: {alt_bg_color}; }} QListWidget::item {{ padding: 6px; border: none; border-bottom: 1px solid rgba(0,0,0, 0.3); }} QListWidget::item:selected {{ background-color: {sel_color}; color: #FFFFFF; }} QListWidget::item:hover {{ background-color: rgba(255, 255, 255, 0.1); }}"
        else:
            style = "QListWidget { border: none; outline: none; background-color: #1e1e1e; alternate-background-color: #151515; } QListWidget::item { padding: 6px; border: none; border-bottom: 1px solid #2A2A2A; } QListWidget::item:selected { background-color: #4a90e2; color: #FFFFFF; } QListWidget::item:hover { background-color: #333333; }"
        self.list_widget.setStyleSheet(style)

    def _update_list(self):
        search_text = self.search_box.text()
        f_type = self.current_filter_type; f_val = self.current_filter_value
        current_color = self.sidebar.get_current_selection_color()
        self._apply_list_theme(current_color)
        total_items = self.db.get_ideas_count(search=search_text, f_type=f_type, f_val=f_val)
        self.total_pages = math.ceil(total_items / self.page_size) if total_items > 0 else 1
        if self.current_page > self.total_pages: self.current_page = self.total_pages
        if self.current_page < 1: self.current_page = 1
        self.toolbar.update_pagination(self.current_page, self.total_pages)
        items = self.db.get_ideas(search=search_text, f_type=f_type, f_val=f_val, page=self.current_page, page_size=self.page_size)
        self.list_widget.clear()
        
        for item_tuple in items:
            list_item = QListWidgetItem()
            list_item.setData(Qt.UserRole, item_tuple)
            text_part = self._get_content_display(item_tuple)
            list_item.setText(text_part)
            
            # --- 智能图标逻辑 (Flexible Logic) ---
            item_type = item_tuple['item_type'] or 'text'
            content = item_tuple['content'] or ""
            
            # 默认
            icon_name = 'text.svg'
            icon_color = "#95a5a6" # 默认浅灰色 (纯文本)

            if item_type == 'image':
                # 如果是图片且有数据，尝试显示缩略图
                if item_tuple['data_blob']:
                    pixmap = QPixmap()
                    pixmap.loadFromData(item_tuple['data_blob'])
                    if not pixmap.isNull():
                        icon = QIcon(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        list_item.setIcon(icon)
                        self._update_list_item_tooltip(list_item, item_tuple)
                        self.list_widget.addItem(list_item)
                        continue
                icon_name = 'image_icon.svg'
                icon_color = "#9b59b6" 
            elif item_type == 'file' or item_type == 'files':
                icon_name = 'file.svg'
                icon_color = "#f1c40f"
            elif item_type == 'folder':
                icon_name = 'folder.svg'
                icon_color = "#e67e22"
            elif item_type == 'text':
                # 【核心修复】智能检测文本内容，忽略引号
                stripped = content.strip()
                # 预处理：去掉两端的引号（解决Windows复制路径带引号问题）
                clean_path = stripped.strip('"\'')
                
                # 1. 检测链接
                if stripped.startswith(('http://', 'https://', 'www.')):
                    icon_name = 'link.svg'
                    icon_color = "#3498db"
                # 2. 检测代码片段
                elif stripped.startswith(('#', 'import ', 'class ', 'def ', '<', '{', 'function', 'var ', 'const ')):
                    icon_name = 'code.svg'
                    icon_color = "#2ecc71"
                # 3. 【新】灵活检测文件路径
                elif len(clean_path) < 260 and (
                    (len(clean_path) > 2 and clean_path[1] == ':') or 
                    clean_path.startswith(('\\\\', '/', './', '../'))
                ):
                    # 只有在看起来像路径时才调用系统IO检测
                    if os.path.exists(clean_path):
                        if os.path.isdir(clean_path):
                            icon_name = 'folder.svg'
                            icon_color = "#e67e22"
                        else:
                            icon_name = 'file.svg' # 这次会正确显示文档图标
                            icon_color = "#f1c40f"
            
            icon = create_svg_icon(icon_name, icon_color)
            list_item.setIcon(icon)
            
            self._update_list_item_tooltip(list_item, item_tuple)
            self.list_widget.addItem(list_item)
            
        if self.list_widget.count() > 0: self.list_widget.setCurrentRow(0)

    def _on_sidebar_selection_changed(self, f_type, f_val):
        self.current_filter_type = f_type; self.current_filter_value = f_val
        self.current_page = 1; self._update_list(); self._update_partition_status_display()

    def _on_sidebar_data_changed(self): self.sidebar.refresh_ui(); self._update_list()

    def _get_icon_html(self, icon_name, color):
        cache_key = (icon_name, color)
        if cache_key in self._icon_html_cache: return self._icon_html_cache[cache_key]
        icon = create_svg_icon(icon_name, color); pixmap = icon.pixmap(14, 14); ba = QByteArray()
        buffer = QBuffer(ba); buffer.open(QIODevice.WriteOnly); pixmap.save(buffer, "PNG")
        base64_str = ba.toBase64().data().decode()
        html = f'<img src="data:image/png;base64,{base64_str}" width="14" height="14" style="vertical-align:middle;">'
        self._icon_html_cache[cache_key] = html; return html

    def _update_list_item_tooltip(self, list_item, item_data):
        category_id = item_data['category_id']
        all_cats = self.db.get_categories(); cat_name = "未分类"
        for c in all_cats:
            if c['id'] == category_id: cat_name = c['name']; break
        tags = self.db.get_tags(item_data['id']); tags_str = ", ".join(tags) if tags else "无"
        full_content = item_data['content'] or ""; preview_limit = 400
        content_preview = full_content[:preview_limit].strip().replace('\n', '<br>')
        if len(full_content) > preview_limit: content_preview += "..."
        if not content_preview and item_data['title']: content_preview = item_data['title']
        flags = []
        if item_data['is_pinned']: flags.append(f"{self._get_icon_html('pin_vertical.svg', '#e74c3c')} 置顶")
        if item_data['is_locked']: flags.append(f"{self._get_icon_html('lock.svg', COLORS['success'])} 锁定")
        if item_data['is_favorite']: flags.append(f"{self._get_icon_html('bookmark.svg', '#ff6b81')} 书签")
        flags_str = "&nbsp;&nbsp;".join(flags) if flags else "无"
        rating_val = item_data['rating'] or 0
        rating_str = (self._get_icon_html('star_filled.svg', '#f39c12') + " ") * rating_val if rating_val > 0 else "无"
        icon_folder = self._get_icon_html("branch.svg", COLORS['primary']); icon_tag = self._get_icon_html("tag.svg", "#FFAB91")
        icon_star = self._get_icon_html("star.svg", "#f39c12"); icon_flag = self._get_icon_html("pin_tilted.svg", "#aaaaaa")
        tooltip_html = f"<html><body><table border='0' cellpadding='1' cellspacing='0' style='color: #ddd;'><tr><td width='20'>{icon_folder}</td><td><b>分区:</b> {cat_name}</td></tr><tr><td width='20'>{icon_tag}</td><td><b>标签:</b> {tags_str}</td></tr><tr><td width='20'>{icon_star}</td><td><b>评级:</b> {rating_str}</td></tr><tr><td width='20'>{icon_flag}</td><td><b>状态:</b> {flags_str}</td></tr></table><hr style='border: 0; border-top: 1px solid #555; margin: 5px 0;'><div style='color: #ccc; font-size: 12px; line-height: 1.4;'>{content_preview}</div></body></html>"
        list_item.setToolTip(tooltip_html)

    def _get_content_display(self, item_tuple):
        title = item_tuple['title']; content = item_tuple['content']; item_type = item_tuple['item_type'] or 'text'
        text_part = title if item_type != 'text' else (content if content else "")
        return text_part.replace('\n', ' ').replace('\r', '').strip()[:150]

    def _create_color_icon(self, color_str):
        pixmap = QPixmap(16, 16); pixmap.fill(Qt.transparent); painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing); painter.setBrush(QColor(color_str or "#808080"))
        painter.setPen(Qt.NoPen); painter.drawRoundedRect(2, 2, 12, 12, 4, 4); painter.end()
        return QIcon(pixmap)

    def _update_partition_status_display(self):
        if self.sidebar.isHidden():
            text = self.sidebar.get_current_selection_text()
            self.partition_status_label.setText(f"当前分区: {text}"); self.partition_status_label.show()
        else: self.partition_status_label.hide()
        
    def _toggle_partition_panel(self):
        is_visible = self.sidebar.isVisible(); self.sidebar.setVisible(not is_visible)
        self.settings.setValue("partition_panel_hidden", not is_visible); self._update_partition_status_display()
    
    def _toggle_stay_on_top(self, is_pinned=None):
        if not user32: return
        self._is_pinned = not self._is_pinned if is_pinned is None else is_pinned
        self.toolbar.set_stay_on_top(self._is_pinned)
        hwnd = int(self.winId())
        user32.SetWindowPos(hwnd, HWND_TOPMOST if self._is_pinned else HWND_NOTOPMOST, 0, 0, 0, 0, SWP_FLAGS)

    def _on_item_activated(self, item):
        item_tuple = item.data(Qt.UserRole)
        if not item_tuple: return
        try:
            clipboard = QApplication.clipboard(); clipboard.clear() 
            item_type = item_tuple['item_type'] or 'text'
            if item_type == 'image':
                if item_tuple['data_blob']:
                    image = QImage(); image.loadFromData(item_tuple['data_blob']); clipboard.setImage(image)
            elif item_type != 'text': 
                content_str = item_tuple['content']
                if content_str:
                    raw_paths = [p.strip() for p in content_str.split(';') if p.strip()]
                    valid_urls = []; missing_files = []
                    for p in raw_paths:
                        if os.path.exists(p): valid_urls.append(QUrl.fromLocalFile(p))
                        else: missing_files.append(os.path.basename(p))
                    if valid_urls:
                        mime_data = QMimeData(); mime_data.setUrls(valid_urls); clipboard.setMimeData(mime_data)
                    else:
                        clipboard.setText(content_str)
                        if missing_files: QToolTip.showText(QCursor.pos(), f"⚠️ 原文件已丢失，已复制路径文本", self)
            else:
                if item_tuple['content']: clipboard.setText(item_tuple['content'])
            QApplication.processEvents()
            self._paste_ditto_style()
        except Exception as e: print(f"❌ 激活条目失败: {e}")

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
        except Exception: pass
        finally:
            if attached: user32.AttachThreadInput(curr_thread, target_thread, False)

    def _request_new_data_from_sidebar(self, cat_id):
        dialog = EditDialog(self.db, category_id_for_new=cat_id, parent=None)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.data_saved.connect(self._update_list); dialog.data_saved.connect(self.sidebar.refresh_ui)
        dialog.finished.connect(lambda: self.open_dialogs.remove(dialog) if dialog in self.open_dialogs else None)
        self.open_dialogs.append(dialog); dialog.show(); dialog.activateWindow()