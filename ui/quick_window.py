# -*- coding: utf-8 -*-
# ui/quick_window.py

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton, QLabel,
                               QApplication)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QCursor

from core.config import STYLES, COLORS
from data.db_manager import DatabaseManager

class QuickWindow(QWidget):
    """
    一个轻量级的快速搜索窗口，作为应用的主入口。
    """
    open_main_window_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self._drag_pos = None

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        self.setWindowTitle('Clipboard Pro - Quick Search')
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(STYLES['main_window'])
        self.resize(800, 600)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(1, 1, 1, 1) # Use a thin margin for the border effect
        main_layout.setSpacing(0)
        
        container = QWidget()
        container.setStyleSheet(f"background-color: {COLORS['bg_dark']}; border-radius: 8px;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 5, 10, 10)
        layout.setSpacing(10)
        
        # Title bar
        title_bar = self._create_titlebar()
        layout.addWidget(title_bar)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索剪贴板历史...")
        self.search_box.setStyleSheet(STYLES['input'] + "QLineEdit { font-size: 16px; border-radius: 8px; }")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._load_data)
        layout.addWidget(self.search_box)

        # Results list
        self.results_list = QListWidget()
        self.results_list.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {COLORS['bg_light']};
                border-radius: 8px;
                background-color: {COLORS['bg_mid']};
            }}
            QListWidget::item {{
                padding: 10px;
                border-bottom: 1px solid {COLORS['bg_light']};
            }}
            QListWidget::item:selected {{
                background-color: {COLORS['primary']};
                color: white;
            }}
        """)
        layout.addWidget(self.results_list)

        main_layout.addWidget(container)

    def _create_titlebar(self):
        """创建自定义标题栏"""
        title_bar = QWidget()
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(10, 0, 0, 0)
        title_bar_layout.setSpacing(10)

        title = QLabel("Clipboard Pro")
        title.setStyleSheet("font-weight: bold; color: #aaa;")
        title_bar_layout.addWidget(title)
        title_bar_layout.addStretch()

        # Buttons
        btn_style = f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: #aaa;
                font-size: 16px;
                font-weight: bold;
                min-width: 30px;
                min-height: 30px;
            }}
            QPushButton:hover {{
                background-color: rgba(255,255,255,0.1);
                color: white;
                border-radius: 4px;
            }}
        """
        
        # 打开主窗口按钮
        open_main_btn = QPushButton("👁️")
        open_main_btn.setToolTip("打开数据管理窗口")
        open_main_btn.setStyleSheet(btn_style)
        open_main_btn.clicked.connect(self.open_main_window_requested)
        title_bar_layout.addWidget(open_main_btn)

        # 最小化按钮
        minimize_btn = QPushButton("─")
        minimize_btn.setToolTip("最小化")
        minimize_btn.setStyleSheet(btn_style)
        minimize_btn.clicked.connect(self.showMinimized)
        title_bar_layout.addWidget(minimize_btn)
        
        # 关闭按钮
        close_btn = QPushButton("✕")
        close_btn.setToolTip("关闭")
        close_btn.setStyleSheet(btn_style + "QPushButton:hover { background-color: #e74c3c; }")
        close_btn.clicked.connect(self.close)
        title_bar_layout.addWidget(close_btn)

        return title_bar

    def _load_data(self):
        """根据搜索框内容加载数据到列表"""
        search_text = self.search_box.text()
        # 使用 get_ideas 方法进行模糊搜索 (假设它支持)
        # 先获取所有数据，之后再根据具体 API 调整
        all_ideas = self.db.get_ideas(search_text, 'all', None)
        
        self.results_list.clear()
        
        for idea in all_ideas:
            # d[0]=id, d[1]=title, d[2]=content
            item = QListWidgetItem(idea[1])
            item.setData(Qt.UserRole, idea[0]) # Store idea ID
            self.results_list.addItem(item)
            
    # --- Window Dragging ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()

if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    window = QuickWindow()
    window.show()
    sys.exit(app.exec_())
