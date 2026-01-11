# 项目代码汇总

生成时间: 2026-01-09 20:03:06
文件总数: 49

---

## 文件: K Main_V3.py

```python
# K Main_V3.py
import sys
import time
import logging
import traceback
import keyboard
from PyQt5.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QDialog
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtNetwork import QLocalServer, QLocalSocket

# 导入 Container 和 Views
from core.container import AppContainer
from core.signals import app_signals
from ui.quick_window import QuickWindow
from ui.main_window import MainWindow
from ui.ball import FloatingBall
from ui.action_popup import ActionPopup
from ui.common_tags_manager import CommonTagsManager
from core.settings import load_setting

SERVER_NAME = "K_KUAIJIBIJI_SINGLE_INSTANCE_SERVER"

# --- Setup Logging ---
log_format = '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
logging.basicConfig(filename='app_log.txt', level=logging.DEBUG, format=log_format, filemode='w')
def excepthook(exc_type, exc_value, exc_tb):
    logging.error("Unhandled exception:", exc_info=(exc_type, exc_value, exc_tb))
    traceback.print_exception(exc_type, exc_value, exc_tb)
sys.excepthook = excepthook
# --- End Logging Setup ---

# 用于在主线程中接收全局热键信号
class HotkeySignal(QObject):
    activated = pyqtSignal()

class AppManager(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        
        # 1. 初始化容器并获取 Service
        self.container = AppContainer()
        self.service = self.container.service
        
        self.main_window = None
        self.quick_window = None
        self.ball = None
        self.popup = None 
        self.tray_icon = None
        self.tags_manager_dialog = None
        
        # 全局热键信号
        self.hotkey_signal = HotkeySignal()
        self.hotkey_signal.activated.connect(self.toggle_quick_window)

    def start(self):
        # 2. 注入 Service 到 UI 组件
        self.main_window = MainWindow(self.service) 
        self.main_window.closing.connect(self.on_main_window_closing)

        self.ball = FloatingBall(self.main_window)
        
        # 悬浮球菜单逻辑
        original_context_menu = self.ball.contextMenuEvent
        def enhanced_context_menu(e):
            from ui.utils import create_svg_icon
            m = QMenu(self.ball)
            m.setStyleSheet("""
                QMenu { 
                    background-color: #2b2b2b; 
                    color: #f0f0f0; 
                    border: 1px solid #444; 
                    border-radius: 5px; 
                    padding: 5px; 
                }
                QMenu::item { 
                    padding: 6px 15px 6px 5px; 
                    border-radius: 3px;
                }
                QMenu::item:selected { 
                    background-color: #5D4037; 
                    color: #fff; 
                }
                QMenu::separator { 
                    background-color: #444; 
                    height: 1px; 
                    margin: 4px 0; 
                }
            """)
            skin_menu = m.addMenu(create_svg_icon('display.svg'), "切换外观")
            a1 = skin_menu.addAction(create_svg_icon('coffee.svg'), "摩卡·勃艮第"); a1.triggered.connect(lambda: self.ball.switch_skin(self.ball.SKIN_MOCHA))
            a2 = skin_menu.addAction(create_svg_icon('grid.svg'), "经典黑金"); a2.triggered.connect(lambda: self.ball.switch_skin(self.ball.SKIN_CLASSIC))
            a3 = skin_menu.addAction(create_svg_icon('book.svg'), "皇家蓝"); a3.triggered.connect(lambda: self.ball.switch_skin(self.ball.SKIN_ROYAL))
            a4 = skin_menu.addAction(create_svg_icon('leaf.svg'), "抹茶绿"); a4.triggered.connect(lambda: self.ball.switch_skin(self.ball.SKIN_MATCHA))
            a5 = skin_menu.addAction(create_svg_icon('book-open.svg'), "摊开手稿"); a5.triggered.connect(lambda: self.ball.switch_skin(self.ball.SKIN_OPEN))

            m.addSeparator()
            m.addAction(create_svg_icon('zap.svg'), '打开快速笔记', self.ball.request_show_quick_window.emit)
            m.addAction(create_svg_icon('monitor.svg'), '打开主界面', self.ball.request_show_main_window.emit)
            m.addAction(create_svg_icon('action_add.svg'), '新建灵感', self.main_window.new_idea)
            m.addSeparator()
            m.addAction(create_svg_icon('tag.svg'), '管理常用标签', self._open_common_tags_manager) 
            m.addSeparator()
            m.addAction(create_svg_icon('power.svg'), '退出', self.ball.request_quit_app.emit)
            m.exec_(e.globalPos())

        self.ball.contextMenuEvent = enhanced_context_menu
        self.ball.request_show_quick_window.connect(self.show_quick_window)
        self.ball.double_clicked.connect(self.show_quick_window)
        self.ball.request_show_main_window.connect(self.show_main_window)
        self.ball.request_quit_app.connect(self.quit_application)
        
        ball_pos = load_setting('floating_ball_pos')
        if ball_pos and isinstance(ball_pos, dict) and 'x' in ball_pos and 'y' in ball_pos:
            self.ball.move(ball_pos['x'], ball_pos['y'])
        else:
            g = QApplication.desktop().screenGeometry()
            self.ball.move(g.width()-80, g.height()//2)
        self.ball.show()

        self.quick_window = QuickWindow(self.service) 
        self.quick_window.toggle_main_window_requested.connect(self.toggle_main_window)
        
        self.popup = ActionPopup(self.service) 
        self.popup.request_favorite.connect(self._handle_popup_favorite)
        self.popup.request_tag_toggle.connect(self._handle_popup_tag_toggle)
        self.popup.request_manager.connect(self._open_common_tags_manager)
        
        self.quick_window.cm.data_captured.connect(self._on_clipboard_data_captured)
        
        self._init_tray_icon()
        
        # 连接全局信号
        app_signals.data_changed.connect(self.main_window._refresh_all)
        app_signals.data_changed.connect(self.quick_window._update_list)
        app_signals.data_changed.connect(self.quick_window._update_partition_tree)

        # 注册全局热键 Alt+Space
        try:
            keyboard.add_hotkey('alt+space', self._on_hotkey_triggered, suppress=False)
            logging.info("Global hotkey Alt+Space registered successfully")
        except Exception as e:
            logging.error(f"Failed to register hotkey Alt+Space: {e}", exc_info=True)

        self.show_quick_window()

    def _on_hotkey_triggered(self):
        self.hotkey_signal.activated.emit()

    def _init_tray_icon(self):
        temp_ball = FloatingBall(None)
        temp_ball.timer.stop()
        temp_ball.is_writing = False
        temp_ball.pen_angle = -45
        temp_ball.pen_x = 0; temp_ball.pen_y = 0; temp_ball.book_y = 0
        pixmap = QPixmap(temp_ball.size()); pixmap.fill(Qt.transparent); temp_ball.render(pixmap)
        dynamic_icon = QIcon(pixmap)
        
        self.app.setWindowIcon(dynamic_icon)
        if self.main_window:
            self.main_window.refresh_logo()
        self.tray_icon = QSystemTrayIcon(self.app)
        self.tray_icon.setIcon(dynamic_icon)
        self.tray_icon.setToolTip("快速笔记")
        
        menu = QMenu()
        menu.setStyleSheet("QMenu { background-color: #2D2D2D; color: #EEE; border: 1px solid #444; } QMenu::item { padding: 6px 24px; } QMenu::item:selected { background-color: #4a90e2; color: white; }")
        
        action_show = menu.addAction("显示主界面"); action_show.triggered.connect(self.show_main_window)
        action_quick = menu.addAction("显示快速笔记"); action_quick.triggered.connect(self.show_quick_window)
        menu.addSeparator()
        action_quit = menu.addAction("退出程序"); action_quit.triggered.connect(self.quit_application)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_icon_activated)
        self.tray_icon.show()

    def _on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger: self.show_quick_window()

    def _open_common_tags_manager(self):
        if self.tags_manager_dialog and self.tags_manager_dialog.isVisible():
            self._force_activate(self.tags_manager_dialog); return
        self.tags_manager_dialog = CommonTagsManager()
        self.tags_manager_dialog.finished.connect(self._on_tags_manager_closed)
        self.tags_manager_dialog.show(); self._force_activate(self.tags_manager_dialog)

    def _on_tags_manager_closed(self, result):
        if result == QDialog.Accepted and self.popup: self.popup.common_tags_bar.reload_tags()
        self.tags_manager_dialog = None

    def _on_clipboard_data_captured(self, idea_id):
        self.ball.trigger_clipboard_feedback()
        if self.popup: self.popup.show_at_mouse(idea_id)

    def _handle_popup_favorite(self, idea_id):
        idea_data = self.service.get_idea(idea_id)
        if not idea_data: return
        is_favorite = idea_data['is_favorite'] == 1
        self.service.set_favorite(idea_id, not is_favorite)

    def _handle_popup_tag_toggle(self, idea_id, tag_name):
        current_tags = self.service.get_tags(idea_id)
        if tag_name in current_tags: self.service.remove_tag_from_multiple_ideas([idea_id], tag_name)
        else: self.service.add_tags_to_multiple_ideas([idea_id], [tag_name])

    def _force_activate(self, window):
        if not window: return
        window.show()
        if window.isMinimized(): window.setWindowState(window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        window.showNormal(); window.raise_(); window.activateWindow()

    def show_quick_window(self): self._force_activate(self.quick_window)
    def toggle_quick_window(self):
        if self.quick_window and self.quick_window.isVisible(): self.quick_window.hide()
        else: self.show_quick_window()
    def show_main_window(self): self._force_activate(self.main_window)
    def toggle_main_window(self):
        if self.main_window.isVisible() and not self.main_window.isMinimized(): self.main_window.hide()
        else: self.show_main_window()
    def on_main_window_closing(self):
        if self.main_window: self.main_window.hide()
    def quit_application(self):
        logging.info("Application quit requested")
        try:
            keyboard.unhook_all()
            logging.debug("Keyboard hooks removed")
        except Exception as e:
            logging.error(f"Failed to unhook keyboard: {e}", exc_info=True)
        
        if self.quick_window:
            try:
                self.quick_window.save_state()
                logging.debug("Quick window state saved")
            except Exception as e:
                logging.error(f"Failed to save quick window state: {e}", exc_info=True)
        
        if self.main_window:
            try:
                self.main_window.save_state()
                logging.debug("Main window state saved")
            except Exception as e:
                logging.error(f"Failed to save main window state: {e}", exc_info=True)
        
        self.app.quit()

def main():
    app = QApplication(sys.argv)
    socket = QLocalSocket(); socket.connectToServer(SERVER_NAME)
    if socket.waitForConnected(500):
        socket.write(b'EXIT'); socket.flush(); socket.waitForBytesWritten(1000)
        socket.disconnectFromServer(); time.sleep(0.5)
    QLocalServer.removeServer(SERVER_NAME)
    server = QLocalServer(); server.listen(SERVER_NAME)
    
    manager = AppManager(app)
    
    def handle_new_connection():
        conn = server.nextPendingConnection()
        if conn and conn.waitForReadyRead(500):
            msg = conn.readAll().data().decode()
            if msg == 'SHOW': manager.show_quick_window()
            elif msg == 'EXIT': manager.quit_application()
    server.newConnection.connect(handle_new_connection)
    
    manager.start()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
```

## 文件: core\config.py

```python
# core/config.py
DB_NAME = 'ideas.db'
BACKUP_DIR = 'backups'

COLORS = {
    'primary': '#4a90e2',   # 核心蓝
    'success': '#2ecc71',   # 成功绿
    'warning': '#f39c12',   # 警告黄
    'danger':  '#e74c3c',   # 危险红
    'info':    '#9b59b6',   # 信息紫
    'teal':    '#1abc9c',   # 青色
    'orange':  '#FF8C00',   # 深橙色
    'default_note': '#2d2d2d', 
    'trash': '#2d2d2d',
    'uncategorized': '#0A362F',
    'bg_dark': '#1e1e1e',   # 窗口背景
    'bg_mid':  '#252526',   # 侧边栏/输入框背景
    'bg_light': '#333333',  # 边框/分割线
    'text':    '#cccccc',   # 主文本
    'text_sub': '#858585'   # 副文本
}

# --- 全局通用样式组件 ---

# 1. 现代滚动条 (极简、无箭头按钮)
GLOBAL_SCROLLBAR = f"""
    QScrollBar:vertical {{
        border: none;
        background: transparent;
        width: 8px;
        margin: 0px; 
    }}
    QScrollBar::handle:vertical {{
        background: #444;
        min-height: 30px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #555; }}
    QScrollBar::handle:vertical:pressed {{ background: {COLORS['primary']}; }}
    
    /* 隐藏上下箭头按钮 */
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
        subcontrol-position: top;
        subcontrol-origin: margin;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

    QScrollBar:horizontal {{
        border: none;
        background: transparent;
        height: 8px;
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background: #444;
        min-width: 30px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: #555; }}
    QScrollBar::handle:horizontal:pressed {{ background: {COLORS['primary']}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
"""

# 2. 现代 Tooltip
MODERN_TOOLTIP = f"""
    QToolTip {{
        color: #ffffff;
        background-color: #2D2D2D;
        border: 1px solid #444;
        border-radius: 4px;
        padding: 4px;
        font-family: "Microsoft YaHei";
        font-size: 12px;
    }}
"""

STYLES = {
    'main_window': f"""
        QWidget {{ background-color: {COLORS['bg_dark']}; color: {COLORS['text']}; font-family: "Microsoft YaHei", "Segoe UI", sans-serif; }}
        QSplitter::handle {{ background-color: {COLORS['bg_light']}; }}
        {GLOBAL_SCROLLBAR}
        {MODERN_TOOLTIP}
    """,
    
    'sidebar': f"""
        QTreeWidget {{
            background-color: {COLORS['bg_mid']};
            color: #ddd;
            border: none;
            font-size: 13px;
            padding: 8px;
            outline: none;
        }}
        QTreeWidget::item {{
            height: 30px;
            padding: 2px 4px;
            border-radius: 4px;
            margin-bottom: 2px;
        }}
        QTreeWidget::item:hover {{ background-color: #2a2d2e; }}
        QTreeWidget::item:selected {{ background-color: #37373d; color: white; }}
        {GLOBAL_SCROLLBAR}
    """,
    
    'dialog': f"""
        QDialog {{ background-color: {COLORS['bg_dark']}; color: {COLORS['text']}; }}
        QLabel {{ color: {COLORS['text_sub']}; font-size: 12px; font-weight: bold; margin-bottom: 4px; }}
        QLineEdit, QTextEdit, QComboBox {{
            background-color: {COLORS['bg_mid']};
            border: 1px solid #333;
            border-radius: 4px;
            padding: 8px;
            color: #eee;
            font-size: 13px;
            selection-background-color: {COLORS['primary']};
        }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
            border: 1px solid {COLORS['primary']};
            background-color: #2a2a2a;
        }}
        {GLOBAL_SCROLLBAR}
        {MODERN_TOOLTIP}
    """,
    
    'btn_primary': f"""
        QPushButton {{
            background-color: {COLORS['primary']};
            border: none;
            color: white;
            padding: 0px 16px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 13px;
        }}
        QPushButton:hover {{ background-color: #357abd; }}
        QPushButton:pressed {{ background-color: #2a5d8f; }}
    """,

    'btn_icon': f"""
        QPushButton {{
            background-color: {COLORS['bg_light']};
            border: 1px solid #444;
            border-radius: 6px;
            min-width: 32px;
            min-height: 32px;
        }}
        QPushButton:hover {{ background-color: {COLORS['primary']}; border-color: {COLORS['primary']}; }}
        QPushButton:pressed {{ background-color: #2a5d8f; }}
        QPushButton:disabled {{ background-color: #252526; color: #555; border-color: #333; }}
    """,
    
    'input': f"""
        QLineEdit {{
            background-color: {COLORS['bg_mid']};
            border: 1px solid {COLORS['bg_light']};
            border-radius: 16px;
            padding: 6px 12px;
            color: #eee;
            font-size: 13px;
        }}
        QLineEdit:focus {{ border: 1px solid {COLORS['primary']}; }}
    """,
    
    'card_base': "border-radius: 12px;"
}
```

## 文件: core\container.py

```python
# -*- coding: utf-8 -*-
# core/container.py
from data.db_context import DBContext
from data.repositories.idea_repository import IdeaRepository
from data.repositories.category_repository import CategoryRepository
from data.repositories.tag_repository import TagRepository
from services.idea_service import IdeaService

class AppContainer:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppContainer, cls).__new__(cls)
            cls._instance._init_components()
        return cls._instance

    def _init_components(self):
        self.db_context = DBContext()
        
        self.idea_repo = IdeaRepository(self.db_context)
        self.category_repo = CategoryRepository(self.db_context)
        self.tag_repo = TagRepository(self.db_context)

        self.idea_service = IdeaService(self.idea_repo, self.category_repo, self.tag_repo)

    @property
    def service(self):
        return self.idea_service
```

## 文件: core\enums.py

```python
# core/enums.py
from enum import Enum

class FilterType(Enum):
    ALL = "all"
    TODAY = "today"
    CATEGORY = "category"
    CLIPBOARD = "clipboard"
    UNCATEGORIZED = "uncategorized"
    UNTAGGED = "untagged"
    FAVORITE = "favorite"
    TRASH = "trash"
```

## 文件: core\logger.py

```python

import logging
import sys
from logging.handlers import RotatingFileHandler

def setup_logging():
    logger = logging.getLogger('RapidNotes')
    logger.setLevel(logging.DEBUG)

    # Prevent adding handlers multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )

    # Console Handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    # File Handler
    file_handler = RotatingFileHandler(
        'app_run.log', maxBytes=1024 * 1024 * 5, backupCount=5, encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info("日志服务初始化成功。")

def get_logger(name):
    return logging.getLogger(name)

```

## 文件: core\settings.py

```python
# core/settings.py
import json
import os

SETTINGS_FILE = 'settings.json'

def save_setting(key, value):
    """保存单个设置项到 JSON 文件"""
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except (json.JSONDecodeError, IOError):
            # 如果文件存在但为空或损坏，则忽略
            pass
    
    settings[key] = value
    
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
        # print(f"[Settings] 已保存 '{key}': {value}")
        pass
    except IOError as e:
        # print(f"[Settings] 错误：无法写入设置文件 {SETTINGS_FILE}: {e}")
        pass

def load_setting(key, default=None):
    """从 JSON 文件加载单个设置项"""
    if not os.path.exists(SETTINGS_FILE):
        return default
        
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            value = settings.get(key, default)
            # print(f"[Settings] 已加载 '{key}': {value}")
            pass
            return value
    except (json.JSONDecodeError, IOError) as e:
        # print(f"[Settings] 错误：无法读取设置文件 {SETTINGS_FILE}: {e}")
        pass
        return default
```

## 文件: core\shared.py

```python
# -*- coding: utf-8 -*-
# core/shared.py
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtCore import Qt

_ICON_CACHE = {}

def get_color_icon(color_str):
    """
    根据颜色字符串生成一个QIcon。
    为了提高性能，相同颜色的图标会被缓存。
    """
    if not color_str:
        color_str = "#808080"
        
    if color_str in _ICON_CACHE:
        return _ICON_CACHE[color_str]

    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    color = QColor(color_str)
    painter.setBrush(color)
    painter.setPen(Qt.NoPen)
    
    # 在16x16的画布上绘制一个12x12的圆角矩形
    painter.drawRoundedRect(2, 2, 12, 12, 4, 4)
    painter.end()
    
    icon = QIcon(pixmap)
    _ICON_CACHE[color_str] = icon
    return icon
```

## 文件: core\signals.py

```python
# core/signals.py
from PyQt5.QtCore import QObject, pyqtSignal

class AppSignals(QObject):
    # 定义一个名为 data_changed 的信号，无参数
    data_changed = pyqtSignal()

# 创建一个全局单例，方便在应用各处统一调用
app_signals = AppSignals()
```

## 文件: core\__init__.py

```python
﻿# -*- coding: utf-8 -*-

```

## 文件: data\db_context.py

```python
# -*- coding: utf-8 -*-
# data/db_context.py
import sqlite3
import logging
from core.config import DB_NAME, COLORS

class DBContext:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        self._fix_trash_consistency()

    def get_cursor(self):
        return self.conn.cursor()

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    def _init_schema(self):
        c = self.conn.cursor()
        
        c.execute(f'''CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, content TEXT, color TEXT DEFAULT '{COLORS['default_note']}',
            is_pinned INTEGER DEFAULT 0, is_favorite INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            category_id INTEGER, is_deleted INTEGER DEFAULT 0,
            item_type TEXT DEFAULT 'text', data_blob BLOB,
            content_hash TEXT, is_locked INTEGER DEFAULT 0, rating INTEGER DEFAULT 0
        )''')
        c.execute('CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)')
        c.execute('''CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT NOT NULL, parent_id INTEGER, 
            color TEXT DEFAULT "#808080", sort_order INTEGER DEFAULT 0, preset_tags TEXT
        )''')
        c.execute('CREATE TABLE IF NOT EXISTS idea_tags (idea_id INTEGER, tag_id INTEGER, PRIMARY KEY (idea_id, tag_id))')
        
        # 补全可能缺失的列
        c.execute("PRAGMA table_info(ideas)")
        cols = [i[1] for i in c.fetchall()]
        updates = [
            ('category_id', 'INTEGER'), ('is_deleted', 'INTEGER DEFAULT 0'),
            ('item_type', "TEXT DEFAULT 'text'"), ('data_blob', 'BLOB'),
            ('content_hash', 'TEXT'), ('is_locked', 'INTEGER DEFAULT 0'),
            ('rating', 'INTEGER DEFAULT 0')
        ]
        for col, type_def in updates:
            if col not in cols:
                try:
                    c.execute(f'ALTER TABLE ideas ADD COLUMN {col} {type_def}')
                    logging.info(f"Added column {col} to ideas table")
                except Exception as e:
                    logging.warning(f"Failed to add column {col} (may already exist): {e}")
        
        if 'content_hash' not in cols:
            try:
                c.execute('CREATE INDEX IF NOT EXISTS idx_content_hash ON ideas(content_hash)')
                logging.info("Created index on content_hash")
            except Exception as e:
                logging.warning(f"Failed to create content_hash index: {e}")
            
        c.execute("PRAGMA table_info(categories)")
        cat_cols = [i[1] for i in c.fetchall()]
        if 'sort_order' not in cat_cols:
            try:
                c.execute('ALTER TABLE categories ADD COLUMN sort_order INTEGER DEFAULT 0')
                logging.info("Added sort_order column to categories table")
            except Exception as e:
                logging.warning(f"Failed to add sort_order column: {e}")
        if 'preset_tags' not in cat_cols:
            try:
                c.execute('ALTER TABLE categories ADD COLUMN preset_tags TEXT')
                logging.info("Added preset_tags column to categories table")
            except Exception as e:
                logging.warning(f"Failed to add preset_tags column: {e}")

        self.conn.commit()

    def _fix_trash_consistency(self):
        try:
            c = self.conn.cursor()
            trash_color = COLORS.get('trash', '#2d2d2d')
            c.execute('UPDATE ideas SET category_id = NULL, color = ? WHERE is_deleted = 1', (trash_color,))
            self.conn.commit()
            logging.debug("Trash consistency check completed")
        except Exception as e:
            logging.error(f"Failed to fix trash consistency: {e}", exc_info=True)
```

## 文件: data\db_manager.py

```python
# -*- coding: utf-8 -*-
# data/db_manager.py
import sqlite3
import hashlib
import os
import random
from core.config import DB_NAME, COLORS

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME)
        self.conn.row_factory = sqlite3.Row
        self.fts5_supported = True  # Assume FTS5 is supported by default
        self._init_schema()
        # 【维护】启动时仅修正回收站数据的格式
        self._fix_trash_consistency()

    def _init_schema(self):
        c = self.conn.cursor()
        
        c.execute(f'''CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, content TEXT, color TEXT DEFAULT '{COLORS['default_note']}',
            is_pinned INTEGER DEFAULT 0, is_favorite INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            category_id INTEGER, is_deleted INTEGER DEFAULT 0
        )''')
        c.execute('CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)')
        c.execute('''CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT NOT NULL, 
            parent_id INTEGER, 
            color TEXT DEFAULT "#808080",
            sort_order INTEGER DEFAULT 0
        )''')
        c.execute('CREATE TABLE IF NOT EXISTS idea_tags (idea_id INTEGER, tag_id INTEGER, PRIMARY KEY (idea_id, tag_id))')
        
        # 检查并补充字段
        c.execute("PRAGMA table_info(ideas)")
        cols = [i[1] for i in c.fetchall()]
        
        updates = [
            ('category_id', 'INTEGER'),
            ('is_deleted', 'INTEGER DEFAULT 0'),
            ('item_type', "TEXT DEFAULT 'text'"),
            ('data_blob', 'BLOB'),
            ('content_hash', 'TEXT'),
            ('is_locked', 'INTEGER DEFAULT 0'),
            ('rating', 'INTEGER DEFAULT 0')
        ]
        
        for col, type_def in updates:
            if col not in cols:
                try: c.execute(f'ALTER TABLE ideas ADD COLUMN {col} {type_def}')
                except: pass
        
        if 'content_hash' not in cols:
            try: c.execute('CREATE INDEX IF NOT EXISTS idx_content_hash ON ideas(content_hash)')
            except: pass
        
        c.execute("PRAGMA table_info(categories)")
        cat_cols = [i[1] for i in c.fetchall()]
        if 'sort_order' not in cat_cols:
            try: c.execute('ALTER TABLE categories ADD COLUMN sort_order INTEGER DEFAULT 0')
            except: pass
        if 'preset_tags' not in cat_cols:
            try: c.execute('ALTER TABLE categories ADD COLUMN preset_tags TEXT')
            except: pass
        
        # --- FTS5 Setup ---
        try:
            # Check for FTS5 support
            c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts_test USING fts5(a)")
            c.execute("DROP TABLE fts_test")

            c.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS ideas_fts USING fts5(
                    title, 
                    content, 
                    content='ideas', 
                    content_rowid='id'
                )
            """)
            
            c.execute("""
                CREATE TRIGGER IF NOT EXISTS ideas_after_insert AFTER INSERT ON ideas BEGIN
                    INSERT INTO ideas_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
                END;
            """)
            c.execute("""
                CREATE TRIGGER IF NOT EXISTS ideas_after_delete AFTER DELETE ON ideas BEGIN
                    INSERT INTO ideas_fts(ideas_fts, rowid, title, content) VALUES ('delete', old.id, old.title, old.content);
                END;
            """)
            c.execute("""
                CREATE TRIGGER IF NOT EXISTS ideas_after_update AFTER UPDATE ON ideas BEGIN
                    INSERT INTO ideas_fts(ideas_fts, rowid, title, content) VALUES ('delete', old.id, old.title, old.content);
                    INSERT INTO ideas_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
                END;
            """)
        except sqlite3.OperationalError as e:
            # If FTS5 is not supported, disable it for this session
            if 'no such module' in str(e).lower() or 'fts5' in str(e).lower():
                self.fts5_supported = False
                self.conn.rollback()  # Roll back any partial FTS setup
            else:
                raise  # Re-raise other operational errors

        self.conn.commit()

    def _fix_trash_consistency(self):
        try:
            c = self.conn.cursor()
            trash_color = COLORS.get('trash', '#2d2d2d')
            c.execute('''
                UPDATE ideas 
                SET category_id = NULL, color = ? 
                WHERE is_deleted = 1 AND (category_id IS NOT NULL OR color != ?)
            ''', (trash_color, trash_color))
            self.conn.commit()
        except Exception as e:
            pass

    def empty_trash(self):
        c = self.conn.cursor()
        c.execute('DELETE FROM idea_tags WHERE idea_id IN (SELECT id FROM ideas WHERE is_deleted=1)')
        c.execute('DELETE FROM ideas WHERE is_deleted=1')
        self.conn.commit()

    def set_locked(self, idea_ids, state):
        if not idea_ids: return
        c = self.conn.cursor()
        val = 1 if state else 0
        placeholders = ','.join('?' * len(idea_ids))
        c.execute(f'UPDATE ideas SET is_locked=? WHERE id IN ({placeholders})', (val, *idea_ids))
        self.conn.commit()

    def get_lock_status(self, idea_ids):
        if not idea_ids: return {}
        c = self.conn.cursor()
        placeholders = ','.join('?' * len(idea_ids))
        c.execute(f'SELECT id, is_locked FROM ideas WHERE id IN ({placeholders})', tuple(idea_ids))
        return dict(c.fetchall())

    def add_idea(self, title, content, color=None, tags=[], category_id=None, item_type='text', data_blob=None):
        if color is None: color = COLORS['default_note']
        c = self.conn.cursor()
        c.execute(
            'INSERT INTO ideas (title, content, color, category_id, item_type, data_blob) VALUES (?,?,?,?,?,?)',
            (title, content, color, category_id, item_type, data_blob)
        )
        iid = c.lastrowid
        self._update_tags(iid, tags)
        self.conn.commit()
        return iid

    def update_idea(self, iid, title, content, color, tags, category_id=None, item_type='text', data_blob=None):
        c = self.conn.cursor()
        c.execute(
            'UPDATE ideas SET title=?, content=?, color=?, category_id=?, item_type=?, data_blob=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (title, content, color, category_id, item_type, data_blob, iid)
        )
        self._update_tags(iid, tags)
        self.conn.commit()

    def update_field(self, iid, field, value):
        c = self.conn.cursor()
        c.execute(f'UPDATE ideas SET {field} = ? WHERE id = ?', (value, iid))
        self.conn.commit()

    def _update_tags(self, iid, tags):
        c = self.conn.cursor()
        c.execute('DELETE FROM idea_tags WHERE idea_id=?', (iid,))
        if not tags: return
        for t in tags:
            t = t.strip()
            if t:
                c.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (t,))
                c.execute('SELECT id FROM tags WHERE name=?', (t,))
                tid = c.fetchone()[0]
                c.execute('INSERT INTO idea_tags VALUES (?,?)', (iid, tid))

    def _append_tags(self, iid, tags):
        c = self.conn.cursor()
        for t in tags:
            t = t.strip()
            if t:
                c.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (t,))
                c.execute('SELECT id FROM tags WHERE name=?', (t,))
                tid = c.fetchone()[0]
                c.execute('INSERT OR IGNORE INTO idea_tags VALUES (?,?)', (iid, tid))

    def add_tags_to_multiple_ideas(self, idea_ids, tags_list):
        if not idea_ids or not tags_list: return
        c = self.conn.cursor()
        for tag_name in tags_list:
            tag_name = tag_name.strip()
            if not tag_name: continue
            c.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (tag_name,))
            c.execute('SELECT id FROM tags WHERE name=?', (tag_name,))
            tid = c.fetchone()[0]
            for iid in idea_ids:
                c.execute('INSERT OR IGNORE INTO idea_tags (idea_id, tag_id) VALUES (?,?)', (iid, tid))
        self.conn.commit()

    def remove_tag_from_multiple_ideas(self, idea_ids, tag_name):
        if not idea_ids or not tag_name: return
        c = self.conn.cursor()
        c.execute('SELECT id FROM tags WHERE name=?', (tag_name,))
        res = c.fetchone()
        if not res: return
        tid = res[0]
        placeholders = ','.join('?' * len(idea_ids))
        sql = f'DELETE FROM idea_tags WHERE tag_id=? AND idea_id IN ({placeholders})'
        c.execute(sql, (tid, *idea_ids))
        self.conn.commit()

    def get_union_tags(self, idea_ids):
        if not idea_ids: return []
        c = self.conn.cursor()
        placeholders = ','.join('?' * len(idea_ids))
        sql = f'''
            SELECT DISTINCT t.name 
            FROM tags t 
            JOIN idea_tags it ON t.id = it.tag_id 
            WHERE it.idea_id IN ({placeholders})
            ORDER BY t.name ASC
        '''
        c.execute(sql, tuple(idea_ids))
        return [r[0] for r in c.fetchall()]

    def add_clipboard_item(self, item_type, content, data_blob=None, category_id=None):
        c = self.conn.cursor()
        c = self.conn.cursor()
        hasher = hashlib.sha256()
        
        # 【逻辑修正】除去明确的image类型外，其他所有类型(text, pdf, folder...)都按内容字符hash
        if item_type == 'image' and data_blob:
            hasher.update(data_blob)
        else:
            hasher.update(content.encode('utf-8'))
            
        content_hash = hasher.hexdigest()

        c.execute("SELECT id FROM ideas WHERE content_hash = ?", (content_hash,))
        existing_idea = c.fetchone()

        if existing_idea:
            idea_id = existing_idea[0]
            c.execute("UPDATE ideas SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (idea_id,))
            self.conn.commit()
            return idea_id, False 
        else:
            # 【逻辑修正】标题生成逻辑
            if item_type == 'text':
                title = content.strip().split('\n')[0][:50]
            elif item_type == 'image':
                title = "[图片]"
            else:
                # 其他所有类型（file, pdf, folder...）均视为文件类，显示文件名
                # 尝试从内容中获取第一个文件名
                try:
                    first_file = content.split(';')[0]
                    fname = os.path.basename(first_file)
                    title = f"[{item_type}] {fname}"
                except:
                    title = f"[{item_type}]"

            default_color = COLORS['default_note']
            c.execute(
                'INSERT INTO ideas (title, content, item_type, data_blob, category_id, content_hash, color) VALUES (?,?,?,?,?,?,?)',
                (title, content, item_type, data_blob, category_id, content_hash, default_color)
            )
            idea_id = c.lastrowid
            
            self.conn.commit()
            return idea_id, True

    def toggle_field(self, iid, field):
        c = self.conn.cursor()
        c.execute(f'UPDATE ideas SET {field} = NOT {field} WHERE id=?', (iid,))
        self.conn.commit()

    def set_deleted(self, iid, state):
        c = self.conn.cursor()
        if state:
            trash_color = COLORS.get('trash', '#2d2d2d')
            c.execute(
                'UPDATE ideas SET is_deleted=1, category_id=NULL, color=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', 
                (trash_color, iid)
            )
        else:
            uncat_color = COLORS.get('uncategorized', '#0A362F')
            c.execute(
                'UPDATE ideas SET is_deleted=0, category_id=NULL, color=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', 
                (uncat_color, iid)
            )
        self.conn.commit()

    def set_favorite(self, iid, state):
        c = self.conn.cursor()
        c.execute('UPDATE ideas SET is_favorite=? WHERE id=?', (1 if state else 0, iid))
        
        if state:
            bookmark_color = '#ff6b81'
            c.execute('UPDATE ideas SET color=? WHERE id=?', (bookmark_color, iid))
        else:
            c.execute('SELECT category_id FROM ideas WHERE id=?', (iid,))
            res = c.fetchone()
            if res and res[0] is not None:
                cat_id = res[0]
                c.execute('SELECT color FROM categories WHERE id=?', (cat_id,))
                cat_res = c.fetchone()
                if cat_res:
                    c.execute('UPDATE ideas SET color=? WHERE id=?', (cat_res[0], iid))
            else:
                uncat_color = COLORS.get('uncategorized', '#0A362F')
                c.execute('UPDATE ideas SET color=? WHERE id=?', (uncat_color, iid))

        self.conn.commit()

    def set_rating(self, idea_id, rating):
        c = self.conn.cursor()
        rating = max(0, min(5, int(rating)))
        c.execute('UPDATE ideas SET rating=? WHERE id=?', (rating, idea_id))
        self.conn.commit()

    def move_category(self, iid, cat_id):
        c = self.conn.cursor()
        c.execute('UPDATE ideas SET category_id=?, is_deleted=0 WHERE id=?', (cat_id, iid))
        if cat_id is not None:
            c.execute('SELECT color, preset_tags FROM categories WHERE id=?', (cat_id,))
            result = c.fetchone()
            if result:
                cat_color = result[0]
                preset_tags_str = result[1]
                if cat_color:
                    c.execute('UPDATE ideas SET color=? WHERE id=?', (cat_color, iid))
                if preset_tags_str:
                    tags_list = [t.strip() for t in preset_tags_str.split(',') if t.strip()]
                    if tags_list:
                        self._append_tags(iid, tags_list)
        else:
            uncat_color = COLORS.get('uncategorized', '#0A362F')
            c.execute('UPDATE ideas SET color=? WHERE id=?', (uncat_color, iid))
        self.conn.commit()

    def delete_permanent(self, iid):
        c = self.conn.cursor()
        c.execute('DELETE FROM ideas WHERE id=?', (iid,))
        self.conn.commit()

    def get_idea(self, iid, include_blob=False):
        c = self.conn.cursor()
        if include_blob:
            c.execute('''
                SELECT id, title, content, color, is_pinned, is_favorite, 
                       created_at, updated_at, category_id, is_deleted, item_type, 
                       data_blob, content_hash, is_locked, rating
                FROM ideas WHERE id=?
            ''', (iid,))
        else:
            c.execute('''
                SELECT id, title, content, color, is_pinned, is_favorite, 
                       created_at, updated_at, category_id, is_deleted, item_type, 
                       NULL as data_blob, NULL as content_hash, is_locked, rating
                FROM ideas WHERE id=?
            ''', (iid,))
        return c.fetchone()

    # === 核心修改：get_filter_stats 支持上下文 ===
    def _get_all_child_categories(self, cat_id):
        """递归获取所有子分类ID"""
        ids = [cat_id]
        c = self.conn.cursor()
        c.execute("SELECT id FROM categories WHERE parent_id = ?", (cat_id,))
        children = c.fetchall()
        for child_row in children:
            ids.extend(self._get_all_child_categories(child_row[0]))
        return ids

    def get_filter_stats(self, search_text='', filter_type='all', filter_value=None):
        """
        获取当前视图范围内的各项统计，用于填充筛选器
        支持根据搜索文本和过滤类型进行上下文相关统计
        """
        c = self.conn.cursor()
        stats = {
            'stars': {},
            'colors': {},
            'types': {},
            'tags': [],
            'date_create': {}
        }
        
        # 1. 构建基础 WHERE 子句
        where_clauses = ["1=1"]
        params = []
        
        if filter_type == 'trash':
            where_clauses.append("i.is_deleted=1")
        else:
            where_clauses.append("(i.is_deleted=0 OR i.is_deleted IS NULL)")
            
        if filter_type == 'category':
            if filter_value is None:
                where_clauses.append("i.category_id IS NULL")
            else:
                # 递归包含子分类
                cat_ids = self._get_all_child_categories(filter_value)
                placeholders = ','.join('?' * len(cat_ids))
                where_clauses.append(f"i.category_id IN ({placeholders})")
                params.extend(cat_ids)
        elif filter_type == 'today':
            where_clauses.append("date(i.updated_at,'localtime')=date('now','localtime')")
        elif filter_type == 'untagged':
            where_clauses.append("i.id NOT IN (SELECT idea_id FROM idea_tags)")
        elif filter_type == 'bookmark':
            where_clauses.append("i.is_favorite=1")
        
        # 添加搜索文本过滤
        if search_text:
            where_clauses.append("(i.title LIKE ? OR i.content LIKE ?)")
            params.extend([f'%{search_text}%', f'%{search_text}%'])
            
        where_str = " AND ".join(where_clauses)
        
        # 2. 执行统计查询
        
        # 2.1 星级统计
        c.execute(f"SELECT i.rating, COUNT(*) FROM ideas i WHERE {where_str} GROUP BY i.rating", params)
        stats['stars'] = dict(c.fetchall())

        # 2.2 颜色统计
        c.execute(f"SELECT i.color, COUNT(*) FROM ideas i WHERE {where_str} GROUP BY i.color", params)
        stats['colors'] = dict(c.fetchall())

        # 2.3 类型统计
        c.execute(f"SELECT i.item_type, COUNT(*) FROM ideas i WHERE {where_str} GROUP BY i.item_type", params)
        stats['types'] = dict(c.fetchall())

        # 2.4 标签统计 (需要关联)
        tag_sql = f"""
            SELECT t.name, COUNT(it.idea_id) as cnt
            FROM tags t
            JOIN idea_tags it ON t.id = it.tag_id
            JOIN ideas i ON it.idea_id = i.id
            WHERE {where_str}
            GROUP BY t.id
            ORDER BY cnt DESC
        """
        c.execute(tag_sql, params)
        stats['tags'] = c.fetchall()

        # 2.5 日期统计 (创建时间)
        base_date_sql = f"SELECT COUNT(*) FROM ideas i WHERE {where_str} AND "
        
        c.execute(base_date_sql + "date(i.created_at, 'localtime') = date('now', 'localtime')", params)
        stats['date_create']['today'] = c.fetchone()[0]
        
        c.execute(base_date_sql + "date(i.created_at, 'localtime') = date('now', '-1 day', 'localtime')", params)
        stats['date_create']['yesterday'] = c.fetchone()[0]
        
        c.execute(base_date_sql + "date(i.created_at, 'localtime') >= date('now', '-6 days', 'localtime')", params)
        stats['date_create']['week'] = c.fetchone()[0]
        
        c.execute(base_date_sql + "strftime('%Y-%m', i.created_at, 'localtime') = strftime('%Y-%m', 'now', 'localtime')", params)
        stats['date_create']['month'] = c.fetchone()[0]

        return stats

    def get_ideas(self, search, f_type, f_val, page=None, page_size=20, tag_filter=None, filter_criteria=None):
        c = self.conn.cursor()
        
        q = """
            SELECT DISTINCT 
                i.id, i.title, i.content, i.color, i.is_pinned, i.is_favorite, 
                i.created_at, i.updated_at, i.category_id, i.is_deleted, 
                i.item_type, i.data_blob, i.content_hash, i.is_locked, i.rating
            FROM ideas i 
            LEFT JOIN idea_tags it ON i.id=it.idea_id 
            LEFT JOIN tags t ON it.tag_id=t.id 
            WHERE 1=1
        """
        p = []
        
        if f_type == 'trash': q += ' AND i.is_deleted=1'
        else: q += ' AND (i.is_deleted=0 OR i.is_deleted IS NULL)'
        
        if f_type == 'category':
            if f_val is None: 
                q += ' AND i.category_id IS NULL'
            else: 
                # 递归包含子分类
                cat_ids = self._get_all_child_categories(f_val)
                placeholders = ','.join('?' * len(cat_ids))
                q += f" AND i.category_id IN ({placeholders})"
                p.extend(cat_ids)
        elif f_type == 'today': q += " AND date(i.updated_at,'localtime')=date('now','localtime')"
        elif f_type == 'untagged': q += ' AND i.id NOT IN (SELECT idea_id FROM idea_tags)'
        elif f_type == 'bookmark': q += ' AND i.is_favorite=1'
        
        if search:
            if self.fts5_supported:
                # FTS5 search for title/content OR regular search for tag name
                q += " AND (i.id IN (SELECT rowid FROM ideas_fts WHERE ideas_fts MATCH ?) OR t.name LIKE ?)"
                p.append(search)
                p.append(f'%{search}%')
            else:
                # Fallback to LIKE search if FTS5 is not available
                q += ' AND (i.title LIKE ? OR i.content LIKE ? OR t.name LIKE ?)'
                p.extend([f'%{search}%'] * 3)

        if tag_filter:
            q += " AND i.id IN (SELECT idea_id FROM idea_tags WHERE tag_id = (SELECT id FROM tags WHERE name = ?))"
            p.append(tag_filter)

        if filter_criteria:
            if 'stars' in filter_criteria:
                stars = filter_criteria['stars']
                placeholders = ','.join('?' * len(stars))
                q += f" AND i.rating IN ({placeholders})"
                p.extend(stars)
            
            if 'colors' in filter_criteria:
                colors = filter_criteria['colors']
                placeholders = ','.join('?' * len(colors))
                q += f" AND i.color IN ({placeholders})"
                p.extend(colors)

            if 'types' in filter_criteria:
                types = filter_criteria['types']
                placeholders = ','.join('?' * len(types))
                q += f" AND i.item_type IN ({placeholders})"
                p.extend(types)

            if 'tags' in filter_criteria:
                tags = filter_criteria['tags']
                tag_placeholders = ','.join('?' * len(tags))
                q += f" AND i.id IN (SELECT idea_id FROM idea_tags JOIN tags ON idea_tags.tag_id = tags.id WHERE tags.name IN ({tag_placeholders}))"
                p.extend(tags)

            if 'date_create' in filter_criteria:
                date_conditions = []
                for d_opt in filter_criteria['date_create']:
                    if d_opt == 'today':
                        date_conditions.append("date(i.created_at,'localtime')=date('now','localtime')")
                    elif d_opt == 'yesterday':
                        date_conditions.append("date(i.created_at,'localtime')=date('now','-1 day','localtime')")
                    elif d_opt == 'week':
                        date_conditions.append("date(i.created_at,'localtime')>=date('now','-6 days','localtime')")
                    elif d_opt == 'month':
                        date_conditions.append("strftime('%Y-%m',i.created_at,'localtime')=strftime('%Y-%m','now','localtime')")
                
                if date_conditions:
                    q += " AND (" + " OR ".join(date_conditions) + ")"

        if f_type == 'trash':
            q += ' ORDER BY i.updated_at DESC'
        else:
            q += ' ORDER BY i.is_pinned DESC, i.updated_at DESC'
            
        if page is not None and page_size is not None:
            limit = page_size
            offset = (page - 1) * page_size
            q += ' LIMIT ? OFFSET ?'
            p.extend([limit, offset])
            
        c.execute(q, p)
        return c.fetchall()

    def get_ideas_count(self, search, f_type, f_val, tag_filter=None, filter_criteria=None):
        c = self.conn.cursor()
        q = "SELECT COUNT(DISTINCT i.id) FROM ideas i LEFT JOIN idea_tags it ON i.id=it.idea_id LEFT JOIN tags t ON it.tag_id=t.id WHERE 1=1"
        p = []
        
        if f_type == 'trash': q += ' AND i.is_deleted=1'
        else: q += ' AND (i.is_deleted=0 OR i.is_deleted IS NULL)'
        
        if f_type == 'category':
            if f_val is None: q += ' AND i.category_id IS NULL'
            else: q += ' AND i.category_id=?'; p.append(f_val)
        elif f_type == 'today': q += " AND date(i.updated_at,'localtime')=date('now','localtime')"
        elif f_type == 'untagged': q += ' AND i.id NOT IN (SELECT idea_id FROM idea_tags)'
        elif f_type == 'bookmark': q += ' AND i.is_favorite=1'
        
        if search:
            if self.fts5_supported:
                q += " AND (i.id IN (SELECT rowid FROM ideas_fts WHERE ideas_fts MATCH ?) OR t.name LIKE ?)"
                p.append(search)
                p.append(f'%{search}%')
            else:
                q += ' AND (i.title LIKE ? OR i.content LIKE ? OR t.name LIKE ?)'
                p.extend([f'%{search}%'] * 3)

        if tag_filter:
            q += " AND i.id IN (SELECT idea_id FROM idea_tags WHERE tag_id = (SELECT id FROM tags WHERE name = ?))"
            p.append(tag_filter)

        if filter_criteria:
            if 'stars' in filter_criteria:
                stars = filter_criteria['stars']
                placeholders = ','.join('?' * len(stars))
                q += f" AND i.rating IN ({placeholders})"
                p.extend(stars)
            if 'colors' in filter_criteria:
                colors = filter_criteria['colors']
                placeholders = ','.join('?' * len(colors))
                q += f" AND i.color IN ({placeholders})"
                p.extend(colors)
            if 'types' in filter_criteria:
                types = filter_criteria['types']
                placeholders = ','.join('?' * len(types))
                q += f" AND i.item_type IN ({placeholders})"
                p.extend(types)
            if 'tags' in filter_criteria:
                tags = filter_criteria['tags']
                tag_placeholders = ','.join('?' * len(tags))
                q += f" AND i.id IN (SELECT idea_id FROM idea_tags JOIN tags ON idea_tags.tag_id = tags.id WHERE tags.name IN ({tag_placeholders}))"
                p.extend(tags)
            if 'date_create' in filter_criteria:
                date_conditions = []
                for d_opt in filter_criteria['date_create']:
                    if d_opt == 'today': date_conditions.append("date(i.created_at,'localtime')=date('now','localtime')")
                    elif d_opt == 'yesterday': date_conditions.append("date(i.created_at,'localtime')=date('now','-1 day','localtime')")
                    elif d_opt == 'week': date_conditions.append("date(i.created_at,'localtime')>=date('now','-6 days','localtime')")
                    elif d_opt == 'month': date_conditions.append("strftime('%Y-%m',i.created_at,'localtime')=strftime('%Y-%m','now','localtime')")
                if date_conditions:
                    q += " AND (" + " OR ".join(date_conditions) + ")"
            
        c.execute(q, p)
        return c.fetchone()[0]

    def get_tags(self, iid):
        c = self.conn.cursor()
        c.execute('SELECT t.name FROM tags t JOIN idea_tags it ON t.id=it.tag_id WHERE it.idea_id=?', (iid,))
        return [r[0] for r in c.fetchall()]

    def get_all_tags(self):
        c = self.conn.cursor()
        c.execute('SELECT name FROM tags ORDER BY name')
        return [r[0] for r in c.fetchall()]

    def get_categories(self):
        c = self.conn.cursor()
        c.execute('SELECT * FROM categories ORDER BY sort_order ASC, name ASC')
        return c.fetchall()

    def add_category(self, name, parent_id=None):
        c = self.conn.cursor()
        if parent_id is None:
            c.execute("SELECT MAX(sort_order) FROM categories WHERE parent_id IS NULL")
        else:
            c.execute("SELECT MAX(sort_order) FROM categories WHERE parent_id = ?", (parent_id,))
        max_order = c.fetchone()[0]
        new_order = (max_order or 0) + 1
        
        palette = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEEAD',
            '#D4A5A5', '#9B59B6', '#3498DB', '#E67E22', '#2ECC71',
            '#E74C3C', '#F1C40F', '#1ABC9C', '#34495E', '#95A5A6'
        ]
        chosen_color = random.choice(palette)
        
        c.execute(
            'INSERT INTO categories (name, parent_id, sort_order, color) VALUES (?, ?, ?, ?)', 
            (name, parent_id, new_order, chosen_color)
        )
        self.conn.commit()

    def rename_category(self, cat_id, new_name):
        c = self.conn.cursor()
        c.execute('UPDATE categories SET name=? WHERE id=?', (new_name, cat_id))
        self.conn.commit()
    
    def set_category_color(self, cat_id, color):
        c = self.conn.cursor()
        try:
            find_ids_query = """
                WITH RECURSIVE category_tree(id) AS (
                    SELECT ?
                    UNION ALL
                    SELECT c.id FROM categories c JOIN category_tree ct ON c.parent_id = ct.id
                )
                SELECT id FROM category_tree;
            """
            c.execute(find_ids_query, (cat_id,))
            all_ids = [row[0] for row in c.fetchall()]

            if not all_ids:
                return

            placeholders = ','.join('?' * len(all_ids))

            update_ideas_query = f"UPDATE ideas SET color = ? WHERE category_id IN ({placeholders})"
            c.execute(update_ideas_query, (color, *all_ids))

            update_categories_query = f"UPDATE categories SET color = ? WHERE id IN ({placeholders})"
            c.execute(update_categories_query, (color, *all_ids))

            self.conn.commit()
        except Exception as e:
            self.conn.rollback()

    def set_category_preset_tags(self, cat_id, tags_str):
        c = self.conn.cursor()
        c.execute('UPDATE categories SET preset_tags=? WHERE id=?', (tags_str, cat_id))
        self.conn.commit()

    def get_category_preset_tags(self, cat_id):
        c = self.conn.cursor()
        c.execute('SELECT preset_tags FROM categories WHERE id=?', (cat_id,))
        res = c.fetchone()
        return res[0] if res else ""

    def apply_preset_tags_to_category_items(self, cat_id, tags_list):
        if not tags_list: return
        c = self.conn.cursor()
        c.execute('SELECT id FROM ideas WHERE category_id=? AND is_deleted=0', (cat_id,))
        items = c.fetchall()
        for (iid,) in items:
            self._append_tags(iid, tags_list)
        self.conn.commit()

    def delete_category(self, cid):
        c = self.conn.cursor()
        c.execute('UPDATE ideas SET category_id=NULL WHERE category_id=?', (cid,))
        c.execute('DELETE FROM categories WHERE id=?', (cid,))
        self.conn.commit()

    def get_counts(self):
        c = self.conn.cursor()
        d = {}
        queries = {
            'all': "is_deleted=0 OR is_deleted IS NULL",
            'today': "(is_deleted=0 OR is_deleted IS NULL) AND date(updated_at,'localtime')=date('now','localtime')",
            'uncategorized': "(is_deleted=0 OR is_deleted IS NULL) AND category_id IS NULL",
            'untagged': "(is_deleted=0 OR is_deleted IS NULL) AND id NOT IN (SELECT idea_id FROM idea_tags)",
            'bookmark': "(is_deleted=0 OR is_deleted IS NULL) AND is_favorite=1",
            'trash': "is_deleted=1"
        }
        for k, v in queries.items():
            c.execute(f"SELECT COUNT(*) FROM ideas WHERE {v}")
            d[k] = c.fetchone()[0]
            
        c.execute("SELECT category_id, COUNT(*) FROM ideas WHERE (is_deleted=0 OR is_deleted IS NULL) GROUP BY category_id")
        d['categories'] = dict(c.fetchall())
        return d

    def get_top_tags(self):
        c = self.conn.cursor()
        c.execute('''SELECT t.name, COUNT(it.idea_id) as c FROM tags t 
                     JOIN idea_tags it ON t.id=it.tag_id JOIN ideas i ON it.idea_id=i.id 
                     WHERE i.is_deleted=0 GROUP BY t.id ORDER BY c DESC LIMIT 5''')
        return c.fetchall()

    def get_partitions_tree(self):
        class Partition:
            def __init__(self, id, name, color, parent_id, sort_order):
                self.id = id
                self.name = name
                self.color = color
                self.parent_id = parent_id
                self.sort_order = sort_order
                self.children = []

        c = self.conn.cursor()
        c.execute("SELECT id, name, color, parent_id, sort_order FROM categories ORDER BY sort_order ASC, name ASC")
        
        nodes = {row[0]: Partition(*row) for row in c.fetchall()}
        
        tree = []
        for node_id, node in nodes.items():
            if node.parent_id in nodes:
                nodes[node.parent_id].children.append(node)
            else:
                tree.append(node)
                
        return tree

    def get_partition_item_counts(self):
        c = self.conn.cursor()
        counts = {'partitions': {}}

        c.execute("SELECT COUNT(*) FROM ideas WHERE is_deleted=0")
        counts['total'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM ideas WHERE is_deleted=0 AND date(updated_at, 'localtime') = date('now', 'localtime')")
        counts['today_modified'] = c.fetchone()[0]
        
        c.execute("SELECT category_id, COUNT(*) FROM ideas WHERE is_deleted=0 GROUP BY category_id")
        for cat_id, count in c.fetchall():
            if cat_id is not None:
                counts['partitions'][cat_id] = count

        # Add missing counts
        c.execute("SELECT COUNT(*) FROM ideas i JOIN idea_tags it ON i.id = it.idea_id JOIN tags t ON it.tag_id = t.id WHERE t.name = '剪贴板' AND i.is_deleted=0")
        counts['clipboard'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM ideas WHERE is_favorite=1 AND is_deleted=0")
        counts['bookmark'] = c.fetchone()[0]

        return counts
    
    def save_category_order(self, update_list):
        c = self.conn.cursor()
        try:
            c.execute("BEGIN TRANSACTION")
            for item in update_list:
                c.execute(
                    "UPDATE categories SET sort_order = ?, parent_id = ? WHERE id = ?",
                    (item['sort_order'], item['parent_id'], item['id'])
                )
            c.execute("COMMIT")
        except Exception as e:
            c.execute("ROLLBACK")
            pass
        finally:
            self.conn.commit()

    def rename_tag(self, old_name, new_name):
        new_name = new_name.strip()
        if not new_name or old_name == new_name: return
        c = self.conn.cursor()
        c.execute("SELECT id FROM tags WHERE name=?", (old_name,))
        old_res = c.fetchone()
        if not old_res: return
        old_id = old_res[0]
        c.execute("SELECT id FROM tags WHERE name=?", (new_name,))
        new_res = c.fetchone()
        try:
            if new_res:
                new_id = new_res[0]
                c.execute("UPDATE OR IGNORE idea_tags SET tag_id=? WHERE tag_id=?", (new_id, old_id))
                c.execute("DELETE FROM idea_tags WHERE tag_id=?", (old_id,))
                c.execute("DELETE FROM tags WHERE id=?", (old_id,))
            else:
                c.execute("UPDATE tags SET name=? WHERE id=?", (new_name, old_id))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()

    def delete_tag(self, tag_name):
        c = self.conn.cursor()
        c.execute("SELECT id FROM tags WHERE name=?", (tag_name,))
        res = c.fetchone()
        if res:
            tag_id = res[0]
            c.execute("DELETE FROM idea_tags WHERE tag_id=?", (tag_id,))
            c.execute("DELETE FROM tags WHERE id=?", (tag_id,))
            self.conn.commit()
```

## 文件: data\schema_migrations.py

```python
# data/schema_migrations.py
import logging

logger = logging.getLogger(__name__)

class SchemaMigration:
    @staticmethod
    def _get_db_version(conn):
        c = conn.cursor()
        try:
            c.execute("PRAGMA user_version")
            version = c.fetchone()[0]
            return version
        except Exception:
            # If user_version does not exist, it's a very old db, treat as version 0
            return 0

    @staticmethod
    def _set_db_version(conn, version):
        c = conn.cursor()
        c.execute(f"PRAGMA user_version = {version}")
        conn.commit()

    @staticmethod
    def apply(conn):
        logger.info("开始检查数据库结构迁移...")
        current_version = SchemaMigration._get_db_version(conn)
        logger.info(f"当前数据库版本: {current_version}")

        if current_version < 1:
            SchemaMigration._migrate_to_v1(conn)
            SchemaMigration._set_db_version(conn, 1)
            logger.info("数据库迁移到 v1")
        
        # Add future migrations here
        # if current_version < 2:
        #     SchemaMigration._migrate_to_v2(conn)
        #     SchemaMigration._set_db_version(conn, 2)
        #     logger.info("数据库迁移到 v2")
            
        logger.info("数据库结构检查完成。")

    @staticmethod
    def _migrate_to_v1(conn):
        c = conn.cursor()
        
        logger.info("v1 迁移: 创建初始表结构...")
        c.execute('''CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, content TEXT, color TEXT DEFAULT '#4a90e2',
            is_pinned INTEGER DEFAULT 0, is_favorite INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            category_id INTEGER, is_deleted INTEGER DEFAULT 0,
            item_type TEXT DEFAULT 'text', data_blob BLOB,
            content_hash TEXT
        )''')
        c.execute('CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)')
        c.execute('''CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT NOT NULL, 
            parent_id INTEGER, 
            color TEXT DEFAULT "#808080",
            sort_order INTEGER DEFAULT 0
        )''')
        c.execute('CREATE TABLE IF NOT EXISTS idea_tags (idea_id INTEGER, tag_id INTEGER, PRIMARY KEY (idea_id, tag_id))')
        c.execute('CREATE INDEX IF NOT EXISTS idx_content_hash ON ideas(content_hash)')
        
        # This part is for migrating from even older, pre-versioning schemas
        logger.info("v1 迁移: 检查并添加旧版本可能缺失的列...")
        c.execute("PRAGMA table_info(ideas)")
        cols = [i[1] for i in c.fetchall()]
        if 'category_id' not in cols:
            try: c.execute('ALTER TABLE ideas ADD COLUMN category_id INTEGER')
            except: pass
        if 'is_deleted' not in cols:
            try: c.execute('ALTER TABLE ideas ADD COLUMN is_deleted INTEGER DEFAULT 0')
            except: pass
        if 'item_type' not in cols:
            try: c.execute("ALTER TABLE ideas ADD COLUMN item_type TEXT DEFAULT 'text'")
            except: pass
        if 'data_blob' not in cols:
            try: c.execute('ALTER TABLE ideas ADD COLUMN data_blob BLOB')
            except: pass
        if 'content_hash' not in cols:
            try: c.execute('ALTER TABLE ideas ADD COLUMN content_hash TEXT')
            except: pass
        
        c.execute("PRAGMA table_info(categories)")
        cat_cols = [i[1] for i in c.fetchall()]
        if 'sort_order' not in cat_cols:
            try: c.execute('ALTER TABLE categories ADD COLUMN sort_order INTEGER DEFAULT 0')
            except: pass
            
        conn.commit()
```

## 文件: data\__init__.py

```python
﻿# -*- coding: utf-8 -*-

```

## 文件: data\repositories\category_repository.py

```python
# -*- coding: utf-8 -*-
# data/repositories/category_repository.py
import random

class CategoryRepository:
    def __init__(self, db_context):
        self.db = db_context

    def get_all(self):
        c = self.db.get_cursor()
        c.execute('SELECT * FROM categories ORDER BY sort_order ASC, name ASC')
        return c.fetchall()

    def add(self, name, parent_id=None):
        c = self.db.get_cursor()
        if parent_id is None:
            c.execute("SELECT MAX(sort_order) FROM categories WHERE parent_id IS NULL")
        else:
            c.execute("SELECT MAX(sort_order) FROM categories WHERE parent_id = ?", (parent_id,))
        max_order = c.fetchone()[0]
        new_order = (max_order or 0) + 1
        
        palette = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEEAD',
            '#D4A5A5', '#9B59B6', '#3498DB', '#E67E22', '#2ECC71'
        ]
        chosen_color = random.choice(palette)
        
        c.execute(
            'INSERT INTO categories (name, parent_id, sort_order, color) VALUES (?, ?, ?, ?)', 
            (name, parent_id, new_order, chosen_color)
        )
        self.db.commit()

    def rename(self, cat_id, new_name):
        c = self.db.get_cursor()
        c.execute('UPDATE categories SET name=? WHERE id=?', (new_name, cat_id))
        self.db.commit()

    def set_color(self, cat_id, color):
        c = self.db.get_cursor()
        try:
            find_ids_query = """
                WITH RECURSIVE category_tree(id) AS (
                    SELECT ?
                    UNION ALL
                    SELECT c.id FROM categories c JOIN category_tree ct ON c.parent_id = ct.id
                )
                SELECT id FROM category_tree;
            """
            c.execute(find_ids_query, (cat_id,))
            all_ids = [row[0] for row in c.fetchall()]

            if all_ids:
                placeholders = ','.join('?' * len(all_ids))
                c.execute(f"UPDATE ideas SET color = ? WHERE category_id IN ({placeholders})", (color, *all_ids))
                c.execute(f"UPDATE categories SET color = ? WHERE id IN ({placeholders})", (color, *all_ids))
                self.db.commit()
        except:
            self.db.conn.rollback()

    def delete(self, cid):
        c = self.db.get_cursor()
        c.execute('UPDATE ideas SET category_id=NULL WHERE category_id=?', (cid,))
        c.execute('DELETE FROM categories WHERE id=?', (cid,))
        self.db.commit()

    def set_preset_tags(self, cat_id, tags_str):
        c = self.db.get_cursor()
        c.execute('UPDATE categories SET preset_tags=? WHERE id=?', (tags_str, cat_id))
        self.db.commit()

    def get_preset_tags(self, cat_id):
        c = self.db.get_cursor()
        c.execute('SELECT preset_tags FROM categories WHERE id=?', (cat_id,))
        res = c.fetchone()
        return res[0] if res else ""

    def save_order(self, update_list):
        c = self.db.get_cursor()
        try:
            c.execute("BEGIN TRANSACTION")
            for item in update_list:
                c.execute(
                    "UPDATE categories SET sort_order = ?, parent_id = ? WHERE id = ?",
                    (item['sort_order'], item['parent_id'], item['id'])
                )
            c.execute("COMMIT")
        except:
            c.execute("ROLLBACK")
        finally:
            self.db.commit()

    def get_tree(self):
        class Partition:
            def __init__(self, id, name, color, parent_id, sort_order):
                self.id = id; self.name = name; self.color = color
                self.parent_id = parent_id; self.sort_order = sort_order; self.children = []

        c = self.db.get_cursor()
        c.execute("SELECT id, name, color, parent_id, sort_order FROM categories ORDER BY sort_order ASC, name ASC")
        nodes = {row[0]: Partition(*row) for row in c.fetchall()}
        tree = []
        for _, node in nodes.items():
            if node.parent_id in nodes: nodes[node.parent_id].children.append(node)
            else: tree.append(node)
        return tree
```

## 文件: data\repositories\idea_repository.py

```python
# -*- coding: utf-8 -*-
# data/repositories/idea_repository.py
from core.config import COLORS

class IdeaRepository:
    # SQL字段白名单 - 防止SQL注入
    ALLOWED_UPDATE_FIELDS = {
        'title', 'content', 'color', 'category_id', 'item_type', 
        'is_pinned', 'is_favorite', 'is_deleted', 'is_locked', 'rating'
    }
    
    def __init__(self, db_context):
        # 【关键修改】这里必须是 self.db，不能是 self.conn
        self.db = db_context

    def get_count_by_filter(self, search, f_type, f_val, tag_filter=None, criteria=None):
        c = self.db.get_cursor()
        q, p = self._build_query(search, f_type, f_val, tag_filter, criteria, count_only=True)
        c.execute(q, p)
        return c.fetchone()[0]

    def get_list_by_filter(self, search, f_type, f_val, page, page_size, tag_filter=None, criteria=None):
        c = self.db.get_cursor()
        q, p = self._build_query(search, f_type, f_val, tag_filter, criteria, count_only=False)
        
        if f_type == 'trash':
            q += ' ORDER BY i.updated_at DESC'
        else:
            q += ' ORDER BY i.is_pinned DESC, i.updated_at DESC'
            
        if page is not None and page_size is not None:
            limit = page_size
            offset = (page - 1) * page_size
            q += ' LIMIT ? OFFSET ?'
            p.extend([limit, offset])
        
        c.execute(q, p)
        return c.fetchall()

    def _build_query(self, search, f_type, f_val, tag_filter, criteria, count_only=False):
        if count_only:
            q = "SELECT COUNT(DISTINCT i.id) FROM ideas i "
        else:
            q = """
                SELECT DISTINCT 
                    i.id, i.title, i.content, i.color, i.is_pinned, i.is_favorite, 
                    i.created_at, i.updated_at, i.category_id, i.is_deleted, 
                    i.item_type, i.data_blob, i.content_hash, i.is_locked, i.rating
                FROM ideas i 
            """
            
        q += "LEFT JOIN idea_tags it ON i.id=it.idea_id LEFT JOIN tags t ON it.tag_id=t.id WHERE 1=1"
        p = []

        if f_type == 'trash': q += ' AND i.is_deleted=1'
        else: q += ' AND (i.is_deleted=0 OR i.is_deleted IS NULL)'
        
        if f_type == 'category':
            if f_val is None: q += ' AND i.category_id IS NULL'
            else: q += ' AND i.category_id=?'; p.append(f_val)
        elif f_type == 'today': q += " AND date(i.updated_at,'localtime')=date('now','localtime')"
        elif f_type == 'untagged': q += ' AND i.id NOT IN (SELECT idea_id FROM idea_tags)'
        elif f_type == 'bookmark': q += ' AND i.is_favorite=1'
        
        if search:
            q += ' AND (i.title LIKE ? OR i.content LIKE ? OR t.name LIKE ?)'
            p.extend([f'%{search}%']*3)

        if tag_filter:
            q += " AND i.id IN (SELECT idea_id FROM idea_tags WHERE tag_id = (SELECT id FROM tags WHERE name = ?))"
            p.append(tag_filter)
            
        if criteria:
            if 'stars' in criteria:
                stars = criteria['stars']
                placeholders = ','.join('?' * len(stars))
                q += f" AND i.rating IN ({placeholders})"
                p.extend(stars)
            if 'colors' in criteria:
                colors = criteria['colors']
                placeholders = ','.join('?' * len(colors))
                q += f" AND i.color IN ({placeholders})"
                p.extend(colors)
            if 'types' in criteria:
                types = criteria['types']
                placeholders = ','.join('?' * len(types))
                q += f" AND i.item_type IN ({placeholders})"
                p.extend(types)
            if 'tags' in criteria:
                tags = criteria['tags']
                tag_placeholders = ','.join('?' * len(tags))
                q += f" AND i.id IN (SELECT idea_id FROM idea_tags JOIN tags ON idea_tags.tag_id = tags.id WHERE tags.name IN ({tag_placeholders}))"
                p.extend(tags)
            if 'date_create' in criteria:
                date_conditions = []
                for d_opt in criteria['date_create']:
                    if d_opt == 'today': date_conditions.append("date(i.created_at,'localtime')=date('now','localtime')")
                    elif d_opt == 'yesterday': date_conditions.append("date(i.created_at,'localtime')=date('now','-1 day','localtime')")
                    elif d_opt == 'week': date_conditions.append("date(i.created_at,'localtime')>=date('now','-6 days','localtime')")
                    elif d_opt == 'month': date_conditions.append("strftime('%Y-%m',i.created_at,'localtime')=strftime('%Y-%m','now','localtime')")
                if date_conditions:
                    q += " AND (" + " OR ".join(date_conditions) + ")"
        
        return q, p

    def get_by_id(self, iid, include_blob=False):
        c = self.db.get_cursor()
        if include_blob:
            c.execute('SELECT * FROM ideas WHERE id=?', (iid,))
        else:
            c.execute('''
                SELECT id, title, content, color, is_pinned, is_favorite, 
                       created_at, updated_at, category_id, is_deleted, item_type, 
                       NULL as data_blob, NULL as content_hash, is_locked, rating
                FROM ideas WHERE id=?
            ''', (iid,))
        return c.fetchone()

    def add(self, title, content, color, category_id, item_type, data_blob, content_hash=None):
        c = self.db.get_cursor()
        c.execute(
            'INSERT INTO ideas (title, content, color, category_id, item_type, data_blob, content_hash) VALUES (?,?,?,?,?,?,?)',
            (title, content, color, category_id, item_type, data_blob, content_hash)
        )
        self.db.commit()
        return c.lastrowid

    def update(self, iid, title, content, color, category_id, item_type, data_blob):
        c = self.db.get_cursor()
        c.execute(
            'UPDATE ideas SET title=?, content=?, color=?, category_id=?, item_type=?, data_blob=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (title, content, color, category_id, item_type, data_blob, iid)
        )
        self.db.commit()

    def update_field(self, iid, field, value):
        # 【安全修复】验证字段名是否在白名单中
        if field not in self.ALLOWED_UPDATE_FIELDS:
            raise ValueError(f"Invalid field name: {field}. Allowed fields: {self.ALLOWED_UPDATE_FIELDS}")
        c = self.db.get_cursor()
        c.execute(f'UPDATE ideas SET {field} = ? WHERE id = ?', (value, iid))
        self.db.commit()

    def toggle_field(self, iid, field):
        # 【安全修复】验证字段名是否在白名单中
        if field not in self.ALLOWED_UPDATE_FIELDS:
            raise ValueError(f"Invalid field name: {field}. Allowed fields: {self.ALLOWED_UPDATE_FIELDS}")
        c = self.db.get_cursor()
        c.execute(f'UPDATE ideas SET {field} = NOT {field} WHERE id=?', (iid,))
        self.db.commit()

    def delete_permanent(self, iid):
        c = self.db.get_cursor()
        c.execute('DELETE FROM ideas WHERE id=?', (iid,))
        c.execute('DELETE FROM idea_tags WHERE idea_id=?', (iid,))
        self.db.commit()
    
    def update_timestamp(self, iid):
        """更新记录的时间戳"""
        c = self.db.get_cursor()
        c.execute("UPDATE ideas SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (iid,))
        self.db.commit()

    def get_counts(self):
        c = self.db.get_cursor()
        d = {}
        queries = {
            'all': "is_deleted=0 OR is_deleted IS NULL",
            'today': "(is_deleted=0 OR is_deleted IS NULL) AND date(updated_at,'localtime')=date('now','localtime')",
            'uncategorized': "(is_deleted=0 OR is_deleted IS NULL) AND category_id IS NULL",
            'untagged': "(is_deleted=0 OR is_deleted IS NULL) AND id NOT IN (SELECT idea_id FROM idea_tags)",
            'bookmark': "(is_deleted=0 OR is_deleted IS NULL) AND is_favorite=1",
            'trash': "is_deleted=1"
        }
        for k, v in queries.items():
            c.execute(f"SELECT COUNT(*) FROM ideas WHERE {v}")
            d[k] = c.fetchone()[0]
        
        c.execute("SELECT category_id, COUNT(*) FROM ideas WHERE (is_deleted=0 OR is_deleted IS NULL) GROUP BY category_id")
        d['categories'] = dict(c.fetchall())
        return d
        
    def get_filter_stats(self, search_text, filter_type, filter_value):
        c = self.db.get_cursor()
        stats = {'stars': {}, 'colors': {}, 'types': {}, 'tags': [], 'date_create': {}}
        
        where_clauses = ["1=1"]
        params = []
        
        if filter_type == 'trash': where_clauses.append("i.is_deleted=1")
        else: where_clauses.append("(i.is_deleted=0 OR i.is_deleted IS NULL)")
            
        if filter_type == 'category':
            if filter_value is None: where_clauses.append("i.category_id IS NULL")
            else: where_clauses.append("i.category_id=?"); params.append(filter_value)
        elif filter_type == 'today': where_clauses.append("date(i.updated_at,'localtime')=date('now','localtime')")
        elif filter_type == 'untagged': where_clauses.append("i.id NOT IN (SELECT idea_id FROM idea_tags)")
        elif filter_type == 'bookmark': where_clauses.append("i.is_favorite=1")
        
        if search_text:
            where_clauses.append("(i.title LIKE ? OR i.content LIKE ?)")
            params.extend([f'%{search_text}%', f'%{search_text}%'])
            
        where_str = " AND ".join(where_clauses)
        
        c.execute(f"SELECT i.rating, COUNT(*) FROM ideas i WHERE {where_str} GROUP BY i.rating", params)
        stats['stars'] = dict(c.fetchall())

        c.execute(f"SELECT i.color, COUNT(*) FROM ideas i WHERE {where_str} GROUP BY i.color", params)
        stats['colors'] = dict(c.fetchall())

        c.execute(f"SELECT i.item_type, COUNT(*) FROM ideas i WHERE {where_str} GROUP BY i.item_type", params)
        stats['types'] = dict(c.fetchall())

        tag_sql = f"""
            SELECT t.name, COUNT(it.idea_id) as cnt
            FROM tags t
            JOIN idea_tags it ON t.id = it.tag_id
            JOIN ideas i ON it.idea_id = i.id
            WHERE {where_str}
            GROUP BY t.id
            ORDER BY cnt DESC
        """
        c.execute(tag_sql, params)
        stats['tags'] = c.fetchall()

        base_date_sql = f"SELECT COUNT(*) FROM ideas i WHERE {where_str} AND "
        c.execute(base_date_sql + "date(i.created_at, 'localtime') = date('now', 'localtime')", params)
        stats['date_create']['today'] = c.fetchone()[0]
        c.execute(base_date_sql + "date(i.created_at, 'localtime') = date('now', '-1 day', 'localtime')", params)
        stats['date_create']['yesterday'] = c.fetchone()[0]
        c.execute(base_date_sql + "date(i.created_at, 'localtime') >= date('now', '-6 days', 'localtime')", params)
        stats['date_create']['week'] = c.fetchone()[0]
        c.execute(base_date_sql + "strftime('%Y-%m', i.created_at, 'localtime') = strftime('%Y-%m', 'now', 'localtime')", params)
        stats['date_create']['month'] = c.fetchone()[0]

        return stats
    
    def get_lock_status(self, idea_ids):
        if not idea_ids: return {}
        c = self.db.get_cursor()
        placeholders = ','.join('?' * len(idea_ids))
        c.execute(f'SELECT id, is_locked FROM ideas WHERE id IN ({placeholders})', tuple(idea_ids))
        return dict(c.fetchall())
        
    def set_locked(self, idea_ids, state):
        if not idea_ids: return
        c = self.db.get_cursor()
        val = 1 if state else 0
        placeholders = ','.join('?' * len(idea_ids))
        c.execute(f'UPDATE ideas SET is_locked=? WHERE id IN ({placeholders})', (val, *idea_ids))
        self.db.commit()

    def find_by_hash(self, content_hash):
        c = self.db.get_cursor()
        c.execute("SELECT id FROM ideas WHERE content_hash = ?", (content_hash,))
        return c.fetchone()

    # --- New Methods for Smart Caching Architecture ---
    
    def get_metadata_by_filter(self, search, f_type, f_val):
        """
        获取符合条件的所有数据的轻量级元数据。
        不包含 data_blob, content 等重字段。
        用于前端瞬间加载和客户端筛选。
        """
        c = self.db.get_cursor()
        
        # 基础查询，只查轻量字段
        q = """
            SELECT DISTINCT 
                i.id, i.title, i.color, i.is_pinned, i.is_favorite, 
                i.created_at, i.updated_at, i.item_type, i.rating, i.is_locked
            FROM ideas i 
            LEFT JOIN idea_tags it ON i.id=it.idea_id 
            LEFT JOIN tags t ON it.tag_id=t.id 
            WHERE 1=1
        """
        p = []

        if f_type == 'trash': q += ' AND i.is_deleted=1'
        else: q += ' AND (i.is_deleted=0 OR i.is_deleted IS NULL)'
        
        if f_type == 'category':
            if f_val is None: q += ' AND i.category_id IS NULL'
            else: q += ' AND i.category_id=?'; p.append(f_val)
        elif f_type == 'today': q += " AND date(i.updated_at,'localtime')=date('now','localtime')"
        elif f_type == 'untagged': q += ' AND i.id NOT IN (SELECT idea_id FROM idea_tags)'
        elif f_type == 'bookmark': q += ' AND i.is_favorite=1'
        
        if search:
            q += ' AND (i.title LIKE ? OR i.content LIKE ? OR t.name LIKE ?)'
            p.extend([f'%{search}%']*3)
            
        # 默认排序
        if f_type == 'trash':
            q += ' ORDER BY i.updated_at DESC'
        else:
            q += ' ORDER BY i.is_pinned DESC, i.updated_at DESC'

        c.execute(q, p)
        rows = c.fetchall()
        
        # 为了高效，直接返回字典列表，包含后续筛选所需的所有字段
        result = []
        # 注意：fetchall 返回的是 tuple，需要配合 description 映射或按索引取
        # 这里的索引顺序: 0:id, 1:title, 2:color, 3:pinned, 4:fav, 5:created, 6:updated, 7:type, 8:rating, 9:locked
        
        # 额外步骤：为了支持Tag筛选，我们需要知道每个idea的tags
        # 但在 SQL 里 join 会导致重复行。
        # 策略：先拿到 ideas，再批量查 tags? 或者在 python 层不做 tag 聚合，
        # 而是为了性能，我们在 SQL 里 GROUP_CONCAT tags?
        #由于 sqlite group_concat 简单，我们用它
        
        # 重写查询以支持 tags 聚合
        q_grouped = f"""
            SELECT 
                i.id, i.title, i.color, i.is_pinned, i.is_favorite, 
                i.created_at, i.updated_at, i.item_type, i.rating, i.is_locked,
                GROUP_CONCAT(t.name) as tag_names
            FROM ideas i 
            LEFT JOIN idea_tags it ON i.id=it.idea_id 
            LEFT JOIN tags t ON it.tag_id=t.id 
            WHERE 1=1
        """
        # ... 复用上面的 where 条件构造逻辑 ...
        # (为了代码简洁，上面那个 blocks 其实可以重构，但这里为了最小化修改风险，我们拷贝逻辑)
        
        where_clause = "1=1"
        p_grp = []
        if f_type == 'trash': where_clause += ' AND i.is_deleted=1'
        else: where_clause += ' AND (i.is_deleted=0 OR i.is_deleted IS NULL)'
        if f_type == 'category':
            if f_val is None: where_clause += ' AND i.category_id IS NULL'
            else: where_clause += ' AND i.category_id=?'; p_grp.append(f_val)
        elif f_type == 'today': where_clause += " AND date(i.updated_at,'localtime')=date('now','localtime')"
        elif f_type == 'untagged': where_clause += ' AND i.id NOT IN (SELECT idea_id FROM idea_tags)'
        elif f_type == 'bookmark': where_clause += ' AND i.is_favorite=1'
        
        if search:
            where_clause += ' AND (i.title LIKE ? OR i.content LIKE ?)' 
            # 注意：search 如果包含 tag 搜索，上面的 join 逻辑是必要的。
            # 如果只搜 title/content，可以不需要 left join tags。
            # 但为了统一逻辑，假设 search 也能搜 tags。
            p_grp.extend([f'%{search}%', f'%{search}%'])

        q_grouped += " AND " + where_clause
        q_grouped += " GROUP BY i.id"
        
        if f_type == 'trash': q_grouped += ' ORDER BY i.updated_at DESC'
        else: q_grouped += ' ORDER BY i.is_pinned DESC, i.updated_at DESC'
            
        c.execute(q_grouped, p_grp)
        rows = c.fetchall()
        
        res_list = []
        for r in rows:
            res_list.append({
                'id': r[0], 'title': r[1], 'color': r[2], 'is_pinned': r[3],
                'is_favorite': r[4], 'created_at': r[5], 'updated_at': r[6],
                'item_type': r[7], 'rating': r[8], 'is_locked': r[9],
                'tags': r[10].split(',') if r[10] else []
            })
        return res_list

    def get_details_by_ids(self, id_list):
        """
        根据 ID 列表批量获取完整详情（包含 content, data_blob 等）。
        同时使用 GROUP_CONCAT 聚合标签，解决 N+1 查询问题。
        用于分页渲染。
        """
        if not id_list: return []
        c = self.db.get_cursor()
        placeholders = ','.join('?' * len(id_list))
        
        q = f"""
            SELECT 
                i.id, i.title, i.content, i.color, i.is_pinned, i.is_favorite, 
                i.created_at, i.updated_at, i.category_id, i.is_deleted, i.item_type, 
                i.data_blob, i.content_hash, i.is_locked, i.rating,
                GROUP_CONCAT(t.name) as tag_names
            FROM ideas i
            LEFT JOIN idea_tags it ON i.id = it.idea_id
            LEFT JOIN tags t ON it.tag_id = t.id
            WHERE i.id IN ({placeholders})
            GROUP BY i.id
        """
        c.execute(q, list(id_list))
        rows = c.fetchall()
        
        # 转为 list of dict
        results = []
        for r in rows:
            results.append({
                'id': r[0], 'title': r[1], 'content': r[2], 'color': r[3],
                'is_pinned': r[4], 'is_favorite': r[5], 'created_at': r[6],
                'updated_at': r[7], 'category_id': r[8], 'is_deleted': r[9],
                'item_type': r[10], 'data_blob': r[11], 'content_hash': r[12],
                'is_locked': r[13], 'rating': r[14],
                'tags': r[15].split(',') if r[15] else []
            })
            
        # 按 id_list 顺序重排
        res_map = {d['id']: d for d in results}
        ordered_res = []
        for iid in id_list:
            if iid in res_map:
                ordered_res.append(res_map[iid])
        return ordered_res
```

## 文件: data\repositories\tag_repository.py

```python
# -*- coding: utf-8 -*-
# data/repositories/tag_repository.py

class TagRepository:
    def __init__(self, db_context):
        self.db = db_context

    def get_by_idea(self, iid):
        c = self.db.get_cursor()
        c.execute('SELECT t.name FROM tags t JOIN idea_tags it ON t.id=it.tag_id WHERE it.idea_id=?', (iid,))
        return [r[0] for r in c.fetchall()]

    def get_all(self):
        c = self.db.get_cursor()
        c.execute('SELECT name FROM tags ORDER BY name')
        return [r[0] for r in c.fetchall()]

    def update_tags(self, iid, tags):
        c = self.db.get_cursor()
        c.execute('DELETE FROM idea_tags WHERE idea_id=?', (iid,))
        if tags:
            for t in tags:
                t = t.strip()
                if t:
                    c.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (t,))
                    c.execute('SELECT id FROM tags WHERE name=?', (t,))
                    res = c.fetchone()
                    if res:
                        tid = res[0]
                        c.execute('INSERT OR IGNORE INTO idea_tags VALUES (?,?)', (iid, tid))
        self.db.commit()

    def add_to_multiple(self, idea_ids, tags):
        if not idea_ids or not tags: return
        c = self.db.get_cursor()
        for t in tags:
            t = t.strip()
            if t:
                c.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (t,))
                c.execute('SELECT id FROM tags WHERE name=?', (t,))
                res = c.fetchone()
                if res:
                    tid = res[0]
                    for iid in idea_ids:
                        c.execute('INSERT OR IGNORE INTO idea_tags (idea_id, tag_id) VALUES (?,?)', (iid, tid))
        self.db.commit()

    def remove_from_multiple(self, idea_ids, tag_name):
        if not idea_ids or not tag_name: return
        c = self.db.get_cursor()
        c.execute('SELECT id FROM tags WHERE name=?', (tag_name,))
        res = c.fetchone()
        if not res: return
        tid = res[0]
        placeholders = ','.join('?' * len(idea_ids))
        sql = f'DELETE FROM idea_tags WHERE tag_id=? AND idea_id IN ({placeholders})'
        c.execute(sql, (tid, *idea_ids))
        self.db.commit()

    def get_top_tags(self):
        c = self.db.get_cursor()
        c.execute('''SELECT t.name, COUNT(it.idea_id) as c FROM tags t 
                     JOIN idea_tags it ON t.id=it.tag_id JOIN ideas i ON it.idea_id=i.id 
                     WHERE i.is_deleted=0 GROUP BY t.id ORDER BY c DESC LIMIT 5''')
        return c.fetchall()
```

## 文件: services\backup_service.py

```python
﻿# -*- coding: utf-8 -*-

# services/backup_service.py
import os
import shutil
from datetime import datetime
from core.config import DB_NAME, BACKUP_DIR

class BackupService:
    @staticmethod
    def run_backup():
        """执行数据库备份并清理旧文件"""
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
        
        if os.path.exists(DB_NAME):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            target = os.path.join(BACKUP_DIR, f'ideas_{timestamp}.db')
            try:
                shutil.copy2(DB_NAME, target)
                BackupService._clean_old_backups()
                print(f"[System] Backup created: {target}")
            except Exception as e:
                print(f"[System] Backup failed: {e}")

    @staticmethod
    def _clean_old_backups(keep=20):
        try:
            files = sorted(
                [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR)],
                key=os.path.getmtime
            )
            while len(files) > keep:
                os.remove(files.pop(0))
        except Exception:
            pass
```

## 文件: services\category_service.py

```python
﻿# application/services/category_service.py
from typing import List, Optional, Dict, Any
from domain.entities import Category
from infrastructure.repositories.category_repository import CategoryRepository
from infrastructure.repositories.idea_repository import IdeaRepository

class CategoryService:
    def __init__(self, category_repository: CategoryRepository, idea_repository: IdeaRepository):
        self._category_repo = category_repository
        self._idea_repo = idea_repository

    def get_all_categories(self) -> List[Dict]:
        """获取所有分类"""
        categories = self._category_repo.get_all()
        return [self._category_to_dict(cat) for cat in categories]
    
    def _category_to_dict(self, cat: Category) -> Dict:
        return {
            'id': cat.id,
            'name': cat.name,
            'parent_id': cat.parent_id,
            'color': cat.color,
            'sort_order': cat.sort_order,
            'preset_tags': cat.preset_tags
        }
        
    def create_category(self, name: str, parent_id: Optional[int] = None) -> None:
        """创建分类"""
        if not name.strip():
            raise ValueError("分类名称不能为空")
        self._category_repo.add(name, parent_id)
        
    def rename_category(self, category_id: int, new_name: str) -> None:
        """重命名分类"""
        if not new_name.strip():
            raise ValueError("分类名称不能为空")
        self._category_repo.rename(category_id, new_name)
        
    def delete_category(self, category_id: int) -> None:
        """删除分类"""
        # 先解绑所有笔记
        cursor = self._idea_repo.connection.cursor()
        cursor.execute('UPDATE ideas SET category_id=NULL WHERE category_id=?', (category_id,))
        self._idea_repo.connection.commit()
        
        # 删除分类
        self._category_repo.delete(category_id)
        
    def set_category_color(self, category_id: int, color: str) -> None:
        """设置分类颜色（包括子分类和笔记）"""
        cursor = self._category_repo.connection.cursor()
        try:
            # 查找所有子分类
            find_ids_query = """
                WITH RECURSIVE category_tree(id) AS (
                    SELECT ?
                    UNION ALL
                    SELECT c.id FROM categories c JOIN category_tree ct ON c.parent_id = ct.id
                )
                SELECT id FROM category_tree;
            """
            cursor.execute(find_ids_query, (category_id,))
            all_ids = [row[0] for row in cursor.fetchall()]

            if not all_ids:
                return

            placeholders = ','.join('?' * len(all_ids))

            # 更新笔记颜色
            update_ideas_query = f"UPDATE ideas SET color = ? WHERE category_id IN ({placeholders})"
            cursor.execute(update_ideas_query, (color, *all_ids))

            # 更新分类颜色
            update_categories_query = f"UPDATE categories SET color = ? WHERE id IN ({placeholders})"
            cursor.execute(update_categories_query, (color, *all_ids))

            self._category_repo.connection.commit()
        except Exception as e:
            self._category_repo.connection.rollback()
            raise e

    def set_preset_tags(self, category_id: int, tags_str: str) -> None:
        """设置预设标签"""
        self._category_repo.set_preset_tags(category_id, tags_str)

    def get_preset_tags(self, category_id: int) -> str:
        """获取预设标签"""
        return self._category_repo.get_preset_tags(category_id)

    def apply_preset_tags_to_items(self, category_id: int, tags_list: List[str]) -> None:
        """应用预设标签到分类下所有笔记"""
        if not tags_list:
            return
        
        cursor = self._idea_repo.connection.cursor()
        cursor.execute('SELECT id FROM ideas WHERE category_id=? AND is_deleted=0', (category_id,))
        items = cursor.fetchall()
        
        for (iid,) in items:
            self._idea_repo.add_tags_to_ideas([iid], tags_list)

    def build_category_tree(self) -> List[Category]:
        """构建分类树"""
        categories = self._category_repo.get_all()
        category_map = {cat.id: cat for cat in categories}
        
        tree = []
        for cat in categories:
            if cat.parent_id in category_map:
                parent = category_map[cat.parent_id]
                parent.children.append(cat)
            else:
                tree.append(cat)
        return tree

    def save_category_order(self, update_list: List[Dict[str, Any]]) -> None:
        """保存分类顺序"""
        self._category_repo.save_order(update_list)
```

## 文件: services\clipboard.py

```python
# -*- coding: utf-8 -*-
# services/clipboard.py
import datetime
import os
import uuid
import hashlib
import logging
from PyQt5.QtCore import QObject, pyqtSignal, QBuffer
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication

class ClipboardManager(QObject):
    """
    管理剪贴板数据,处理数据并将其存入数据库。
    """
    data_captured = pyqtSignal(int)

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self._last_hash = None

    def _hash_data(self, data):
        """为数据创建一个统一的哈希值以检查重复。"""
        try:
            if isinstance(data, QImage):
                # 【安全规范】禁止使用MD5,必须使用SHA256
                buffer = QBuffer()
                buffer.open(QBuffer.ReadWrite)
                data.save(buffer, "PNG")
                return hashlib.sha256(buffer.data()).hexdigest()
            return hashlib.sha256(str(data).encode('utf-8')).hexdigest()
        except Exception as e:
            logging.error(f"Failed to hash data: {e}", exc_info=True)
            return None

    def process_clipboard(self, mime_data, category_id=None):
        """
        处理来自剪贴板的 MIME 数据。
        """
        # 【关键修复】正确的逻辑:只屏蔽应用自己的窗口
        # 检查当前活动窗口是否是应用自己的窗口
        active_win = QApplication.activeWindow()
        if active_win is not None:
            # 导入窗口类进行类型检查(延迟导入避免循环依赖)
            try:
                from ui.main_window import MainWindow
                from ui.quick_window import QuickWindow
                if isinstance(active_win, (MainWindow, QuickWindow)):
                    # 是应用自己的窗口,不处理剪贴板(避免内部复制操作)
                    return
            except ImportError as e:
                logging.warning(f"Failed to import window classes for clipboard check: {e}")

        extra_tags = set() # 用于收集智能分析的标签

        try:
            # --- 优先处理 文件/文件夹 ---
            if mime_data.hasUrls():
                urls = mime_data.urls()
                filepaths = [url.toLocalFile() for url in urls if url.isLocalFile()]
                
                if filepaths:
                    content = ";".join(filepaths)
                    current_hash = self._hash_data(content)
                    
                    if current_hash is None:
                        logging.error("Failed to hash file paths, skipping clipboard processing")
                        return
                    
                    if current_hash != self._last_hash:
                        
                        # 【优化逻辑:扩展名作为类型记录】
                        detected_type = 'file' # 默认
                        
                        # 分析文件类型
                        exts = set()
                        is_folder = False
                        for path in filepaths:
                            if os.path.isdir(path):
                                is_folder = True
                            elif os.path.isfile(path):
                                ext = os.path.splitext(path)[1].lower().lstrip('.')
                                if ext: exts.add(ext)
                        
                        # 决定最终记录的类型
                        if is_folder and not exts:
                            detected_type = 'folder'
                        elif len(exts) == 1:
                            detected_type = list(exts)[0] # 单一类型直接用扩展名
                        elif len(exts) > 1:
                            detected_type = 'files' # 多种类型混合
                        
                        try:
                            # 将 detected_type 传入 item_type
                            result = self.db.add_clipboard_item(item_type=detected_type, content=content, category_id=category_id)
                            self._last_hash = current_hash
                            
                            if result:
                                idea_id, is_new = result
                                if is_new:
                                    # 注意：不再将扩展名作为标签添加
                                    self.data_captured.emit(idea_id)
                        except Exception as e:
                            logging.error(f"Failed to save file clipboard item: {e}", exc_info=True)
                        return

            # --- 处理图片 ---
            if mime_data.hasImage():
                try:
                    image = mime_data.imageData()
                    buffer = QBuffer()
                    buffer.open(QBuffer.ReadWrite)
                    image.save(buffer, "PNG")
                    image_bytes = buffer.data()
                    
                    # 【安全规范】禁止使用MD5,必须使用SHA256
                    current_hash = hashlib.sha256(image_bytes).hexdigest()
                    
                    if current_hash != self._last_hash:
                        result = self.db.add_clipboard_item(item_type='image', content='[Image Data]', data_blob=image_bytes, category_id=category_id)
                        self._last_hash = current_hash
                        
                        if result:
                            idea_id, is_new = result
                            if is_new:
                                self.data_captured.emit(idea_id)
                        return
                except Exception as e:
                    logging.error(f"Failed to process image from clipboard: {e}", exc_info=True)
                    return

            # --- 处理文本 (含网址识别) ---
            if mime_data.hasText():
                try:
                    text = mime_data.text()
                    if not text.strip(): 
                        return
                    
                    current_hash = self._hash_data(text)
                    if current_hash is None:
                        logging.error("Failed to hash text, skipping clipboard processing")
                        return
                        
                    if current_hash != self._last_hash:
                        
                        # 【智能打标逻辑:网址】
                        stripped_text = text.strip()
                        if stripped_text.startswith(('http://', 'https://')):
                            extra_tags.add("网址")
                            extra_tags.add("链接")
                        
                        result = self.db.add_clipboard_item(item_type='text', content=text, category_id=category_id)
                        self._last_hash = current_hash
                        
                        if result:
                            idea_id, is_new = result
                            if is_new:
                                # 【应用智能标签】
                                if extra_tags:
                                    try:
                                        self.db.add_tags_to_multiple_ideas([idea_id], list(extra_tags))
                                    except Exception as e:
                                        logging.error(f"Failed to add tags to idea {idea_id}: {e}", exc_info=True)
                                self.data_captured.emit(idea_id)
                        return
                except Exception as e:
                    logging.error(f"Failed to process text from clipboard: {e}", exc_info=True)
                    return

        except Exception as e:
            logging.error(f"Unexpected error in clipboard processing: {e}", exc_info=True)
```

## 文件: services\clipboard_service.py

```python
# services/clipboard_service.py
import os
from PyQt5.QtCore import QObject, pyqtSignal, QBuffer
from PyQt5.QtGui import QImage

class ClipboardService(QObject):
    data_captured = pyqtSignal()

    def __init__(self, idea_repo, tag_repo, hash_calculator):
        super().__init__()
        self.idea_repo = idea_repo
        self.tag_repo = tag_repo
        self.hasher = hash_calculator

    def process_mime_data(self, mime_data, category_id=None):
        try:
            if mime_data.hasUrls():
                urls = mime_data.urls()
                filepaths = [url.toLocalFile() for url in urls if url.isLocalFile()]
                if filepaths:
                    content = ";".join(filepaths)
                    self._save_clipboard_item('file', content, category_id=category_id)
                    return

            if mime_data.hasImage():
                image = mime_data.imageData()
                buffer = QBuffer()
                buffer.open(QBuffer.ReadWrite)
                image.save(buffer, "PNG")
                image_bytes = buffer.data()
                self._save_clipboard_item('image', '[Image Data]', data_blob=image_bytes, category_id=category_id)
                return

            if mime_data.hasText():
                text = mime_data.text()
                if text:
                    self._save_clipboard_item('text', text, category_id=category_id)
                    return
        except Exception as e:
            import logging
            logging.error(f"Failed to process MIME data in clipboard service: {e}", exc_info=True)

    def _save_clipboard_item(self, item_type, content, data_blob=None, category_id=None):
        content_hash = self.hasher.compute(content, data_blob)
        if not content_hash:
            return

        existing_idea = self.idea_repo.find_by_hash(content_hash)

        if existing_idea:
            idea_id = existing_idea[0]
            self.idea_repo.update_timestamp(idea_id)
            return idea_id
        else:
            if item_type == 'text':
                title = content.strip().split('\\n')[0][:50]
            elif item_type == 'image':
                title = "[图片]"
            elif item_type == 'file':
                title = f"[文件] {os.path.basename(content.split(';')[0])}"
            else:
                title = "未命名"
            
            idea_id = self.idea_repo.add(
                title=title,
                content=content,
                color=None, # Use default color
                category_id=category_id,
                item_type=item_type,
                data_blob=data_blob,
                content_hash=content_hash
            )
            
            # Automatically add "剪贴板" tag
            existing_tags = self.tag_repo.get_tags_for_idea(idea_id)
            if "剪贴板" not in existing_tags:
                existing_tags.append("剪贴板")
                self.tag_repo.update_tags_for_idea(idea_id, existing_tags)
            
            self.data_captured.emit()
            return idea_id
```

## 文件: services\hash_calculator.py

```python
# services/hash_calculator.py
import hashlib

class HashCalculator:
    def compute(self, content, data_blob=None):
        """
        Computes the SHA256 hash for the given content.
        """
        hasher = hashlib.sha256()
        if data_blob:
            hasher.update(data_blob)
        elif content:
            hasher.update(str(content).encode('utf-8'))
        else:
            return None
        return hasher.hexdigest()
```

## 文件: services\idea_service.py

```python
# -*- coding: utf-8 -*-
# services/idea_service.py
from core.config import COLORS
from core.signals import app_signals
import hashlib
import os

class IdeaService:
    def __init__(self, idea_repo, category_repo, tag_repo):
        self.idea_repo = idea_repo
        self.category_repo = category_repo
        self.tag_repo = tag_repo
        self.conn = self.idea_repo.db.conn # 用于暴露给需要直接访问 conn 的旧代码(如 AdvancedTagSelector)

    # --- Idea Operations ---
    def get_ideas(self, search, f_type, f_val, page=1, page_size=100, tag_filter=None, filter_criteria=None):
        return self.idea_repo.get_list_by_filter(search, f_type, f_val, page, page_size, tag_filter, filter_criteria)

    def get_ideas_count(self, search, f_type, f_val, tag_filter=None, filter_criteria=None):
        return self.idea_repo.get_count_by_filter(search, f_type, f_val, tag_filter, filter_criteria)

    # --- Smart Caching Methods ---
    def get_metadata(self, search, f_type, f_val):
        return self.idea_repo.get_metadata_by_filter(search, f_type, f_val)
        
    def get_details(self, id_list):
        return self.idea_repo.get_details_by_ids(id_list)
    # -----------------------------

    def get_idea(self, iid, include_blob=False):
        return self.idea_repo.get_by_id(iid, include_blob)

    def add_idea(self, title, content, color, tags, category_id=None, item_type='text', data_blob=None):
        if color is None: color = COLORS['default_note']
        iid = self.idea_repo.add(title, content, color, category_id, item_type, data_blob)
        self.tag_repo.update_tags(iid, tags)
        app_signals.data_changed.emit()
        return iid

    def update_idea(self, iid, title, content, color, tags, category_id=None, item_type='text', data_blob=None):
        self.idea_repo.update(iid, title, content, color, category_id, item_type, data_blob)
        self.tag_repo.update_tags(iid, tags)
        app_signals.data_changed.emit()

    def update_field(self, iid, field, value):
        self.idea_repo.update_field(iid, field, value)
        app_signals.data_changed.emit()

    def toggle_field(self, iid, field):
        self.idea_repo.toggle_field(iid, field)
        app_signals.data_changed.emit()

    def set_favorite(self, iid, state):
        self.idea_repo.update_field(iid, 'is_favorite', 1 if state else 0)
        app_signals.data_changed.emit()

    def set_deleted(self, iid, state):
        val = 1 if state else 0
        self.idea_repo.update_field(iid, 'is_deleted', val)
        if state:
            self.idea_repo.update_field(iid, 'category_id', None)
            self.idea_repo.update_field(iid, 'color', COLORS['trash'])
        else:
            self.idea_repo.update_field(iid, 'color', COLORS['uncategorized'])
        app_signals.data_changed.emit()

    def set_rating(self, iid, rating):
        self.idea_repo.update_field(iid, 'rating', rating)
        app_signals.data_changed.emit()

    def delete_permanent(self, iid):
        self.idea_repo.delete_permanent(iid)
        app_signals.data_changed.emit()

    def move_category(self, iid, cat_id):
        self.idea_repo.update_field(iid, 'category_id', cat_id)
        self.idea_repo.update_field(iid, 'is_deleted', 0)
        # 如果移动到分类，应应用分类颜色（略）
        app_signals.data_changed.emit()

    def get_lock_status(self, ids):
        return self.idea_repo.get_lock_status(ids)

    def set_locked(self, ids, state):
        self.idea_repo.set_locked(ids, state)
        app_signals.data_changed.emit()

    def get_filter_stats(self, search, f_type, f_val):
        return self.idea_repo.get_filter_stats(search, f_type, f_val)
        
    def empty_trash(self):
        c = self.idea_repo.db.get_cursor()
        c.execute('DELETE FROM idea_tags WHERE idea_id IN (SELECT id FROM ideas WHERE is_deleted=1)')
        c.execute('DELETE FROM ideas WHERE is_deleted=1')
        self.idea_repo.db.commit()
        app_signals.data_changed.emit()

    # --- Clipboard Logic (Ported from db_manager) ---
    def add_clipboard_item(self, item_type, content, data_blob=None, category_id=None):
        hasher = hashlib.sha256()
        if item_type == 'text' or item_type == 'file':
            hasher.update(content.encode('utf-8'))
        elif item_type == 'image' and data_blob:
            hasher.update(data_blob)
        content_hash = hasher.hexdigest()

        existing = self.idea_repo.find_by_hash(content_hash)
        if existing:
            # 【修复】使用专门的时间戳更新方法
            self.idea_repo.update_timestamp(existing[0])
            app_signals.data_changed.emit()
            return existing[0], False
        else:
            if item_type == 'text': title = content.strip().split('\n')[0][:50]
            elif item_type == 'image': title = "[图片]"
            elif item_type == 'file': title = f"[文件] {os.path.basename(content.split(';')[0])}"
            else: title = "未命名"
            
            iid = self.idea_repo.add(title, content, COLORS['default_note'], category_id, item_type, data_blob, content_hash)
            app_signals.data_changed.emit()
            return iid, True

    # --- Tag Operations ---
    def get_tags(self, iid):
        return self.tag_repo.get_by_idea(iid)
    
    def get_all_tags(self):
        return self.tag_repo.get_all()

    def add_tags_to_multiple_ideas(self, idea_ids, tags):
        self.tag_repo.add_to_multiple(idea_ids, tags)
        app_signals.data_changed.emit()
        
    def remove_tag_from_multiple_ideas(self, idea_ids, tag_name):
        self.tag_repo.remove_from_multiple(idea_ids, tag_name)
        app_signals.data_changed.emit()
        
    def get_top_tags(self):
        return self.tag_repo.get_top_tags()

    # --- Category Operations ---
    def get_categories(self):
        return self.category_repo.get_all()

    def get_partitions_tree(self):
        return self.category_repo.get_tree()

    def get_counts(self):
        return self.idea_repo.get_counts()
        
    def add_category(self, name, parent_id=None):
        self.category_repo.add(name, parent_id)
        app_signals.data_changed.emit()
        
    def rename_category(self, cat_id, new_name):
        self.category_repo.rename(cat_id, new_name)
        app_signals.data_changed.emit()
        
    def delete_category(self, cat_id):
        self.category_repo.delete(cat_id)
        app_signals.data_changed.emit()
        
    def set_category_color(self, cat_id, color):
        self.category_repo.set_color(cat_id, color)
        app_signals.data_changed.emit()
        
    def set_category_preset_tags(self, cat_id, tags):
        self.category_repo.set_preset_tags(cat_id, tags)
        app_signals.data_changed.emit()
        
    def get_category_preset_tags(self, cat_id):
        return self.category_repo.get_preset_tags(cat_id)
        
    def apply_preset_tags_to_category_items(self, cat_id, tags_list):
        # 复杂逻辑：先找 idea ids，再加 tags
        c = self.idea_repo.db.get_cursor()
        c.execute('SELECT id FROM ideas WHERE category_id=? AND is_deleted=0', (cat_id,))
        ids = [r[0] for r in c.fetchall()]
        self.tag_repo.add_to_multiple(ids, tags_list)
        app_signals.data_changed.emit()
        
    def save_category_order(self, update_list):
        self.category_repo.save_order(update_list)
        app_signals.data_changed.emit()
```

## 文件: services\preview_service.py

```python
﻿# -*- coding: utf-8 -*-
# services/preview_service.py

import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, 
                             QWidget, QDesktopWidget, QShortcut, QPushButton, 
                             QGraphicsDropShadowEffect, QSizePolicy, QStyle)
from PyQt5.QtCore import Qt, QPoint, QSize, QEvent, QRect
from PyQt5.QtGui import QPixmap, QKeySequence, QFont, QColor, QPainter, QIcon, QPalette

from core.config import COLORS, STYLES
# 关键修改 1: 引入支持语法高亮的 RichTextEdit
from ui.components.rich_text_edit import RichTextEdit

class ScalableImageLabel(QLabel):
    """
    智能图片标签：
    支持随窗口大小变化自动缩放图片，保持比例并居中。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._original_pixmap = None
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(200, 200)

    def set_pixmap(self, pixmap):
        self._original_pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        if not self._original_pixmap or self._original_pixmap.isNull():
            text = "无法加载图片"
            painter = QPainter(self)
            painter.setPen(QColor("#666"))
            painter.drawText(self.rect(), Qt.AlignCenter, text)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # 计算缩放后的尺寸，保持纵横比
        scaled_size = self._original_pixmap.size().scaled(self.size(), Qt.KeepAspectRatio)
        
        # 计算居中位置
        x = (self.width() - scaled_size.width()) // 2
        y = (self.height() - scaled_size.height()) // 2
        
        # 绘制
        target_rect = QRect(x, y, scaled_size.width(), scaled_size.height())
        painter.drawPixmap(target_rect, self._original_pixmap)

class PreviewDialog(QDialog):
    """
    增强版预览窗口：支持拖动、最大化、最小化、自适应缩放、多图切换
    """
    def __init__(self, mode, data_list, parent=None):
        """
        :param mode: 'text' 或 'gallery' (图片集合)
        :param data_list: 数据列表。如果是文本则是 [text_str]，如果是画廊则是 [path1, path2, blob...]
        """
        super().__init__(parent)
        # 普通无边框窗口
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose) 
        
        # 状态变量
        self.mode = mode
        self.data_list = data_list
        self.current_index = 0
        self._drag_pos = None
        
        self._init_ui()
        self._setup_shortcuts()
        self._load_current_content()

    def _init_ui(self):
        # 1. 根布局
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        
        # 2. 主容器
        self.container = QWidget()
        self.container.setObjectName("PreviewContainer")
        # 关键修改 2: 注入 STYLES['dialog'] 以获取全局滚动条和基础样式
        self.container.setStyleSheet(f"""
            QWidget#PreviewContainer {{
                background-color: {COLORS['bg_dark']};
                border: 1px solid {COLORS['bg_light']};
                border-radius: 8px;
            }}
        """ + STYLES.get('dialog', ''))
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.container.setGraphicsEffect(shadow)
        
        root_layout.addWidget(self.container)
        
        # 3. 内容布局
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 4. 标题栏
        self.title_bar = self._create_title_bar()
        self.main_layout.addWidget(self.title_bar)
        
        # 5. 内容显示区域
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(15, 5, 15, 5)
        self.main_layout.addWidget(self.content_area, 1)
        
        # 初始化显示控件
        self.text_edit = None
        self.image_label = None
        
        if self.mode == 'text':
            self._init_text_widget()
        else:
            self._init_image_widget()
            
        # 6. 底部控制栏 (仅多图模式显示)
        self.control_bar = QWidget()
        ctrl_layout = QHBoxLayout(self.control_bar)
        ctrl_layout.setContentsMargins(20, 5, 20, 10)
        
        self.btn_prev = QPushButton("◀ 上一张")
        self.btn_next = QPushButton("下一张 ▶")
        
        btn_style = f"""
            QPushButton {{
                background-color: {COLORS['bg_mid']};
                border: 1px solid {COLORS['bg_light']};
                color: #ddd;
                padding: 6px 15px;
                border-radius: 4px;
            }}
            QPushButton:hover {{ background-color: {COLORS['primary']}; border-color: {COLORS['primary']}; color: white; }}
        """
        self.btn_prev.setStyleSheet(btn_style)
        self.btn_next.setStyleSheet(btn_style)
        
        self.btn_prev.clicked.connect(self._prev_image)
        self.btn_next.clicked.connect(self._next_image)
        
        ctrl_layout.addWidget(self.btn_prev)
        ctrl_layout.addStretch()
        
        # 提示文字
        hint = QLabel("按 [Space] 关闭 | [←/→] 切换")
        hint.setStyleSheet(f"color: {COLORS['text_sub']}; font-size: 11px;")
        ctrl_layout.addWidget(hint)
        
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.btn_next)
        
        self.main_layout.addWidget(self.control_bar)
        
        # 如果只有一张图或文本模式，隐藏控制栏
        if len(self.data_list) <= 1:
            self.control_bar.hide()

    def _init_text_widget(self):
        # 关键修改 3: 使用 RichTextEdit 替代 QTextEdit，支持语法高亮
        self.text_edit = RichTextEdit()
        self.text_edit.setReadOnly(True)
        # self.text_edit.setFont(QFont("Microsoft YaHei", 12)) # 字体通常由 RichTextEdit 内部管理或通过样式表设置
        
        # 关键修改 4: 强制深色样式 (三重保险: 样式表 + Palette)
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['bg_dark']};
                border: none;
                color: #eee;
                selection-background-color: {COLORS['primary']}60;
                padding: 10px;
                font-family: "Microsoft YaHei", Consolas, "Courier New", monospace;
                font-size: 14px;
            }}
        """)
        
        # 设置底层调色板，防止样式表失效时回退到白色
        p = self.text_edit.palette()
        p.setColor(QPalette.Base, QColor(COLORS['bg_dark']))
        p.setColor(QPalette.Text, QColor('#eee'))
        self.text_edit.setPalette(p)

        self.content_layout.addWidget(self.text_edit)
        self.resize(1130, 740)

    def _init_image_widget(self):
        self.image_label = ScalableImageLabel()
        self.content_layout.addWidget(self.image_label)
        self.resize(1130, 740)

    def _create_title_bar(self):
        title_bar = QWidget()
        title_bar.setFixedHeight(36)
        title_bar.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_mid']};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border-bottom: 1px solid {COLORS['bg_light']};
            }}
        """)
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(10, 0, 10, 0)
        
        self.title_label = QLabel("预览")
        self.title_label.setStyleSheet("font-weight: bold; color: #ddd; border: none; background: transparent;")
        layout.addWidget(self.title_label)
        
        layout.addStretch()
        
        btn_style = "QPushButton { background: transparent; border: none; color: #aaa; border-radius: 4px; font-family: Arial; font-size: 14px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); color: white; }"
        
        btn_min = QPushButton("─")
        btn_min.setFixedSize(28, 28)
        btn_min.setStyleSheet(btn_style)
        btn_min.clicked.connect(self.showMinimized)
        
        self.btn_max = QPushButton("□")
        self.btn_max.setFixedSize(28, 28)
        self.btn_max.setStyleSheet(btn_style)
        self.btn_max.clicked.connect(self._toggle_maximize)
        
        btn_close = QPushButton("×")
        btn_close.setFixedSize(28, 28)
        btn_close.setStyleSheet("QPushButton { background: transparent; border: none; color: #aaa; border-radius: 4px; font-size: 16px; } QPushButton:hover { background-color: #e74c3c; color: white; }")
        btn_close.clicked.connect(self.close)
        
        layout.addWidget(btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(btn_close)
        return title_bar

    def _load_current_content(self):
        """核心方法：根据 index 加载数据"""
        if not self.data_list: return
        
        current_data = self.data_list[self.current_index]
        total = len(self.data_list)
        
        # 更新标题
        if self.mode == 'text':
            self.title_label.setText("📝 文本预览")
            # 关键修改 5: 使用 setPlainText 保持源码格式，配合 RichTextEdit 实现高亮
            if self.text_edit:
                self.text_edit.setPlainText(str(current_data))
        else:
            self.title_label.setText(f"🖼️ 图片预览 [{self.current_index + 1}/{total}]")
            self._show_image(current_data)
            
        # 居中窗口 (仅在第一次显示时)
        if not self.isVisible():
            self._center_on_screen()

    def _show_image(self, data):
        """显示单张图片，支持路径或二进制数据"""
        pixmap = QPixmap()
        
        if isinstance(data, bytes):
            pixmap.loadFromData(data)
        elif isinstance(data, str) and os.path.exists(data):
            pixmap.load(data)
        
        self.image_label.set_pixmap(pixmap)

    def _center_on_screen(self):
        screen = QDesktopWidget().screenNumber(QDesktopWidget().cursor().pos())
        center = QDesktopWidget().screenGeometry(screen).center()
        self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.btn_max.setText("□")
            self.layout().setContentsMargins(10, 10, 10, 10)
        else:
            self.showMaximized()
            self.btn_max.setText("❐")
            self.layout().setContentsMargins(0, 0, 0, 0)

    def _prev_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            self._load_current_content()

    def _next_image(self):
        if self.current_index < len(self.data_list) - 1:
            self.current_index += 1
            self._load_current_content()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key_Escape), self, self.close)
        QShortcut(QKeySequence(Qt.Key_Space), self, self.close)
        
        # 左右键切换图片
        QShortcut(QKeySequence(Qt.Key_Left), self, self._prev_image)
        QShortcut(QKeySequence(Qt.Key_Right), self, self._next_image)

    # --- 拖动逻辑 ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.y() < 50:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            if not self.isMaximized():
                self.move(event.globalPos() - self._drag_pos)
                event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)
        
    def mouseDoubleClickEvent(self, event):
        if event.y() < 50:
            self._toggle_maximize()

class PreviewService:
    def __init__(self, db_manager, parent_window):
        self.db = db_manager
        self.parent = parent_window
        self.current_dialog = None

    def toggle_preview(self, selected_ids):
        if self.current_dialog and self.current_dialog.isVisible():
            self.current_dialog.close()
            self.current_dialog = None
            return

        if not selected_ids: return
        if len(selected_ids) != 1:
            self._show_tooltip('⚠️ 只能预览单个项目')
            return
            
        idea_id = list(selected_ids)[0]
        self._open_preview(idea_id)

    def _open_preview(self, idea_id):
        idea = self.db.get_idea(idea_id, include_blob=True)
        if not idea: return
        
        # 字段: 2=content, 10=item_type, 11=data_blob
        content = idea[2]
        try:
            item_type = idea[10] if len(idea) > 10 else 'text'
            data_blob = idea[11] if len(idea) > 11 else None
        except IndexError:
            item_type = 'text'
            data_blob = None
            
        mode = 'text'
        data_list = []
        
        # 1. 数据库 Blob 图片
        if item_type == 'image' and data_blob:
            mode = 'gallery'
            data_list = [data_blob]
        
        # 2. 文本内容分析 (核心修复逻辑)
        elif content:
            # 检查是否包含分号 (多文件路径特征)
            potential_paths = content.split(';')
            valid_images = []
            img_exts = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.ico', '.svg', '.tif'}
            
            for p in potential_paths:
                p = p.strip()
                if p and os.path.exists(p):
                    ext = os.path.splitext(p)[1].lower()
                    if ext in img_exts:
                        valid_images.append(p)
            
            if valid_images:
                mode = 'gallery'
                data_list = valid_images
            else:
                mode = 'text'
                data_list = [content]
        else:
            self._show_tooltip('⚠️ 内容为空')
            return
            
        # 创建窗口
        self.current_dialog = PreviewDialog(mode, data_list, self.parent)
        self.current_dialog.finished.connect(self._on_dialog_closed)
        self.current_dialog.show()

    def _on_dialog_closed(self):
        self.current_dialog = None

    def _show_tooltip(self, msg):
        if hasattr(self.parent, '_show_tooltip'):
            self.parent._show_tooltip(msg, 1500)
```

## 文件: services\selection_service.py

```python
﻿# services/selection_service.py
from PyQt5.QtCore import QObject, pyqtSignal, QPoint
from pynput import mouse
import threading

class SelectionMonitor(QObject):
    # 定义信号：当检测到可能的划选动作时，发送鼠标当前的坐标
    text_selected = pyqtSignal(QPoint)

    def __init__(self):
        super().__init__()
        self.press_pos = None
        self._is_running = True

    def start(self):
        # 在独立线程中启动监听，避免阻塞主界面
        self.thread = threading.Thread(target=self._run_listener, daemon=True)
        self.thread.start()

    def _run_listener(self):
        with mouse.Listener(on_click=self._on_click) as listener:
            listener.join()

    def _on_click(self, x, y, button, pressed):
        if button == mouse.Button.left:
            if pressed:
                # 记录按下时的位置
                self.press_pos = (x, y)
            else:
                # 鼠标松开时，计算移动距离
                if self.press_pos:
                    dx = abs(x - self.press_pos[0])
                    dy = abs(y - self.press_pos[1])
                    # 如果移动距离超过 15 像素，判定为划选动作
                    if dx > 15 or dy > 15:
                        self.text_selected.emit(QPoint(int(x), int(y)))
                self.press_pos = None
```

## 文件: services\statistics_service.py

```python
﻿# application/services/statistics_service.py
import sqlite3
from typing import Dict, Any

class StatisticsService:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def get_sidebar_counts(self) -> Dict[str, Any]:
        """获取侧边栏统计数据"""
        c = self._connection.cursor()
        d = {}
        queries = {
            'all': "is_deleted=0 OR is_deleted IS NULL",
            'today': "(is_deleted=0 OR is_deleted IS NULL) AND date(updated_at,'localtime')=date('now','localtime')",
            'uncategorized': "(is_deleted=0 OR is_deleted IS NULL) AND category_id IS NULL",
            'untagged': "(is_deleted=0 OR is_deleted IS NULL) AND id NOT IN (SELECT idea_id FROM idea_tags)",
            'bookmark': "(is_deleted=0 OR is_deleted IS NULL) AND is_favorite=1",
            'trash': "is_deleted=1"
        }
        for k, v in queries.items():
            c.execute(f"SELECT COUNT(*) FROM ideas WHERE {v}")
            d[k] = c.fetchone()[0]
            
        c.execute("SELECT category_id, COUNT(*) FROM ideas WHERE (is_deleted=0 OR is_deleted IS NULL) GROUP BY category_id")
        d['categories'] = dict(c.fetchall())
        return d

    def get_filter_panel_stats(self, search_text: str = '', filter_type: str = 'all', 
                               filter_value: Any = None) -> Dict[str, Any]:
        """获取筛选面板统计数据"""
        c = self._connection.cursor()
        stats = {
            'stars': {},
            'colors': {},
            'types': {},
            'tags': [],
            'date_create': {}
        }
        
        where_clauses = ["1=1"]
        params = []
        
        if filter_type == 'trash':
            where_clauses.append("i.is_deleted=1")
        else:
            where_clauses.append("(i.is_deleted=0 OR i.is_deleted IS NULL)")
            
        if filter_type == 'category':
            if filter_value is None:
                where_clauses.append("i.category_id IS NULL")
            else:
                where_clauses.append("i.category_id=?")
                params.append(filter_value)
        elif filter_type == 'today':
            where_clauses.append("date(i.updated_at,'localtime')=date('now','localtime')")
        elif filter_type == 'untagged':
            where_clauses.append("i.id NOT IN (SELECT idea_id FROM idea_tags)")
        elif filter_type == 'bookmark':
            where_clauses.append("i.is_favorite=1")
        
        if search_text:
            where_clauses.append("(i.title LIKE ? OR i.content LIKE ?)")
            params.extend([f'%{search_text}%', f'%{search_text}%'])
            
        where_str = " AND ".join(where_clauses)
        
        # 星级统计
        c.execute(f"SELECT i.rating, COUNT(*) FROM ideas i WHERE {where_str} GROUP BY i.rating", params)
        stats['stars'] = dict(c.fetchall())

        # 颜色统计
        c.execute(f"SELECT i.color, COUNT(*) FROM ideas i WHERE {where_str} GROUP BY i.color", params)
        stats['colors'] = dict(c.fetchall())

        # 类型统计
        c.execute(f"SELECT i.item_type, COUNT(*) FROM ideas i WHERE {where_str} GROUP BY i.item_type", params)
        stats['types'] = dict(c.fetchall())

        # 标签统计
        tag_sql = f"""
            SELECT t.name, COUNT(it.idea_id) as cnt
            FROM tags t
            JOIN idea_tags it ON t.id = it.tag_id
            JOIN ideas i ON it.idea_id = i.id
            WHERE {where_str}
            GROUP BY t.id
            ORDER BY cnt DESC
        """
        c.execute(tag_sql, params)
        stats['tags'] = c.fetchall()

        # 日期统计
        base_date_sql = f"SELECT COUNT(*) FROM ideas i WHERE {where_str} AND "
        c.execute(base_date_sql + "date(i.created_at, 'localtime') = date('now', 'localtime')", params)
        stats['date_create']['today'] = c.fetchone()[0]
        c.execute(base_date_sql + "date(i.created_at, 'localtime') = date('now', '-1 day', 'localtime')", params)
        stats['date_create']['yesterday'] = c.fetchone()[0]
        c.execute(base_date_sql + "date(i.created_at, 'localtime') >= date('now', '-6 days', 'localtime')", params)
        stats['date_create']['week'] = c.fetchone()[0]
        c.execute(base_date_sql + "strftime('%Y-%m', i.created_at, 'localtime') = strftime('%Y-%m', 'now', 'localtime')", params)
        stats['date_create']['month'] = c.fetchone()[0]

        return stats

    def empty_trash(self) -> None:
        """清空回收站"""
        c = self._connection.cursor()
        c.execute('DELETE FROM idea_tags WHERE idea_id IN (SELECT id FROM ideas WHERE is_deleted=1)')
        c.execute('DELETE FROM ideas WHERE is_deleted=1')
        self._connection.commit()
```

## 文件: services\tag_service.py

```python
﻿# application/services/tag_service.py
from typing import List, Tuple
from infrastructure.repositories.tag_repository import TagRepository

class TagService:
    def __init__(self, tag_repository: TagRepository):
        self._tag_repo = tag_repository

    def get_all_tags(self) -> List[str]:
        """获取所有标签名称"""
        tags = self._tag_repo.get_all()
        return [tag.name for tag in tags]

    def get_tags_for_idea(self, idea_id: int) -> List[str]:
        """获取指定笔记的标签"""
        tags = self._tag_repo.get_by_idea_id(idea_id)
        return [tag.name for tag in tags]

    def get_top_tags(self, limit: int = 5) -> List[Tuple[str, int]]:
        """获取热门标签"""
        return self._tag_repo.get_top_tags(limit)

    def rename_tag(self, old_name: str, new_name: str) -> None:
        """重命名标签"""
        if not new_name or not new_name.strip():
            raise ValueError("标签名不能为空")
        self._tag_repo.rename(old_name.strip(), new_name.strip())

    def delete_tag(self, tag_name: str) -> None:
        """删除标签"""
        if not tag_name:
            raise ValueError("标签名不能为空")
        self._tag_repo.delete(tag_name.strip())

    def get_union_tags_for_ideas(self, idea_ids: List[int]) -> List[str]:
        """获取多个笔记的并集标签"""
        if not idea_ids:
            return []
        return self._tag_repo.get_union_tags_for_ideas(idea_ids)

    def get_all_tags_with_counts(self) -> List[Tuple[str, int]]:
        """获取所有标签及其使用次数"""
        return self._tag_repo.get_all_tags_with_counts()
```

## 文件: services\__init__.py

```python
﻿# -*- coding: utf-8 -*-

```

## 文件: ui\action_popup.py

```python
# -*- coding: utf-8 -*-
# ui/action_popup.py

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QGraphicsDropShadowEffect, QApplication
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPoint, QSize
from PyQt5.QtGui import QCursor, QColor
from core.config import COLORS
from ui.common_tags import CommonTags
from ui.writing_animation import WritingAnimationWidget
from ui.utils import create_svg_icon

class ActionPopup(QWidget):
    request_favorite = pyqtSignal(int)
    request_tag_toggle = pyqtSignal(int, str)
    request_manager = pyqtSignal()

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service 
        self.current_idea_id = None
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 【关键修复】设置焦点策略，使其能捕获焦点
        self.setFocusPolicy(Qt.StrongFocus)
        
        self._init_ui()
        
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._animate_hide)

    def _init_ui(self):
        self.container = QWidget(self)
        self.container.setStyleSheet(f"""
            QWidget {{
                background-color: #2D2D2D;
                border: 1px solid #444;
                border-radius: 18px;
            }}
        """)
        
        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        self.success_animation = WritingAnimationWidget()
        layout.addWidget(self.success_animation)
        
        line = QLabel("|")
        line.setStyleSheet("color: #555; border:none; background: transparent;")
        layout.addWidget(line)

        self.btn_fav = QPushButton()
        self.btn_fav.setToolTip("收藏")
        self.btn_fav.setFixedSize(20, 20)
        self.btn_fav.setCursor(Qt.PointingHandCursor)
        self.btn_fav.setStyleSheet("background: transparent; border: none;")
        self.btn_fav.clicked.connect(self._on_fav_clicked)
        layout.addWidget(self.btn_fav)

        self.common_tags_bar = CommonTags(self.service) 
        self.common_tags_bar.tag_clicked.connect(self._on_quick_tag_clicked)
        self.common_tags_bar.manager_requested.connect(self._on_manager_clicked)
        self.common_tags_bar.refresh_requested.connect(self._adjust_size_dynamically)
        
        layout.addWidget(self.common_tags_bar)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.container.setGraphicsEffect(shadow)

    def _adjust_size_dynamically(self):
        if self.isVisible():
            self.container.adjustSize()
            self.resize(self.container.size() + QSize(10, 10))

    def _refresh_ui_state(self):
        if not self.current_idea_id: return
        idea_data = self.service.get_idea(self.current_idea_id)
        if not idea_data: return
        # 使用字典访问，更安全
        is_favorite = idea_data['is_favorite'] == 1
        active_tags = self.service.get_tags(self.current_idea_id)
        self.common_tags_bar.reload_tags(active_tags)
        if is_favorite: self.btn_fav.setIcon(create_svg_icon("star_filled.svg", COLORS['warning']))
        else: self.btn_fav.setIcon(create_svg_icon("star.svg", "#BBB"))
        self.container.adjustSize()
        self.resize(self.container.size() + QSize(10, 10))

    def show_at_mouse(self, idea_id):
        self.current_idea_id = idea_id
        self.success_animation.start()
        self._refresh_ui_state()
        cursor_pos = QCursor.pos()
        screen_geometry = QApplication.screenAt(cursor_pos).geometry()
        x = cursor_pos.x() - self.width() // 2
        y = cursor_pos.y() - self.height() - 20
        if x < screen_geometry.left(): x = screen_geometry.left()
        elif x + self.width() > screen_geometry.right(): x = screen_geometry.right() - self.width()
        if y < screen_geometry.top(): y = cursor_pos.y() + 25
        if y + self.height() > screen_geometry.bottom(): y = screen_geometry.bottom() - self.height()
        self.move(x, y)
        
        self.show()
        # 【关键修复】激活并强制获取焦点，触发 focusOutEvent 的必要条件
        self.activateWindow()
        self.setFocus()
        
        self.hide_timer.start(3500)

    def _on_fav_clicked(self):
        if self.current_idea_id:
            self.request_favorite.emit(self.current_idea_id)
            self._refresh_ui_state()
            self.hide_timer.start(1500)

    def _on_quick_tag_clicked(self, tag_name):
        if self.current_idea_id:
            self.request_tag_toggle.emit(self.current_idea_id, tag_name)
            self._refresh_ui_state()
            self.hide_timer.start(3500)

    def _on_manager_clicked(self):
        self.request_manager.emit()
        self.hide() 

    def _animate_hide(self):
        self.hide()

    # 失去焦点时立即关闭
    def focusOutEvent(self, event):
        self._animate_hide()
        super().focusOutEvent(event)

    def enterEvent(self, event):
        self.hide_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        # 鼠标移出后也开始计时，防止一直不关闭
        self.hide_timer.start(1500)
        super().leaveEvent(event)
```

## 文件: ui\advanced_tag_selector.py

```python
# -*- coding: utf-8 -*-
# ui/advanced_tag_selector.py

from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLineEdit, QScrollArea, QLabel, QLayout, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QRect, QSize
from PyQt5.QtGui import QCursor, QColor
from core.config import COLORS

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super(FlowLayout, self).__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margin = self.contentsMargins()
        size += QSize(margin.left() + margin.right(), margin.top() + margin.bottom())
        return size

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        spacing = self.spacing()

        for item in self.itemList:
            wid = item.widget()
            spaceX = spacing + wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Horizontal)
            spaceY = spacing + wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Vertical)
            
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())

        return y + lineHeight - rect.y()

class AdvancedTagSelector(QWidget):
    """
    功能强大的悬浮标签选择面板
    支持两种模式：
    1. 绑定模式 (传入 idea_id): 直接修改数据库，即时保存
    2. 选择模式 (传入 initial_tags): 仅作为选择器，返回结果，不直接修改数据库
    """
    tags_confirmed = pyqtSignal(list)

    # 【核心修改】增加 initial_tags 参数，允许传入初始标签列表
    def __init__(self, db, idea_id=None, initial_tags=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.idea_id = idea_id
        
        # 初始化选中状态
        self.selected_tags = set()
        if initial_tags:
            self.selected_tags = set(initial_tags)
            
        self.tag_buttons = {} 
        self._is_closing = False 

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self._init_ui()
        self._load_tags()
        
        QApplication.instance().focusChanged.connect(self._on_focus_changed)

    def _init_ui(self):
        container = QWidget()
        container.setObjectName("mainContainer")
        container.setStyleSheet(f"""
            #mainContainer {{
                background-color: #1E1E1E; 
                border: 1px solid #333;
                border-radius: 8px;
                color: #EEE;
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索或新建...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #2D2D2D; 
                border: none;
                border-bottom: 1px solid #444;
                border-radius: 4px; 
                padding: 8px; 
                font-size: 13px; 
                color: #DDD;
            }}
            QLineEdit:focus {{ border-bottom: 1px solid {COLORS['primary']}; }}
        """)
        self.search_input.textChanged.connect(self._filter_tags)
        self.search_input.returnPressed.connect(self._on_search_return)
        layout.addWidget(self.search_input)

        self.recent_label = QLabel("最近使用")
        self.recent_label.setStyleSheet("color: #888; font-size: 12px; font-weight: bold; margin-top: 5px;")
        layout.addWidget(self.recent_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QWidget { background: transparent; }
            QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0px; }
            QScrollBar::handle:vertical { background: #444; border-radius: 3px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #555; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)
        
        self.scroll_content = QWidget()
        self.flow_layout = FlowLayout(self.scroll_content, margin=0, spacing=8)
        
        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)
        
        self.setFixedSize(360, 450)

    def _load_tags(self):
        # 如果有 idea_id，从数据库加载该 idea 的标签并合并到当前选中
        if self.idea_id:
            self.selected_tags = set(self.db.get_tags(self.idea_id))
        
        c = self.db.conn.cursor()
        c.execute('''
            SELECT t.name, COUNT(it.idea_id) as cnt, MAX(i.updated_at) as last_used
            FROM tags t
            LEFT JOIN idea_tags it ON t.id = it.tag_id
            LEFT JOIN ideas i ON it.idea_id = i.id AND i.is_deleted = 0
            GROUP BY t.id 
            ORDER BY last_used DESC, cnt DESC, t.name ASC
            LIMIT 20
        ''')
        all_tags = c.fetchall()
        
        self.recent_label.setText(f"最近使用 ({len(all_tags)})")

        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.tag_buttons.clear()

        for row in all_tags:
            name = row[0]
            count = row[1]
            self._create_tag_chip(name, count)

    def _create_tag_chip(self, name, count=0):
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setChecked(name in self.selected_tags)
        btn.setCursor(Qt.PointingHandCursor)
        
        btn.setProperty("tag_name", name)
        btn.setProperty("tag_count", count)
        
        self._update_chip_state(btn)
        
        btn.toggled.connect(lambda checked, b=btn, n=name: self._on_tag_toggled(b, n, checked))
        
        self.flow_layout.addWidget(btn)
        self.tag_buttons[name] = btn

    def _update_chip_state(self, btn):
        name = btn.property("tag_name")
        count = btn.property("tag_count")
        checked = btn.isChecked()
        
        icon = "✓" if checked else "🕒"
        text = f"{icon} {name}"
        if count > 0:
            text += f" ({count})"
        
        btn.setText(text)
        
        if checked:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['primary']};
                    color: white;
                    border: 1px solid {COLORS['primary']};
                    border-radius: 14px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-family: "Segoe UI", "Microsoft YaHei";
                }}
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2D2D2D;
                    color: #BBB;
                    border: 1px solid #444;
                    border-radius: 14px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-family: "Segoe UI", "Microsoft YaHei";
                }
                QPushButton:hover {
                    background-color: #383838;
                    border-color: #666;
                    color: white;
                }
            """)

    def _on_tag_toggled(self, button, name, checked):
        if checked:
            self.selected_tags.add(name)
        else:
            self.selected_tags.discard(name)
        self._update_chip_state(button)

    def _filter_tags(self):
        term = self.search_input.text().lower().strip()
        for name, btn in self.tag_buttons.items():
            if term in name.lower():
                btn.show()
            else:
                btn.hide()

    def _on_search_return(self):
        text = self.search_input.text().strip()
        if not text:
            self._handle_close()
            return

        found_existing = False
        for name, btn in self.tag_buttons.items():
            if name.lower() == text.lower():
                if not btn.isChecked():
                    btn.setChecked(True)
                found_existing = True
                break
        
        if not found_existing:
            self.selected_tags.add(text)
            self._create_tag_chip(text, 0)
            new_btn = self.tag_buttons.get(text)
            if new_btn: 
                new_btn.setChecked(True)
        
        self.search_input.clear()
        self._filter_tags()

    def _save_tags(self):
        """仅在绑定模式下保存到数据库"""
        # 【核心修改】如果 self.idea_id 为空，说明是纯选择模式，不进行数据库绑定操作
        if not self.idea_id:
            return

        c = self.db.conn.cursor()
        c.execute('DELETE FROM idea_tags WHERE idea_id = ?', (self.idea_id,))
        for tag_name in self.selected_tags:
            c.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (tag_name,))
            c.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
            result = c.fetchone()
            if result:
                tag_id = result[0]
                c.execute('INSERT INTO idea_tags (idea_id, tag_id) VALUES (?, ?)', (self.idea_id, tag_id))
        self.db.conn.commit()

    def _is_child_widget(self, widget):
        if widget is None: return False
        current = widget
        while current:
            if current is self: return True
            current = current.parent()
        return False

    def _on_focus_changed(self, old_widget, new_widget):
        if self._is_closing or not self.isVisible(): return
        if not self._is_child_widget(new_widget):
            self._handle_close()

    def _handle_close(self):
        if self._is_closing: return
        self._is_closing = True
        try:
            QApplication.instance().focusChanged.disconnect(self._on_focus_changed)
        except: pass
        
        self._save_tags()
        self.tags_confirmed.emit(list(self.selected_tags))
        self.close()

    def show_at_cursor(self):
        cursor_pos = QCursor.pos()
        screen_geo = QApplication.desktop().screenGeometry()
        x, y = cursor_pos.x() + 15, cursor_pos.y() + 15
        if x + self.width() > screen_geo.right(): x = cursor_pos.x() - self.width() - 15
        if y + self.height() > screen_geo.bottom(): y = screen_geo.bottom() - self.height() - 15
        self.move(x, y)
        self.show()
        self.activateWindow()
        self.search_input.setFocus()
```

## 文件: ui\ball.py

```python
# -*- coding: utf-8 -*-
# ui/ball.py
import math
import random
from PyQt5.QtWidgets import QWidget, QMenu
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer, QRectF
from PyQt5.QtGui import (QPainter, QColor, QPen, QBrush, 
                         QLinearGradient, QPainterPath, QPolygonF)
from core.settings import save_setting

class FloatingBall(QWidget):
    request_show_quick_window = pyqtSignal()
    request_show_main_window = pyqtSignal()
    request_quit_app = pyqtSignal()
    double_clicked = pyqtSignal()

    # --- 皮肤枚举 ---
    SKIN_MOCHA = 0   # 摩卡·勃艮第 (最新款)
    SKIN_CLASSIC = 1 # 经典黑金 (商务风)
    SKIN_ROYAL = 2   # 皇家蓝 (学术风)
    SKIN_MATCHA = 3  # 抹茶绿 (清新风) - 新增
    SKIN_OPEN = 4    # 摊开手稿 (沉浸风)

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window 
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(120, 120) # 尺寸加大适配各种款式
        self.setAcceptDrops(True)

        self.dragging = False
        self.is_hovering = False 
        
        # --- 状态与配置 ---
        self.current_skin = self.SKIN_MOCHA # 默认样式
        self.is_writing = False 
        self.write_timer = 0     
        self.offset = QPoint()
        
        # --- 动画物理量 ---
        self.time_step = 0.0
        self.pen_x = 0.0
        self.pen_y = 0.0
        self.pen_angle = -45.0 
        self.book_y = 0.0
        
        # 粒子
        self.particles = [] 

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_physics)
        self.timer.start(16) 

    def trigger_clipboard_feedback(self):
        """触发记录成功特效"""
        self.is_writing = True
        self.write_timer = 0

    def switch_skin(self, skin_id):
        """切换皮肤并刷新"""
        self.current_skin = skin_id
        self.update()

    def _update_physics(self):
        self.time_step += 0.05
        
        # 1. 待机悬浮 (Breathing)
        # 不同的书可能有不同的悬浮重心，但动画逻辑通用
        idle_pen_y = math.sin(self.time_step * 0.5) * 4
        idle_book_y = math.sin(self.time_step * 0.5 - 1.0) * 2
        
        target_pen_angle = -45
        target_pen_x = 0
        target_pen_y = idle_pen_y
        
        # 2. 书写动画 (Fluid Signature Flow) - 适用于所有皮肤
        if self.is_writing or self.is_hovering:
            self.write_timer += 1
            
            # 笔立起来
            target_pen_angle = -65 
            
            # 流畅的连笔字轨迹 (Lissajous)
            write_speed = self.time_step * 3.0
            flow_x = math.sin(write_speed) * 8     
            flow_y = math.cos(write_speed * 2) * 2 
            
            target_pen_x = flow_x
            target_pen_y = 5 + flow_y 
            idle_book_y = -3 # 书本上浮迎接

            if self.is_writing and self.write_timer > 90: 
                self.is_writing = False
        
        # 3. 物理平滑
        easing = 0.1
        self.pen_angle += (target_pen_angle - self.pen_angle) * easing
        self.pen_x += (target_pen_x - self.pen_x) * easing
        self.pen_y += (target_pen_y - self.pen_y) * easing
        self.book_y += (idle_book_y - self.book_y) * easing

        # 4. 粒子更新
        self._update_particles()
        self.update()

    def _update_particles(self):
        # 只有在书写时产生
        if (self.is_writing or self.is_hovering) and len(self.particles) < 15:
            if random.random() < 0.3:
                rad = math.radians(self.pen_angle)
                tip_len = 35 
                
                # 根据皮肤决定粒子颜色
                is_gold = random.random() > 0.3
                self.particles.append({
                    'x': self.width()/2 + self.pen_x - math.sin(rad)*tip_len,
                    'y': self.height()/2 + self.pen_y + math.cos(rad)*tip_len,
                    'vx': random.uniform(-0.5, 0.5),
                    'vy': random.uniform(0.5, 1.5),
                    'life': 1.0,
                    'size': random.uniform(1, 3),
                    'type': 'gold' if is_gold else 'ink'
                })

        alive = []
        for p in self.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['life'] -= 0.03
            p['size'] *= 0.96
            if p['life'] > 0:
                alive.append(p)
        self.particles = alive

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        
        # --- 1. 绘制阴影 (通用) ---
        p.save()
        p.translate(cx, cy + self.book_y + 15)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawEllipse(QRectF(-35, -10, 70, 20))
        p.restore()

        # --- 2. 绘制笔记本 (根据皮肤) ---
        p.save()
        p.translate(cx, cy + self.book_y)
        # 大部分本子微倾斜，除了摊开的
        if self.current_skin != self.SKIN_OPEN:
            p.rotate(-6)
            
        if self.current_skin == self.SKIN_MOCHA:
            self._draw_book_mocha(p)
        elif self.current_skin == self.SKIN_CLASSIC:
            self._draw_book_classic(p)
        elif self.current_skin == self.SKIN_ROYAL:
            self._draw_book_royal(p)
        elif self.current_skin == self.SKIN_MATCHA:
            self._draw_book_matcha(p)
        elif self.current_skin == self.SKIN_OPEN:
            self._draw_book_open(p)
        p.restore()

        # --- 3. 绘制笔的投影 ---
        p.save()
        p.translate(cx + self.pen_x + 5, cy + self.book_y - 2 + self.pen_y * 0.5) 
        p.rotate(self.pen_angle)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(40, 30, 20, 50)) 
        p.drawRoundedRect(QRectF(-4, -15, 8, 40), 4, 4)
        p.restore()

        # --- 4. 绘制钢笔 (统一使用高质感笔模型，但可微调色相) ---
        p.save()
        p.translate(cx + self.pen_x, cy + self.pen_y - 15)
        p.rotate(self.pen_angle)
        self._draw_universal_pen(p)
        p.restore()
        
        # --- 5. 绘制粒子 ---
        for pt in self.particles:
            alpha = int(255 * pt['life'])
            if pt['type'] == 'gold':
                c = QColor(255, 215, 0, alpha)
            else:
                # 墨水颜色根据皮肤适配
                if self.current_skin == self.SKIN_ROYAL:
                    c = QColor(25, 25, 112, int(alpha*0.8)) # 蓝墨水
                else:
                    c = QColor(60, 0, 0, int(alpha*0.8)) # 红/褐墨水
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawEllipse(QRectF(pt['x']-pt['size']/2, pt['y']-pt['size']/2, pt['size'], pt['size']))

    # ============================================
    #              DRAWING IMPL
    # ============================================

    def _draw_universal_pen(self, p):
        """一支高精度的钢笔，颜色根据皮肤自动适配"""
        w_pen, h_pen = 12, 46
        
        # 决定笔身颜色
        if self.current_skin == self.SKIN_ROYAL:
            # 皇家蓝配黑金笔
            c_light, c_mid, c_dark = QColor(60, 60, 70), QColor(20, 20, 25), QColor(0, 0, 0)
        elif self.current_skin == self.SKIN_CLASSIC:
            # 经典款配纯黑笔
            c_light, c_mid, c_dark = QColor(80, 80, 80), QColor(30, 30, 30), QColor(10, 10, 10)
        elif self.current_skin == self.SKIN_MATCHA:
            # 抹茶配白金笔
            c_light, c_mid, c_dark = QColor(255, 255, 250), QColor(240, 240, 230), QColor(200, 200, 190)
        else:
            # 摩卡/其他配勃艮第红笔
            c_light, c_mid, c_dark = QColor(180, 60, 70), QColor(140, 20, 30), QColor(60, 5, 10)

        # 笔身渐变
        body_grad = QLinearGradient(-w_pen/2, 0, w_pen/2, 0)
        body_grad.setColorAt(0.0, c_light) 
        body_grad.setColorAt(0.5, c_mid) 
        body_grad.setColorAt(1.0, c_dark) 

        # 绘制笔身
        path_body = QPainterPath()
        path_body.addRoundedRect(QRectF(-w_pen/2, -h_pen/2, w_pen, h_pen), 5, 5)
        p.setPen(Qt.NoPen)
        p.setBrush(body_grad)
        p.drawPath(path_body)
        
        # 笔尖 (香槟金)
        path_tip = QPainterPath()
        tip_h = 14
        path_tip.moveTo(-w_pen/2 + 3, h_pen/2)
        path_tip.lineTo(w_pen/2 - 3, h_pen/2)
        path_tip.lineTo(0, h_pen/2 + tip_h)
        path_tip.closeSubpath()
        
        tip_grad = QLinearGradient(-5, 0, 5, 0)
        tip_grad.setColorAt(0, QColor(240, 230, 180)) 
        tip_grad.setColorAt(1, QColor(190, 170, 100)) 
        p.setBrush(tip_grad)
        p.drawPath(path_tip)
        
        # 装饰细节 (金环 + 笔夹)
        p.setBrush(QColor(220, 200, 140))
        p.drawRect(QRectF(-w_pen/2, h_pen/2 - 4, w_pen, 4))
        p.setBrush(QColor(210, 190, 130)) 
        p.drawRoundedRect(QRectF(-1.5, -h_pen/2 + 6, 3, 24), 1.5, 1.5)

    def _draw_book_mocha(self, p):
        """摩卡·勃艮第 (Mocha Theme)"""
        w, h = 56, 76
        # 页厚
        p.setBrush(QColor(245, 240, 225))
        p.drawRoundedRect(QRectF(-w/2+6, -h/2+6, w, h), 3, 3)
        # 封面渐变 (褐)
        grad = QLinearGradient(-w, -h, w, h)
        grad.setColorAt(0, QColor(90, 60, 50))
        grad.setColorAt(1, QColor(50, 30, 25))
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(-w/2, -h/2, w, h), 3, 3)
        # 红色书签带
        p.setBrush(QColor(120, 20, 30))
        p.drawRect(QRectF(w/2 - 15, -h/2, 8, h))

    def _draw_book_classic(self, p):
        """经典黑金 (Classic Theme)"""
        w, h = 54, 74
        # 页厚 (更白一点的纸)
        p.setBrush(QColor(235, 235, 230))
        p.drawRoundedRect(QRectF(-w/2+6, -h/2+6, w, h), 3, 3)
        # 封面 (黑灰)
        grad = QLinearGradient(-w, -h, w, h)
        grad.setColorAt(0, QColor(60, 60, 65))
        grad.setColorAt(1, QColor(20, 20, 25))
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(-w/2, -h/2, w, h), 3, 3)
        # 黑色弹力带
        p.setBrush(QColor(10, 10, 10, 200))
        p.drawRect(QRectF(w/2 - 12, -h/2, 6, h))

    def _draw_book_royal(self, p):
        """皇家蓝 (Royal Theme)"""
        w, h = 58, 76
        # 页厚
        p.setBrush(QColor(240, 240, 235))
        p.drawRoundedRect(QRectF(-w/2+6, -h/2+6, w, h), 2, 2)
        # 封面 (午夜蓝)
        grad = QLinearGradient(-w, -h, w, 0)
        grad.setColorAt(0, QColor(40, 40, 100))
        grad.setColorAt(1, QColor(10, 10, 50))
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(-w/2, -h/2, w, h), 2, 2)
        # 金色包角
        p.setBrush(QColor(218, 165, 32))
        c_size = 12
        p.drawPolygon(QPolygonF([QPoint(int(w/2), int(-h/2)), QPoint(int(w/2-c_size), int(-h/2)), QPoint(int(w/2), int(-h/2+c_size))]))

    def _draw_book_matcha(self, p):
        """抹茶绿 (Matcha Theme) - 浅色系"""
        w, h = 54, 74
        # 页厚
        p.setBrush(QColor(250, 250, 245))
        p.drawRoundedRect(QRectF(-w/2+5, -h/2+5, w, h), 3, 3)
        # 封面 (抹茶绿)
        grad = QLinearGradient(-w, -h, w, h)
        grad.setColorAt(0, QColor(160, 190, 150))
        grad.setColorAt(1, QColor(100, 130, 90))
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(-w/2, -h/2, w, h), 3, 3)
        # 白色标签
        p.setBrush(QColor(255, 255, 255, 200))
        p.drawRoundedRect(QRectF(-w/2+10, -20, 34, 15), 2, 2)

    def _draw_book_open(self, p):
        """摊开的手稿 (Open Theme)"""
        w, h = 80, 50
        p.rotate(-5)
        # 纸张形状
        path = QPainterPath()
        path.moveTo(-w/2, -h/2); path.lineTo(0, -h/2 + 4)
        path.lineTo(w/2, -h/2); path.lineTo(w/2, h/2)
        path.lineTo(0, h/2 + 4); path.lineTo(-w/2, h/2); path.closeSubpath()
        
        p.setBrush(QColor(248, 248, 245))
        p.setPen(Qt.NoPen)
        p.drawPath(path)
        
        # 中缝阴影
        grad = QLinearGradient(-10, 0, 10, 0)
        grad.setColorAt(0, QColor(0,0,0,0)); grad.setColorAt(0.5, QColor(0,0,0,20)); grad.setColorAt(1, QColor(0,0,0,0))
        p.setBrush(grad)
        p.drawRect(QRectF(-5, -h/2+4, 10, h-4))
        
        # 横线
        p.setPen(QPen(QColor(200, 200, 200), 1))
        for y in range(int(-h/2)+15, int(h/2), 7):
            p.drawLine(int(-w/2+5), y, -5, y+2)
            p.drawLine(5, y+2, int(w/2-5), y)

    # --- 交互逻辑 ---
    def dragEnterEvent(self, e):
        if e.mimeData().hasText():
            e.accept()
            self.is_hovering = True
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self.is_hovering = False

    def dropEvent(self, e):
        self.is_hovering = False
        text = e.mimeData().text()
        if text.strip():
            self.mw.quick_add_idea(text)
            self.trigger_clipboard_feedback()
            e.acceptProposedAction()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = e.pos()
            self.pen_y += 3

    def mouseMoveEvent(self, e):
        if self.dragging:
            self.move(self.mapToGlobal(e.pos() - self.offset))

    def mouseReleaseEvent(self, e):
        if self.dragging:
            self.dragging = False
            pos = self.pos()
            save_setting('floating_ball_pos', {'x': pos.x(), 'y': pos.y()})

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.double_clicked.emit()
```

## 文件: ui\cards.py

```python
# -*- coding: utf-8 -*-
# ui/cards.py
import sys
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QApplication, QSizePolicy, QWidget
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData, QSize
from PyQt5.QtGui import QDrag, QPixmap, QImage, QPainter
from core.config import STYLES, COLORS
from ui.utils import create_svg_icon

class IdeaCard(QFrame):
    selection_requested = pyqtSignal(int, bool, bool)
    double_clicked = pyqtSignal(int)

    def __init__(self, data, db, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground)
        self.db = db
        self.setCursor(Qt.PointingHandCursor)
        
        # 布局策略：水平填满，垂直适应
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        self.setMinimumWidth(0)
        self.setMaximumWidth(16777215)
        self.setMinimumHeight(80)
        
        self._drag_start_pos = None
        self._is_potential_click = False
        self.get_selected_ids_func = None
        
        self._setup_ui_structure()
        self.update_data(data)

    def update_data(self, data):
        self.data = data
        # 使用键名访问，确保 ID 获取正确
        self.id = data['id']
        self._refresh_ui_content()

    def _setup_ui_structure(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 12, 15, 12)
        self.main_layout.setSpacing(6)

        # 1. 顶部区域
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)
        
        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size:15px; font-weight:bold; background:transparent; color:white;")
        self.title_label.setWordWrap(True) 
        self.title_label.setContentsMargins(0, 0, 5, 0)
        # 强制换行策略
        self.title_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        
        top_layout.addWidget(self.title_label, 1) # 权重1
        
        self.icon_layout = QHBoxLayout()
        self.icon_layout.setSpacing(4)
        
        self.rating_label = QLabel()
        self.lock_icon = QLabel()
        self.pin_icon = QLabel()
        self.fav_icon = QLabel()
        
        for icon in [self.rating_label, self.lock_icon, self.pin_icon, self.fav_icon]:
            icon.setStyleSheet("background: transparent; border: none;")
            icon.setAlignment(Qt.AlignCenter)
            self.icon_layout.addWidget(icon)
            
        top_layout.addLayout(self.icon_layout)
        self.main_layout.addLayout(top_layout)

        # 2. 中间内容区域
        self.content_widget = QFrame()
        self.content_widget.setStyleSheet("background:transparent; border:none;")
        self.content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0,0,0,0)
        self.main_layout.addWidget(self.content_widget)

        # 3. 底部区域
        bot_layout = QHBoxLayout()
        bot_layout.setSpacing(6)
        
        self.time_label = QLabel()
        self.time_label.setStyleSheet("color:rgba(255,255,255,100); font-size:12px; background:transparent;")
        self.time_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
        bot_layout.addWidget(self.time_label)
        bot_layout.addStretch() 
        
        self.tags_layout = QHBoxLayout()
        self.tags_layout.setSpacing(4)
        bot_layout.addLayout(self.tags_layout)
        
        self.main_layout.addLayout(bot_layout)

    def _refresh_ui_content(self):
        # 使用键名访问，防止索引错位
        self.title_label.setText(self.data['title'])
        
        # 安全获取字段
        rating = self.data['rating'] if 'rating' in self.data.keys() else 0
        is_locked = self.data['is_locked'] if 'is_locked' in self.data.keys() else 0
        is_pinned = self.data['is_pinned']
        is_favorite = self.data['is_favorite']

        # 星级
        if rating and rating > 0:
            self.rating_label.setPixmap(self._generate_stars_pixmap(rating))
            self.rating_label.show()
        else:
            self.rating_label.hide()
            
        # 锁定 (绿色图标)
        if is_locked:
            self.lock_icon.setPixmap(create_svg_icon("lock.svg", COLORS['success']).pixmap(14, 14))
            self.lock_icon.show()
        else:
            self.lock_icon.hide()

        # 置顶 (红色实心图标)
        if is_pinned:
            self.pin_icon.setPixmap(create_svg_icon("pin_vertical.svg", "#e74c3c").pixmap(14, 14))
            self.pin_icon.show()
        else:
            self.pin_icon.hide()

        # 书签 (核心修复：背景是粉色，所以图标必须是白色，否则看不见)
        if is_favorite:
            self.fav_icon.setPixmap(create_svg_icon("bookmark.svg", "#ff6b81").pixmap(14, 14))
            self.fav_icon.show()
        else:
            self.fav_icon.hide()

        # 内容渲染
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        item_type = self.data['item_type'] or 'text'
        
        if item_type == 'image' and self.data['data_blob']:
            pixmap = QPixmap()
            pixmap.loadFromData(self.data['data_blob'])
            if not pixmap.isNull():
                img_label = QLabel()
                scaled_pixmap = pixmap.scaled(QSize(600, 300), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                img_label.setPixmap(scaled_pixmap)
                img_label.setStyleSheet("background: transparent;")
                img_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                self.content_layout.addWidget(img_label)
                
        elif self.data['content']:
            preview_text = self.data['content'].strip()[:300].replace('\n', ' ')
            if len(self.data['content']) > 300: preview_text += "..."
            content = QLabel(preview_text)
            content.setStyleSheet("color: rgba(255,255,255,180); margin-top: 4px; background: transparent; font-size: 13px; line-height: 1.5;")
            content.setWordWrap(True)
            content.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)
            self.content_layout.addWidget(content)

        # 时间 (带时钟符号)
        self.time_label.setText(f'{self.data["updated_at"][:16]}')
        
        # 标签
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        
        # 优先使用预加载的标签，避免 N+1 查询
        if 'tags' in self.data:
            tags = self.data['tags']
        else:
            tags = self.db.get_tags(self.id)
            
        limit = 6 
        for i, tag in enumerate(tags):
            if i >= limit:
                more_label = QLabel(f'+{len(tags) - limit}')
                more_label.setStyleSheet(f"background: rgba(74,144,226,0.3); border-radius: 4px; padding: 2px 6px; font-size: 10px; color: {COLORS['primary']}; font-weight:bold;")
                self.tags_layout.addWidget(more_label)
                break
            tag_label = QLabel(f"#{tag}")
            tag_label.setStyleSheet("background: rgba(255,255,255,0.1); border-radius: 4px; padding: 2px 6px; font-size: 10px; color: rgba(255,255,255,180);")
            self.tags_layout.addWidget(tag_label)

        self.update_selection(False)

    def _generate_stars_pixmap(self, rating):
        star_size = 12
        spacing = 2
        total_width = (star_size * rating) + (spacing * (rating - 1))
        pixmap = QPixmap(total_width, star_size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        star_icon = create_svg_icon("star_filled.svg", COLORS['warning'])
        for i in range(rating):
            x = i * (star_size + spacing)
            star_icon.paint(painter, x, 0, star_size, star_size)
        painter.end()
        return pixmap

    def update_selection(self, selected):
        bg_color = self.data['color']
        base_style = f"""
            IdeaCard {{
                background-color: {bg_color};
                border-radius: 8px;
                padding: 0px;
            }}
            QLabel {{
                background-color: transparent;
                border: none;
            }}
        """
        if selected:
            border_style = "border: 2px solid white;"
        else:
            border_style = "border: 1px solid rgba(255,255,255,0.05);"
            
        final_style = base_style + f"""
            IdeaCard {{ {border_style} }}
            IdeaCard:hover {{
                border: 1px solid rgba(255,255,255,0.3);
            }}
        """
        if selected:
            final_style += "IdeaCard:hover { border: 2px solid white; }"
            
        self.setStyleSheet(final_style)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_start_pos = e.pos()
            self._is_potential_click = True
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not (e.buttons() & Qt.LeftButton) or not self._drag_start_pos: return
        if (e.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance(): return
        self._is_potential_click = False
        drag = QDrag(self)
        mime = QMimeData()
        ids_to_move = [self.id]
        if self.get_selected_ids_func:
            selected_ids = self.get_selected_ids_func()
            if self.id in selected_ids: ids_to_move = selected_ids
        mime.setData('application/x-idea-ids', (','.join(map(str, ids_to_move))).encode('utf-8'))
        mime.setData('application/x-idea-id', str(self.id).encode())
        drag.setMimeData(mime)
        pixmap = self.grab().scaledToWidth(200, Qt.SmoothTransformation)
        drag.setPixmap(pixmap)
        drag.setHotSpot(e.pos())
        drag.exec_(Qt.MoveAction)
        
    def mouseReleaseEvent(self, e):
        if self._is_potential_click and e.button() == Qt.LeftButton:
            modifiers = QApplication.keyboardModifiers()
            is_ctrl = bool(modifiers & Qt.ControlModifier)
            is_shift = bool(modifiers & Qt.ShiftModifier)
            self.selection_requested.emit(self.id, is_ctrl, is_shift)
        self._drag_start_pos = None
        self._is_potential_click = False
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.double_clicked.emit(self.id)
        super().mouseDoubleClickEvent(e)
```

## 文件: ui\card_list_view.py

```python
# -*- coding: utf-8 -*-
# ui/card_list_view.py

from PyQt5.QtWidgets import QWidget, QScrollArea, QLabel, QVBoxLayout, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal
from ui.cards import IdeaCard

class ContentContainer(QWidget):
    cleared = pyqtSignal()
    def mousePressEvent(self, e):
        if self.childAt(e.pos()) is None: self.cleared.emit(); e.accept()
        else: super().mousePressEvent(e)

class CardListView(QScrollArea):
    selection_cleared = pyqtSignal()
    card_selection_requested = pyqtSignal(int, bool, bool)
    card_double_clicked = pyqtSignal(int)
    card_context_menu_requested = pyqtSignal(int, object)

    # 【核心修改】构造函数接收 service
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.db = service # 为了兼容 IdeaCard，这里 self.db 实际上是 service
        self.cards = {}
        self.ordered_ids = []
        
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { border: none; background: transparent; width: 8px; margin: 0px; }
            QScrollBar::handle:vertical { background: #444; border-radius: 4px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #555; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)
        
        self.container = ContentContainer()
        self.container.setStyleSheet("background: transparent;")
        self.container.cleared.connect(self.selection_cleared)
        self.container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(10, 10, 10, 10) 
        self.layout.setSpacing(12) 
        
        self.setWidget(self.container)

    def clear_all(self):
        """完全清空并销毁所有卡片，通常用于切换分类时。"""
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.cards = {}
        self.ordered_ids = []
        self.layout.addStretch(1)

    def clear(self):
        """仅从布局中移除并隐藏，不销毁组件，用于内存池复用。"""
        # 移除所有组件并将它们隐藏
        for card in self.cards.values():
            card.hide()
            self.layout.removeWidget(card)
        
        # 移除底部的 stretch (如果有)
        for i in reversed(range(self.layout.count())):
            item = self.layout.itemAt(i)
            if item.spacerItem():
                self.layout.takeAt(i)
        
        self.ordered_ids = []

    def render_cards(self, data_list):
        # 先清除当前布局中的显示（但不销毁卡片）
        self.clear()
        
        if not data_list:
            empty_container = QWidget()
            empty_layout = QVBoxLayout(empty_container)
            empty_layout.setAlignment(Qt.AlignCenter)
            empty_layout.setContentsMargins(0, 50, 0, 0)
            
            icon_lbl = QLabel()
            icon_lbl.setPixmap(create_svg_icon("all_data.svg", "#444").pixmap(48, 48))
            icon_lbl.setAlignment(Qt.AlignCenter)
            
            lbl = QLabel("空空如也")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color:#666;font-size:16px;")
            
            empty_layout.addWidget(icon_lbl)
            empty_layout.addWidget(lbl)
            
            self.layout.addWidget(empty_container)
            self.layout.addStretch(1) 
            return

        for d in data_list:
            iid = d['id']
            if iid in self.cards:
                # 复用现有卡片
                c = self.cards[iid]
            else:
                # 创建新卡片
                c = IdeaCard(d, self.db)
                c.selection_requested.connect(self.card_selection_requested)
                c.double_clicked.connect(self.card_double_clicked)
                c.setContextMenuPolicy(Qt.CustomContextMenu)
                c.customContextMenuRequested.connect(lambda pos, iid=iid: self.card_context_menu_requested.emit(iid, pos))
                self.cards[iid] = c
            
            self.layout.addWidget(c)
            c.show()
            self.ordered_ids.append(iid)
            
        self.layout.addStretch(1) 

    def get_card(self, idea_id): return self.cards.get(idea_id)

    def remove_card(self, idea_id):
        if idea_id in self.cards:
            card = self.cards.pop(idea_id)
            if idea_id in self.ordered_ids: self.ordered_ids.remove(idea_id)
            self.layout.removeWidget(card)
            card.hide(); card.deleteLater()

    def update_all_selections(self, selected_ids):
        for iid, card in self.cards.items():
            card.update_selection(iid in selected_ids)
            card.get_selected_ids_func = lambda: list(selected_ids)

    def recalc_layout(self): pass
```

## 文件: ui\common_tags.py

```python
# -*- coding: utf-8 -*-
# ui/common_tags.py

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal
from core.config import COLORS
from core.settings import load_setting
from ui.utils import create_svg_icon

class CommonTags(QWidget):
    tag_clicked = pyqtSignal(str) 
    manager_requested = pyqtSignal()
    refresh_requested = pyqtSignal() 

    # 【核心修改】构造函数接收 service
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self._init_ui()
        self.reload_tags()

    def _init_ui(self):
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def reload_tags(self, active_tags=None):
        if active_tags is None:
            active_tags = []
            
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        raw_tags = load_setting('manual_common_tags', ['工作', '待办', '重要'])
        limit = load_setting('common_tags_limit', 5)

        processed_tags = []
        for item in raw_tags:
            if isinstance(item, str):
                processed_tags.append({'name': item, 'visible': True})
            elif isinstance(item, dict):
                processed_tags.append(item)
        
        visible_tags = [t for t in processed_tags if t.get('visible', True)]
        display_tags = visible_tags[:limit]

        for tag in display_tags:
            name = tag['name']
            btn = QPushButton(f"{name}")
            btn.setCursor(Qt.PointingHandCursor)
            
            is_active = name in active_tags
            
            if is_active:
                style = f"""
                    QPushButton {{
                        background-color: {COLORS['primary']};
                        color: white;
                        border: 1px solid {COLORS['primary']};
                        border-radius: 10px; padding: 2px 8px; font-size: 11px; min-height: 20px; max-width: 80px;
                    }}
                    QPushButton:hover {{
                        background-color: #D32F2F; border-color: #D32F2F;
                    }}
                """
            else:
                style = f"""
                    QPushButton {{
                        background-color: #3E3E42; color: #DDD; border: 1px solid #555;
                        border-radius: 10px; padding: 2px 8px; font-size: 11px; min-height: 20px; max-width: 80px;
                    }}
                    QPushButton:hover {{
                        background-color: {COLORS['primary']}; border-color: {COLORS['primary']}; color: white;
                    }}
                """
            
            btn.setStyleSheet(style)
            btn.clicked.connect(lambda _, n=name: self.tag_clicked.emit(n))
            self.layout.addWidget(btn)

        btn_edit = QPushButton()
        btn_edit.setIcon(create_svg_icon("pencil.svg", "#888"))
        btn_edit.setToolTip("管理常用标签")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.setFixedSize(20, 20)
        btn_edit.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #666;
                border-radius: 10px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #444;
                border-color: #888;
            }
        """)
        btn_edit.clicked.connect(self.manager_requested.emit)
        self.layout.addWidget(btn_edit)
        
        self.refresh_requested.emit()
```

## 文件: ui\common_tags_manager.py

```python
# -*- coding: utf-8 -*-
# ui/common_tags_manager.py

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QLineEdit, QPushButton, QLabel, QListWidgetItem, 
                             QMessageBox, QAbstractItemView, QSpinBox, QCheckBox, QWidget, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor
from core.config import COLORS
from core.settings import load_setting, save_setting

class CommonTagsManager(QDialog):
    """
    常用标签管理界面 (现代卡片风格版)
    - 视觉升级：独立的圆角卡片列表，去除传统网格感
    - 修复：滚动条样式统一为现代极简风格
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 加载数据
        raw_tags = load_setting('manual_common_tags', ['工作', '待办', '重要'])
        self.tags_data = []
        for item in raw_tags:
            if isinstance(item, str):
                self.tags_data.append({'name': item, 'visible': True})
            elif isinstance(item, dict):
                self.tags_data.append(item)
                
        self.limit = load_setting('common_tags_limit', 5)
        
        self.setWindowTitle("🏷️ 管理常用标签")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(340, 520) 
        
        self._init_ui()
        self._refresh_list()

    def _init_ui(self):
        # 主容器
        container = QWidget(self)
        container.setGeometry(10, 10, 320, 500) 
        container.setStyleSheet(f"""
            QWidget {{
                background-color: #1E1E1E;
                border: 1px solid #333;
                border-radius: 12px;
                color: #EEE;
            }}
        """)
        
        # 窗口阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 100))
        container.setGraphicsEffect(shadow)

        # --- 主布局 ---
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 1. 顶部标题栏 (标题 + 关闭按钮)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel("管理常用标签")
        title.setStyleSheet("font-weight: bold; font-size: 15px; border: none; color: #DDD;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        self.btn_close = QPushButton("×")
        self.btn_close.setFixedSize(32, 32)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setToolTip("保存并关闭")
        self.btn_close.clicked.connect(self._save_and_close)
        self.btn_close.setStyleSheet("""
            QPushButton { 
                background-color: transparent; 
                border: none; 
                font-size: 20px; 
                color: #888; 
                font-family: Arial;
                border-radius: 4px;
            } 
            QPushButton:hover { 
                background-color: #E81123; 
                color: white; 
            }
        """)
        header_layout.addWidget(self.btn_close)
        
        layout.addLayout(header_layout)
        
        # 2. 输入区
        input_container = QWidget()
        input_container.setStyleSheet("background: transparent; border: none;")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)
        
        self.inp_tag = QLineEdit()
        self.inp_tag.setPlaceholderText("输入新标签...")
        self.inp_tag.setStyleSheet(f"""
            QLineEdit {{
                background-color: #2D2D2D; 
                border: 1px solid #444; 
                border-radius: 6px; 
                padding: 8px 10px; 
                color: white;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {COLORS['primary']}; background-color: #333; }}
        """)
        self.inp_tag.returnPressed.connect(self._add_tag)
        
        btn_add = QPushButton("添加")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']}; 
                color: white; 
                border: none; 
                border-radius: 6px; 
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: #357ABD; }}
        """)
        btn_add.clicked.connect(self._add_tag)
        
        input_layout.addWidget(self.inp_tag)
        input_layout.addWidget(btn_add)
        layout.addWidget(input_container)
        
        # 3. 数量限制
        limit_layout = QHBoxLayout()
        lbl_limit = QLabel("悬浮条最大显示数量:")
        lbl_limit.setStyleSheet("color: #AAA; font-size: 12px; border:none;")
        
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(1, 10)
        self.spin_limit.setValue(self.limit)
        self.spin_limit.setFixedWidth(60)
        self.spin_limit.setStyleSheet("""
            QSpinBox { 
                background-color: #2D2D2D; 
                border: 1px solid #444; 
                color: white; 
                padding: 4px; 
                border-radius: 4px; 
            }
            QSpinBox:focus { border-color: #555; }
            QSpinBox::up-button, QSpinBox::down-button { background: none; border: none; }
        """)
        
        limit_layout.addWidget(lbl_limit)
        limit_layout.addWidget(self.spin_limit)
        limit_layout.addStretch()
        layout.addLayout(limit_layout)
        
        # 4. 列表区
        lbl_hint = QLabel("💡 拖拽调整顺序，勾选控制显示")
        lbl_hint.setStyleSheet("color: #666; font-size: 11px; border:none; margin-bottom: 5px;")
        layout.addWidget(lbl_hint)

        self.list_widget = QListWidget()
        # 【关键修复】在此处注入 QScrollBar 样式，覆盖系统默认
        self.list_widget.setStyleSheet(f"""
            QListWidget {{ 
                background-color: transparent; 
                border: none; 
                outline: none; 
            }}
            QListWidget::item {{ 
                background-color: #2D2D2D; 
                color: #DDD; 
                border: 1px solid #3A3A3A;
                border-radius: 8px; 
                margin-bottom: 6px; 
                padding: 8px 10px; 
            }}
            QListWidget::item:hover {{ 
                background-color: #333333; 
                border: 1px solid #555;
            }}
            QListWidget::item:selected {{ 
                background-color: #2D2D2D; 
                border: 1px solid {COLORS['primary']}; 
                color: white; 
            }}
            QListWidget::indicator {{ 
                width: 16px; height: 16px; 
                border-radius: 4px; 
                border: 1px solid #666; 
                background: transparent;
            }}
            QListWidget::indicator:checked {{ 
                background-color: {COLORS['primary']}; 
                border-color: {COLORS['primary']}; 
                image: url(none); 
            }}
            
            /* --- 现代滚动条样式修复 --- */
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 6px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: #444;
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #555;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)
        
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.MoveAction)
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel) 
        
        layout.addWidget(self.list_widget)
        
        # 5. 底部按钮
        btn_del = QPushButton("删除选中项")
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(231, 76, 60, 0.1); 
                color: {COLORS['danger']}; 
                border: 1px solid {COLORS['danger']}; 
                border-radius: 6px; 
                padding: 8px;
                font-size: 13px;
            }}
            QPushButton:hover {{ 
                background-color: {COLORS['danger']}; 
                color: white; 
            }}
        """)
        btn_del.clicked.connect(self._del_tag)
        layout.addWidget(btn_del)
        
        # 拖拽窗口支持
        self.drag_pos = None

    def _refresh_list(self):
        """将数据渲染到列表"""
        self.list_widget.clear()
        for tag_data in self.tags_data:
            item = QListWidgetItem(tag_data['name'])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            state = Qt.Checked if tag_data.get('visible', True) else Qt.Unchecked
            item.setCheckState(state)
            self.list_widget.addItem(item)

    def _add_tag(self):
        text = self.inp_tag.text().strip()
        if not text: return
        
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).text() == text:
                QMessageBox.warning(self, "提示", "该标签已存在")
                return
        
        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
        item.setCheckState(Qt.Checked)
        self.list_widget.addItem(item)
        self.inp_tag.clear()
        self.list_widget.scrollToBottom()

    def _del_tag(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)

    def _save_and_close(self):
        new_tags_data = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            new_tags_data.append({
                'name': item.text(),
                'visible': (item.checkState() == Qt.Checked)
            })
            
        save_setting('manual_common_tags', new_tags_data)
        save_setting('common_tags_limit', self.spin_limit.value())
        self.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos:
            self.move(event.globalPos() - self.drag_pos)
            event.accept()
```

## 文件: ui\dialogs.py

```python
# ui/dialogs.py
import sys
from PyQt5.QtWidgets import QCompleter
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QHBoxLayout,
                              QLabel, QLineEdit, QTextEdit, QComboBox, QPushButton,
                              QProgressBar, QFrame, QApplication, QMessageBox, QShortcut,
                             QSpacerItem, QSizePolicy, QSplitter, QWidget, QScrollBar,
                             QGraphicsDropShadowEffect, QCheckBox)
from PyQt5.QtGui import QKeySequence, QColor, QCursor, QTextDocument, QTextCursor, QTextListFormat, QTextCharFormat, QPixmap, QImage
from PyQt5.QtCore import Qt, QPoint, QRect, QEvent, pyqtSignal
from PyQt5.QtWidgets import QDesktopWidget
from core.config import STYLES, COLORS
from core.settings import save_setting, load_setting
from .components.rich_text_edit import RichTextEdit
from ui.utils import create_svg_icon

class BaseDialog(QDialog):
    def __init__(self, parent=None, window_title="快速笔记"):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(window_title)
        self._setup_container()
    
    def _setup_container(self):
        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(15, 15, 15, 15)
        self.content_container = QWidget()
        self.content_container.setObjectName("DialogContainer")
        self.content_container.setStyleSheet(f"""
            #DialogContainer {{
                background-color: {COLORS['bg_dark']};
                border-radius: 12px;
            }}
        """ + STYLES['dialog'])
        self.outer_layout.addWidget(self.content_container)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(6)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.content_container.setGraphicsEffect(shadow)
        return self.content_container

class EditDialog(BaseDialog):
    RESIZE_MARGIN = 10
    data_saved = pyqtSignal()

    def __init__(self, db, idea_id=None, parent=None, category_id_for_new=None):
        window_title = "编辑笔记" if idea_id else "新建笔记"
        super().__init__(parent, window_title=window_title)
        self.db = db
        self.idea_id = idea_id
        
        saved_default = load_setting('user_default_color')
        if saved_default:
            self.selected_color = saved_default
            self.is_using_saved_default = True
        else:
            self.selected_color = COLORS['orange']
            self.is_using_saved_default = False
        
        self.category_id = None 
        self.category_id_for_new = category_id_for_new 
        
        self._resize_area = None
        self._drag_pos = None
        self._resize_start_pos = None
        self._resize_start_geometry = None
        
        self.setMouseTracking(True)
        
        self._init_ui()
        if idea_id: 
            self._load_data()
        elif category_id_for_new:
             idx = self.category_combo.findData(category_id_for_new)
             if idx >= 0: self.category_combo.setCurrentIndex(idx)
            
        self.title_inp.installEventFilter(self)
        self.tags_inp.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Down:
                if obj == self.title_inp:
                    self.tags_inp.setFocus()
                    return True
                elif obj == self.tags_inp:
                    self.content_inp.setFocus()
                    return True
            elif event.key() == Qt.Key_Up:
                if obj == self.tags_inp:
                    self.title_inp.setFocus()
                    return True
        return super().eventFilter(obj, event)
        
    def _init_ui(self):
        self.resize(950, 650)
        main_layout = QVBoxLayout(self.content_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(40)
        self.title_bar.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_mid']};
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                border-bottom: 1px solid {COLORS['bg_light']};
            }}
        """)
        tb_layout = QHBoxLayout(self.title_bar)
        tb_layout.setContentsMargins(15, 0, 10, 0)
        
        title_icon = QLabel()
        title_icon.setPixmap(create_svg_icon("action_edit.svg", COLORS['primary']).pixmap(14, 14))
        tb_layout.addWidget(title_icon)
        
        self.win_title = QLabel('记录灵感' if not self.idea_id else '编辑笔记')
        self.win_title.setStyleSheet("font-weight: bold; color: #ddd; font-size: 13px; border: none; background: transparent;")
        tb_layout.addWidget(self.win_title)
        
        tb_layout.addStretch()
        
        ctrl_btn_style = "QPushButton { background: transparent; border: none; border-radius: 4px; width: 30px; height: 30px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }"
        close_btn_style = "QPushButton { background: transparent; border: none; border-radius: 4px; width: 30px; height: 30px; } QPushButton:hover { background-color: #e74c3c; }"
        
        btn_min = QPushButton()
        btn_min.setIcon(create_svg_icon("win_min.svg", "#aaa"))
        btn_min.setStyleSheet(ctrl_btn_style)
        btn_min.clicked.connect(self.showMinimized)
        
        self.btn_max = QPushButton()
        self.btn_max.setIcon(create_svg_icon("win_max.svg", "#aaa"))
        self.btn_max.setStyleSheet(ctrl_btn_style)
        self.btn_max.clicked.connect(self._toggle_maximize)
        
        btn_close = QPushButton()
        btn_close.setIcon(create_svg_icon("win_close.svg", "#aaa"))
        btn_close.setStyleSheet(close_btn_style)
        btn_close.clicked.connect(self.close) 
        
        tb_layout.addWidget(btn_min); tb_layout.addWidget(self.btn_max); tb_layout.addWidget(btn_close)
        main_layout.addWidget(self.title_bar)
        
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {COLORS['bg_mid']}; width: 2px; margin: 0 5px; }} QSplitter::handle:hover {{ background-color: {COLORS['primary']}; }}")
        
        left_container = QWidget()
        left_panel = QVBoxLayout(left_container)
        left_panel.setContentsMargins(5, 5, 5, 5)
        left_panel.setSpacing(12)
        
        left_panel.addWidget(QLabel('分区'))
        self.category_combo = QComboBox()
        self.category_combo.setFixedHeight(40)
        self.category_combo.addItem("未分类", None)
        cats = self.db.get_categories()
        for c in cats: self.category_combo.addItem(f"{c[1]}", c[0])
        left_panel.addWidget(self.category_combo)

        left_panel.addWidget(QLabel('标题'))
        self.title_inp = QLineEdit()
        self.title_inp.setPlaceholderText("请输入灵感标题...")
        self.title_inp.setFixedHeight(40)
        left_panel.addWidget(self.title_inp)
        
        left_panel.addWidget(QLabel('标签 (智能补全)'))
        self.tags_inp = QLineEdit()
        self.tags_inp.setPlaceholderText("使用逗号分隔，如: 工作, 待办")
        self.tags_inp.setFixedHeight(40)
        self._init_completer()
        left_panel.addWidget(self.tags_inp)
        
        left_panel.addSpacing(10)
        left_panel.addWidget(QLabel('标记颜色'))
        color_layout = QGridLayout()
        color_layout.setSpacing(10)
        
        self.color_btns = []
        colors = [COLORS['orange'], COLORS['default_note'], COLORS['primary'], COLORS['success'], COLORS['danger'], COLORS['info']]
        for i, c in enumerate(colors):
            btn = QPushButton()
            btn.setFixedSize(34, 34)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"QPushButton {{ background-color: {c}; border-radius: 17px; border: 2px solid transparent; }}")
            btn.clicked.connect(lambda _, x=c: self._set_color(x))
            self.color_btns.append(btn)
            color_layout.addWidget(btn, i // 3, i % 3)
        left_panel.addLayout(color_layout)
        
        self.chk_set_default = QCheckBox("设为默认颜色")
        self.chk_set_default.setStyleSheet(f"QCheckBox {{ color: {COLORS['text_sub']}; font-size: 12px; margin-top: 5px; }} QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid #555; border-radius: 3px; background: transparent; }} QCheckBox::indicator:checked {{ background-color: {COLORS['primary']}; border-color: {COLORS['primary']}; }}")
        if self.is_using_saved_default: self.chk_set_default.setChecked(True)
        left_panel.addWidget(self.chk_set_default)
        
        left_panel.addStretch()
        self.save_btn = QPushButton('  保存 (Ctrl+S)')
        self.save_btn.setIcon(create_svg_icon("action_save.svg", "white"))
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setFixedHeight(50)
        self.save_btn.setStyleSheet(STYLES['btn_primary'])
        self.save_btn.clicked.connect(self._save_data)
        left_panel.addWidget(self.save_btn)
        
        right_container = QWidget()
        right_panel = QVBoxLayout(right_container)
        right_panel.setContentsMargins(5, 5, 5, 5)
        right_panel.setSpacing(10)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel('详细内容'))
        
        btn_style = "QPushButton { background: transparent; border: 1px solid #444; border-radius: 4px; margin-left: 2px; } QPushButton:hover { background-color: #444; }"
        
        def _create_tool_btn(text, tooltip, callback):
            btn = QPushButton(text)
            btn.setFixedSize(28, 28)
            btn.setToolTip(tooltip)
            btn.setStyleSheet(btn_style)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(callback)
            header_layout.addWidget(btn)
            return btn

        header_layout.addSpacing(10)
        # 撤销重做
        u = _create_tool_btn("", "撤销 (Ctrl+Z)", lambda: self.content_inp.undo()); u.setIcon(create_svg_icon("edit_undo.svg", '#ccc'))
        r = _create_tool_btn("", "重做 (Ctrl+Y)", lambda: self.content_inp.redo()); r.setIcon(create_svg_icon("edit_redo.svg", '#ccc'))
        header_layout.addSpacing(5)
        # 列表
        l1 = _create_tool_btn("", "无序列表", lambda: self.content_inp.toggle_list(QTextListFormat.ListDisc)); l1.setIcon(create_svg_icon("edit_list_ul.svg", '#ccc'))
        l2 = _create_tool_btn("", "有序列表", lambda: self.content_inp.toggle_list(QTextListFormat.ListDecimal)); l2.setIcon(create_svg_icon("edit_list_ol.svg", '#ccc'))
        
        # === 新增功能按钮 ===
        header_layout.addSpacing(5)
        # 待办事项
        btn_todo = QPushButton("Todo")
        btn_todo.setFixedSize(28, 28)
        btn_todo.setToolTip("插入待办事项")
        btn_todo.setStyleSheet(btn_style)
        btn_todo.clicked.connect(lambda: self.content_inp.insert_todo())
        header_layout.addWidget(btn_todo)
        
        # Markdown 预览
        btn_preview = QPushButton("Pre")
        btn_preview.setFixedSize(28, 28)
        btn_preview.setToolTip("切换 Markdown 预览/编辑")
        btn_preview.setStyleSheet(btn_style)
        btn_preview.clicked.connect(lambda: self.content_inp.toggle_markdown_preview())
        header_layout.addWidget(btn_preview)

        c = _create_tool_btn("", "清除格式", lambda: self.content_inp.setCurrentCharFormat(QTextCharFormat())); c.setIcon(create_svg_icon("edit_clear.svg", '#ccc'))

        header_layout.addStretch()
        
        highlight_colors = [('#c0392b', None), ('#d35400', None), ('#f1c40f', None), ('#27ae60', None), ('#2980b9', None), ('#8e44ad', None), (None, 'edit_clear.svg')]
        for color, icon in highlight_colors:
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.PointingHandCursor)
            if icon:
                btn.setIcon(create_svg_icon(icon, '#ccc'))
                btn.setToolTip("清除高亮")
                btn.setStyleSheet(btn_style)
            else:
                btn.setToolTip("高亮文字")
                btn.setStyleSheet(f"QPushButton {{ background-color: {color}; border: 1px solid #444; border-radius: 12px; margin-left: 2px; }} QPushButton:hover {{ border-color: white; }}")
            btn.clicked.connect(lambda _, c=color: self.content_inp.highlight_selection(c))
            header_layout.addWidget(btn)
            
        right_panel.addLayout(header_layout)

        self.search_bar = QWidget()
        self.search_bar.setVisible(False)
        self.search_bar.setStyleSheet(f"background-color: {COLORS['bg_mid']}; border-radius: 6px; padding: 2px;")
        sb_layout = QHBoxLayout(self.search_bar)
        sb_layout.setContentsMargins(5, 2, 5, 2)
        sb_layout.setSpacing(5)
        self.search_inp = QLineEdit()
        self.search_inp.setPlaceholderText("查找内容...")
        self.search_inp.setStyleSheet("border: none; background: transparent; color: #fff;")
        self.search_inp.returnPressed.connect(self._find_next)
        btn_prev = QPushButton(); btn_prev.setIcon(create_svg_icon("nav_prev.svg", "#ccc")); btn_prev.setFixedSize(24, 24); btn_prev.clicked.connect(self._find_prev); btn_prev.setStyleSheet("background: transparent; border: none;")
        btn_next = QPushButton(); btn_next.setIcon(create_svg_icon("nav_next.svg", "#ccc")); btn_next.setFixedSize(24, 24); btn_next.clicked.connect(self._find_next); btn_next.setStyleSheet("background: transparent; border: none;")
        btn_cls = QPushButton(); btn_cls.setIcon(create_svg_icon("win_close.svg", "#ccc")); btn_cls.setFixedSize(24, 24); btn_cls.clicked.connect(lambda: self.search_bar.hide()); btn_cls.setStyleSheet("background: transparent; border: none;")
        sb_layout.addWidget(self.search_inp); sb_layout.addWidget(btn_prev); sb_layout.addWidget(btn_next); sb_layout.addWidget(btn_cls)
        right_panel.addWidget(self.search_bar)

        self.content_inp = RichTextEdit()
        self.content_inp.setPlaceholderText("在这里记录详细内容（支持 Markdown 和粘贴图片）...")
        shortcut_search = QShortcut(QKeySequence("Ctrl+F"), self.content_inp)
        shortcut_search.activated.connect(self._toggle_search_bar)
        right_panel.addWidget(self.content_inp)
        
        self.splitter.addWidget(left_container); self.splitter.addWidget(right_container); self.splitter.setSizes([300, 650]); self.splitter.setStretchFactor(0, 0); self.splitter.setStretchFactor(1, 1)
        content_layout.addWidget(self.splitter)
        main_layout.addWidget(content_widget)
        
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_data)
        QShortcut(QKeySequence("Escape"), self, self.close)
        QShortcut(QKeySequence("Ctrl+W"), self, self.close)
        self._set_color(self.selected_color)

    def _get_resize_area(self, pos):
        x, y = pos.x(), pos.y(); w, h = self.width(), self.height(); m = self.RESIZE_MARGIN
        areas = []
        if x < m: areas.append('left')
        elif x > w - m: areas.append('right')
        if y < m: areas.append('top')
        elif y > h - m: areas.append('bottom')
        return areas

    def _set_cursor_for_resize(self, areas):
        if not areas: self.setCursor(Qt.ArrowCursor); return
        if 'left' in areas and 'top' in areas: self.setCursor(Qt.SizeFDiagCursor)
        elif 'right' in areas and 'bottom' in areas: self.setCursor(Qt.SizeFDiagCursor)
        elif 'left' in areas and 'bottom' in areas: self.setCursor(Qt.SizeBDiagCursor)
        elif 'right' in areas and 'top' in areas: self.setCursor(Qt.SizeBDiagCursor)
        elif 'left' in areas or 'right' in areas: self.setCursor(Qt.SizeHorCursor)
        elif 'top' in areas or 'bottom' in areas: self.setCursor(Qt.SizeVerCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            areas = self._get_resize_area(e.pos())
            if areas:
                self._resize_area = areas; self._resize_start_pos = e.globalPos(); self._resize_start_geometry = self.geometry(); self._drag_pos = None
            elif e.pos().y() < 60: 
                self._drag_pos = e.globalPos() - self.frameGeometry().topLeft(); self._resize_area = None
            e.accept()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.NoButton:
            self._set_cursor_for_resize(self._get_resize_area(e.pos())); return
        if e.buttons() == Qt.LeftButton:
            if self._resize_area:
                delta = e.globalPos() - self._resize_start_pos; rect = self._resize_start_geometry; min_w, min_h = 600, 400; new_rect = rect.adjusted(0,0,0,0)
                if 'left' in self._resize_area:
                    if rect.right() - (rect.left() + delta.x()) >= min_w: new_rect.setLeft(rect.left() + delta.x())
                if 'right' in self._resize_area:
                    if (rect.width() + delta.x()) >= min_w: new_rect.setWidth(rect.width() + delta.x())
                if 'top' in self._resize_area:
                    if rect.bottom() - (rect.top() + delta.y()) >= min_h: new_rect.setTop(rect.top() + delta.y())
                if 'bottom' in self._resize_area:
                    if (rect.height() + delta.y()) >= min_h: new_rect.setHeight(rect.height() + delta.y())
                self.setGeometry(new_rect)
            elif self._drag_pos: self.move(e.globalPos() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None; self._resize_area = None; self.setCursor(Qt.ArrowCursor)

    def mouseDoubleClickEvent(self, e):
        if e.pos().y() < 60: self._toggle_maximize()

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal(); self.btn_max.setIcon(create_svg_icon("win_max.svg", "#aaa")); self.outer_layout.setContentsMargins(15, 15, 15, 15)
            self.content_container.setStyleSheet(f"#DialogContainer {{ background-color: {COLORS['bg_dark']}; border-radius: 12px; }}" + STYLES['dialog'])
            self.title_bar.setStyleSheet(f"QWidget {{ background-color: {COLORS['bg_mid']}; border-top-left-radius: 12px; border-top-right-radius: 12px; border-bottom: 1px solid {COLORS['bg_light']}; }}")
        else:
            self.showMaximized(); self.btn_max.setIcon(create_svg_icon("win_restore.svg", "#aaa")); self.outer_layout.setContentsMargins(0, 0, 0, 0)
            self.content_container.setStyleSheet(f"#DialogContainer {{ background-color: {COLORS['bg_dark']}; border-radius: 0px; }}" + STYLES['dialog'])
            self.title_bar.setStyleSheet(f"QWidget {{ background-color: {COLORS['bg_mid']}; border-radius: 0px; border-bottom: 1px solid {COLORS['bg_light']}; }}")

    def _set_color(self, color):
        self.selected_color = color
        saved_default = load_setting('user_default_color')
        self.chk_set_default.setChecked(saved_default == color)
        for btn in self.color_btns:
            style = btn.styleSheet()
            if color in style: new_style = f"background-color: {color}; border-radius: 17px; border: 3px solid white;"
            else: bg = style.split('background-color:')[1].split(';')[0].strip(); new_style = f"background-color: {bg}; border-radius: 17px; border: 2px solid transparent;"
            btn.setStyleSheet(f"QPushButton {{ {new_style} }}")

    def _init_completer(self):
        all_tags = self.db.get_all_tags()
        self.completer = QCompleter(all_tags, self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.setWidget(self.tags_inp)
        self.completer.activated.connect(self._on_completion_activated)
        self.tags_inp.textEdited.connect(self._update_completion_prefix)

    def _update_completion_prefix(self, text):
        cursor_pos = self.tags_inp.cursorPosition()
        text_before = text[:cursor_pos]
        last_comma = text_before.rfind(',')
        prefix = text_before[last_comma+1:].strip() if last_comma != -1 else text_before.strip()
        if prefix:
            self.completer.setCompletionPrefix(prefix)
            if self.completer.completionCount() > 0:
                cr = self.tags_inp.cursorRect(); cr.setWidth(self.completer.popup().sizeHintForColumn(0) + self.completer.popup().verticalScrollBar().sizeHint().width())
                self.completer.complete(cr)
            else: self.completer.popup().hide()
        else: self.completer.popup().hide()

    def _on_completion_activated(self, text):
        current_text = self.tags_inp.text()
        cursor_pos = self.tags_inp.cursorPosition()
        text_before = current_text[:cursor_pos]
        last_comma = text_before.rfind(',')
        start_replace = last_comma + 1 if last_comma != -1 else 0
        prefix = current_text[:start_replace]
        suffix = current_text[cursor_pos:]
        new_text = prefix + text + ", " + suffix
        self.tags_inp.setText(new_text)
        self.tags_inp.setCursorPosition(len(prefix) + len(text) + 2)

    def _toggle_search_bar(self):
        self.search_bar.setVisible(not self.search_bar.isVisible())
        if self.search_bar.isVisible():
            self.search_inp.setFocus()
            sel = self.content_inp.textCursor().selectedText()
            if sel: self.search_inp.setText(sel)
        else: self.content_inp.setFocus()

    def _find_next(self):
        text = self.search_inp.text()
        if not text: return
        if not self.content_inp.find(text):
            curr = self.content_inp.textCursor(); self.content_inp.moveCursor(QTextCursor.Start)
            if not self.content_inp.find(text): self.content_inp.setTextCursor(curr)

    def _find_prev(self):
        text = self.search_inp.text()
        if not text: return
        if not self.content_inp.find(text, QTextDocument.FindBackward):
            curr = self.content_inp.textCursor(); self.content_inp.moveCursor(QTextCursor.End)
            if not self.content_inp.find(text, QTextDocument.FindBackward): self.content_inp.setTextCursor(curr)

    def _load_data(self):
        d = self.db.get_idea(self.idea_id, include_blob=True)
        if d:
            self.title_inp.setText(d[1])
            item_type = d[10] if len(d) > 10 else 'text'
            if item_type != 'image': self.content_inp.setText(d[2])
            else: self.content_inp.clear()
            self._set_color(d[3])
            self.category_id = d[8]
            if self.category_id is not None:
                idx = self.category_combo.findData(self.category_id)
                if idx >= 0: self.category_combo.setCurrentIndex(idx)
            data_blob = d[11] if len(d) > 11 else None
            if item_type == 'image' and data_blob: self.content_inp.set_image_data(data_blob)
            self.tags_inp.setText(','.join(self.db.get_tags(self.idea_id)))

    def _save_data(self):
        title = self.title_inp.text().strip()
        if not title: self.title_inp.setPlaceholderText("标题不能为空!"); self.title_inp.setFocus(); return
        tags = [t.strip() for t in self.tags_inp.text().split(',') if t.strip()]
        
        # 确保保存前退出 Markdown 预览模式，获取最新的纯文本源码
        if hasattr(self.content_inp, 'is_markdown_preview') and self.content_inp.is_markdown_preview:
            self.content_inp.toggle_markdown_preview()
            
        content = self.content_inp.toPlainText()
        color = self.selected_color
        if self.chk_set_default.isChecked(): save_setting('user_default_color', color)
        item_type = 'text'
        data_blob = self.content_inp.get_image_data()
        if data_blob: item_type = 'image'
        cat_id = self.category_combo.currentData()
        if self.idea_id: self.db.update_idea(self.idea_id, title, content, color, tags, cat_id, item_type, data_blob)
        else: self.db.add_idea(title, content, color, tags, cat_id, item_type, data_blob)
        self.data_saved.emit()
        self.accept()

# === 看板窗口 ===
class StatsDialog(BaseDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle('📊 数据看板')
        self.resize(550, 450)
        layout = QVBoxLayout(self.content_container)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        stats_header = QHBoxLayout()
        stats_header.setSpacing(8)
        header_icon = QLabel()
        header_icon.setPixmap(create_svg_icon("display.svg", COLORS['primary']).pixmap(20, 20))
        stats_header.addWidget(header_icon)
        stats_title = QLabel("数据看板")
        stats_title.setStyleSheet(f"color: {COLORS['primary']}; font-size: 16px; font-weight: bold;")
        stats_header.addWidget(stats_title)
        stats_header.addStretch()
        layout.addLayout(stats_header)

        counts = db.get_counts()
        grid = QGridLayout(); grid.setSpacing(15)
        grid.addWidget(self._box("总灵感", counts['all'], COLORS['primary']), 0, 0)
        grid.addWidget(self._box("今日新增", counts['today'], COLORS['success']), 0, 1)
        grid.addWidget(self._box("我的收藏", counts['favorite'], COLORS['warning']), 1, 0)
        grid.addWidget(self._box("待整理", counts['untagged'], COLORS['danger']), 1, 1)
        layout.addLayout(grid)
        layout.addSpacing(10); layout.addWidget(QLabel("热门标签 Top 5"))
        stats = db.get_top_tags()
        if not stats: layout.addWidget(QLabel("暂无标签数据", styleSheet="color:#666; font-style:italic; font-weight:normal;"))
        else:
            max_val = stats[0][1]
            for name, cnt in stats:
                h = QHBoxLayout()
                lbl = QLabel(f"#{name}"); lbl.setFixedWidth(80); lbl.setStyleSheet("color:#eee; font-weight:bold; margin:0;")
                h.addWidget(lbl)
                p = QProgressBar(); p.setMaximum(max_val); p.setValue(cnt); p.setFixedHeight(18); p.setFormat(f" {cnt}")
                p.setStyleSheet(f"QProgressBar {{ background-color: {COLORS['bg_mid']}; border: none; border-radius: 9px; color: white; text-align: center; }} QProgressBar::chunk {{ background-color: {COLORS['primary']}; border-radius: 9px; }}")
                h.addWidget(p); layout.addLayout(h)
        layout.addStretch()
        close_btn = QPushButton("关闭"); close_btn.setFixedHeight(40); close_btn.setStyleSheet(f"background-color:{COLORS['bg_mid']}; border:1px solid #444; color:#ccc; border-radius:5px;"); close_btn.clicked.connect(self.accept); layout.addWidget(close_btn)

    def _box(self, t, v, c):
        f = QFrame(); f.setStyleSheet(f"QFrame {{ background-color: {c}15; border: 1px solid {c}40; border-radius: 10px; }}")
        vl = QVBoxLayout(f); vl.setContentsMargins(15, 15, 15, 15)
        lbl_title = QLabel(t); lbl_title.setStyleSheet(f"color:{c}; font-size:13px; font-weight:bold; border:none; margin:0;")
        lbl_val = QLabel(str(v)); lbl_val.setStyleSheet(f"color:{c}; font-size:28px; font-weight:bold; border:none; margin-top:5px;")
        vl.addWidget(lbl_title); vl.addWidget(lbl_val)
        return f

# === 提取窗口 ===
class ExtractDialog(BaseDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle('📋 提取内容')
        self.resize(700, 600)
        layout = QVBoxLayout(self.content_container)
        layout.setContentsMargins(20, 20, 20, 20)
        
        extract_header = QHBoxLayout()
        extract_header.setSpacing(8)
        header_icon = QLabel()
        header_icon.setPixmap(create_svg_icon("action_export.svg", COLORS['primary']).pixmap(20, 20))
        extract_header.addWidget(header_icon)
        extract_title = QLabel("提取内容")
        extract_title.setStyleSheet(f"color: {COLORS['primary']}; font-size: 16px; font-weight: bold;")
        extract_header.addWidget(extract_title)
        extract_header.addStretch()
        layout.addLayout(extract_header)

        self.txt = QTextEdit(); self.txt.setReadOnly(True); self.txt.setPlaceholderText("暂无数据..."); layout.addWidget(self.txt)
        data = db.get_ideas('', 'all', None)
        text = '\n' + '-'*60 + '\n'; text += '\n'.join([f"【{d[1]}】\n{d[2]}\n" + '-'*60 for d in data])
        self.txt.setText(text)
        layout.addSpacing(10)
        btn = QPushButton('  复制全部到剪贴板'); btn.setIcon(create_svg_icon("action_export.svg", "white")); btn.setFixedHeight(45); btn.setStyleSheet(STYLES['btn_primary'])
        btn.clicked.connect(lambda: (QApplication.clipboard().setText(text), QMessageBox.information(self,'成功','内容已复制'))); layout.addWidget(btn)

# === 预览窗口 ===
class PreviewDialog(QDialog):
    def __init__(self, item_type, data, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._init_ui(item_type, data)
        QShortcut(QKeySequence(Qt.Key_Escape), self, self.close)
        QShortcut(QKeySequence(Qt.Key_Space), self, self.close)

    def _init_ui(self, item_type, data):
        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(0, 0, 0, 0)
        container = QWidget(); container.setStyleSheet(f"QWidget {{ background-color: {COLORS['bg_dark']}; border: 2px solid {COLORS['bg_mid']}; border-radius: 12px; }}")
        container_layout = QVBoxLayout(container); main_layout.addWidget(container)
        if item_type == 'text': self._setup_text_preview(container_layout, data)
        elif item_type == 'image': self._setup_image_preview(container_layout, data)

    def _setup_text_preview(self, layout, text_data):
        self.resize(600, 500)
        text_edit = QTextEdit(); text_edit.setReadOnly(True); text_edit.setText(text_data)
        text_edit.setStyleSheet("QTextEdit { background-color: transparent; border: none; padding: 15px; color: #ddd; font-size: 14px; }")
        layout.addWidget(text_edit)

    def _setup_image_preview(self, layout, image_data):
        pixmap = QPixmap(); pixmap.loadFromData(image_data)
        if pixmap.isNull():
            label = QLabel("无法加载图片"); label.setAlignment(Qt.AlignCenter); label.setStyleSheet("color: #E81123; font-size: 16px;")
            layout.addWidget(label); self.resize(300, 200); return
        label = QLabel(); label.setAlignment(Qt.AlignCenter); layout.addWidget(label)
        screen_geo = QDesktopWidget().availableGeometry(self)
        max_width = screen_geo.width() * 0.8; max_height = screen_geo.height() * 0.8
        scaled_pixmap = pixmap.scaled(int(max_width), int(max_height), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(scaled_pixmap)
        self.resize(scaled_pixmap.width() + 20, scaled_pixmap.height() + 20)

    def mousePressEvent(self, event): self.close()
```

## 文件: ui\filter_panel.py

```python
# -*- coding: utf-8 -*-
# ui/filter_panel.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                             QTreeWidgetItem, QPushButton, QLabel, QFrame, QApplication, QMenu, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QMimeData, QPoint
from PyQt5.QtGui import QDrag, QPixmap, QPainter, QCursor, QColor, QPen
from core.config import COLORS
from core.shared import get_color_icon
from ui.utils import create_svg_icon
import logging

log = logging.getLogger("FilterPanel")

class FilterPanel(QWidget):
    filterChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_start_pos = None
        self._resize_start_pos = None
        self._resize_start_geometry = None
        self._resize_edge = None  # 'right', 'bottom', 'corner'
        self.resize_margin = 10  # 边缘检测区域宽度（增大到10像素更容易抓取）
        
        # 启用鼠标跟踪以实时更新光标 - 但只在边缘区域
        self.setMouseTracking(False)
        
        # 设置最小和默认尺寸
        self.setMinimumSize(250, 350)
        self.resize(280, 450)
        
        # 主容器
        self.container = QWidget()
        self.container.setObjectName("FilterPanelContainer")
        self.container.setStyleSheet(f"""
            #FilterPanelContainer {{
                background-color: {COLORS['bg_dark']}; 
                border: 1px solid {COLORS['bg_light']};
                border-radius: 12px;
            }}
        """)
        
        # 外层布局（用于阴影）
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.addWidget(self.container)
        
        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.container.setGraphicsEffect(shadow)

        # 内容布局
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(8)
        
        # 标题栏（用于拖拽）
        self.header = QWidget()
        self.header.setFixedHeight(32)
        self.header.setStyleSheet(f"background-color: {COLORS['bg_mid']}; border-radius: 6px;")
        self.header.setCursor(Qt.SizeAllCursor)  # 移动光标
        
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(10, 0, 10, 0)
        
        header_icon = QLabel()
        header_icon.setPixmap(create_svg_icon("select.svg", COLORS['primary']).pixmap(16, 16))
        header_layout.addWidget(header_icon)
        
        header_title = QLabel("高级筛选")
        header_title.setStyleSheet(f"color: {COLORS['primary']}; font-size: 13px; font-weight: bold;")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        
        close_btn = QPushButton()
        close_btn.setIcon(create_svg_icon('win_close.svg', '#888'))
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton { background-color: transparent; border: none; border-radius: 4px; }
            QPushButton:hover { background-color: #e74c3c; }
        """)
        close_btn.clicked.connect(self.hide)
        header_layout.addWidget(close_btn)
        
        self.layout.addWidget(self.header)
        
        # 树形筛选器
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(20)
        self.tree.setFocusPolicy(Qt.NoFocus)
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setAnimated(True)
        self.tree.setAllColumnsShowFocus(True)
        
        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {COLORS['bg_dark']};
                color: #ddd;
                border: none;
                font-size: 12px;
            }}
            QTreeWidget::item {{
                height: 28px;
                border-radius: 4px;
                padding: 2px 5px;
            }}
            QTreeWidget::item:hover {{ background-color: #2a2d2e; }}
            QTreeWidget::item:selected {{ background-color: #37373d; color: white; }}
            QTreeWidget::indicator {{
                width: 14px;
                height: 14px;
            }}
            QScrollBar:vertical {{ border: none; background: transparent; width: 6px; margin: 0px; }}
            QScrollBar::handle:vertical {{ background: #444; border-radius: 3px; min-height: 20px; }}
            QScrollBar::handle:vertical:hover {{ background: #555; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """)
        
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.layout.addWidget(self.tree)
        
        # 底部区域：重置按钮 + 调整大小手柄
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(4)
        
        # 重置按钮（缩窄宽度）
        self.btn_reset = QPushButton(" 重置")
        self.btn_reset.setIcon(create_svg_icon("action_restore.svg", "white"))
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setFixedWidth(80)
        self.btn_reset.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_mid']};
                border: 1px solid #444;
                color: #888;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }}
            QPushButton:hover {{ color: #ddd; background-color: #333; }}
        """)
        self.btn_reset.clicked.connect(self.reset_filters)
        bottom_layout.addWidget(self.btn_reset)
        
        bottom_layout.addStretch()
        
        # 调整大小手柄 - 使用绝对布局确保贴边
        self.resize_handle = QLabel(self.container) # 直接作为容器的子组件，不进入 Layout
        self.resize_handle.setPixmap(create_svg_icon('grip_diagonal.svg', '#666').pixmap(20, 20))
        self.resize_handle.setFixedSize(20, 20)
        self.resize_handle.setCursor(Qt.SizeFDiagCursor)
        self.resize_handle.setStyleSheet("background: transparent; border: none;")
        self.resize_handle.raise_() # 确保在最顶层
        
        self.layout.addLayout(bottom_layout)

        self._block_item_click = False
        self.roots = {}
        
        # 定义结构
        order = [
            ('stars', '评级'),
            ('colors', '颜色'),
            ('types', '类型'),
            ('date_create', '创建时间'),
            ('tags', '标签'),
        ]
        
        # 定义 Header 图标映射 (Icon, Color)
        header_icons = {
            'stars': ('star_filled.svg', '#f39c12'),      # 金色
            'colors': ('palette.svg', '#e91e63'),         # 粉色/调色板
            'types': ('folder.svg', '#3498db'),           # 蓝色
            'date_create': ('calendar.svg', '#2ecc71'),   # 绿色
            'tags': ('tag.svg', '#e67e22')                # 橙色
        }
        
        font_header = self.tree.font()
        font_header.setBold(True)
        
        for key, label in order:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, label)
            # 设置 Header 图标 (带颜色)
            if key in header_icons:
                icon_name, icon_color = header_icons[key]
                item.setIcon(0, create_svg_icon(icon_name, icon_color))
            
            item.setExpanded(True)
            item.setFlags(Qt.ItemIsEnabled) 
            item.setFont(0, font_header)
            item.setForeground(0, Qt.gray)
            self.roots[key] = item
            
        self._add_fixed_date_options('date_create')

    def _add_fixed_date_options(self, key):
        root = self.roots[key]
        options = [
            ("today", "今日", "today.svg"), 
            ("yesterday", "昨日", "clock.svg"), 
            ("week", "本周", "calendar.svg"), 
            ("month", "本月", "calendar.svg")
        ]
        for key_val, label, icon_name in options:
            child = QTreeWidgetItem(root)
            child.setText(0, f"{label} (0)")
            child.setData(0, Qt.UserRole, key_val)
            child.setCheckState(0, Qt.Unchecked)
            # 移除子项图标

    def _on_item_changed(self, item, col):
        if self._block_item_click: return
        
        # 记录最近改变的项，用于防止 itemClicked 重复处理导致状态回退
        # 场景：点击复选框 -> Qt改变状态 -> 触发changed -> 触发clicked -> 代码再次反转状态(错误)
        self._last_changed_item = item
        QTimer.singleShot(100, lambda: setattr(self, '_last_changed_item', None))
        
        self.filterChanged.emit()

    def _on_item_clicked(self, item, column):
        if not item:
            return
            
        # 如果该项刚刚由 Qt 原生机制改变了状态（点击了复选框），则忽略此次点击事件
        if getattr(self, '_last_changed_item', None) == item:
            return
            
        if item.parent() is None:
            item.setExpanded(not item.isExpanded())
        elif item.flags() & Qt.ItemIsUserCheckable:
            self._block_item_click = True
            state = item.checkState(0)
            item.setCheckState(0, Qt.Unchecked if state == Qt.Checked else Qt.Checked)
            self._block_item_click = False
            self.filterChanged.emit()

    def update_stats(self, stats):
        self.tree.blockSignals(True)
        self._block_item_click = True
        
        star_data = []
        # star_icon = create_svg_icon('star_filled.svg', '#f39c12') # 用户倾向于直接显示字符星星
        star_empty_icon = create_svg_icon('star_filled.svg', '#555')
        
        for i in range(5, 0, -1):
            c = stats['stars'].get(i, 0)
            if c > 0: 
                # 回归字符星星显示: ★★★★★
                star_data.append((i, "★" * i, c))
        if stats['stars'].get(0, 0) > 0:
            star_data.append((0, "无评级", stats['stars'][0]))
        self._refresh_node('stars', star_data)

        color_data = []
        for c_hex, count in stats['colors'].items():
            if count > 0:
                # 颜色节点不需要传 icon，因为 is_col=True 会处理
                color_data.append((c_hex, c_hex, count)) 
        self._refresh_node('colors', color_data, is_col=True)
        
        tag_data = []
        # tag_icon = create_svg_icon('tag.svg', '#FFAB91') # 用户要求移除标签列表的图标
        for name, count in stats.get('tags', []):
            tag_data.append((name, name, count))
        self._refresh_node('tags', tag_data)
        
        self._update_fixed_node('date_create', stats.get('date_create', {}))
        
        type_map = {'text': '文本', 'image': '图片', 'file': '文件'}
        type_icons = {
            'text': create_svg_icon('edit_list_ul.svg', '#aaa'),
            'image': create_svg_icon('monitor.svg', '#aaa'), # 或者 action_eye
            'file': create_svg_icon('folder.svg', '#aaa')
        }
        
        type_data = []
        for t, count in stats.get('types', {}).items():
            if count > 0:
                type_data.append((t, type_map.get(t, t), count))
        self._refresh_node('types', type_data)
        
        self._block_item_click = False
        self.tree.blockSignals(False)

    def _refresh_node(self, key, data_list, is_col=False):
        """
        优化后的节点刷新逻辑：
        不再粗暴地 takeChildren() 清空重建，而是尝试复用现有 Item。
        这样可以避免界面闪烁，且保持滚动条位置和点击状态的连贯性。
        data_list: [(key, label, count, icon_obj), ...]  <-- Modified to support icon
        """
        root = self.roots[key]
        
        # 建立现有的 key -> item 映射
        existing_items = {}
        for i in range(root.childCount()):
            child = root.child(i)
            # data(0, Qt.UserRole) 存储的是 key
            item_key = child.data(0, Qt.UserRole)
            existing_items[item_key] = child
            
        # 标记哪些 key 是本次更新中存在的
        current_keys = set()
        
        for data_item in data_list:
            # 兼容旧格式 (key, label, count) 和新格式 (key, label, count, icon)
            if len(data_item) == 4:
                item_key, label, count, icon = data_item
            else:
                item_key, label, count = data_item
                icon = None

            current_keys.add(item_key)
            
            if item_key in existing_items:
                # 更新现有 Item
                child = existing_items[item_key]
                # 只有文本/数量变了才更新，减少重绘
                new_text = f"{label} ({count})"
                if child.text(0) != new_text:
                    child.setText(0, new_text)
                if icon:
                    child.setIcon(0, icon)
            else:
                # 创建新 Item
                child = QTreeWidgetItem(root)
                child.setText(0, f"{label} ({count})")
                child.setData(0, Qt.UserRole, item_key)
                child.setCheckState(0, Qt.Unchecked)
                if icon:
                    child.setIcon(0, icon)
                    
                # 特殊处理颜色圆点
                if is_col:
                    self._set_color_icon(child, item_key) # item_key here is hex color
                    
        # 移除不再存在的 Item
        # 需要倒序移除，否则索引会乱
        for i in range(root.childCount() - 1, -1, -1):
            child = root.child(i)
            if child.data(0, Qt.UserRole) not in current_keys:
                root.removeChild(child)

    def _set_color_icon(self, item, color_hex):
        """为颜色筛选器项设置颜色圆点图标"""
        icon = get_color_icon(color_hex)
        item.setIcon(0, icon)

    def _update_fixed_node(self, key, stats_dict):
        # 对于固定节点 (如：日期)，只更新数字，不增删
        root = self.roots[key]
        labels = {"today": "今日", "yesterday": "昨日", "week": "本周", "month": "本月"}
        
        for i in range(root.childCount()):
            child = root.child(i)
            val = child.data(0, Qt.UserRole)
            count = stats_dict.get(val, 0)
            
            new_text = f"{labels.get(val, val)} ({count})"
            if child.text(0) != new_text:
                child.setText(0, new_text)

    def get_checked_criteria(self):
        criteria = {}
        for key, root in self.roots.items():
            checked_values = []
            for i in range(root.childCount()):
                child = root.child(i)
                if child.checkState(0) == Qt.Checked:
                    checked_values.append(child.data(0, Qt.UserRole))
            if checked_values:
                criteria[key] = checked_values
        return criteria

    def reset_filters(self):
        self.tree.blockSignals(True)
        for key, root in self.roots.items():
            for i in range(root.childCount()):
                root.child(i).setCheckState(0, Qt.Unchecked)
        self.tree.blockSignals(False)
        self.filterChanged.emit()
    
    # --- 拖拽和调整大小逻辑 ---
    def _get_resize_edge(self, pos):
        """检测鼠标是否在边缘，返回边缘类型"""
        rect = self.rect()
        margin = self.resize_margin
        
        # 考虑到外层布局的边距(8px)
        at_right = (rect.width() - pos.x()) <= margin
        at_bottom = (rect.height() - pos.y()) <= margin
        
        if at_right and at_bottom:
            return 'corner'
        elif at_right:
            return 'right'
        elif at_bottom:
            return 'bottom'
        return None
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 检测是否点击了调整大小手柄
            handle_global_rect = self.resize_handle.rect()
            handle_pos = self.resize_handle.mapTo(self, QPoint(0, 0))
            handle_global_rect.translate(handle_pos)
            if handle_global_rect.contains(event.pos()):
                self._resize_edge = 'corner'
                self._resize_start_pos = event.globalPos()
                self._resize_start_geometry = self.geometry()
                self.setCursor(Qt.SizeFDiagCursor)
                event.accept()
                return
            
            # 检测是否在边缘（用于调整大小）
            edge = self._get_resize_edge(event.pos())
            if edge:
                self._resize_edge = edge
                self._resize_start_pos = event.globalPos()
                self._resize_start_geometry = self.geometry()
                if edge == 'corner':
                    self.setCursor(Qt.SizeFDiagCursor)
                elif edge == 'right':
                    self.setCursor(Qt.SizeHorCursor)
                elif edge == 'bottom':
                    self.setCursor(Qt.SizeVerCursor)
                event.accept()
                return
            
            # 在标题栏区域才能拖拽
            header_global_rect = self.header.rect()
            header_pos = self.header.mapTo(self, QPoint(0, 0))
            header_global_rect.translate(header_pos)
            if header_global_rect.contains(event.pos()):
                self._drag_start_pos = event.pos()
                self.setCursor(Qt.SizeAllCursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 处理调整大小
        if self._resize_edge and (event.buttons() & Qt.LeftButton):
            delta = event.globalPos() - self._resize_start_pos
            geo = self._resize_start_geometry
            
            new_width = geo.width()
            new_height = geo.height()
            
            if self._resize_edge in ['right', 'corner']:
                new_width = max(self.minimumWidth(), geo.width() + delta.x())
            if self._resize_edge in ['bottom', 'corner']:
                new_height = max(self.minimumHeight(), geo.height() + delta.y())
            
            self.resize(new_width, new_height)
            event.accept()
            return
        
        # 处理拖拽移动
        if self._drag_start_pos and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPos() - self._drag_start_pos)
            event.accept()
            return
        
        event.ignore()

    def mouseReleaseEvent(self, event):
        self._drag_start_pos = None
        self._resize_edge = None
        self._resize_start_pos = None
        self._resize_start_geometry = None
        self.setCursor(Qt.ArrowCursor)
        
        # 保存尺寸
        from core.settings import save_setting
        save_setting('filter_panel_size', {'width': self.width(), 'height': self.height()})
        
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 始终保持手柄在容器右下角 (考虑容器自身的边框和偏移)
        if hasattr(self, 'resize_handle'):
            # 贴合到底部边角，不需要考虑布局的 margin
            self.resize_handle.move(
                self.container.width() - self.resize_handle.width() - 2,
                self.container.height() - self.resize_handle.height() - 2
            )
```

## 文件: ui\filter_panel_旧版本.py

```python
# -*- coding: utf-8 -*-
# ui/filter_panel.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                             QTreeWidgetItem, QPushButton, QLabel, QFrame, QApplication, QMenu, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QMimeData, QPoint
from PyQt5.QtGui import QDrag, QPixmap, QPainter, QCursor, QColor, QPen
from core.config import COLORS
from core.shared import get_color_icon
from ui.utils import create_svg_icon
import logging

log = logging.getLogger("FilterPanel")

class FilterPanel(QWidget):
    filterChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_start_pos = None
        self._resize_start_pos = None
        self._resize_start_geometry = None
        self._resize_edge = None  # 'right', 'bottom', 'corner'
        self.resize_margin = 10  # 边缘检测区域宽度（增大到10像素更容易抓取）
        
        # 启用鼠标跟踪以实时更新光标 - 但只在边缘区域
        self.setMouseTracking(False)
        
        # 设置最小和默认尺寸
        self.setMinimumSize(250, 350)
        self.resize(280, 450)
        
        # 主容器
        self.container = QWidget()
        self.container.setObjectName("FilterPanelContainer")
        self.container.setStyleSheet(f"""
            #FilterPanelContainer {{
                background-color: {COLORS['bg_dark']}; 
                border: 1px solid {COLORS['bg_light']};
                border-radius: 12px;
            }}
        """)
        
        # 外层布局（用于阴影）
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.addWidget(self.container)
        
        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.container.setGraphicsEffect(shadow)

        # 内容布局
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(8)
        
        # 标题栏（用于拖拽）
        self.header = QWidget()
        self.header.setFixedHeight(32)
        self.header.setStyleSheet(f"background-color: {COLORS['bg_mid']}; border-radius: 6px;")
        self.header.setCursor(Qt.SizeAllCursor)  # 移动光标
        
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(10, 0, 10, 0)
        
        header_icon = QLabel()
        header_icon.setPixmap(create_svg_icon("select.svg", COLORS['primary']).pixmap(16, 16))
        header_layout.addWidget(header_icon)
        
        header_title = QLabel("🔍 高级筛选")
        header_title.setStyleSheet(f"color: {COLORS['primary']}; font-size: 13px; font-weight: bold;")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        
        close_btn = QPushButton()
        close_btn.setIcon(create_svg_icon('win_close.svg', '#888'))
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton { background-color: transparent; border: none; border-radius: 4px; }
            QPushButton:hover { background-color: #e74c3c; }
        """)
        close_btn.clicked.connect(self.hide)
        header_layout.addWidget(close_btn)
        
        self.layout.addWidget(self.header)
        
        # 树形筛选器
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(20)
        self.tree.setFocusPolicy(Qt.NoFocus)
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setAnimated(True)
        self.tree.setAllColumnsShowFocus(True)
        
        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {COLORS['bg_dark']};
                color: #ddd;
                border: none;
                font-size: 12px;
            }}
            QTreeWidget::item {{
                height: 28px;
                border-radius: 4px;
                padding: 2px 5px;
            }}
            QTreeWidget::item:hover {{ background-color: #2a2d2e; }}
            QTreeWidget::item:selected {{ background-color: #37373d; color: white; }}
            QTreeWidget::indicator {{
                width: 14px;
                height: 14px;
            }}
            QScrollBar:vertical {{ border: none; background: transparent; width: 6px; margin: 0px; }}
            QScrollBar::handle:vertical {{ background: #444; border-radius: 3px; min-height: 20px; }}
            QScrollBar::handle:vertical:hover {{ background: #555; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """)
        
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.layout.addWidget(self.tree)
        
        # 底部区域：重置按钮 + 调整大小手柄
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(4)
        
        # 重置按钮（缩窄宽度）
        self.btn_reset = QPushButton("🔄 重置")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setFixedWidth(80)
        self.btn_reset.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_mid']};
                border: 1px solid #444;
                color: #888;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }}
            QPushButton:hover {{ color: #ddd; background-color: #333; }}
        """)
        self.btn_reset.clicked.connect(self.reset_filters)
        bottom_layout.addWidget(self.btn_reset)
        
        bottom_layout.addStretch()
        
        # 调整大小手柄
        self.resize_handle = QLabel("◢")
        self.resize_handle.setFixedSize(30, 30)
        self.resize_handle.setAlignment(Qt.AlignCenter)
        self.resize_handle.setCursor(Qt.SizeFDiagCursor)
        self.resize_handle.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS['bg_mid']};
                border: 1px solid #444;
                border-radius: 6px;
                color: #666;
                font-size: 20px;
                font-weight: bold;
            }}
            QLabel:hover {{ background-color: #333; color: #999; }}
        """)
        bottom_layout.addWidget(self.resize_handle)
        
        self.layout.addLayout(bottom_layout)

        self._block_item_click = False
        self.roots = {}
        
        # 定义结构
        order = [
            ('stars', '评级'),
            ('colors', '颜色'),
            ('types', '类型'),
            ('date_create', '创建时间'),
            ('tags', '标签'),
        ]
        
        # 定义 Header 图标映射 (Icon, Color)
        header_icons = {
            'stars': ('star_filled.svg', '#f39c12'),      # 金色
            'colors': ('palette.svg', '#e91e63'),         # 粉色/调色板
            'types': ('folder.svg', '#3498db'),           # 蓝色
            'date_create': ('calendar.svg', '#2ecc71'),   # 绿色
            'tags': ('tag.svg', '#e67e22')                # 橙色
        }
        
        font_header = self.tree.font()
        font_header.setBold(True)
        
        for key, label in order:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, label)
            # 设置 Header 图标 (带颜色)
            if key in header_icons:
                icon_name, icon_color = header_icons[key]
                item.setIcon(0, create_svg_icon(icon_name, icon_color))
            
            item.setExpanded(True)
            item.setFlags(Qt.ItemIsEnabled) 
            item.setFont(0, font_header)
            item.setForeground(0, Qt.gray)
            self.roots[key] = item
            
        self._add_fixed_date_options('date_create')

    def _add_fixed_date_options(self, key):
        root = self.roots[key]
        options = [
            ("today", "今日", "today.svg"), 
            ("yesterday", "昨日", "clock.svg"), 
            ("week", "本周", "calendar.svg"), 
            ("month", "本月", "calendar.svg")
        ]
        for key_val, label, icon_name in options:
            child = QTreeWidgetItem(root)
            child.setText(0, f"{label} (0)")
            child.setData(0, Qt.UserRole, key_val)
            child.setCheckState(0, Qt.Unchecked)
            child.setIcon(0, create_svg_icon(icon_name, '#888'))

    def _on_item_changed(self, item, col):
        if self._block_item_click: return
        
        # 记录最近改变的项，用于防止 itemClicked 重复处理导致状态回退
        # 场景：点击复选框 -> Qt改变状态 -> 触发changed -> 触发clicked -> 代码再次反转状态(错误)
        self._last_changed_item = item
        QTimer.singleShot(100, lambda: setattr(self, '_last_changed_item', None))
        
        self.filterChanged.emit()

    def _on_item_clicked(self, item, column):
        if not item:
            return
            
        # 如果该项刚刚由 Qt 原生机制改变了状态（点击了复选框），则忽略此次点击事件
        if getattr(self, '_last_changed_item', None) == item:
            return
            
        if item.parent() is None:
            item.setExpanded(not item.isExpanded())
        elif item.flags() & Qt.ItemIsUserCheckable:
            self._block_item_click = True
            state = item.checkState(0)
            item.setCheckState(0, Qt.Unchecked if state == Qt.Checked else Qt.Checked)
            self._block_item_click = False
            self.filterChanged.emit()

    def update_stats(self, stats):
        self.tree.blockSignals(True)
        self._block_item_click = True
        
        star_data = []
        # star_icon = create_svg_icon('star_filled.svg', '#f39c12') # 用户倾向于直接显示字符星星
        star_empty_icon = create_svg_icon('star_filled.svg', '#555')
        
        for i in range(5, 0, -1):
            c = stats['stars'].get(i, 0)
            if c > 0: 
                # 回归字符星星显示: ★★★★★
                star_data.append((i, "★" * i, c))
        if stats['stars'].get(0, 0) > 0:
            star_data.append((0, "无评级", stats['stars'][0], star_empty_icon))
        self._refresh_node('stars', star_data)

        color_data = []
        for c_hex, count in stats['colors'].items():
            if count > 0:
                # 颜色节点不需要传 icon，因为 is_col=True 会处理
                color_data.append((c_hex, c_hex, count)) 
        self._refresh_node('colors', color_data, is_col=True)
        
        tag_data = []
        # tag_icon = create_svg_icon('tag.svg', '#FFAB91') # 用户要求移除标签列表的图标
        for name, count in stats.get('tags', []):
            tag_data.append((name, name, count))
        self._refresh_node('tags', tag_data)
        
        self._update_fixed_node('date_create', stats.get('date_create', {}))
        
        type_map = {'text': '文本', 'image': '图片', 'file': '文件'}
        type_icons = {
            'text': create_svg_icon('edit_list_ul.svg', '#aaa'),
            'image': create_svg_icon('monitor.svg', '#aaa'), # 或者 action_eye
            'file': create_svg_icon('folder.svg', '#aaa')
        }
        
        type_data = []
        for t, count in stats.get('types', {}).items():
            if count > 0:
                icon = type_icons.get(t, create_svg_icon('folder.svg', '#aaa'))
                type_data.append((t, type_map.get(t, t), count, icon))
        self._refresh_node('types', type_data)
        
        self._block_item_click = False
        self.tree.blockSignals(False)

    def _refresh_node(self, key, data_list, is_col=False):
        """
        优化后的节点刷新逻辑：
        不再粗暴地 takeChildren() 清空重建，而是尝试复用现有 Item。
        这样可以避免界面闪烁，且保持滚动条位置和点击状态的连贯性。
        data_list: [(key, label, count, icon_obj), ...]  <-- Modified to support icon
        """
        root = self.roots[key]
        
        # 建立现有的 key -> item 映射
        existing_items = {}
        for i in range(root.childCount()):
            child = root.child(i)
            # data(0, Qt.UserRole) 存储的是 key
            item_key = child.data(0, Qt.UserRole)
            existing_items[item_key] = child
            
        # 标记哪些 key 是本次更新中存在的
        current_keys = set()
        
        for data_item in data_list:
            # 兼容旧格式 (key, label, count) 和新格式 (key, label, count, icon)
            if len(data_item) == 4:
                item_key, label, count, icon = data_item
            else:
                item_key, label, count = data_item
                icon = None

            current_keys.add(item_key)
            
            if item_key in existing_items:
                # 更新现有 Item
                child = existing_items[item_key]
                # 只有文本/数量变了才更新，减少重绘
                new_text = f"{label} ({count})"
                if child.text(0) != new_text:
                    child.setText(0, new_text)
                if icon:
                    child.setIcon(0, icon)
            else:
                # 创建新 Item
                child = QTreeWidgetItem(root)
                child.setText(0, f"{label} ({count})")
                child.setData(0, Qt.UserRole, item_key)
                child.setCheckState(0, Qt.Unchecked)
                if icon:
                    child.setIcon(0, icon)
                    
                # 特殊处理颜色圆点
                if is_col:
                    self._set_color_icon(child, item_key) # item_key here is hex color
                    
        # 移除不再存在的 Item
        # 需要倒序移除，否则索引会乱
        for i in range(root.childCount() - 1, -1, -1):
            child = root.child(i)
            if child.data(0, Qt.UserRole) not in current_keys:
                root.removeChild(child)

    def _set_color_icon(self, item, color_hex):
        """为颜色筛选器项设置颜色圆点图标"""
        icon = get_color_icon(color_hex)
        item.setIcon(0, icon)

    def _update_fixed_node(self, key, stats_dict):
        # 对于固定节点 (如：日期)，只更新数字，不增删
        root = self.roots[key]
        labels = {"today": "今日", "yesterday": "昨日", "week": "本周", "month": "本月"}
        
        for i in range(root.childCount()):
            child = root.child(i)
            val = child.data(0, Qt.UserRole)
            count = stats_dict.get(val, 0)
            
            new_text = f"{labels.get(val, val)} ({count})"
            if child.text(0) != new_text:
                child.setText(0, new_text)

    def get_checked_criteria(self):
        criteria = {}
        for key, root in self.roots.items():
            checked_values = []
            for i in range(root.childCount()):
                child = root.child(i)
                if child.checkState(0) == Qt.Checked:
                    checked_values.append(child.data(0, Qt.UserRole))
            if checked_values:
                criteria[key] = checked_values
        return criteria

    def reset_filters(self):
        self.tree.blockSignals(True)
        for key, root in self.roots.items():
            for i in range(root.childCount()):
                root.child(i).setCheckState(0, Qt.Unchecked)
        self.tree.blockSignals(False)
        self.filterChanged.emit()
    
    # --- 拖拽和调整大小逻辑 ---
    def _get_resize_edge(self, pos):
        """检测鼠标是否在边缘，返回边缘类型"""
        rect = self.rect()
        margin = self.resize_margin
        
        # 考虑到外层布局的边距(8px)
        at_right = (rect.width() - pos.x()) <= margin
        at_bottom = (rect.height() - pos.y()) <= margin
        
        if at_right and at_bottom:
            return 'corner'
        elif at_right:
            return 'right'
        elif at_bottom:
            return 'bottom'
        return None
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 检测是否点击了调整大小手柄
            handle_global_rect = self.resize_handle.rect()
            handle_pos = self.resize_handle.mapTo(self, QPoint(0, 0))
            handle_global_rect.translate(handle_pos)
            if handle_global_rect.contains(event.pos()):
                self._resize_edge = 'corner'
                self._resize_start_pos = event.globalPos()
                self._resize_start_geometry = self.geometry()
                self.setCursor(Qt.SizeFDiagCursor)
                event.accept()
                return
            
            # 检测是否在边缘（用于调整大小）
            edge = self._get_resize_edge(event.pos())
            if edge:
                self._resize_edge = edge
                self._resize_start_pos = event.globalPos()
                self._resize_start_geometry = self.geometry()
                if edge == 'corner':
                    self.setCursor(Qt.SizeFDiagCursor)
                elif edge == 'right':
                    self.setCursor(Qt.SizeHorCursor)
                elif edge == 'bottom':
                    self.setCursor(Qt.SizeVerCursor)
                event.accept()
                return
            
            # 在标题栏区域才能拖拽
            header_global_rect = self.header.rect()
            header_pos = self.header.mapTo(self, QPoint(0, 0))
            header_global_rect.translate(header_pos)
            if header_global_rect.contains(event.pos()):
                self._drag_start_pos = event.pos()
                self.setCursor(Qt.SizeAllCursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 处理调整大小
        if self._resize_edge and (event.buttons() & Qt.LeftButton):
            delta = event.globalPos() - self._resize_start_pos
            geo = self._resize_start_geometry
            
            new_width = geo.width()
            new_height = geo.height()
            
            if self._resize_edge in ['right', 'corner']:
                new_width = max(self.minimumWidth(), geo.width() + delta.x())
            if self._resize_edge in ['bottom', 'corner']:
                new_height = max(self.minimumHeight(), geo.height() + delta.y())
            
            self.resize(new_width, new_height)
            event.accept()
            return
        
        # 处理拖拽移动
        if self._drag_start_pos and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPos() - self._drag_start_pos)
            event.accept()
            return
        
        event.ignore()

    def mouseReleaseEvent(self, event):
        self._drag_start_pos = None
        self._resize_edge = None
        self._resize_start_pos = None
        self._resize_start_geometry = None
        self.setCursor(Qt.ArrowCursor)
        
        # 保存尺寸
        from core.settings import save_setting
        save_setting('filter_panel_size', {'width': self.width(), 'height': self.height()})
        
        super().mouseReleaseEvent(event)
```

## 文件: ui\flow_layout.py

```python
# -*- coding: utf-8 -*-
# ui/flow_layout.py

from PyQt5.QtWidgets import QLayout, QSizePolicy
from PyQt5.QtCore import Qt, QRect, QSize, QPoint

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super(FlowLayout, self).__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margin = self.contentsMargins()
        size += QSize(margin.left() + margin.right(), margin.top() + margin.bottom())
        return size

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        spacing = self.spacing()

        for item in self.itemList:
            wid = item.widget()
            spaceX = spacing + wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Horizontal)
            spaceY = spacing + wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Vertical)
            
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())

        return y + lineHeight - rect.y()
```

## 文件: ui\main_window.py

```python
# -*- coding: utf-8 -*-
# ui/main_window.py
import sys
import math
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QLineEdit,
                               QPushButton, QLabel, QShortcut, QMessageBox,
                               QApplication, QToolTip, QMenu, QFrame, QDialog,
                               QGraphicsDropShadowEffect, QLayout, QSizePolicy, QTextEdit)
from PyQt5.QtCore import Qt, QTimer, QPoint, pyqtSignal, QRect, QSize, QByteArray, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QKeySequence, QCursor, QColor, QIntValidator

from core.config import STYLES, COLORS
from core.settings import load_setting, save_setting
from ui.sidebar import Sidebar
from ui.card_list_view import CardListView 
from ui.dialogs import EditDialog
from ui.advanced_tag_selector import AdvancedTagSelector
from ui.components.search_line_edit import SearchLineEdit
from services.preview_service import PreviewService
from ui.utils import create_svg_icon, create_clear_button_icon
from ui.filter_panel import FilterPanel 

# ==========================================
# 辅助组件类
# ==========================================

class ClickableLineEdit(QLineEdit):
    doubleClicked = pyqtSignal()
    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)

class TagChipWidget(QWidget):
    deleted = pyqtSignal(str)
    def __init__(self, tag_name, parent=None):
        super().__init__(parent)
        self.tag_name = tag_name
        self.setObjectName("TagChip")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 5, 5, 5)
        layout.setSpacing(6)
        self.label = QLabel(tag_name)
        self.label.setStyleSheet("border: none; background: transparent; color: #DDD; font-size: 12px;")
        self.delete_btn = QPushButton()
        self.delete_btn.setIcon(create_svg_icon("win_close.svg", "#AAA"))
        self.delete_btn.setFixedSize(16, 16)
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setStyleSheet(f"QPushButton {{ background-color: transparent; border: none; border-radius: 8px; }} QPushButton:hover {{ background-color: {COLORS['danger']}; }}")
        layout.addWidget(self.label)
        layout.addWidget(self.delete_btn)
        self.setStyleSheet("#TagChip { background-color: #383838; border: 1px solid #4D4D4D; border-radius: 14px; }")
        self.delete_btn.clicked.connect(self._emit_delete)
    def _emit_delete(self):
        self.deleted.emit(self.tag_name)

class InfoWidget(QWidget):
    def __init__(self, icon_name, title, subtitle, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 40, 20, 20)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignCenter)
        icon_label = QLabel()
        icon_label.setPixmap(create_svg_icon(icon_name).pixmap(64, 64))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(icon_label)
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e0e0e0; border: none; background: transparent;")
        layout.addWidget(title_label)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("font-size: 12px; color: #888; border: none; background: transparent;")
        layout.addWidget(subtitle_label)
        layout.addStretch(1)

class MetadataDisplay(QWidget):
    """优化的元数据显示组件 - 使用Widget复用机制提升性能"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: transparent;")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 5, 0, 5)
        self.layout.setSpacing(8)
        self.layout.setAlignment(Qt.AlignTop)
        
        # 预先创建所有行widget,保存值标签的引用
        self.rows = {}
        self._create_all_rows()

    def _create_all_rows(self):
        """预先创建所有固定的元数据行,避免频繁创建/销毁widget"""
        row_configs = [
            ('created', '创建于'),
            ('updated', '更新于'),
            ('category', '分类'),
            ('status', '状态'),
            ('rating', '星级'),
            ('tags', '标签')
        ]
        
        for key, label_text in row_configs:
            row = QWidget()
            row.setObjectName("CapsuleRow")
            row.setAttribute(Qt.WA_StyledBackground, True)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 8, 12, 8)
            row_layout.setSpacing(10)
            
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 11px; color: #AAA; border: none; min-width: 45px; background: transparent;")
            
            val = QLabel()
            val.setWordWrap(True)
            val.setStyleSheet("font-size: 12px; color: #FFF; border: none; font-weight: bold; background: transparent;")
            
            row_layout.addWidget(lbl)
            row_layout.addWidget(val)
            row.setStyleSheet(f"QWidget {{ background-color: transparent; }} #CapsuleRow {{ background-color: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; }}")
            
            self.layout.addWidget(row)
            self.rows[key] = val  # 保存值标签的引用

    def update_data(self, data, tags, category_name):
        """只更新文本内容,不重建widget - 性能提升10倍以上"""
        if not data:
            return
        
        # 批量更新,减少重绘次数
        self.setUpdatesEnabled(False)
        
        # 直接更新文本
        self.rows['created'].setText(data['created_at'][:16])
        self.rows['updated'].setText(data['updated_at'][:16])
        self.rows['category'].setText(category_name if category_name else "未分类")
        
        # 状态
        states = []
        if data['is_pinned']: states.append("置顶")
        if data['is_locked']: states.append("锁定")
        if data['is_favorite']: states.append("书签")
        self.rows['status'].setText(", ".join(states) if states else "无")
        
        # 星级
        rating_str = '★' * data['rating'] + '☆' * (5 - data['rating'])
        self.rows['rating'].setText(rating_str)
        
        # 标签
        self.rows['tags'].setText(", ".join(tags) if tags else "无")
        
        self.setUpdatesEnabled(True)

class TitleEditorDialog(QDialog):
    def __init__(self, current_text, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(320, 180)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.container = QWidget()
        self.container.setStyleSheet(f"QWidget {{ background-color: {COLORS['bg_dark']}; border: 2px solid {COLORS['primary']}; border-radius: 8px; }}")
        inner_layout = QVBoxLayout(self.container)
        inner_layout.setContentsMargins(15, 15, 15, 15)
        title_header = QHBoxLayout()
        title_header.setSpacing(6)
        title_icon = QLabel()
        title_icon.setPixmap(create_svg_icon("action_edit.svg", COLORS['primary']).pixmap(14, 14))
        title_header.addWidget(title_icon)
        label = QLabel("编辑标题")
        label.setStyleSheet("color: #AAA; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        title_header.addWidget(label)
        title_header.addStretch()
        inner_layout.addLayout(title_header)
        self.text_edit = QTextEdit()
        self.text_edit.setText(current_text)
        self.text_edit.setPlaceholderText("请输入标题...")
        self.text_edit.setStyleSheet(f"QTextEdit {{ background-color: {COLORS['bg_mid']}; border: 1px solid #444; border-radius: 6px; color: white; font-size: 14px; padding: 8px; }} QTextEdit:focus {{ border: 1px solid {COLORS['primary']}; }}")
        inner_layout.addWidget(self.text_edit)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_save = QPushButton("保存")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet(f"QPushButton {{ background-color: {COLORS['primary']}; color: white; border: none; border-radius: 4px; padding: 6px 16px; font-weight: bold; }} QPushButton:hover {{ background-color: #357abd; }}")
        self.btn_save.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_save)
        inner_layout.addLayout(btn_layout)
        layout.addWidget(self.container)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.container.setGraphicsEffect(shadow)

    def get_text(self): return self.text_edit.toPlainText().strip()

    def show_at_cursor(self):
        pos = QCursor.pos()
        self.move(pos.x() - 300, pos.y() - 20)
        self.show()
        self.text_edit.setFocus()
        self.text_edit.selectAll()

# ==========================================
# 主窗口类
# ==========================================

class MainWindow(QWidget):
    closing = pyqtSignal()
    RESIZE_MARGIN = 8

    def __init__(self, service):
        super().__init__()
        QApplication.setQuitOnLastWindowClosed(False)
        self.service = service
        self.preview_service = PreviewService(self.service, self)
        
        self.curr_filter = ('all', None)
        self.selected_ids = set()
        self.current_tag_filter = None
        self.last_clicked_id = None 
        self.card_ordered_ids = []
        
        # --- 智能缓存变量 ---
        self.cached_metadata = []   # 当前分类下所有数据的轻量级元数据
        self.filtered_ids = []      # 经过筛选后，当前需要显示的 ID 列表
        self.cards_cache = {}       # 详情数据缓存 (可选，目前简单起见还是依赖 service.get_details)
        # --------------------
        
        self._drag_pos = None
        self._resize_area = None
        self._resize_start_pos = None
        self._resize_start_geometry = None
        self.is_metadata_panel_visible = False
        
        self.is_metadata_panel_visible = False
        
        # 分页状态
        self.current_page = 1
        self.page_size = 100
        self.total_pages = 1
        
        self.open_dialogs = []
        
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.Window | 
            Qt.WindowSystemMenuHint | 
            Qt.WindowMinimizeButtonHint | 
            Qt.WindowMaximizeButtonHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        self.setWindowTitle('数据管理')
        
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        
        self.container = QWidget()
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet(STYLES['main_window'])
        root_layout.addWidget(self.container)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 100))
        self.container.setGraphicsEffect(shadow)
        
        outer_layout = QVBoxLayout(self.container)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        
        # 顶部标题栏
        titlebar = self._create_titlebar()
        outer_layout.addWidget(titlebar)
        
        # --- 中央内容区 ---
        central_content = QWidget()
        central_layout = QHBoxLayout(central_content)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        
        # 1. 侧边栏
        self.sidebar = Sidebar(self.service)
        self.sidebar.filter_changed.connect(self._set_filter)
        self.sidebar.data_changed.connect(self._load_data)
        self.sidebar.new_data_requested.connect(self._on_new_data_in_category_requested)
        self.sidebar.setMinimumWidth(200)
        
        # 2. 中间卡片区
        middle_panel = self._create_middle_panel()

        # 3. 右侧元数据面板
        self.metadata_panel = self._create_metadata_panel()
        self.metadata_panel.setMinimumWidth(0)
        self.metadata_panel.hide()

        # Splitter 布局
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self.sidebar)

        right_container = QWidget()
        right_layout = QHBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(middle_panel, 1)
        right_layout.addWidget(self.metadata_panel)

        self.main_splitter.addWidget(right_container)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([280, 100])
        # 保留接口，虽然 CardListView 现在是自动适应的
        self.main_splitter.splitterMoved.connect(lambda: self.card_list_view.recalc_layout())
        
        central_layout.addWidget(self.main_splitter)
        outer_layout.addWidget(central_content, 1)
        
        # 4. 独立悬浮筛选器
        self.filter_panel = FilterPanel()
        self.filter_panel.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.filter_panel.setAttribute(Qt.WA_TranslucentBackground)
        self.filter_panel.filterChanged.connect(self._on_filter_criteria_changed)
        self.filter_panel.hide()
        
        self._setup_shortcuts()
        self._restore_window_state()

    # --- 分页逻辑 ---
    def _set_page(self, page_num):
        if page_num < 1: page_num = 1
        self.current_page = page_num
        self._load_data()

    def _jump_to_page(self):
        text = self.page_input.text().strip()
        if text.isdigit(): self._set_page(int(text))
        else: self.page_input.setText(str(self.current_page))

    def _update_pagination_ui(self):
        self.page_input.setText(str(self.current_page))
        self.total_page_label.setText(f"/ {self.total_pages}")
        self.btn_first.setDisabled(self.current_page <= 1)
        self.btn_prev.setDisabled(self.current_page <= 1)
        self.btn_next.setDisabled(self.current_page >= self.total_pages)
        self.btn_last.setDisabled(self.current_page >= self.total_pages)

    def _create_titlebar(self):
        titlebar = QWidget()
        titlebar.setFixedHeight(40)
        titlebar.setStyleSheet(f"QWidget {{ background-color: {COLORS['bg_mid']}; border-bottom: 1px solid {COLORS['bg_light']}; border-top-left-radius: 8px; border-top-right-radius: 8px; }}")
        layout = QHBoxLayout(titlebar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(0)
        
        # 应用程序 Logo
        self.app_logo = QLabel()
        self.app_logo.setFixedSize(18, 18)
        self.app_logo.setScaledContents(True)
        # 设置初始占位 Logo (蓝色咖啡)，等待 AppManager 更新为正式 Logo
        from ui.utils import create_svg_icon
        self.app_logo.setPixmap(create_svg_icon('coffee.svg', COLORS['primary']).pixmap(18, 18))
        layout.addWidget(self.app_logo)
        layout.addSpacing(6)
        
        # 初始尝试从 QApplication 获取 (如果已经设置了)
        self.refresh_logo()
        
        title = QLabel('快速笔记')
        title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {COLORS['primary']};")
        layout.addWidget(title)
        layout.addSpacing(15)
        
        self.search = SearchLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText('搜索灵感 (双击查看历史)')
        self.search.setFixedWidth(280)
        self.search.setFixedHeight(28)
        
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
        self.search.setStyleSheet(STYLES['input'] + "QLineEdit { border-radius: 14px; padding-right: 25px; }" + clear_button_style)
        
        self.search.textChanged.connect(lambda: self._set_page(1))
        self.search.returnPressed.connect(self._add_search_to_history)
        layout.addWidget(self.search)
        
        layout.addSpacing(15)
        
        # 分页按钮样式 - 强化圆角和边框
        page_btn_style = f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid #555;
                border-radius: 12px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
                padding: 0px;
            }}
            QPushButton:hover {{ background-color: #333; border-color: #777; }}
            QPushButton:disabled {{ border-color: #333; }}
        """
        
        self.btn_first = QPushButton()
        self.btn_first.setIcon(create_svg_icon('nav_first.svg', '#aaa'))
        self.btn_first.setStyleSheet(page_btn_style)
        self.btn_first.setToolTip("第一页")
        self.btn_first.clicked.connect(lambda: self._set_page(1))
        
        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(create_svg_icon('nav_prev.svg', '#aaa'))
        self.btn_prev.setStyleSheet(page_btn_style)
        self.btn_prev.setToolTip("上一页")
        self.btn_prev.clicked.connect(lambda: self._set_page(self.current_page - 1))
        
        self.page_input = QLineEdit()
        self.page_input.setFixedWidth(40)
        self.page_input.setFixedHeight(24) 
        self.page_input.setAlignment(Qt.AlignCenter)
        self.page_input.setValidator(QIntValidator(1, 9999))
        # 强化样式：增加显眼边框和强制圆角
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
        self.page_input.setToolTip("当前页码")
        self.page_input.returnPressed.connect(self._jump_to_page)
        
        self.total_page_label = QLabel("/ 1")
        self.total_page_label.setStyleSheet("color: #888; font-size: 12px; margin-left: 2px; margin-right: 5px;")
        
        self.btn_next = QPushButton()
        self.btn_next.setIcon(create_svg_icon('nav_next.svg', '#aaa'))
        self.btn_next.setStyleSheet(page_btn_style)
        self.btn_next.setToolTip("下一页")
        self.btn_next.clicked.connect(lambda: self._set_page(self.current_page + 1))
        
        self.btn_last = QPushButton()
        self.btn_last.setIcon(create_svg_icon('nav_last.svg', '#aaa'))
        self.btn_last.setStyleSheet(page_btn_style)
        self.btn_last.setToolTip("最后一页")
        self.btn_last.clicked.connect(lambda: self._set_page(self.total_pages))
        
        layout.addWidget(self.btn_first); layout.addSpacing(6)
        layout.addWidget(self.btn_prev); layout.addSpacing(8)
        layout.addWidget(self.page_input); layout.addSpacing(6)
        layout.addWidget(self.total_page_label); layout.addSpacing(10)
        layout.addWidget(self.btn_next); layout.addSpacing(6)
        layout.addWidget(self.btn_last)
        
        layout.addStretch()
        
        # 功能按钮样式 - 更紧凑
        func_btn_size = 26
        func_btn_style = f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 5px;
                min-width: {func_btn_size}px;
                max-width: {func_btn_size}px;
                min-height: {func_btn_size}px;
                max-height: {func_btn_size}px;
            }}
            QPushButton:hover {{ background-color: rgba(255, 255, 255, 0.1); }}
            QPushButton:pressed {{ background-color: rgba(255, 255, 255, 0.2); }}
        """

        
        # 筛选按钮
        self.filter_btn = QPushButton()
        self.filter_btn.setCheckable(True)
        self.filter_btn.setIcon(create_svg_icon('select.svg', '#FFF'))
        self.filter_btn.setStyleSheet(func_btn_style)
        self.filter_btn.setToolTip("高级筛选 (Ctrl+G)")
        self.filter_btn.clicked.connect(self._toggle_filter_panel)
        layout.addWidget(self.filter_btn)
        layout.addSpacing(4)
        
        # 新建按钮
        new_btn = QPushButton()
        new_btn.setIcon(create_svg_icon('action_add.svg', '#FFF'))
        new_btn.setStyleSheet(func_btn_style)
        new_btn.setToolTip("新建笔记 (Ctrl+N)")
        new_btn.clicked.connect(self.new_idea)
        layout.addWidget(new_btn)
        layout.addSpacing(4)
        
        # 元数据面板切换
        self.toggle_metadata_btn = QPushButton()
        self.toggle_metadata_btn.setCheckable(True)
        self.toggle_metadata_btn.setToolTip("显示/隐藏元数据面板 (Ctrl+I)")
        self.toggle_metadata_btn.setIcon(create_svg_icon('sidebar_right.svg', '#aaa'))
        self.toggle_metadata_btn.setStyleSheet(func_btn_style + f"QPushButton:checked {{ background-color: {COLORS['primary']}; }}")
        self.toggle_metadata_btn.clicked.connect(self._toggle_metadata_panel)
        layout.addWidget(self.toggle_metadata_btn)
        
        layout.addSpacing(12) # 与窗口控制按钮保持充足距离
        
        # 窗口控制按钮
        ctrl_btn_style = func_btn_style
        
        min_btn = QPushButton()
        min_btn.setIcon(create_svg_icon('win_min.svg', '#aaa'))
        min_btn.setStyleSheet(ctrl_btn_style)
        min_btn.setToolTip("最小化")
        min_btn.clicked.connect(self.showMinimized)
        layout.addWidget(min_btn)
        layout.addSpacing(2)
        
        self.max_btn = QPushButton()
        self.max_btn.setIcon(create_svg_icon('win_max.svg', '#aaa'))
        self.max_btn.setStyleSheet(ctrl_btn_style)
        self.max_btn.setToolTip("最大化/还原")
        self.max_btn.clicked.connect(self._toggle_maximize)
        layout.addWidget(self.max_btn)
        layout.addSpacing(2)
        
        close_btn = QPushButton()
        close_btn.setIcon(create_svg_icon('win_close.svg', '#aaa'))
        close_btn.setStyleSheet(ctrl_btn_style + "QPushButton:hover { background-color: #e74c3c; }")
        close_btn.setToolTip("关闭")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        return titlebar

    def _create_middle_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 顶部操作栏
        act_bar = QHBoxLayout()
        act_bar.setSpacing(4)
        act_bar.setContentsMargins(20, 10, 20, 10)
        
        self.header_icon = QLabel()
        self.header_icon.setPixmap(create_svg_icon("all_data.svg", COLORS['primary']).pixmap(20, 20))
        act_bar.addWidget(self.header_icon)
        
        self.header_label = QLabel('全部数据')
        self.header_label.setStyleSheet("font-size:18px;font-weight:bold;")
        act_bar.addWidget(self.header_label)
        
        self.tag_filter_label = QLabel()
        self.tag_filter_label.setStyleSheet(f"background-color: {COLORS['primary']}; color: white; border-radius: 10px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
        self.tag_filter_label.hide()
        act_bar.addWidget(self.tag_filter_label)
        act_bar.addStretch()

        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("color: #444;")
        act_bar.addWidget(separator)
        
        self.btns = {}
        btn_defs = [
            ('pin', 'action_pin.svg', self._do_pin),
            ('fav', 'action_fav.svg', self._do_fav),
            ('edit', 'action_edit.svg', self._do_edit),
            ('extract', 'action_export.svg', self._do_extract_selected), 
            ('del', 'action_delete.svg', self._do_del),
            ('rest', 'action_restore.svg', self._do_restore),
            ('dest', 'action_delete.svg', self._do_destroy)
        ]
        
        # 中间面板功能按钮样式 - 深灰色高亮, 无蓝色
        middle_panel_btn_style = f"""
            QPushButton {{
                background-color: {COLORS['bg_light']};
                border: 1px solid #444;
                border-radius: 6px;
                min-width: 32px;
                min-height: 32px;
            }}
            QPushButton:hover {{
                background-color: #505050;
                border: 1px solid #999;
            }}
            QPushButton:pressed {{
                background-color: #222;
                border: 1px solid #333;
            }}
            QPushButton:disabled {{
                background-color: transparent;
                border: 1px solid #2d2d2d;
                /* Icons will be dimmed by opacity automatically or need specific handling, 
                   but background transparency helps distinguish disabled state. */
                opacity: 0.5; 
            }}
        """
        
        for k, icon_name, f in btn_defs:
            b = QPushButton()
            b.setIcon(create_svg_icon(icon_name, '#aaa'))
            b.setStyleSheet(middle_panel_btn_style)
            b.clicked.connect(f)
            b.setEnabled(False)
            act_bar.addWidget(b)
            self.btns[k] = b
            
        layout.addLayout(act_bar)
        
        self.card_list_view = CardListView(self.service, self)
        
        self.card_list_view.selection_cleared.connect(self._clear_all_selections)
        self.card_list_view.card_selection_requested.connect(self._handle_selection_request)
        self.card_list_view.card_double_clicked.connect(self._extract_single)
        self.card_list_view.card_context_menu_requested.connect(self._show_card_menu)
        
        layout.addWidget(self.card_list_view)
        
        return panel

    def _create_metadata_panel(self):
        panel = QWidget()
        panel.setObjectName("RightPanel")
        panel.setStyleSheet(f"#RightPanel {{ background-color: {COLORS['bg_mid']}; }}")
        panel.setFixedWidth(240)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        title_container = QWidget(); title_container.setStyleSheet("background-color: transparent;")
        title_layout = QHBoxLayout(title_container); title_layout.setContentsMargins(0, 0, 0, 0); title_layout.setSpacing(6)
        icon = QLabel(); icon.setPixmap(create_svg_icon('all_data.svg', '#4a90e2').pixmap(18, 18)); icon.setStyleSheet("background: transparent; border: none;")
        lbl = QLabel("元数据"); lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #4a90e2; background: transparent; border: none;")
        title_layout.addWidget(icon); title_layout.addWidget(lbl); title_layout.addStretch()
        
        layout.addWidget(title_container)

        self.info_stack = QWidget(); self.info_stack.setStyleSheet("background-color: transparent;")
        self.info_stack_layout = QVBoxLayout(self.info_stack); self.info_stack_layout.setContentsMargins(0,0,0,0)
        self.no_selection_widget = InfoWidget('select.svg', "未选择项目", "请选择一个项目以查看其元数据")
        self.multi_selection_widget = InfoWidget('all_data.svg', "已选择多个项目", "请仅选择一项以查看其元数据")
        self.metadata_display = MetadataDisplay()
        self.info_stack_layout.addWidget(self.no_selection_widget); self.info_stack_layout.addWidget(self.multi_selection_widget); self.info_stack_layout.addWidget(self.metadata_display)
        layout.addWidget(self.info_stack)

        self.title_input = ClickableLineEdit()
        self.title_input.setPlaceholderText("标题")
        self.title_input.setAlignment(Qt.AlignLeft)
        self.title_input.setObjectName("CapsuleInput")
        self.title_input.setStyleSheet(f"""
            #CapsuleInput {{
                background-color: rgba(255, 255, 255, 0.05); 
                border: 1px solid rgba(255, 255, 255, 0.1); 
                border-radius: 10px; 
                color: #EEE; 
                font-size: 13px; 
                font-weight: bold; 
                padding: 8px 12px; 
                margin-top: 10px;
            }}
            #CapsuleInput:focus {{
                border: 1px solid {COLORS['primary']}; 
                background-color: rgba(255, 255, 255, 0.08);
            }}
        """)
        self.title_input.editingFinished.connect(self._save_title_from_sidebar)
        self.title_input.returnPressed.connect(self.title_input.clearFocus)
        self.title_input.doubleClicked.connect(self._open_expanded_title_editor)
        layout.addWidget(self.title_input)

        layout.addStretch(1)
        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setFrameShadow(QFrame.Plain); line.setStyleSheet("background-color: #505050; border: none; max-height: 1px; margin-bottom: 5px;"); layout.addWidget(line)

        self.tag_input = ClickableLineEdit(); self.tag_input.setPlaceholderText("输入标签添加... (双击更多)"); self.tag_input.setObjectName("CapsuleTagInput")
        self.tag_input.setStyleSheet(f"#CapsuleTagInput {{ background-color: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 8px 12px; font-size: 12px; color: #EEE; }} #CapsuleTagInput:focus {{ border-color: {COLORS['primary']}; background-color: rgba(255, 255, 255, 0.08); }} #CapsuleTagInput:disabled {{ background-color: transparent; border: 1px solid #333; color: #666; }}")
        self.tag_input.returnPressed.connect(self._handle_tag_input_return)
        self.tag_input.doubleClicked.connect(self._open_tag_selector_for_selection)
        layout.addWidget(self.tag_input)
        
        return panel

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+T"), self, self._handle_extract_key)
        QShortcut(QKeySequence("Ctrl+N"), self, self.new_idea)
        QShortcut(QKeySequence("Ctrl+W"), self, self.close)
        QShortcut(QKeySequence("Ctrl+A"), self, self._select_all)
        QShortcut(QKeySequence("Ctrl+F"), self, self.search.setFocus)
        self.sidebar.filter_changed.connect(self._rebuild_filter_panel)
        self.search.textChanged.connect(self._rebuild_filter_panel)
        QShortcut(QKeySequence("Ctrl+B"), self, self._toggle_sidebar)
        QShortcut(QKeySequence("Ctrl+I"), self, self._toggle_metadata_panel)
        QShortcut(QKeySequence("Ctrl+G"), self, self._toggle_filter_panel)
        QShortcut(QKeySequence("Delete"), self, self._handle_del_key)
        QShortcut(QKeySequence("Ctrl+S"), self, self._do_lock)
        QShortcut(QKeySequence("Ctrl+E"), self, self._do_fav)
        QShortcut(QKeySequence("Ctrl+P"), self, self._do_pin)

        for i in range(6):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, lambda r=i: self._do_set_rating(r))
        
        self.space_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.space_shortcut.setContext(Qt.WindowShortcut)
        self.space_shortcut.activated.connect(lambda: self.preview_service.toggle_preview(self.selected_ids))

    # --- 核心逻辑重构：智能缓存 + 客户端筛选 ---
    
    def _load_data(self):
        """
        [第一步] 刷新缓存：当切换分类、搜索或数据发生变更时调用。
        从数据库拉取当前分类下所有数据的'轻量级元数据'到内存。
        """
        # 数据变更或大分类切换时，重置详情缓存
        self.cards_cache.clear()
        
        # 1. 获取全量元数据
        self.cached_metadata = self.service.get_metadata(
            self.search.text(), 
            self.curr_filter[0], 
            self.curr_filter[1]
        )
        
        # 2. 如果当前有标签筛选(侧边栏的tag)，预先过滤一下
        if self.current_tag_filter:
            # 这里的 tags 数据已经在 repository 的 get_metadata_by_filter 里聚合了
            new_cache = []
            for item in self.cached_metadata:
                if self.current_tag_filter in item['tags']:
                    new_cache.append(item)
            self.cached_metadata = new_cache

        # 3. 重置并应用筛选面板条件
        # self.current_page = 1  (保持当前页码体验可能更好，或者重置为1)
        # 暂时保持逻辑：如果是数据刷新（如新增），可能希望停留在当前？
        # 但如果是搜索变化，Trigger 已经调用了 _set_page(1)。
        
        self._apply_filters_and_render()
        
        # 4. 同步更新筛选面板统计信息 (确保新建/删除后统计正确)
        if self.is_metadata_panel_visible:
            self._rebuild_filter_panel()

    def _apply_filters_and_render(self):
        """
        [第二步] 应用筛选：根据 FilterPanel 的条件过滤内存中的元数据。
        这一步是 纯内存操作，极快，不读库。
        """
        criteria = self.filter_panel.get_checked_criteria()
        
        matched_ids = []
        
        for item in self.cached_metadata:
            match = True
            
            # --- 智能筛选逻辑 ---
            if criteria:
                if 'stars' in criteria:
                    if item['rating'] not in criteria['stars']: match = False
                
                if match and 'colors' in criteria:
                    if item['color'] not in criteria['colors']: match = False
                    
                if match and 'types' in criteria:
                    if (item['item_type'] or 'text') not in criteria['types']: match = False
                
                if match and 'tags' in criteria:
                    # item['tags'] 是 list
                    # 只要包含筛选集中的任意一个？还是所有？通常筛选器逻辑是 OR 或 IN
                    # 假设 criteria['tags'] 是选中的标签名列表
                    has_tag = False
                    for tag in criteria['tags']:
                        if tag in item['tags']:
                            has_tag = True; break
                    if not has_tag: match = False

                if match and 'date_create' in criteria:
                    from datetime import datetime, timedelta
                    created_dt = datetime.strptime(item['created_at'], "%Y-%m-%d %H:%M:%S")
                    created_date = created_dt.date()
                    now_date = datetime.now().date()
                    
                    date_match = False
                    for d_opt in criteria['date_create']:
                        if d_opt == 'today':
                            if created_date == now_date: date_match = True
                        elif d_opt == 'yesterday':
                            if created_date == now_date - timedelta(days=1): date_match = True
                        elif d_opt == 'week':
                            if created_date >= now_date - timedelta(days=6): date_match = True
                        elif d_opt == 'month':
                            if created_date.year == now_date.year and created_date.month == now_date.month: date_match = True
                    
                    if not date_match: match = False
            
            if match:
                matched_ids.append(item['id'])
                
        self.filtered_ids = matched_ids
        
        # 4. 计算分页 (在筛选之后)
        total_items = len(self.filtered_ids)
        self.total_pages = math.ceil(total_items / self.page_size) if total_items > 0 else 1
        
        if self.current_page > self.total_pages: self.current_page = self.total_pages
        if self.current_page < 1: self.current_page = 1
        
        self._render_current_page()

    def _render_current_page(self):
        """
        渲染：从缓存或数据库获取详情数据并显示。
        通过 self.cards_cache 避免重复访问数据库。
        """
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = start_idx + self.page_size
        
        page_ids = self.filtered_ids[start_idx:end_idx]
        
        # 1. 检查哪些 ID 还没在缓存里
        ids_to_fetch = [iid for iid in page_ids if iid not in self.cards_cache]
        
        if ids_to_fetch:
            # 批量获取缺失的详情
            new_details = self.service.get_details(ids_to_fetch)
            for d in new_details:
                self.cards_cache[d['id']] = d
        
        # 2. 从缓存构建当前页的数据列表
        data_list = []
        for iid in page_ids:
            if iid in self.cards_cache:
                data_list.append(self.cards_cache[iid])
        
        # 3. 渲染（采用隐藏/复用策略）
        self.card_list_view.render_cards(data_list)
        self.card_ordered_ids = [d['id'] for d in data_list]
        
        self._update_pagination_ui()
        self._update_ui_state()

    # 原 _on_filter_criteria_changed 方法重写
    def _on_filter_criteria_changed(self):
        self.current_page = 1
        self._apply_filters_and_render()

    def _refresh_metadata_panel(self):
        num_selected = len(self.selected_ids)
        if num_selected == 0:
            self.no_selection_widget.show(); self.multi_selection_widget.hide(); self.metadata_display.hide(); self.title_input.hide(); self.tag_input.setEnabled(False); self.tag_input.setPlaceholderText("请先选择一个项目")
        elif num_selected == 1:
            self.no_selection_widget.hide(); self.multi_selection_widget.hide(); self.metadata_display.show(); self.title_input.show(); self.tag_input.setEnabled(True); self.tag_input.setPlaceholderText("输入标签添加... (双击更多)")
            idea_id = list(self.selected_ids)[0]
            data = self.service.get_idea(idea_id)
            if data:
                self.title_input.setText(data['title'])
                self.title_input.setCursorPosition(0)
                tags = self.service.get_tags(idea_id)
                category_name = ""
                if data['category_id']:
                    all_categories = self.service.get_categories()
                    cat = next((c for c in all_categories if c['id'] == data['category_id']), None)
                    if cat: category_name = cat['name']
                self.metadata_display.update_data(data, tags, category_name)
        else: # num_selected > 1
            self.no_selection_widget.hide(); self.multi_selection_widget.show(); self.metadata_display.hide(); self.title_input.hide(); self.tag_input.setEnabled(False); self.tag_input.setPlaceholderText("请仅选择一项以查看元数据")

    def _open_expanded_title_editor(self):
        if len(self.selected_ids) != 1: return
        idea_id = list(self.selected_ids)[0]
        data = self.service.get_idea(idea_id)
        if not data: return
        
        dialog = TitleEditorDialog(data['title'], self)
        
        def on_save():
            new_title = dialog.get_text()
            if new_title and new_title != data['title']:
                self.service.update_field(idea_id, 'title', new_title)
                self.title_input.setText(new_title)
                self.title_input.setCursorPosition(0)
                # 刷新卡片
                card = self.card_list_view.get_card(idea_id)
                if card:
                    new_data = self.service.get_idea(idea_id, include_blob=True)
                    if new_data: card.update_data(new_data)
        
        dialog.btn_save.clicked.connect(on_save)
        dialog.show_at_cursor()

    # --- 布局控制 ---
    def _toggle_sidebar(self):
        is_collapsed = self.sidebar.width() == 60
        target_width = 280 if is_collapsed else 60
        self.sidebar_animation = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self.sidebar_animation.setDuration(300)
        self.sidebar_animation.setStartValue(self.sidebar.width())
        self.sidebar_animation.setEndValue(target_width)
        self.sidebar_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.sidebar_animation.start()

    def _show_metadata_panel(self):
        if self.is_metadata_panel_visible: return
        self.is_metadata_panel_visible = True
        self.toggle_metadata_btn.setChecked(True)
        save_setting("metadata_panel_visible", True)
        
        self.metadata_panel.show()
        self.metadata_panel.setMaximumWidth(0)
        
        # 优化: 使用更流畅的缓动曲线和更短的动画时间
        self.metadata_animation = QPropertyAnimation(self.metadata_panel, b"maximumWidth")
        self.metadata_animation.setDuration(250)  # 从300ms缩短到250ms
        self.metadata_animation.setStartValue(0)
        self.metadata_animation.setEndValue(240)
        self.metadata_animation.setEasingCurve(QEasingCurve.OutCubic)  # 更自然的缓动
        
        # 同步设置 minimumWidth
        def sync_min_width(value):
            self.metadata_panel.setMinimumWidth(value)
        
        self.metadata_animation.valueChanged.connect(sync_min_width)
        self.metadata_animation.finished.connect(lambda: self.card_list_view.recalc_layout())
        self.metadata_animation.start()


    def _hide_metadata_panel(self):
        if not self.is_metadata_panel_visible: return
        self.is_metadata_panel_visible = False
        self.toggle_metadata_btn.setChecked(False)
        save_setting("metadata_panel_visible", False)
        
        # 优化: 使用更流畅的缓动曲线和更短的动画时间
        self.metadata_animation = QPropertyAnimation(self.metadata_panel, b"maximumWidth")
        self.metadata_animation.setDuration(250)  # 从300ms缩短到250ms
        self.metadata_animation.setStartValue(self.metadata_panel.width())
        self.metadata_animation.setEndValue(0)
        self.metadata_animation.setEasingCurve(QEasingCurve.InCubic)  # 更自然的缓动
        
        # 同步设置 minimumWidth
        def sync_min_width(value):
            self.metadata_panel.setMinimumWidth(value)
        
        self.metadata_animation.valueChanged.connect(sync_min_width)
        self.metadata_animation.finished.connect(self.metadata_panel.hide)
        self.metadata_animation.finished.connect(lambda: self.card_list_view.recalc_layout())
        self.metadata_animation.start()


    def _toggle_metadata_panel(self):
        if self.is_metadata_panel_visible:
            self._hide_metadata_panel()
        else:
            self._show_metadata_panel()

    def _toggle_filter_panel(self):
        if self.filter_panel.isVisible():
            self.filter_panel.hide()
            self.filter_btn.setChecked(False)
        else:
            saved_size = load_setting('filter_panel_size')
            if saved_size and 'width' in saved_size: self.filter_panel.resize(saved_size['width'], saved_size['height'])
            main_geo = self.geometry()
            x = main_geo.right() - self.filter_panel.width() - 20
            y = main_geo.bottom() - self.filter_panel.height() - 20
            self.filter_panel.move(x, y)
            self.filter_panel.show(); self.filter_panel.raise_(); self.filter_panel.activateWindow()
            self.filter_btn.setChecked(True)
            self._rebuild_filter_panel()


    def _rebuild_filter_panel(self):
        stats = self.service.get_filter_stats(self.search.text(), self.curr_filter[0], self.curr_filter[1])
        self.filter_panel.update_stats(stats)
    
    # --- 其他辅助逻辑 ---
    def _save_title_from_sidebar(self):
        if len(self.selected_ids) != 1: return
        new_title = self.title_input.text().strip()
        if not new_title: return
        idea_id = list(self.selected_ids)[0]
        self.service.update_field(idea_id, 'title', new_title)
        card = self.card_list_view.get_card(idea_id)
        if card:
            data = self.service.get_idea(idea_id, include_blob=True)
            if data: card.update_data(data)

    def _handle_tag_input_return(self):
        text = self.tag_input.text().strip()
        if not text: return
        if self.selected_ids:
            self._add_tag_to_selection([text])
            self.tag_input.clear()

    def _open_tag_selector_for_selection(self):
        if self.selected_ids:
            selector = AdvancedTagSelector(self.service, idea_id=None, initial_tags=[])
            selector.tags_confirmed.connect(self._add_tag_to_selection)
            selector.show_at_cursor()

    def _add_tag_to_selection(self, tags):
        if not self.selected_ids or not tags: return
        self.service.add_tags_to_multiple_ideas(list(self.selected_ids), tags)
        self._refresh_all()

    def _add_search_to_history(self):
        search_text = self.search.text().strip()
        if search_text: self.search.add_history_entry(search_text)
        
    def new_idea(self):
        self._open_edit_dialog()
        
    def _do_edit(self):
        if len(self.selected_ids) == 1:
            idea_id = list(self.selected_ids)[0]
            status = self.service.get_lock_status([idea_id])
            if status.get(idea_id, 0): return
            self._open_edit_dialog(idea_id=idea_id)
            
    def _open_edit_dialog(self, idea_id=None, category_id_for_new=None):
        for dialog in self.open_dialogs:
            if hasattr(dialog, 'idea_id') and dialog.idea_id == idea_id and idea_id is not None:
                dialog.activateWindow(); return
        dialog = EditDialog(self.service, idea_id=idea_id, category_id_for_new=category_id_for_new, parent=None)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.data_saved.connect(self._refresh_all)
        dialog.finished.connect(lambda: self.open_dialogs.remove(dialog) if dialog in self.open_dialogs else None)
        self.open_dialogs.append(dialog)
        dialog.show(); dialog.activateWindow()
        
    def _extract_single(self, idea_id):
        data = self.service.get_idea(idea_id)
        if not data: self._show_tooltip('数据不存在', 1500); return
        content = data['content'] or ""
        QApplication.clipboard().setText(content)
        preview = content.replace('\n', ' ')[:40] + ('...' if len(content)>40 else '')
        self._show_tooltip(f'内容已提取到剪贴板\n\n{preview}', 2500)

    def _do_extract_selected(self):
        """提取选中项的内容到剪贴板"""
        if not self.selected_ids: return
        
        # 获取选中的数据
        ideas = []
        for iid in self.selected_ids:
            data = self.service.get_idea(iid)
            if data:
                ideas.append(data)
        
        if not ideas: return
        
        if len(ideas) == 1:
            # 单个提取
            self._extract_single(ideas[0]['id'])
        else:
            # 多个提取
            text = '\n'.join([f"【{d['title']}】\n{d['content']}\n{'-'*60}" for d in ideas])
            QApplication.clipboard().setText(text)
            self._show_tooltip(f'已提取 {len(ideas)} 条选中笔记到剪贴板!', 2000)

        
    def _extract_all(self):
        data = self.service.get_ideas('', 'all', None)
        if not data: self._show_tooltip('暂无数据', 1500); return
        text = '\n'.join([f"【{d['title']}】\n{d['content']}\n{'-'*60}" for d in data])
        QApplication.clipboard().setText(text)
        self._show_tooltip(f'已提取 {len(data)} 条到剪贴板!', 2000)
        
    def _handle_extract_key(self):
        if len(self.selected_ids) == 1: self._extract_single(list(self.selected_ids)[0])
        else: self._show_tooltip('请选择一条笔记', 1500)
        
    def _handle_del_key(self):
        self._do_destroy() if self.curr_filter[0] == 'trash' else self._do_del()
        
    def _refresh_all(self):
        if not self.isVisible(): return
        QTimer.singleShot(10, self._load_data)
        QTimer.singleShot(10, self.sidebar.refresh)
        QTimer.singleShot(10, self._update_ui_state)
        
    def _show_tooltip(self, msg, dur=2000):
        QToolTip.showText(QCursor.pos(), msg, self)
        QTimer.singleShot(dur, QToolTip.hideText)
        
    def _set_filter(self, f_type, val):
        if self.curr_filter == (f_type, val): return
        
        self.curr_filter = (f_type, val)
        self.selected_ids.clear()
        self.last_clicked_id = None
        self.current_tag_filter = None
        self.tag_filter_label.hide()
        
        # 切换大分类时，清空缓存和卡片池，释放内存并保证数据最新
        self.cards_cache.clear()
        self.card_list_view.clear_all()
        
        titles = {'all':'全部数据','today':'今日数据','trash':'回收站','favorite':'我的收藏'}
        cat_name = '文件夹'
        if f_type == 'category':
            for c in self.service.get_categories():
                if c['id'] == val:
                    cat_name = c['name']
                    break
        self.header_label.setText(f"{cat_name}" if f_type=='category' else titles.get(f_type, '灵感列表'))
        
        icon_map = {
            'all': 'all_data.svg',
            'today': 'today.svg',
            'uncategorized': 'uncategorized.svg',
            'untagged': 'untagged.svg',
            'bookmark': 'bookmark.svg',
            'trash': 'trash.svg',
            'category': 'folder.svg'
        }
        icon_name = icon_map.get(f_type, 'all_data.svg')
        self.header_icon.setPixmap(create_svg_icon(icon_name, COLORS['primary']).pixmap(20, 20))
        self._refresh_all()
        QTimer.singleShot(10, self._rebuild_filter_panel)
        
    def _on_filter_criteria_changed(self):
        # 筛选条件改变时，只在内存中重新过滤，不查数据库
        self.current_page = 1
        self._apply_filters_and_render()


        
    def _on_new_data_in_category_requested(self, cat_id):
        self._open_edit_dialog(category_id_for_new=cat_id)
    
    def _update_all_card_selections(self):
        self.card_list_view.update_all_selections(self.selected_ids)

    def _clear_all_selections(self):
        if not self.selected_ids: return
        self.selected_ids.clear()
        self.last_clicked_id = None
        self._update_all_card_selections()
        self._update_ui_state()
        
    def _select_all(self):
        if not self.card_ordered_ids: return
        if len(self.selected_ids) == len(self.card_ordered_ids):
            self.selected_ids.clear()
        else:
            self.selected_ids = set(self.card_ordered_ids)
        self._update_all_card_selections()
        self._update_ui_state()

    def _do_pin(self):
        if self.selected_ids:
            for iid in self.selected_ids: self.service.toggle_field(iid, 'is_pinned')
            self._load_data()

    def _do_fav(self):
        if self.selected_ids:
            any_not_favorited = False
            for iid in self.selected_ids:
                data = self.service.get_idea(iid)
                if data and not data['is_favorite']:
                    any_not_favorited = True
                    break
            target_state = True if any_not_favorited else False
            for iid in self.selected_ids:
                self.service.set_favorite(iid, target_state)
            
            for iid in self.selected_ids:
                card = self.card_list_view.get_card(iid)
                if card:
                    new_data = self.service.get_idea(iid, include_blob=True)
                    if new_data: card.update_data(new_data)
            
            self._update_ui_state()
            self.sidebar.refresh()

    def _do_del(self):
        if self.selected_ids:
            valid_ids = self._get_valid_ids_ignoring_locked(self.selected_ids)
            if not valid_ids: 
                self._show_tooltip("🔒 锁定项目无法删除", 1500)
                return
            
            for iid in valid_ids:
                self.service.set_deleted(iid, True)
                self.card_list_view.remove_card(iid)
            
            self.selected_ids.clear()
            self._update_ui_state()
            self.sidebar.refresh()

    def _do_restore(self):
        if self.selected_ids:
            for iid in self.selected_ids:
                self.service.set_deleted(iid, False)
                self.card_list_view.remove_card(iid)
            self.selected_ids.clear()
            self._update_ui_state()
            self.sidebar.refresh()

    def _do_destroy(self):
        if self.selected_ids:
            msg = f'确定永久删除选中的 {len(self.selected_ids)} 项?\n此操作不可恢复!'
            if QMessageBox.Yes == QMessageBox.question(self, "永久删除", msg):
                for iid in self.selected_ids:
                    self.service.delete_permanent(iid)
                    self.card_list_view.remove_card(iid)
                self.selected_ids.clear()
                self._update_ui_state()
                self.sidebar.refresh()

    def _do_set_rating(self, rating):
        if not self.selected_ids: return
        for idea_id in self.selected_ids:
            self.service.set_rating(idea_id, rating)
            card = self.card_list_view.get_card(idea_id)
            if card:
                new_data = self.service.get_idea(idea_id, include_blob=True)
                if new_data: card.update_data(new_data)

    def _do_lock(self):
        if not self.selected_ids: return
        status_map = self.service.get_lock_status(list(self.selected_ids))
        any_unlocked = any(not locked for locked in status_map.values())
        target_state = 1 if any_unlocked else 0
        self.service.set_locked(list(self.selected_ids), target_state)
        for iid in self.selected_ids:
            card = self.card_list_view.get_card(iid)
            if card:
                new_data = self.service.get_idea(iid, include_blob=True)
                if new_data: card.update_data(new_data)
        self._update_ui_state()

    def _get_valid_ids_ignoring_locked(self, ids):
        valid = []
        status_map = self.service.get_lock_status(list(ids))
        for iid in ids:
            if not status_map.get(iid, 0):
                valid.append(iid)
        return valid

    def _move_to_category(self, cat_id):
        if self.selected_ids:
            valid_ids = list(self.selected_ids)
            if not valid_ids: return
            for iid in valid_ids:
                self.service.move_category(iid, cat_id)
                self.card_list_view.remove_card(iid)
            self.selected_ids.clear()
            self._update_ui_state()
            self.sidebar.refresh()

    def _update_ui_state(self):
        in_trash = (self.curr_filter[0] == 'trash')
        selection_count = len(self.selected_ids)
        has_selection = selection_count > 0
        is_single = selection_count == 1
        
        for k in ['pin', 'fav', 'extract', 'del']: self.btns[k].setVisible(not in_trash)
        for k in ['rest', 'dest']: self.btns[k].setVisible(in_trash)
        self.btns['edit'].setVisible(not in_trash)
        self.btns['edit'].setEnabled(is_single)
        for k in ['pin', 'fav', 'extract', 'del', 'rest', 'dest']: self.btns[k].setEnabled(has_selection)
        
        if is_single and not in_trash:
            idea_id = list(self.selected_ids)[0]
            d = self.service.get_idea(idea_id)
            if d:
                if d['is_pinned']:
                    self.btns['pin'].setIcon(create_svg_icon('pin_vertical.svg', '#e74c3c')) 
                else:
                    self.btns['pin'].setIcon(create_svg_icon('pin_tilted.svg', '#aaaaaa')) 
        else:
            self.btns['pin'].setIcon(create_svg_icon('pin_tilted.svg', '#aaaaaa'))
            
        QTimer.singleShot(0, self._refresh_metadata_panel)

    def _handle_selection_request(self, iid, is_ctrl, is_shift):
        if is_shift and self.last_clicked_id is not None:
            try:
                start_index = self.card_ordered_ids.index(self.last_clicked_id)
                end_index = self.card_ordered_ids.index(iid)
                min_idx = min(start_index, end_index)
                max_idx = max(start_index, end_index)
                if not is_ctrl: self.selected_ids.clear()
                for idx in range(min_idx, max_idx + 1):
                    self.selected_ids.add(self.card_ordered_ids[idx])
            except ValueError:
                self.selected_ids.clear()
                self.selected_ids.add(iid)
                self.last_clicked_id = iid
        elif is_ctrl:
            if iid in self.selected_ids: self.selected_ids.remove(iid)
            else: self.selected_ids.add(iid)
            self.last_clicked_id = iid
        else:
            self.selected_ids.clear()
            self.selected_ids.add(iid)
            self.last_clicked_id = iid
            
        self._update_all_card_selections()
        QTimer.singleShot(0, self._update_ui_state)

    def _show_card_menu(self, idea_id, pos):
        if idea_id not in self.selected_ids:
            self.selected_ids = {idea_id}
            self.last_clicked_id = idea_id
            self._update_all_card_selections()
            self._update_ui_state()
            
        data = self.service.get_idea(idea_id)
        if not data: return
        
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ 
                background-color: {COLORS['bg_mid']}; 
                color: white; 
                border: 1px solid {COLORS['bg_light']}; 
                border-radius: 6px; 
                padding: 4px; 
            }} 
            QMenu::item {{ 
                padding: 6px 10px 6px 28px; 
                border-radius: 4px; 
            }} 
            QMenu::item:selected {{ 
                background-color: {COLORS['primary']}; 
            }} 
            QMenu::separator {{ 
                height: 1px; 
                background: {COLORS['bg_light']}; 
                margin: 4px 0px; 
            }}
            QMenu::icon {{
                position: absolute;
                left: 6px;
                top: 6px;
            }}
        """)
        
        in_trash = (self.curr_filter[0] == 'trash')
        is_locked = data['is_locked']
        rating = data['rating']
        
        if not in_trash:
            menu.addAction(create_svg_icon('action_edit.svg', '#4a90e2'), '编辑', self._do_edit)
            menu.addAction(create_svg_icon('action_export.svg', '#1abc9c'), '提取(Ctrl+T)', lambda: self._extract_single(idea_id))
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
                menu.addAction(create_svg_icon('lock.svg', COLORS['success']), '解锁', self._do_lock)
            else:
                menu.addAction(create_svg_icon('lock.svg', '#aaaaaa'), '锁定 (Ctrl+S)', self._do_lock)
                
            menu.addSeparator()
            
            if data['is_pinned']:
                menu.addAction(create_svg_icon('pin_vertical.svg', '#e74c3c'), '取消置顶', self._do_pin)
            else:
                menu.addAction(create_svg_icon('pin_tilted.svg', '#aaaaaa'), '置顶', self._do_pin)
            
            menu.addAction(create_svg_icon('bookmark.svg', '#ff6b81'), '取消书签' if data['is_favorite'] else '添加书签', self._do_fav)
            menu.addSeparator()
            
            cat_menu = menu.addMenu(create_svg_icon('folder.svg', '#cccccc'), '移动到分类')
            cat_menu.addAction('⚠️ 未分类', lambda: self._move_to_category(None))
            for cat in self.service.get_categories():
                cat_menu.addAction(f'📂 {cat["name"]}', lambda cid=cat["id"]: self._move_to_category(cid))
            
            menu.addSeparator()
            
            if not is_locked:
                menu.addAction(create_svg_icon('action_delete.svg', '#e74c3c'), '移至回收站', self._do_del)
            else:
                act = menu.addAction(create_svg_icon('action_delete.svg', '#555555'), '移至回收站 (已锁定)')
                act.setEnabled(False)
        else:
            menu.addAction(create_svg_icon('action_restore.svg', '#2ecc71'), '恢复', self._do_restore)
            menu.addAction(create_svg_icon('trash.svg', '#e74c3c'), '永久删除', self._do_destroy)
            
        card = self.card_list_view.get_card(idea_id)
        if card: menu.exec_(card.mapToGlobal(pos))

    # --- 窗口拖拽与调整大小逻辑 ---
    def _get_resize_area(self, pos):
        x, y = pos.x(), pos.y(); w, h = self.width(), self.height(); m = self.RESIZE_MARGIN
        areas = []
        if x < m: areas.append('left')
        elif x > w - m: areas.append('right')
        if y < m: areas.append('top')
        elif y > h - m: areas.append('bottom')
        return areas
        
    def _set_cursor_for_resize(self, a):
        if not a: self.setCursor(Qt.ArrowCursor); return
        if 'left' in a and 'top' in a: self.setCursor(Qt.SizeFDiagCursor)
        elif 'right' in a and 'bottom' in a: self.setCursor(Qt.SizeFDiagCursor)
        elif 'left' in a and 'bottom' in a: self.setCursor(Qt.SizeBDiagCursor)
        elif 'right' in a and 'top' in a: self.setCursor(Qt.SizeBDiagCursor)
        elif 'left' in a or 'right' in a: self.setCursor(Qt.SizeHorCursor)
        elif 'top' in a or 'bottom' in a: self.setCursor(Qt.SizeVerCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            areas = self._get_resize_area(event.pos())
            if areas: self.resize_area = areas; self.resize_start_pos = event.globalPos(); self.resize_start_geometry = self.geometry(); self._drag_pos = None
            elif event.y() < 40: self._drag_pos = event.globalPos() - self.frameGeometry().topLeft(); self.resize_area = None
            else: self._drag_pos = None; self.resize_area = None
            event.accept()
            
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.NoButton:
            self._set_cursor_for_resize(self._get_resize_area(event.pos()))
            event.accept(); return
        if event.buttons() == Qt.LeftButton:
            if self.resize_area:
                d = event.globalPos() - self.resize_start_pos; r = self.resize_start_geometry; nr = r.adjusted(0,0,0,0)
                if 'left' in self.resize_area: 
                    nl = r.left() + d.x()
                    if r.right() - nl >= 600: nr.setLeft(nl)
                if 'right' in self.resize_area: 
                    nw = r.width() + d.x()
                    if nw >= 600: nr.setWidth(nw)
                if 'top' in self.resize_area:
                    nt = r.top() + d.y()
                    if r.bottom() - nt >= 400: nr.setTop(nt)
                if 'bottom' in self.resize_area:
                    nh = r.height() + d.y()
                    if nh >= 400: nr.setHeight(nh)
                self.setGeometry(nr)
                event.accept()
            elif self._drag_pos:
                self.move(event.globalPos() - self._drag_pos); event.accept()
                
    def mouseReleaseEvent(self, event):
        self._drag_pos = None; self.resize_area = None; self.setCursor(Qt.ArrowCursor)
        
    def mouseDoubleClickEvent(self, event):
        if event.y() < 40: self._toggle_maximize()
        
    def _toggle_maximize(self):
        if self.isMaximized(): self.showNormal(); self.max_btn.setIcon(create_svg_icon("win_max.svg", "#aaa"))
        else: self.showMaximized(); self.max_btn.setIcon(create_svg_icon("win_restore.svg", "#aaa"))

    def closeEvent(self, event):
        self._save_window_state(); self.closing.emit(); self.hide(); event.ignore()
        
    def _save_window_state(self):
        save_setting("main_window_geometry_hex", self.saveGeometry().toHex().data().decode())
        save_setting("main_window_maximized", self.isMaximized())
        if hasattr(self, "sidebar"): save_setting("sidebar_width", self.sidebar.width())

    def refresh_logo(self):
        """刷新标题栏 Logo"""
        icon = QApplication.windowIcon()
        if not icon.isNull():
            self.app_logo.setPixmap(icon.pixmap(20, 20))
        else:
            # 备选：如果还没有窗口图标，使用 coffee 图标
            from ui.utils import create_svg_icon
            self.app_logo.setPixmap(create_svg_icon('coffee.svg', COLORS['primary']).pixmap(20, 20))

    def save_state(self):
        self._save_window_state()
    
    def _restore_window_state(self):
        geo = load_setting("main_window_geometry_hex")
        if geo: 
            try: self.restoreGeometry(QByteArray.fromHex(geo.encode()))
            except: self.resize(1000, 500)
        else: self.resize(1000, 500)
        if load_setting("main_window_maximized", False): self.showMaximized(); self.max_btn.setIcon(create_svg_icon("win_restore.svg", "#aaa"))
        else: self.max_btn.setIcon(create_svg_icon("win_max.svg", "#aaa"))
        sw = load_setting("sidebar_width")
        if sw and hasattr(self, "main_splitter"): QTimer.singleShot(0, lambda: self.main_splitter.setSizes([int(sw), self.width()-int(sw)]))

        # Restore metadata panel visibility
        if load_setting("metadata_panel_visible", False):
            self._show_metadata_panel()

    def show_main_window(self): self.show(); self.activateWindow()
```

## 文件: ui\quick_window.py

```python
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
        
        title_icon = QLabel()
        title_icon.setPixmap(create_svg_icon("zap.svg", COLORS['primary']).pixmap(16, 16))
        title_bar_layout.addWidget(title_icon)
        
        self.title_label = QLabel("快速笔记")
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
        self.search_box.setPlaceholderText("搜索灵感 (双击查看历史)")
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
            text_part = self._get_content_display(item_tuple)
            
            # 创建自定义显示组件以支持多个 SVG 图标
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(10, 4, 10, 4)
            layout.setSpacing(10)
            
            # 主图标 (如果是图片显示预览，否则显示类型图标)
            icon_lbl = QLabel()
            icon_lbl.setFixedSize(32, 32)
            icon_lbl.setAlignment(Qt.AlignCenter)
            if item_type == 'image' and item_tuple['data_blob']:
                pixmap = QPixmap(); pixmap.loadFromData(item_tuple['data_blob'])
                if not pixmap.isNull():
                    icon_lbl.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                icon_lbl.setPixmap(create_svg_icon("all_data.svg", "#666").pixmap(18, 18))
            layout.addWidget(icon_lbl)
            
            # 文本标签
            lbl = QLabel(text_part)
            lbl.setStyleSheet("color: #ccc; font-size: 13px; background: transparent; border: none;")
            layout.addWidget(lbl, 1)
            
            # 状态图标布局
            status_layout = QHBoxLayout()
            status_layout.setSpacing(6)
            
            # 星级
            rating = item_tuple['rating'] or 0
            if rating > 0:
                stars = QLabel("★" * rating)
                stars.setStyleSheet("color: #f39c12; font-size: 10px;")
                status_layout.addWidget(stars)
            
            # 各种状态图标
            if item_tuple['is_locked']:
                il = QLabel(); il.setPixmap(create_svg_icon("lock.svg", COLORS['success']).pixmap(14, 14))
                status_layout.addWidget(il)
            if item_tuple['is_pinned']:
                ip = QLabel(); ip.setPixmap(create_svg_icon("pin_vertical.svg", "#e74c3c").pixmap(14, 14))
                status_layout.addWidget(ip)
            if item_tuple['is_favorite']:
                if_ = QLabel(); if_.setPixmap(create_svg_icon("bookmark.svg", "#ff6b81").pixmap(14, 14))
                status_layout.addWidget(if_)
                
            layout.addLayout(status_layout)
            
            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, container)
            
            idea_id = item_tuple['id']; category_id = item_tuple['category_id']
            cat_name = categories.get(category_id, "未分类")
            tags = self.db.get_tags(idea_id); tags_str = " ".join([f"#{t}" for t in tags]) if tags else "无"
            
            list_item.setToolTip(f"分区: {cat_name}\n标签: {tags_str}")
            
        if self.list_widget.count() > 0: self.list_widget.setCurrentRow(0)

    def _get_content_display(self, item_tuple):
        # We now return only the text part, icons are handled via setItemWidget
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
                
                menu.addAction('新建数据', lambda: self._request_new_data(cat_id))
                menu.addSeparator()
                menu.addAction('设置颜色', lambda: self._change_color(cat_id))
                menu.addAction('设置预设标签', lambda: self._set_preset_tags(cat_id))
                menu.addSeparator()
                menu.addAction('新建分组', self._new_group)
                menu.addAction('新建分区', lambda: self._new_zone(cat_id))
                menu.addAction('重命名', lambda: self._rename_category(cat_id, current_name))
                menu.addAction('删除', lambda: self._del_category(cat_id))
                
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

```

## 文件: ui\sidebar.py

```python
# -*- coding: utf-8 -*-
# ui/sidebar.py
import random
import os
from PyQt5.QtWidgets import (QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox, QInputDialog, 
                             QFrame, QColorDialog, QDialog, QVBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QHBoxLayout, QApplication, QWidget, QStyle)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QEvent, QTimer
from PyQt5.QtGui import QFont, QColor, QPixmap, QPainter, QIcon, QCursor
from core.config import COLORS
from ui.advanced_tag_selector import AdvancedTagSelector
from ui.utils import create_svg_icon

class ClickableLineEdit(QLineEdit):
    doubleClicked = pyqtSignal()
    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)

class Sidebar(QTreeWidget):
    filter_changed = pyqtSignal(str, object)
    data_changed = pyqtSignal()
    new_data_requested = pyqtSignal(int)

    # 【核心修改】构造函数接收 service
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.db = service # 为了兼容性，变量名暂用 self.db，但实际上是 service
        self.setHeaderHidden(True)
        self.setIndentation(15)
        
        self.setCursor(Qt.ArrowCursor)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(self.InternalMove)

        self.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {COLORS['bg_mid']};
                color: #e0e0e0;
                border: none;
                font-size: 13px;
                padding: 4px;
                outline: none;
            }}
            QTreeWidget::item {{
                height: 28px;
                padding: 1px 4px;
                border-radius: 6px;
                margin-bottom: 2px;
            }}
            QTreeWidget::item:hover {{
                background-color: #2a2d2e;
            }}
            QTreeWidget::item:selected {{
                background-color: #37373d;
                color: white;
            }}
            QScrollBar:vertical {{ border: none; background: transparent; width: 6px; margin: 0px; }}
            QScrollBar::handle:vertical {{ background: #444; border-radius: 3px; min-height: 20px; }}
            QScrollBar::handle:vertical:hover {{ background: #555; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """)

        self.itemClicked.connect(self._on_click)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)
        self.refresh_sync()

    def enterEvent(self, event):
        self.setCursor(Qt.ArrowCursor)
        super().enterEvent(event)

    def refresh(self):
        QTimer.singleShot(10, self.refresh_sync)

    def refresh_sync(self):
        # 【关键修复】保存当前选中项的数据,以便刷新后恢复
        current_selection = None
        current_item = self.currentItem()
        if current_item:
            current_selection = current_item.data(0, Qt.UserRole)
        
        self.blockSignals(True)
        try:
            self.clear()
            self.setColumnCount(1)
            counts = self.db.get_counts()

            system_menu_items = [
                ("全部数据", 'all', 'all_data.svg'),
                ("今日数据", 'today', 'today.svg'),
                ("未分类", 'uncategorized', 'uncategorized.svg'),
                ("未标签", 'untagged', 'untagged.svg'),
                ("书签", 'bookmark', 'bookmark.svg'),
                ("回收站", 'trash', 'trash.svg')
            ]

            for name, key, icon_filename in system_menu_items:
                item = QTreeWidgetItem(self, [f"{name} ({counts.get(key, 0)})"])
                item.setIcon(0, create_svg_icon(icon_filename))
                item.setData(0, Qt.UserRole, (key, None))
                item.setFlags(item.flags() & ~Qt.ItemIsDragEnabled) 
                item.setExpanded(False)

            sep_item = QTreeWidgetItem(self)
            sep_item.setFlags(Qt.NoItemFlags)
            sep_item.setSizeHint(0, QSize(0, 16)) 
            container = QWidget()
            container.setStyleSheet("background: transparent;")
            layout = QVBoxLayout(container)
            layout.setContentsMargins(10, 0, 10, 0)
            layout.setAlignment(Qt.AlignCenter)
            line = QFrame()
            line.setFixedHeight(1) 
            line.setStyleSheet("background-color: #505050; border: none;") 
            layout.addWidget(line)
            self.setItemWidget(sep_item, 0, container)

            user_partitions_root = QTreeWidgetItem(self, ["我的分区"])
            user_partitions_root.setIcon(0, create_svg_icon("all_data.svg", "white"))
            user_partitions_root.setFlags(user_partitions_root.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsDragEnabled)
            font = user_partitions_root.font(0)
            font.setBold(True)
            user_partitions_root.setFont(0, font)
            user_partitions_root.setForeground(0, QColor("#FFFFFF"))
            
            partitions_tree = self.db.get_partitions_tree()
            self._add_partition_recursive(partitions_tree, user_partitions_root, counts.get('categories', {}))
            
            self.expandAll()
            
            # 【关键修复】恢复之前的选中状态
            if current_selection:
                self._restore_selection(current_selection)
                
        finally:
            self.blockSignals(False)
    
    def _restore_selection(self, target_data):
        """恢复指定数据的选中状态"""
        from PyQt5.QtWidgets import QTreeWidgetItemIterator
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            item_data = item.data(0, Qt.UserRole)
            if item_data == target_data:
                self.setCurrentItem(item)
                return
            iterator += 1

    def _create_color_icon(self, color_str):
        pixmap = QPixmap(14, 14)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        c = QColor(color_str if color_str else "#808080")
        painter.setBrush(c)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(1, 1, 12, 12)
        painter.end()
        return QIcon(pixmap)

    def _add_partition_recursive(self, partitions, parent_item, counts):
        for p in partitions:
            count = counts.get(p.id, 0)
            child_counts = sum(counts.get(child.id, 0) for child in p.children)
            total_count = count + child_counts

            item = QTreeWidgetItem(parent_item, [f"{p.name} ({total_count})"])
            item.setIcon(0, self._create_color_icon(p.color))
            item.setData(0, Qt.UserRole, ('category', p.id))
            
            if p.children:
                self._add_partition_recursive(p.children, item, counts)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat('application/x-tree-widget-internal-move') or \
           e.mimeData().hasFormat('application/x-idea-id') or \
           e.mimeData().hasFormat('application/x-idea-ids'):
            e.accept()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        item = self.itemAt(e.pos())
        if item:
            d = item.data(0, Qt.UserRole)
            if d and d[0] in ['category', 'trash', 'bookmark', 'uncategorized']:
                self.setCurrentItem(item)
                e.accept()
                return
            if e.mimeData().hasFormat('application/x-tree-widget-internal-move'):
                e.accept()
                return
        e.ignore()

    def dropEvent(self, e):
        ids_to_process = []
        if e.mimeData().hasFormat('application/x-idea-ids'):
            try:
                data = e.mimeData().data('application/x-idea-ids').data().decode('utf-8')
                ids_to_process = [int(x) for x in data.split(',') if x]
            except Exception: pass
        elif e.mimeData().hasFormat('application/x-idea-id'):
            try: 
                ids_to_process = [int(e.mimeData().data('application/x-idea-id'))]
            except Exception: pass
        
        if ids_to_process:
            try:
                item = self.itemAt(e.pos())
                if not item: return
                d = item.data(0, Qt.UserRole)
                if not d: return
                key, val = d
                
                for iid in ids_to_process:
                    if key == 'category': self.db.move_category(iid, val)
                    elif key == 'uncategorized': self.db.move_category(iid, None)
                    elif key == 'trash': self.db.set_deleted(iid, True)
                    elif key == 'bookmark': self.db.set_favorite(iid, True)
                
                self.data_changed.emit()
                self.refresh()
                e.acceptProposedAction()
            except Exception as err:
                pass
        else:
            super().dropEvent(e)
            self._save_current_order()

    def _save_current_order(self):
        update_list = []
        def iterate_items(parent_item, parent_id):
            for i in range(parent_item.childCount()):
                item = parent_item.child(i)
                data = item.data(0, Qt.UserRole)
                if data and data[0] == 'category':
                    cat_id = data[1]
                    update_list.append({'id': cat_id, 'sort_order': i, 'parent_id': parent_id})
                    if item.childCount() > 0:
                        iterate_items(item, cat_id)
        iterate_items(self.invisibleRootItem(), None)
        if update_list:
            self.db.save_category_order(update_list)

    def _on_click(self, item):
        data = item.data(0, Qt.UserRole)
        if data: self.filter_changed.emit(*data)

    def _show_menu(self, pos):
        item = self.itemAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet("background:#2d2d2d;color:white")

        if not item or item.text(0) == "🗃️ 我的分区":
            menu.addAction('新建组', self._new_group)
            menu.exec_(self.mapToGlobal(pos))
            return

        data = item.data(0, Qt.UserRole)
        if not data: return

        if data[0] == 'trash':
            menu.addAction('清空回收站', self._empty_trash)
            menu.exec_(self.mapToGlobal(pos))
            return

        if data[0] == 'category':
            cat_id = data[1]
            raw_text = item.text(0)
            current_name = raw_text.split(' (')[0]

            menu.addAction('添加数据', lambda: self._request_new_data(cat_id))
            menu.addSeparator()
            menu.addAction('设置颜色', lambda: self._change_color(cat_id))
            menu.addAction('随机颜色', lambda: self._set_random_color(cat_id))
            menu.addAction('设置预设标签', lambda: self._set_preset_tags(cat_id))
            menu.addSeparator()
            menu.addAction('新建组', self._new_group)
            menu.addAction('新建分区', lambda: self._new_zone(cat_id))
            menu.addAction('重命名', lambda: self._rename_category(cat_id, current_name))
            menu.addAction('删除', lambda: self._del_category(cat_id))
            menu.exec_(self.mapToGlobal(pos))

    def _empty_trash(self):
        if QMessageBox.Yes == QMessageBox.warning(self, '清空回收站', '确定要清空回收站吗？\n此操作将永久删除所有内容，不可恢复！', QMessageBox.Yes | QMessageBox.No):
            self.db.empty_trash()
            self.data_changed.emit()
            self.refresh()

    def _set_preset_tags(self, cat_id):
        current_tags = self.db.get_category_preset_tags(cat_id)
        
        dlg = QDialog(self)
        dlg.setWindowTitle("设置预设标签")
        dlg.setStyleSheet(f"background-color: {COLORS['bg_dark']}; color: #EEE;")
        dlg.setFixedSize(350, 150)
        
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)
        
        info = QLabel("拖入该分类时自动绑定以下标签：\n(双击输入框选择历史标签)")
        info.setStyleSheet("color: #888; font-size: 12px; margin-bottom: 5px;")
        layout.addWidget(info)
        
        inp = ClickableLineEdit()
        inp.setText(current_tags)
        inp.setPlaceholderText("例如: 工作, 重要 (逗号分隔)")
        inp.setStyleSheet(f"background-color: {COLORS['bg_mid']}; border: 1px solid #444; padding: 6px; border-radius: 4px; color: white;")
        layout.addWidget(inp)
        
        def open_tag_selector():
            initial_list = [t.strip() for t in inp.text().split(',') if t.strip()]
            selector = AdvancedTagSelector(self.db, idea_id=None, initial_tags=initial_list)
            def on_confirmed(tags):
                inp.setText(', '.join(tags))
            selector.tags_confirmed.connect(on_confirmed)
            selector.show_at_cursor()
            
        inp.doubleClicked.connect(open_tag_selector)
        
        btns = QHBoxLayout()
        btns.addStretch()
        btn_ok = QPushButton("完成")
        btn_ok.setStyleSheet(f"background-color: {COLORS['primary']}; border:none; padding: 5px 15px; border-radius: 4px; font-weight:bold;")
        btn_ok.clicked.connect(dlg.accept)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)
        
        if dlg.exec_() == QDialog.Accepted:
            new_tags = inp.text().strip()
            self.db.set_category_preset_tags(cat_id, new_tags)
            
            tags_list = [t.strip() for t in new_tags.split(',') if t.strip()]
            if tags_list:
                self.db.apply_preset_tags_to_category_items(cat_id, tags_list)
                
            self.data_changed.emit()

    def _change_color(self, cat_id):
        color = QColorDialog.getColor(Qt.gray, self, "选择分类颜色")
        if color.isValid():
            color_name = color.name()
            self.db.set_category_color(cat_id, color_name)
            
            self.refresh()
            self.data_changed.emit()

    def _set_random_color(self, cat_id):
        r = random.randint(0, 255)
        g = random.randint(0, 255)
        b = random.randint(0, 255)
        color = QColor(r, g, b)
        while color.lightness() < 80:
            r = random.randint(0, 255); g = random.randint(0, 255); b = random.randint(0, 255)
            color = QColor(r, g, b)
        self.db.set_category_color(cat_id, color.name())
        self.refresh()
        self.data_changed.emit()

    def _request_new_data(self, cat_id):
        self.new_data_requested.emit(cat_id)

    def _new_group(self):
        text, ok = QInputDialog.getText(self, '新建组', '组名称:')
        if ok and text:
            self.db.add_category(text, parent_id=None)
            self.refresh()
            
    def _new_zone(self, parent_id):
        text, ok = QInputDialog.getText(self, '新建区', '区名称:')
        if ok and text:
            self.db.add_category(text, parent_id=parent_id)
            self.refresh()

    def _rename_category(self, cat_id, old_name):
        text, ok = QInputDialog.getText(self, '重命名', '新名称:', text=old_name)
        if ok and text and text.strip():
            self.db.rename_category(cat_id, text.strip())
            self.refresh()

    def _del_category(self, cid):
        c = self.db.conn.cursor() # 访问 service.conn
        c.execute("SELECT COUNT(*) FROM categories WHERE parent_id = ?", (cid,))
        child_count = c.fetchone()[0]

        msg = '确认删除此分类? (其中的内容将移至未分类)'
        if child_count > 0:
            msg = f'此组包含 {child_count} 个区，确认一并删除?\n(所有内容都将移至未分类)'

        if QMessageBox.Yes == QMessageBox.question(self, '确认删除', msg):
            c.execute("SELECT id FROM categories WHERE parent_id = ?", (cid,))
            child_ids = [row[0] for row in c.fetchall()]
            for child_id in child_ids:
                self.db.delete_category(child_id)
            self.db.delete_category(cid)
            self.refresh()
```

## 文件: ui\success_animation.py

```python
﻿# -*- coding: utf-8 -*-
# ui/success_animation.py

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QPainterPath

class SuccessAnimationWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.progress = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_anim)
        
    def start(self):
        self.progress = 0.0
        self.timer.start(20) # 50fps
        self.show()
        
    def _update_anim(self):
        self.progress += 0.1
        if self.progress >= 1.0:
            self.progress = 1.0
            self.timer.stop()
        self.update()
        
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        # 绘制背景圆圈 (渐现)
        alpha = int(255 * min(1.0, self.progress * 2))
        color = QColor("#2ecc71") # 绿色
        p.setPen(Qt.NoPen)
        color.setAlpha(alpha)
        p.setBrush(color)
        p.drawEllipse(2, 2, 20, 20)
        
        # 绘制打钩 (Stroke 动画)
        if self.progress > 0.3:
            path = QPainterPath()
            path.moveTo(7, 12)
            path.lineTo(10, 15)
            path.lineTo(17, 8)
            
            check_prog = (self.progress - 0.3) / 0.7
            if check_prog > 1: check_prog = 1
            
            # 简单的遮罩或截断实现比较复杂，这里用简单的分段绘制模拟
            # 为保持代码简洁，直接绘制完整钩，配合透明度
            p.setPen(QPen(Qt.white, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            
            # 计算动态路径
            len_total = path.length()
            len_curr = len_total * check_prog
            
            # 创建子路径
            percent = path.percentAtLength(len_curr)
            # 注意: PyQt5旧版本可能没有 pointAtPercent，这里简化处理：
            # 直接画出完整路径，依靠速度快，肉眼看不出太大区别，或者用上面的圆圈淡入即可
            p.drawPath(path)
```

## 文件: ui\tag_selector.py

```python
﻿# -*- coding: utf-8 -*-
# ui/tag_selector.py

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QLineEdit, QScrollArea, QLabel
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QCursor
from core.config import COLORS

class TagSelectorFloat(QWidget):
    """标签选择悬浮面板"""
    tags_confirmed = pyqtSignal(list)
    
    def __init__(self, db, idea_id, parent=None):
        super().__init__(parent)
        self.db = db
        self.idea_id = idea_id
        self.selected_tags = set()
        
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        
        self._init_ui()
        self._load_tags()
        
    def _init_ui(self):
        # 主容器
        container = QWidget()
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_dark']};
                border: 2px solid {COLORS['primary']};
                border-radius: 12px;
            }}
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 标题栏
        header = QHBoxLayout()
        title = QLabel('🏷️ 快速选择标签')
        title.setStyleSheet(f"""
            font-size: 14px; 
            font-weight: bold; 
            color: {COLORS['primary']};
            background: transparent;
            border: none;
        """)
        header.addWidget(title)
        
        close_btn = QPushButton('✕')
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid #666;
                border-radius: 10px;
                color: #999;
                font-size: 12px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['danger']};
                border-color: {COLORS['danger']};
                color: white;
            }}
        """)
        close_btn.clicked.connect(self._on_close)
        header.addWidget(close_btn)
        
        layout.addLayout(header)
        
        hint = QLabel('💡 点击选择标签，失去焦点后自动保存')
        hint.setStyleSheet("""
            color: #888; 
            font-size: 11px; 
            background: transparent;
            border: none;
        """)
        layout.addWidget(hint)
        
        input_layout = QHBoxLayout()
        self.new_tag_input = QLineEdit()
        self.new_tag_input.setPlaceholderText('输入新标签...')
        self.new_tag_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['bg_mid']};
                border: 1px solid {COLORS['bg_light']};
                border-radius: 8px;
                padding: 6px 10px;
                color: #eee;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLORS['primary']};
            }}
        """)
        self.new_tag_input.returnPressed.connect(self._add_new_tag)
        input_layout.addWidget(self.new_tag_input)
        
        add_btn = QPushButton('➕')
        add_btn.setFixedSize(28, 28)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #357abd;
            }}
        """)
        add_btn.clicked.connect(self._add_new_tag)
        input_layout.addWidget(add_btn)
        
        layout.addLayout(input_layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(200)
        # 【关键修复】在此处注入 QScrollBar 样式
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #444;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #555;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
        self.tag_list_widget = QWidget()
        self.tag_list_layout = QVBoxLayout(self.tag_list_widget)
        self.tag_list_layout.setAlignment(Qt.AlignTop)
        self.tag_list_layout.setSpacing(6)
        self.tag_list_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll.setWidget(self.tag_list_widget)
        layout.addWidget(scroll)
        
        self.count_label = QLabel('已选择 0 个标签')
        self.count_label.setStyleSheet(f"""
            color: {COLORS['primary']}; 
            font-size: 11px; 
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        layout.addWidget(self.count_label)
        
        self.setFixedWidth(300)
        
    def _load_tags(self):
        while self.tag_list_layout.count():
            item = self.tag_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        c = self.db.conn.cursor()
        c.execute('''
            SELECT DISTINCT t.name, COUNT(it.idea_id) as cnt 
            FROM tags t
            LEFT JOIN idea_tags it ON t.id = it.tag_id
            LEFT JOIN ideas i ON it.idea_id = i.id AND i.is_deleted = 0
            GROUP BY t.id
            ORDER BY cnt DESC, t.name ASC
        ''')
        all_tags = c.fetchall()
        
        current_tags = set(self.db.get_tags(self.idea_id))
        self.selected_tags = current_tags.copy()
        
        if not all_tags:
            empty = QLabel('暂无标签，请创建新标签')
            empty.setStyleSheet("color: #666; font-style: italic; font-size: 11px;")
            empty.setAlignment(Qt.AlignCenter)
            self.tag_list_layout.addWidget(empty)
        else:
            for tag_name, count in all_tags:
                checkbox = QCheckBox(f'{tag_name} ({count})')
                checkbox.setChecked(tag_name in current_tags)
                checkbox.setStyleSheet(f"""
                    QCheckBox {{
                        color: #ddd;
                        font-size: 12px;
                        spacing: 8px;
                        background: transparent;
                        border: none;
                    }}
                    QCheckBox::indicator {{
                        width: 16px;
                        height: 16px;
                        border: 2px solid #666;
                        border-radius: 4px;
                        background-color: {COLORS['bg_mid']};
                    }}
                    QCheckBox::indicator:checked {{
                        background-color: {COLORS['primary']};
                        border-color: {COLORS['primary']};
                        image: url(none);
                    }}
                    QCheckBox::indicator:hover {{
                        border-color: {COLORS['primary']};
                    }}
                    QCheckBox:hover {{
                        color: white;
                    }}
                """)
                checkbox.stateChanged.connect(lambda state, name=tag_name: self._on_tag_changed(name, state))
                self.tag_list_layout.addWidget(checkbox)
                
        self._update_count()
        
    def _on_tag_changed(self, tag_name, state):
        if state == Qt.Checked:
            self.selected_tags.add(tag_name)
        else:
            self.selected_tags.discard(tag_name)
        self._update_count()
        
    def _add_new_tag(self):
        tag_name = self.new_tag_input.text().strip()
        if not tag_name:
            return
            
        c = self.db.conn.cursor()
        c.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
        if c.fetchone():
            self.selected_tags.add(tag_name)
            self._load_tags()
            self.new_tag_input.clear()
            return
            
        c.execute('INSERT INTO tags (name) VALUES (?)', (tag_name,))
        self.db.conn.commit()
        
        self.selected_tags.add(tag_name)
        
        self._load_tags()
        self.new_tag_input.clear()
        
    def _update_count(self):
        count = len(self.selected_tags)
        self.count_label.setText(f'已选择 {count} 个标签')
        
    def _save_tags(self):
        c = self.db.conn.cursor()
        c.execute('DELETE FROM idea_tags WHERE idea_id = ?', (self.idea_id,))
        
        for tag_name in self.selected_tags:
            c.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
            result = c.fetchone()
            if result:
                tag_id = result[0]
                c.execute('INSERT INTO idea_tags (idea_id, tag_id) VALUES (?, ?)', 
                          (self.idea_id, tag_id))
                self.db.conn.commit()
        
    def _on_close(self):
        self._save_tags()
        self.tags_confirmed.emit(list(self.selected_tags))
        self.close()
        
    def focusOutEvent(self, event):
        self._save_tags()
        self.tags_confirmed.emit(list(self.selected_tags))
        self.close()
        super().focusOutEvent(event)
        
    def show_at_cursor(self):
        cursor_pos = QCursor.pos()
        screen_geo = self.screen().geometry()
        
        x = cursor_pos.x() + 10
        y = cursor_pos.y() + 10
        
        if x + self.width() > screen_geo.right():
            x = cursor_pos.x() - self.width() - 10
            
        if y + self.height() > screen_geo.bottom():
            y = screen_geo.bottom() - self.height() - 10
            
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
```

## 文件: ui\utils.py

```python
# -*- coding: utf-8 -*-
# ui/utils.py

import os
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtCore import Qt, QByteArray
from PyQt5.QtGui import QPalette, QIcon, QPixmap, QPainter
from PyQt5.QtWidgets import QApplication

# ==========================================
# 🎨 专业配色方案 (用于 Icon 智能着色)
# ==========================================
_icon_theme_colors = {
    'all_data.svg':      '#3498db',
    'today.svg':         '#2ecc71',
    'uncategorized.svg': '#e67e22',
    'untagged.svg':      '#95a5a6',
    'bookmark.svg':      '#ff6b81',
    'trash.svg':         '#e74c3c',
    'select.svg':        '#1abc9c',
    'lock.svg':          '#e74c3c', 
    'star_filled.svg':   '#f39c12',
    'action_fav_filled.svg': '#ff6b81', 
    'pencil.svg':        '#aaaaaa',
    'clock.svg':         '#aaaaaa',
    
    # 【新增】置顶图标配色
    'pin_tilted.svg':    '#aaaaaa', # 未置顶：灰色
    'pin_vertical.svg':  '#e74c3c',  # 已置顶：红色
    
    # --- 悬浮球菜单配色 ---
    'display.svg': '#81D4FA',  # 切换外观: 淡蓝色
    'coffee.svg': '#BCAAA4',   # 摩卡: 浅棕色
    'grid.svg': '#90A4AE',     # 黑金: 蓝灰色
    'book.svg': '#9FA8DA',     # 皇家蓝: 薰衣草紫
    'leaf.svg': '#A5D6A7',     # 抹茶: 淡绿色
    'book-open.svg': '#FFCC80',# 手稿: 橘黄色
    'zap.svg': '#FFEB3B',      # 快速笔记: 黄色
    'monitor.svg': '#B0BEC5',  # 主界面: 蓝灰色
    'action_add.svg': '#C5E1A5',# 新建: 淡绿色
    'tag.svg': '#FFAB91',      # 标签: 橙红色
    'power.svg': '#EF9A9A'     # 退出: 淡红色
}

# ==========================================
# 💎 内置 SVG 图标数据 (无符号化)
# ==========================================
_system_icons = {
    # --- 核心导航 ---
    'select.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>""",
    'all_data.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>""",
    'today.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>""",
    'uncategorized.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/></svg>""",
    'untagged.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>""",
    'bookmark.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>""",
    'trash.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>""",
    
    # --- 窗口控制 ---
    'win_close.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>""",
    'win_max.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/></svg>""",
    'win_restore.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="10" height="10" rx="1"/><rect x="11" y="3" width="10" height="10" rx="1"/></svg>""",
    'win_min.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/></svg>""",
    'win_sidebar.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="3" x2="9" y2="21"/></svg>""",
    'sidebar_right.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="15" y1="3" x2="15" y2="21"/></svg>""",

    # --- 功能操作 ---
    'action_add.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>""",
    'action_edit.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>""",
    
    # 【新增】pin_tilted.svg: 倾斜、空心 (Outline)
    'pin_tilted.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" transform="rotate(45 12 12)"><path d="M16 12V8H8v4l-2 2v2h5v6l1 1 1-1v-6h5v-2l-2-2z"></path></svg>""",
    
    # 【新增】pin_vertical.svg: 垂直、实心 (Filled)
    'pin_vertical.svg': """<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M16 9V4h1c.55 0 1-.45 1-1s-.45-1-1-1H7c-.55 0-1 .45-1 1s.45 1 1 1h1v5c0 1.66-1.34 3-3 3v2h5.97v7l1.03 1 1.03-1v-7H19v-2c-1.66 0-3-1.34-3-3z"></path></svg>""",
    
    'action_fav.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>""",
    'action_fav_filled.svg': """<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>""",
    'action_eye.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>""",
    'action_restore.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>""",
    'action_delete.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>""",
    'action_export.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>""",
    'action_save.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>""",
    
    # --- 编辑器工具栏 ---
    'edit_undo.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/></svg>""",
    'edit_redo.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 7v6h-6"/><path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3l3 2.7"/></svg>""",
    'edit_list_ul.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>""",
    'edit_list_ol.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="10" y1="6" x2="21" y2="6"/><line x1="10" y1="12" x2="21" y2="12"/><line x1="10" y1="18" x2="21" y2="18"/><path d="M4 6h1v4"/><path d="M4 10h2"/><path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1"/></svg>""",
    'edit_clear.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>""",
    
    # --- 分页/导航 ---
    'nav_first.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="11 17 6 12 11 7"/><polyline points="18 17 13 12 18 7"/></svg>""",
    'nav_prev.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>""",
    'nav_next.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>""",
    'nav_last.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="13 17 18 12 13 7"/><polyline points="6 17 11 12 6 7"/></svg>""",
    
    # --- 杂项 ---
    'tag.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>""",
    'folder.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>""",
    'calendar.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>""",
    'clock.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>""",
    'star.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>""",
    'star_filled.svg': """<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>""",
    'pin.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>""",
    'lock.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>""",
    'pencil.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg>""",
    # --- 悬浮球菜单 ---
    'display.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="12" rx="2" ry="2"/><line x1="3" y1="21" x2="21" y2="21"/><line x1="12" y1="15" x2="12" y2="21"/></svg>""",
    'coffee.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8h1a4 4 0 0 1 0 8h-1"/><path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"/><line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/></svg>""",
    'grid.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/><line x1="15" y1="3" x2="15" y2="21"/></svg>""",
    'book.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20v2H6.5A2.5 2.5 0 0 1 4 19.5z"/><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v2H6.5A2.5 2.5 0 0 1 4 5.5z"/></svg>""",
    'leaf.svg':"""<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12c0-4.42-3.58-8-8-8S4 7.58 4 12s3.58 8 8 8 8-3.58 8-8z"/><path d="M12 2a10 10 0 0 0-10 10h20a10 10 0 0 0-10-10z"/></svg>""",
    'book-open.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>""",
    'zap.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>""",
    'monitor.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>""",
    'power.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg>""",
    'palette.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="13.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="10.5" r="2.5"/><circle cx="8.5" cy="7.5" r="2.5"/><circle cx="6.5" cy="12.5" r="2.5"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/></svg>""",
    'grip_diagonal.svg': """<svg viewBox="0 0 20 20" fill="currentColor">
        <circle cx="18" cy="18" r="1.2"/><circle cx="14" cy="18" r="1.2"/><circle cx="10" cy="18" r="1.2"/><circle cx="6" cy="18" r="1.2"/><circle cx="2" cy="18" r="1.2"/>
        <circle cx="18" cy="14" r="1.2"/><circle cx="14" cy="14" r="1.2"/><circle cx="10" cy="14" r="1.2"/><circle cx="6" cy="14" r="1.2"/>
        <circle cx="18" cy="10" r="1.2"/><circle cx="14" cy="10" r="1.2"/><circle cx="10" cy="10" r="1.2"/>
        <circle cx="18" cy="6" r="1.2"/><circle cx="14" cy="6" r="1.2"/>
        <circle cx="18" cy="2" r="1.2"/>
    </svg>"""
}

# 全局图标缓存
_icon_cache = {}

def create_svg_icon(icon_name, color=None):
    """
    创建一个基于 SVG 的 QIcon，具有智能着色和缓存功能。
    :param icon_name: SVG 图标的文件名 (例如 'all_data.svg')
    :param color: 强制指定颜色 (Hex 字符串)，否则使用智能配色或默认色
    :return: QIcon 对象
    """
    # 默认使用当前应用程序调色板的文本颜色
    default_color = QApplication.palette().color(QPalette.WindowText).name()
    
    if color:
        render_color = color
    else:
        # 智能着色：检查是否有预定义的专业配色
        render_color = _icon_theme_colors.get(icon_name, default_color)

    cache_key = (icon_name, render_color)

    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    svg_data = ""
    if icon_name in _system_icons:
        svg_data = _system_icons[icon_name]
    
    if not svg_data:
        # 作为备用，尝试从文件系统加载
        icon_path = os.path.join("ui", "icons", icon_name)
        if os.path.exists(icon_path):
            try:
                with open(icon_path, 'r', encoding='utf-8') as f:
                    svg_data = f.read()
            except Exception:
                pass

    if not svg_data:
        return QIcon()  # 返回一个空图标

    # 将 SVG 中的 "currentColor" 替换为我们指定的颜色
    svg_data = svg_data.replace("currentColor", render_color)

    renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
    
    # 增加渲染尺寸以提高高分屏清晰度
    render_size = 64
    pixmap = QPixmap(render_size, render_size)
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    icon = QIcon(pixmap)
    _icon_cache[cache_key] = icon
    return icon

def create_clear_button_icon():
    """
    专门为 QLineEdit 的 clearButton 生成一个经典的 '×' 图标,
    并返回其文件路径, 供 QSS 使用。
    """
    import tempfile
    
    # 定义一个经典的 '×' SVG
    svg_data = """
    <svg viewBox="0 0 24 24" fill="none" stroke="#999999" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"/>
        <line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
    """
    
    # 检查缓存
    temp_dir = tempfile.gettempdir()
    icon_path = os.path.join(temp_dir, "clear_icon.png")
    
    if os.path.exists(icon_path):
        return icon_path.replace("\\", "/") # 确保路径格式正确
        
    renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    
    pixmap.save(icon_path, "PNG")
    
    # 确保 QSS 能正确使用路径
    return icon_path.replace("\\", "/")

```

## 文件: ui\writing_animation.py

```python
# -*- coding: utf-8 -*-
# ui/writing_animation.py
import math
import random
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QLinearGradient, QPainterPath

class WritingAnimationWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.is_writing = False
        self.time_step = 0.0
        self.pen_angle = -45.0
        self.pen_x = 0
        self.pen_y = 0
        self.book_y = 0
        self.particles = []
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_physics)

    def start(self):
        self.is_writing = True
        self.time_step = 0
        if not self.timer.isActive():
            self.timer.start(20)
        self.show()

    def _update_physics(self):
        self.time_step += 0.1
        
        target_pen_angle = -65
        write_speed = self.time_step * 3.0
        flow_x = math.sin(write_speed) * 4
        flow_y = math.cos(write_speed * 2) * 1
        target_pen_x = flow_x
        target_pen_y = 2 + flow_y
        target_book_y = -1

        easing = 0.1
        self.pen_angle += (target_pen_angle - self.pen_angle) * easing
        self.pen_x += (target_pen_x - self.pen_x) * easing
        self.pen_y += (target_pen_y - self.pen_y) * easing
        self.book_y += (target_book_y - self.book_y) * easing

        self._update_particles()
        self.update()

        if self.time_step > 5: # Stop after a while
            self.timer.stop()
            self.is_writing = False

    def _update_particles(self):
        if self.is_writing and len(self.particles) < 10:
            if random.random() < 0.4:
                rad = math.radians(self.pen_angle)
                tip_len = 12
                self.particles.append({
                    'x': self.width()/2 + self.pen_x - math.sin(rad)*tip_len,
                    'y': self.height()/2 + self.pen_y + math.cos(rad)*tip_len,
                    'vx': random.uniform(-0.2, 0.2),
                    'vy': random.uniform(0.2, 0.5),
                    'life': 1.0,
                    'size': random.uniform(0.5, 1.5)
                })
        
        alive = []
        for p in self.particles:
            p['x'] += p['vx']; p['y'] += p['vy']; p['life'] -= 0.04; p['size'] *= 0.95
            if p['life'] > 0: alive.append(p)
        self.particles = alive

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        cx, cy = self.width() / 2, self.height() / 2
        
        p.save()
        p.translate(cx, cy + self.book_y)
        p.scale(0.3, 0.3) # Scale down drawing
        self._draw_book_mocha(p)
        p.restore()

        p.save()
        p.translate(cx + self.pen_x, cy + self.pen_y - 5)
        p.scale(0.3, 0.3)
        p.rotate(self.pen_angle)
        self._draw_universal_pen(p)
        p.restore()
        
        for pt in self.particles:
            alpha = int(255 * pt['life'])
            c = QColor(255, 215, 0, alpha)
            p.setPen(Qt.NoPen); p.setBrush(c)
            p.drawEllipse(QRectF(pt['x']-pt['size']/2, pt['y']-pt['size']/2, pt['size'], pt['size']))

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

    def _draw_book_mocha(self, p):
        w, h = 56, 76
        p.setBrush(QColor(245, 240, 225)); p.drawRoundedRect(QRectF(-w/2+6, -h/2+6, w, h), 3, 3)
        grad = QLinearGradient(-w, -h, w, h)
        grad.setColorAt(0, QColor(90, 60, 50)); grad.setColorAt(1, QColor(50, 30, 25))
        p.setBrush(grad); p.drawRoundedRect(QRectF(-w/2, -h/2, w, h), 3, 3)
        p.setBrush(QColor(120, 20, 30)); p.drawRect(QRectF(w/2 - 15, -h/2, 8, h))
```

## 文件: ui\__init__.py

```python
﻿# -*- coding: utf-8 -*-

```

## 文件: ui\components\rich_text_edit.py

```python
# -*- coding: utf-8 -*-
# ui/components/rich_text_edit.py

from PyQt5.QtWidgets import QTextEdit, QRubberBand
from PyQt5.QtGui import QImage, QColor, QTextCharFormat, QTextCursor, QPainter, QTextImageFormat, QTextBlockFormat, QTextListFormat
from PyQt5.QtCore import Qt, QByteArray, QBuffer, QIODevice, QPoint, QRect
import markdown2
from .syntax_highlighter import MarkdownHighlighter

class ImageResizer(QRubberBand):
    def __init__(self, parent=None, cursor=None, image_format=None):
        super().__init__(QRubberBand.Rectangle, parent)
        self.editor = parent
        self.cursor = cursor
        self.image_format = image_format
        self.current_image_name = image_format.name()
        
        self.original_width = image_format.width()
        self.original_height = image_format.height()
        self.aspect_ratio = self.original_height / self.original_width if self.original_width > 0 else 1.0
        
        self.dragging = False
        self.drag_start_pos = QPoint()
        self.start_rect = QRect()
        
        self.show()
        self.update_geometry()

    def update_geometry(self):
        rect = self.editor.cursorRect(self.cursor)
        w = int(self.image_format.width())
        h = int(self.image_format.height())
        self.setGeometry(rect.x(), rect.y(), w, h)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if (self.width() - event.pos().x() < 20) and (self.height() - event.pos().y() < 20):
                self.dragging = True
                self.drag_start_pos = event.globalPos()
                self.start_rect = self.geometry()
                event.accept()
            else:
                self.editor.deselect_image()
        
    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.globalPos() - self.drag_start_pos
            new_w = max(50, self.start_rect.width() + delta.x())
            new_h = int(new_w * self.aspect_ratio)
            self.resize(new_w, new_h)
            event.accept()
            
    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.dragging = False
            self._apply_new_size()
            
    def _apply_new_size(self):
        new_fmt = QTextImageFormat(self.image_format)
        new_fmt.setWidth(self.width())
        new_fmt.setHeight(self.height())
        new_fmt.setName(self.current_image_name)
        
        c = QTextCursor(self.cursor)
        c.setPosition(self.cursor.position())
        c.setPosition(self.cursor.position() + 1, QTextCursor.KeepAnchor)
        c.insertImage(new_fmt)
        
        image_name = new_fmt.name()
        self.editor.document().addResource(3, image_name, self.editor.document().resource(3, image_name))
        
        self.image_format = new_fmt
        self.cursor = QTextCursor(c)
        self.cursor.setPosition(c.position() - 1)
        self.update_geometry()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(Qt.blue)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(0, 0, self.width()-1, self.height()-1)
        painter.setBrush(Qt.blue)
        painter.drawRect(self.width()-10, self.height()-10, 10, 10)

class RichTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_data = None
        self.current_resizer = None
        
        # 初始化 Markdown 高亮器 (确保 syntax_highlighter.py 已经更新!)
        self.highlighter = MarkdownHighlighter(self.document())
        
        self.is_markdown_preview = False
        self._source_text = ""

        # 样式设置，确保背景色不干扰
        self.setStyleSheet("""
            QTextEdit { border: none; color: #dddddd; }
            QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0px; }
            QScrollBar::handle:vertical { background: #444; border-radius: 3px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #555; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)

    # --- Markdown 增强功能 ---
    def toggle_markdown_preview(self):
        """切换 Markdown 源码编辑与 HTML 预览"""
        if not self.is_markdown_preview:
            # 进入预览模式
            self._source_text = self.toPlainText()
            try:
                # 使用 markdown2 转 HTML
                html_content = markdown2.markdown(
                    self._source_text, 
                    extras=["fenced-code-blocks", "tables", "strike", "task_list"]
                )
                
                # 预览样式 CSS
                css = """
                <style>
                    body { font-family: "Microsoft YaHei"; color: #ddd; font-size: 14px; }
                    code { background-color: #333; padding: 2px 4px; border-radius: 3px; font-family: Consolas; color: #98C379; }
                    pre { background-color: #1e1e1e; padding: 10px; border-radius: 5px; border: 1px solid #444; color: #ccc; }
                    blockquote { border-left: 4px solid #569CD6; padding-left: 10px; color: #888; background: #252526; }
                    a { color: #4a90e2; text-decoration: none; }
                    table { border-collapse: collapse; width: 100%; }
                    th, td { border: 1px solid #444; padding: 6px; }
                    th { background-color: #333; }
                </style>
                """
                self.setHtml(css + html_content)
                self.setReadOnly(True)
                self.is_markdown_preview = True
            except Exception as e:
                print(f"Markdown preview error: {e}")
        else:
            # 返回编辑模式
            self.setReadOnly(False)
            self.setPlainText(self._source_text)
            self.highlighter.setDocument(self.document()) # 重新绑定高亮器
            self.is_markdown_preview = False

    def insert_todo(self):
        """插入待办事项 Checkbox"""
        cursor = self.textCursor()
        # 如果当前行不是空的且不在开头，先换行
        if not cursor.atBlockStart():
            cursor.insertText("\n")
        cursor.insertText("- [ ] ")
        self.setTextCursor(cursor)
        self.setFocus()

    # --- 原有功能保持 ---
    def mousePressEvent(self, event):
        if self.is_markdown_preview: return 
        cursor = self.cursorForPosition(event.pos())
        fmt = cursor.charFormat()
        
        if fmt.isImageFormat():
            image_fmt = fmt.toImageFormat()
            self.select_image(cursor, image_fmt)
            return
            
        self.deselect_image()
        super().mousePressEvent(event)

    def select_image(self, cursor, image_fmt):
        self.deselect_image()
        self.current_resizer = ImageResizer(self, cursor, image_fmt)
        self.current_resizer.show()

    def deselect_image(self):
        if self.current_resizer:
            self.current_resizer.close()
            self.current_resizer = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.current_resizer:
            self.deselect_image()
            return
        super().keyPressEvent(event)
        
    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        cursor = self.cursorForPosition(event.pos())
        fmt = cursor.charFormat()
        
        if fmt.isImageFormat():
            menu.addSeparator()
            target_cursor = QTextCursor(cursor)
            target_fmt = QTextImageFormat(fmt.toImageFormat())
            restore_action = menu.addAction("还原原始大小")
            restore_action.triggered.connect(lambda checked=False, c=target_cursor, f=target_fmt: self._restore_image_size(c, f))
            
        menu.exec_(event.globalPos())
        
    def _restore_image_size(self, cursor, image_fmt):
        try:
            image_name = image_fmt.name()
            image_variant = self.document().resource(3, image_name)
            if not image_variant: return
            
            image = image_variant
            if hasattr(image, 'toImage'): image = image.toImage()
            if not isinstance(image, QImage) or image.isNull(): return
            
            new_fmt = QTextImageFormat(image_fmt)
            new_fmt.setWidth(image.width())
            new_fmt.setHeight(image.height())
            new_fmt.setName(image_name)
            
            c = QTextCursor(cursor)
            if c.position() < self.document().characterCount():
                c.setPosition(cursor.position())
                c.setPosition(cursor.position() + 1, QTextCursor.KeepAnchor)
                c.insertImage(new_fmt)
            self.deselect_image()
        except Exception: pass

    def highlight_selection(self, color_str):
        cursor = self.textCursor()
        if not cursor.hasSelection(): return
        fmt = QTextCharFormat()
        if not color_str: fmt.setBackground(Qt.transparent)
        else: fmt.setBackground(QColor(color_str))
        cursor.mergeCharFormat(fmt)
        self.setTextCursor(cursor)

    def canInsertFromMimeData(self, source):
        return source.hasImage() or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source.hasImage():
            image = source.imageData()
            if isinstance(image, QImage):
                byte_array = QByteArray()
                buffer = QBuffer(byte_array)
                buffer.open(QIODevice.WriteOnly)
                image.save(buffer, "PNG")
                self.image_data = byte_array.data()

                cursor = self.textCursor()
                max_width = self.viewport().width() - 40
                if image.width() > max_width:
                    scale = max_width / image.width()
                    scaled_image = image.scaled(
                        int(max_width), 
                        int(image.height() * scale),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    cursor.insertImage(scaled_image)
                else:
                    cursor.insertImage(image)
                return
        super().insertFromMimeData(source)

    def get_image_data(self): return self.image_data

    def set_image_data(self, data):
        self.image_data = data
        if data:
            image = QImage()
            image.loadFromData(data)
            if not image.isNull():
                self.clear()
                cursor = self.textCursor()
                max_width = self.viewport().width() - 40
                if image.width() > max_width:
                    scale = max_width / image.width()
                    scaled_image = image.scaled(int(max_width), int(image.height() * scale), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    cursor.insertImage(scaled_image)
                else:
                    cursor.insertImage(image)

    def toggle_list(self, list_style):
        cursor = self.textCursor()
        cursor.beginEditBlock()
        current_list = cursor.currentList()
        if current_list:
             fmt = current_list.format()
             if fmt.style() == list_style:
                 block_fmt = QTextBlockFormat()
                 block_fmt.setObjectIndex(-1)
                 cursor.setBlockFormat(block_fmt)
             else:
                 fmt.setStyle(list_style)
                 current_list.setFormat(fmt)
        else:
             list_fmt = QTextListFormat()
             list_fmt.setStyle(list_style)
             cursor.createList(list_fmt)
        cursor.endEditBlock()
```

## 文件: ui\components\search_line_edit.py

```python
# -*- coding: utf-8 -*-
# ui/components/search_line_edit.py

from PyQt5.QtWidgets import (QLineEdit, QPushButton, QHBoxLayout, QWidget, 
                             QVBoxLayout, QApplication, QLabel, QLayout, 
                             QScrollArea, QFrame, QGraphicsDropShadowEffect, QSizePolicy)
from PyQt5.QtCore import Qt, QSettings, QPoint, QRect, QSize, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QFont, QCursor

# --- 1. 流式布局 ---
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super(FlowLayout, self).__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margin = self.contentsMargins()
        size += QSize(margin.left() + margin.right(), margin.top() + margin.bottom())
        return size

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        spacing = self.spacing()

        for item in self.itemList:
            wid = item.widget()
            spaceX = spacing + wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Horizontal)
            spaceY = spacing + wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Vertical)
            
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())

        return y + lineHeight - rect.y()

# --- 2. 历史记录气泡 ---
class HistoryChip(QFrame):
    clicked = pyqtSignal(str)
    deleted = pyqtSignal(str)

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("HistoryChip")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 4, 4)
        layout.setSpacing(6)
        
        lbl = QLabel(text)
        lbl.setStyleSheet("border: none; background: transparent; color: #DDD; font-size: 12px;")
        layout.addWidget(lbl)
        
        self.btn_del = QPushButton("×")
        self.btn_del.setFixedSize(16, 16)
        self.btn_del.setCursor(Qt.PointingHandCursor)
        self.btn_del.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #666;
                border-radius: 8px;
                font-weight: bold;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background-color: #E74C3C;
                color: white;
            }
        """)
        self.btn_del.clicked.connect(self._on_delete)
        layout.addWidget(self.btn_del)
        
        self.setStyleSheet("""
            #HistoryChip {
                background-color: #3A3A3E;
                border: 1px solid #555;
                border-radius: 12px;
            }
            #HistoryChip:hover {
                background-color: #454549;
                border-color: #4a90e2;
            }
        """)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and not self.btn_del.underMouse():
            self.clicked.emit(self.text)
        super().mousePressEvent(e)

    def _on_delete(self):
        self.deleted.emit(self.text)

# --- 3. 现代感弹窗 (完美对齐版) ---
class SearchHistoryPopup(QWidget):
    item_selected = pyqtSignal(str)
    
    def __init__(self, search_edit):
        super().__init__(search_edit.window()) 
        self.search_edit = search_edit
        self.settings = QSettings("KMain_V3", "SearchHistory")
        
        # 阴影边距设置 (左右下各留空间，上方少留一点)
        self.shadow_margin = 12 
        
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 使用根布局来管理边距，确保容器居中，阴影不被切
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(self.shadow_margin, self.shadow_margin, self.shadow_margin, self.shadow_margin)
        
        # 主容器
        self.container = QWidget()
        self.container.setObjectName("PopupContainer")
        self.container.setStyleSheet("""
            #PopupContainer {
                background-color: #252526;
                border: 1px solid #444;
                border-radius: 10px;
            }
        """)
        self.root_layout.addWidget(self.container)
        
        # 阴影
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.container.setGraphicsEffect(shadow)
        
        # 内容布局
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # 顶部栏
        top_layout = QHBoxLayout()
        lbl_title = QLabel("🕒 搜索历史")
        lbl_title.setStyleSheet("color: #888; font-weight: bold; font-size: 11px; background: transparent; border: none;")
        top_layout.addWidget(lbl_title)
        
        top_layout.addStretch()
        
        btn_clear = QPushButton("清空")
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.setStyleSheet("""
            QPushButton { background: transparent; color: #666; border: none; font-size: 11px; }
            QPushButton:hover { color: #E74C3C; }
        """)
        btn_clear.clicked.connect(self._clear_all)
        top_layout.addWidget(btn_clear)
        
        layout.addLayout(top_layout)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # 强制全透明背景
        scroll.setStyleSheet("""
            QScrollArea { background-color: transparent; border: none; }
            QScrollArea > QWidget > QWidget { background-color: transparent; }
        """)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.chips_widget = QWidget()
        self.chips_widget.setStyleSheet("background-color: transparent;")
        self.flow_layout = FlowLayout(self.chips_widget, margin=0, spacing=8)
        scroll.setWidget(self.chips_widget)
        
        layout.addWidget(scroll)
        
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        
        self.refresh_ui()

    def refresh_ui(self):
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        history = self.search_edit.get_history()
        
        # 【核心修正】强制宽度与输入框一致
        target_content_width = self.search_edit.width()
        
        if not history:
            lbl_empty = QLabel("暂无历史记录")
            lbl_empty.setAlignment(Qt.AlignCenter)
            lbl_empty.setStyleSheet("color: #555; font-style: italic; margin: 20px; background: transparent; border: none;")
            self.flow_layout.addWidget(lbl_empty)
            content_height = 100
        else:
            for text in history:
                chip = HistoryChip(text)
                chip.clicked.connect(self._on_chip_clicked)
                chip.deleted.connect(self._on_chip_deleted)
                self.flow_layout.addWidget(chip)
            
            # 计算高度：内容宽度 = 容器宽度 - 内部边距(24) - 滚动条预留(6)
            effective_width = target_content_width - 30
            flow_height = self.flow_layout.heightForWidth(effective_width)
            content_height = min(400, max(120, flow_height + 50)) # 加上顶部栏高度

        # 计算窗口总尺寸：内容尺寸 + 阴影边距
        total_width = target_content_width + (self.shadow_margin * 2)
        total_height = content_height + (self.shadow_margin * 2)
        
        self.resize(total_width, total_height)

    def _on_chip_clicked(self, text):
        self.item_selected.emit(text)
        self.close()

    def _on_chip_deleted(self, text):
        self.search_edit.remove_history_entry(text)
        self.refresh_ui()

    def _clear_all(self):
        self.search_edit.clear_history()
        self.refresh_ui()

    def show_animated(self):
        self.refresh_ui()
        
        # 【核心修正】坐标对齐逻辑
        # 1. 获取输入框左下角坐标
        pos = self.search_edit.mapToGlobal(QPoint(0, self.search_edit.height()))
        
        # 2. 偏移坐标：X轴减去阴影边距，Y轴加上间距并减去阴影边距
        # 这样 Container 的左边框就会和 Input 的左边框完全对齐
        x_pos = pos.x() - self.shadow_margin
        y_pos = pos.y() + 5 - self.shadow_margin # 5px 垂直间距
        
        self.move(x_pos, y_pos)
        
        self.setWindowOpacity(0)
        self.show()
        
        self.opacity_anim.setDuration(200)
        self.opacity_anim.setStartValue(0)
        self.opacity_anim.setEndValue(1)
        self.opacity_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.opacity_anim.start()

# --- 4. 搜索框本体 ---
class SearchLineEdit(QLineEdit):
    SETTINGS_KEY = "SearchHistoryList"
    MAX_HISTORY = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("KMain_V3", "KMain_V3")
        self.popup = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._show_popup()
        super().mouseDoubleClickEvent(event)

    def _show_popup(self):
        if self.popup and self.popup.isVisible():
            self.popup.close()
            return
            
        self.popup = SearchHistoryPopup(self)
        self.popup.item_selected.connect(self._on_history_selected)
        self.popup.show_animated()

    def _on_history_selected(self, text):
        self.setText(text)
        self.returnPressed.emit()

    def add_history_entry(self, text):
        if not text or not text.strip(): return
        text = text.strip()
        history = self.get_history()
        
        if text in history:
            history.remove(text)
        history.insert(0, text)
        
        if len(history) > self.MAX_HISTORY:
            history = history[:self.MAX_HISTORY]
            
        self.settings.setValue(self.SETTINGS_KEY, history)

    def remove_history_entry(self, text):
        history = self.get_history()
        if text in history:
            history.remove(text)
            self.settings.setValue(self.SETTINGS_KEY, history)

    def clear_history(self):
        self.settings.setValue(self.SETTINGS_KEY, [])

    def get_history(self):
        val = self.settings.value(self.SETTINGS_KEY, [])
        if not isinstance(val, list): return []
        return [str(v) for v in val]
```

## 文件: ui\components\syntax_highlighter.py

```python
# -*- coding: utf-8 -*-
# ui/components/syntax_highlighter.py

import re
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

class MarkdownHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = []

        # --- 1. 标题 (Headers) ---
        # 匹配 # 开头，蓝色，加粗
        headerFormat = QTextCharFormat()
        headerFormat.setForeground(QColor("#569CD6")) 
        headerFormat.setFontWeight(QFont.Bold)
        self.rules.append((re.compile(r"^#{1,6}\s.*"), headerFormat))

        # --- 2. 粗体 (**bold**) ---
        # 匹配 **中间的内容**，红色，加粗
        boldFormat = QTextCharFormat()
        boldFormat.setFontWeight(QFont.Bold)
        boldFormat.setForeground(QColor("#E06C75")) 
        self.rules.append((re.compile(r"\*\*.*?\*\*"), boldFormat))

        # --- 3. 待办事项 ([ ] [x]) ---
        # 未完成，黄色
        uncheckedFormat = QTextCharFormat()
        uncheckedFormat.setForeground(QColor("#E5C07B")) 
        self.rules.append((re.compile(r"-\s\[\s\]"), uncheckedFormat))
        
        # 已完成，绿色
        checkedFormat = QTextCharFormat()
        checkedFormat.setForeground(QColor("#6A9955")) 
        self.rules.append((re.compile(r"-\s\[x\]"), checkedFormat))

        # --- 4. 代码块 (``` ... ```) ---
        # 绿色，等宽字体
        codeFormat = QTextCharFormat()
        codeFormat.setForeground(QColor("#98C379")) 
        codeFormat.setFontFamily("Consolas") 
        # 注意：这里处理简单的多行代码块会有局限，但在 QSyntaxHighlighter 中
        # 使用多行正则比较复杂，这里先确保单行 ``` 和行内 `code` 能亮
        self.rules.append((re.compile(r"`[^`]+`"), codeFormat)) 
        self.rules.append((re.compile(r"```.*"), codeFormat)) # 简单的代码块头

        # --- 5. 引用 (> Quote) ---
        # 灰色，斜体
        quoteFormat = QTextCharFormat()
        quoteFormat.setForeground(QColor("#808080")) 
        quoteFormat.setFontItalic(True)
        self.rules.append((re.compile(r"^\s*>.*"), quoteFormat))
        
        # --- 6. 列表项 (- item) ---
        # 紫色
        listFormat = QTextCharFormat()
        listFormat.setForeground(QColor("#C678DD")) 
        self.rules.append((re.compile(r"^\s*[\-\*]\s"), listFormat))

    def highlightBlock(self, text):
        """
        使用 Python 的 re 模块进行匹配，速度快且语法支持全。
        """
        for pattern, format in self.rules:
            # 使用 finditer 查找所有匹配项
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, format)
```

