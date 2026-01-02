# -*- coding: utf-8 -*-
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
                             QLabel, QTreeWidgetItemIterator, QShortcut, QAbstractItemView, QMenu)
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QSettings, QUrl, QMimeData, pyqtSignal, QObject, QSize
from PyQt5.QtGui import QImage, QColor, QCursor, QPixmap, QPainter, QIcon, QKeySequence, QDrag
from services.preview_service import PreviewService
from ui.dialogs import EditDialog  # 【新增】导入编辑窗口

# =================================================================================
#   Win32 API 定义
# =================================================================================
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

def log(message):
    try: print(message, flush=True)
    except: pass

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

# =================================================================================
#   自定义增强控件
# =================================================================================

class DraggableListWidget(QListWidget):
    """支持拖出数据的列表"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item: return
        
        data = item.data(Qt.UserRole)
        if not data: return
        idea_id = data[0]

        mime = QMimeData()
        mime.setData('application/x-idea-id', str(idea_id).encode())
        
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec_(Qt.MoveAction)

class DropTreeWidget(QTreeWidget):
    """支持接收数据的分类树"""
    item_dropped = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('application/x-idea-id'):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat('application/x-idea-id'):
            item = self.itemAt(event.pos())
            if item:
                data = item.data(0, Qt.UserRole)
                if data and data.get('type') == 'partition':
                    self.setCurrentItem(item)
                    event.accept()
                    return
        event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasFormat('application/x-idea-id'):
            try:
                idea_id = int(event.mimeData().data('application/x-idea-id'))
                item = self.itemAt(event.pos())
                if item:
                    data = item.data(0, Qt.UserRole)
                    if data and data.get('type') == 'partition':
                        cat_id = data.get('id')
                        self.item_dropped.emit(idea_id, cat_id)
                        event.acceptProposedAction()
            except Exception as e:
                print(f"Drop error: {e}")

# =================================================================================
#   样式表
# =================================================================================
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
"""

class QuickWindow(QWidget):
    RESIZE_MARGIN = 18 
    open_main_window_requested = pyqtSignal()

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
        
        self.preview_service = PreviewService(self.db, self)
        
        self._init_ui()
        self._setup_shortcuts()
        self._restore_window_state()
        
        self.setMouseTracking(True)
        self.container.setMouseTracking(True)
        
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._monitor_foreground_window)
        if user32:
            self.monitor_timer.start(200)

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._update_list)
        
        self.search_box.textChanged.connect(self._on_search_text_changed)
        self.list_widget.itemActivated.connect(self._on_item_activated)
        
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_list_context_menu)
        
        self.partition_tree.currentItemChanged.connect(self._on_partition_selection_changed)
        self.partition_tree.item_dropped.connect(self._handle_category_drop)
        
        self.clear_action.triggered.connect(self.search_box.clear)
        self.search_box.textChanged.connect(lambda text: self.clear_action.setVisible(bool(text)))
        self.clear_action.setVisible(False)
        
        self.btn_stay_top.clicked.connect(self._toggle_stay_on_top)
        self.btn_toggle_side.clicked.connect(self._toggle_partition_panel)
        self.btn_open_full.clicked.connect(self.open_main_window_requested)
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
        
        # --- Title Bar ---
        title_bar_layout = QHBoxLayout()
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        title_bar_layout.setSpacing(5)
        
        self.title_label = QLabel("⚡️ 快速笔记")
        self.title_label.setObjectName("TitleLabel")
        title_bar_layout.addWidget(self.title_label)
        
        title_bar_layout.addStretch()
        
        self.btn_stay_top = QPushButton("📌", self)
        self.btn_stay_top.setObjectName("PinButton")
        self.btn_stay_top.setToolTip("保持置顶")
        self.btn_stay_top.setCheckable(True)
        self.btn_stay_top.setFixedSize(32, 32)

        self.btn_toggle_side = QPushButton("👁️", self)
        self.btn_toggle_side.setObjectName("ToolButton")
        self.btn_toggle_side.setToolTip("显示/隐藏侧边栏")
        self.btn_toggle_side.setFixedSize(32, 32)
        
        self.btn_open_full = QPushButton(self)
        self.btn_open_full.setObjectName("MaxButton")
        self.btn_open_full.setToolTip("打开主程序界面")
        self.btn_open_full.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMaxButton))
        self.btn_open_full.setFixedSize(32, 32)

        self.btn_minimize = QPushButton("—", self)
        self.btn_minimize.setObjectName("MinButton")
        self.btn_minimize.setToolTip("最小化")
        self.btn_minimize.setFixedSize(32, 32)
        
        self.btn_close = QPushButton(self)
        self.btn_close.setObjectName("CloseButton")
        self.btn_close.setToolTip("关闭")
        self.btn_close.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        self.btn_close.setFixedSize(32, 32)
        
        title_bar_layout.addWidget(self.btn_stay_top)
        title_bar_layout.addWidget(self.btn_toggle_side)
        title_bar_layout.addWidget(self.btn_open_full) 
        title_bar_layout.addWidget(self.btn_minimize)
        title_bar_layout.addWidget(self.btn_close)
        
        self.main_layout.addLayout(title_bar_layout)
        
        # --- Search Bar ---
        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("搜索剪贴板历史...")
        self.clear_action = QAction(self)
        self.clear_action.setIcon(self.style().standardIcon(QStyle.SP_DialogCloseButton))
        self.search_box.addAction(self.clear_action, QLineEdit.TrailingPosition)
        
        self.main_layout.addWidget(self.search_box)
        
        # --- Splitter Content ---
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

        # --- Status Bar ---
        self.partition_status_label = QLabel("当前分区: 全部数据")
        self.partition_status_label.setObjectName("PartitionStatusLabel")
        self.partition_status_label.setStyleSheet("font-size: 11px; color: #888; padding-left: 5px;")
        self.main_layout.addWidget(self.partition_status_label)
        self.partition_status_label.hide()

    # --- 快捷键设置 ---
    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+F"), self, self.search_box.setFocus)
        QShortcut(QKeySequence("Delete"), self, self._do_delete_selected)
        QShortcut(QKeySequence("Ctrl+E"), self, self._do_toggle_favorite)
        QShortcut(QKeySequence("Ctrl+P"), self, self._do_toggle_pin)
        QShortcut(QKeySequence("Ctrl+W"), self, self.close)
        
        # 监听空格键：预览
        self.space_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.space_shortcut.setContext(Qt.WindowShortcut)
        self.space_shortcut.activated.connect(self._do_preview)

    def _do_preview(self):
        iid = self._get_selected_id()
        if iid:
            self.preview_service.toggle_preview({iid})

    # --- 右键菜单逻辑 ---
    def _show_list_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item: return

        data = item.data(Qt.UserRole)
        if not data: return
        
        is_pinned = data[4]
        is_fav = data[5]

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2D2D2D; color: #EEE; border: 1px solid #444; border-radius: 4px; padding: 4px; }
            QMenu::item { padding: 6px 20px; border-radius: 3px; }
            QMenu::item:selected { background-color: #4a90e2; color: white; }
            QMenu::separator { background-color: #444; height: 1px; margin: 4px 0px; }
        """)

        action_preview = menu.addAction("👁️ 预览 (Space)")
        action_preview.triggered.connect(self._do_preview)
        
        menu.addSeparator()

        action_copy = menu.addAction("📋 复制内容")
        action_copy.triggered.connect(lambda: self._copy_item_content(data))
        
        menu.addSeparator()

        action_pin = menu.addAction("📌 取消置顶" if is_pinned else "📌 置顶")
        action_pin.triggered.connect(self._do_toggle_pin)

        action_fav = menu.addAction("⭐ 取消收藏" if is_fav else "⭐ 收藏")
        action_fav.triggered.connect(self._do_toggle_favorite)
        
        # 【新增】编辑选项
        action_edit = menu.addAction("✏️ 编辑")
        action_edit.triggered.connect(self._do_edit_selected)

        menu.addSeparator()

        action_del = menu.addAction("🗑️ 删除")
        action_del.triggered.connect(self._do_delete_selected)

        menu.exec_(self.list_widget.mapToGlobal(pos))

    def _copy_item_content(self, data):
        item_type_idx = 10
        item_type = data[item_type_idx] if len(data) > item_type_idx else 'text'
        content = data[2]
        if item_type == 'text' and content:
            QApplication.clipboard().setText(content)

    # --- 逻辑处理 ---

    def _get_selected_id(self):
        item = self.list_widget.currentItem()
        if not item: return None
        data = item.data(Qt.UserRole)
        if data: return data[0] 
        return None
    
    # 【新增】编辑功能
    def _do_edit_selected(self):
        iid = self._get_selected_id()
        if iid:
            dialog = EditDialog(self.db, idea_id=iid)
            if dialog.exec_():
                self._update_list()
                self._update_partition_tree()

    def _do_delete_selected(self):
        iid = self._get_selected_id()
        if iid:
            self.db.set_deleted(iid, True)
            self._update_list()
            self._update_partition_tree()

    def _do_toggle_favorite(self):
        iid = self._get_selected_id()
        if iid:
            self.db.toggle_field(iid, 'is_favorite')
            self._update_list() 

    def _do_toggle_pin(self):
        iid = self._get_selected_id()
        if iid:
            self.db.toggle_field(iid, 'is_pinned')
            self._update_list()

    def _handle_category_drop(self, idea_id, cat_id):
        self.db.move_category(idea_id, cat_id)
        self._update_list()
        self._update_partition_tree()

    # --- Restore & Save State ---
    def _restore_window_state(self):
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            screen_geo = QApplication.desktop().screenGeometry()
            win_geo = self.geometry()
            x = (screen_geo.width() - win_geo.width()) // 2
            y = (screen_geo.height() - win_geo.height()) // 2
            self.move(x, y)
        splitter_state = self.settings.value("splitter_state")
        if splitter_state: self.splitter.restoreState(splitter_state)

        is_hidden = self.settings.value("partition_panel_hidden", False, type=bool)
        self.partition_tree.setHidden(is_hidden)
        self._update_partition_status_display()

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter_state", self.splitter.saveState())
        self.hide()
        event.ignore()

    # --- Mouse Logic ---
    def _get_resize_area(self, pos):
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = self.RESIZE_MARGIN
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
            if areas:
                self.resize_area = areas
                self.m_drag = False
            else:
                self.resize_area = None
                self.m_drag = True
                self.m_DragPosition = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.NoButton:
            areas = self._get_resize_area(event.pos())
            self._set_cursor_shape(areas)
            event.accept()
            return
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
        self.m_drag = False
        self.resize_area = None
        self.setCursor(Qt.ArrowCursor)

    # --- Core Logic ---
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
            curr_thread = kernel32.GetCurrentThreadId()
            attached = False
            if curr_thread != self.last_thread_id:
                attached = user32.AttachThreadInput(curr_thread, self.last_thread_id, True)
            try:
                gui_info = GUITHREADINFO()
                gui_info.cbSize = ctypes.sizeof(GUITHREADINFO)
                if user32.GetGUIThreadInfo(self.last_thread_id, ctypes.byref(gui_info)):
                    self.last_focus_hwnd = gui_info.hwndFocus or gui_info.hwndActive
            except: pass
            finally:
                if attached: user32.AttachThreadInput(curr_thread, self.last_thread_id, False)

    def _on_search_text_changed(self): self.search_timer.start(300)

    def _update_list(self):
        search_text = self.search_box.text()
        current_partition = self.partition_tree.currentItem()
        if current_partition:
            partition_data = current_partition.data(0, Qt.UserRole)
            if partition_data:
                if partition_data.get('type') == 'today':
                    f_type, f_val = 'today', None
                elif partition_data.get('type') == 'partition':
                    f_type, f_val = 'category', partition_data.get('id')
                else: # all
                    f_type, f_val = 'all', None
            else:
                f_type, f_val = 'all', None
        else:
            f_type, f_val = 'all', None

        items = self.db.get_ideas(search=search_text, f_type=f_type, f_val=f_val)
        self.list_widget.clear()
        
        # 1. 预加载分类映射 (ID -> Name)
        categories = {c[0]: c[1] for c in self.db.get_categories()}
        
        for item_tuple in items:
            list_item = QListWidgetItem()
            list_item.setData(Qt.UserRole, item_tuple)
            
            item_type = item_tuple[10] if len(item_tuple) > 10 else 'text'
            if item_type == 'image':
                blob_data = item_tuple[11] if len(item_tuple) > 11 else None
                if blob_data:
                    pixmap = QPixmap()
                    pixmap.loadFromData(blob_data)
                    if not pixmap.isNull():
                        icon = QIcon(pixmap)
                        list_item.setIcon(icon)

            display_text = self._get_content_display(item_tuple)
            list_item.setText(display_text)
            
            # Tooltip 只显示分区和标签
            idea_id = item_tuple[0]
            category_id = item_tuple[8]
            
            cat_name = categories.get(category_id, "未分类")
            tags = self.db.get_tags(idea_id)
            tags_str = " ".join([f"#{t}" for t in tags]) if tags else "无"
            
            tooltip = f"📂 分区: {cat_name}\n🏷️ 标签: {tags_str}"
            list_item.setToolTip(tooltip)
            
            self.list_widget.addItem(list_item)
        if self.list_widget.count() > 0: self.list_widget.setCurrentRow(0)

    def _get_content_display(self, item_tuple):
        title = item_tuple[1]
        content = item_tuple[2]
        
        prefix = ""
        if item_tuple[4]: prefix += "📌 "
        if item_tuple[5]: prefix += "⭐ "
        
        item_type = item_tuple[10] if len(item_tuple) > 10 and item_tuple[10] else 'text'

        text_part = ""
        if item_type == 'image':
            text_part = title 
        elif item_type == 'file':
            text_part = title 
        else: 
            text_part = title if title else (content if content else "")
            text_part = text_part.replace('\n', ' ').replace('\r', '').strip()[:150]
            
        return prefix + text_part

    def _create_color_icon(self, color_str):
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(color_str or "#808080"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(2, 2, 12, 12, 4, 4)
        painter.end()
        return QIcon(pixmap)

    def _update_partition_tree(self):
        current_selection_data = None
        if self.partition_tree.currentItem():
            current_selection_data = self.partition_tree.currentItem().data(0, Qt.UserRole)
            
        self.partition_tree.clear()
        
        counts = self.db.get_partition_item_counts()
        partition_counts = counts.get('partitions', {})

        static_items = [
            ("全部数据", {'type': 'all', 'id': -1}, QStyle.SP_DirHomeIcon, counts.get('total', 0)),
            ("今日数据", {'type': 'today', 'id': -5}, QStyle.SP_FileDialogDetailedView, counts.get('today_modified', 0)),
        ]
        
        for name, data, icon, count in static_items:
            item = QTreeWidgetItem(self.partition_tree, [f"{name} ({count})"])
            item.setData(0, Qt.UserRole, data)
            item.setIcon(0, self.style().standardIcon(icon))
        
        top_level_partitions = self.db.get_partitions_tree()
        self._add_partition_recursive(top_level_partitions, self.partition_tree, partition_counts)

        self.partition_tree.expandAll()
        
        if current_selection_data:
            it = QTreeWidgetItemIterator(self.partition_tree)
            while it.value():
                item = it.value()
                item_data = item.data(0, Qt.UserRole)
                if item_data and item_data.get('id') == current_selection_data.get('id') and item_data.get('type') == current_selection_data.get('type'):
                    self.partition_tree.setCurrentItem(item)
                    break
                it += 1
        else:
            if self.partition_tree.topLevelItemCount() > 0:
                self.partition_tree.setCurrentItem(self.partition_tree.topLevelItem(0))

    def _add_partition_recursive(self, partitions, parent_item, partition_counts):
        for partition in partitions:
            count = partition_counts.get(partition.id, 0)
            item = QTreeWidgetItem(parent_item, [f"{partition.name} ({count})"])
            item.setData(0, Qt.UserRole, {'type': 'partition', 'id': partition.id, 'color': partition.color})
            item.setIcon(0, self._create_color_icon(partition.color))
            
            if partition.children:
                self._add_partition_recursive(partition.children, item, partition_counts)

    def _update_partition_status_display(self):
        is_hidden = self.partition_tree.isHidden()
        if is_hidden:
            current_item = self.partition_tree.currentItem()
            if current_item:
                text = current_item.text(0).split(' (')[0]
                self.partition_status_label.setText(f"当前分区: {text}")
            else:
                self.partition_status_label.setText("当前分区: N/A")
            self.partition_status_label.show()
        else:
            self.partition_status_label.hide()

    def _on_partition_selection_changed(self, c, p):
        self._update_list()
        self._update_partition_status_display()
        
    def _toggle_partition_panel(self):
        is_currently_visible = self.partition_tree.isVisible()
        self.partition_tree.setVisible(not is_currently_visible)
        self.settings.setValue("partition_panel_hidden", not is_currently_visible)
        self._update_partition_status_display()
    
    def _toggle_stay_on_top(self):
        if not user32: return
        self._is_pinned = self.btn_stay_top.isChecked()
        hwnd = int(self.winId())
        if self._is_pinned:
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_FLAGS)
        else:
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_FLAGS)

    def _on_item_activated(self, item):
        item_tuple = item.data(Qt.UserRole)
        if not item_tuple: return

        try:
            clipboard = QApplication.clipboard()
            
            item_type_index = 10
            item_type = item_tuple[item_type_index] if len(item_tuple) > item_type_index and item_tuple[item_type_index] else 'text'
            
            if item_type == 'image':
                blob_index = 11
                image_blob = item_tuple[blob_index]
                if image_blob:
                    image = QImage()
                    image.loadFromData(image_blob)
                    clipboard.setImage(image)
            elif item_type == 'file':
                content_index = 2
                file_path_str = item_tuple[content_index]
                if file_path_str:
                    mime_data = QMimeData()
                    urls = [QUrl.fromLocalFile(p) for p in file_path_str.split(';') if p]
                    mime_data.setUrls(urls)
                    clipboard.setMimeData(mime_data)
            else:
                content_index = 2
                content_to_copy = item_tuple[content_index] if item_tuple[content_index] else ""
                clipboard.setText(content_to_copy)

            self._paste_ditto_style()
        except Exception as e: 
            log(f"❌ 粘贴操作失败: {e}")

    def _paste_ditto_style(self):
        if not user32: return
        target_win = self.last_active_hwnd
        target_focus = self.last_focus_hwnd
        target_thread = self.last_thread_id
        if not target_win or not user32.IsWindow(target_win): return
        curr_thread = kernel32.GetCurrentThreadId()
        attached = False
        if target_thread and curr_thread != target_thread:
            attached = user32.AttachThreadInput(curr_thread, target_thread, True)
        try:
            if user32.IsIconic(target_win): user32.ShowWindow(target_win, 9)
            user32.SetForegroundWindow(target_win)
            if target_focus and user32.IsWindow(target_focus): user32.SetFocus(target_focus)
            time.sleep(0.1)
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            user32.keybd_event(VK_V, 0, 0, 0)
            user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        except Exception as e: log(f"❌ 粘贴异常: {e}")
        finally:
            if attached: user32.AttachThreadInput(curr_thread, target_thread, False)

    def on_clipboard_changed(self):
        if self._processing_clipboard:
            return
        self._processing_clipboard = True
        try:
            mime = self.clipboard.mimeData()
            self.cm.process_clipboard(mime, None)
        finally:
            self._processing_clipboard = False

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape: self.close()
        elif key in (Qt.Key_Up, Qt.Key_Down):
            if not self.list_widget.hasFocus():
                self.list_widget.setFocus()
                QApplication.sendEvent(self.list_widget, event)
        else: super().keyPressEvent(event)