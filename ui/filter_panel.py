# -*- coding: utf-8 -*-
# ui/filter_panel.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                             QTreeWidgetItem, QPushButton, QLabel, QFrame, QApplication)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QMimeData, QPoint
from PyQt5.QtGui import QDrag, QPixmap, QPainter, QCursor
from core.config import COLORS
from core.shared import get_color_icon
from ui.utils import create_svg_icon
import logging

log = logging.getLogger("FilterPanel")

class FilterHeader(QWidget):
    """筛选器自定义标题栏，支持拖拽"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setStyleSheet(f"background-color: {COLORS['bg_mid']}; border-radius: 4px;")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        
        self.icon = QLabel()
        self.icon.setPixmap(create_svg_icon("select.svg", "#aaa").pixmap(14, 14))
        layout.addWidget(self.icon)
        
        self.title = QLabel("高级筛选")
        self.title.setStyleSheet("font-weight: bold; color: #ccc; font-size: 12px; border:none;")
        layout.addWidget(self.title)
        
        layout.addStretch()
        
        self.btn_float = QPushButton()
        self.btn_float.setIcon(create_svg_icon("win_restore.svg", "#888")) # 用 restore 图标表示浮动
        self.btn_float.setFixedSize(20, 20)
        self.btn_float.setToolTip("悬浮 / 拖拽移动")
        self.btn_float.setCursor(Qt.PointingHandCursor)
        self.btn_float.setStyleSheet("border:none; background:transparent;")
        # 按钮点击事件由父级处理
        layout.addWidget(self.btn_float)

class FilterPanel(QWidget):
    filterChanged = pyqtSignal()
    dockRequest = pyqtSignal() # 请求停靠回主窗口
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_floating = False
        self._drag_start_pos = None
        
        # 自身样式
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"background-color: {COLORS['bg_mid']}; border-radius: 8px;")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(5)
        
        # 1. 标题栏 (用于拖拽)
        self.header = FilterHeader(self)
        self.header.btn_float.clicked.connect(self.toggle_floating)
        self.layout.addWidget(self.header)
        
        # 2. 树形筛选器
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
                background-color: {COLORS['bg_mid']};
                color: #ddd;
                border: none;
                font-size: 13px;
            }}
            QTreeWidget::item {{
                height: 26px;
                border-radius: 4px;
                padding-right: 5px;
            }}
            QTreeWidget::item:hover {{ background-color: #2a2d2e; }}
            QTreeWidget::item:selected {{ background-color: #37373d; color: white; }}
        """)
        
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.layout.addWidget(self.tree)
        
        # 3. 重置按钮
        self.btn_reset = QPushButton("重置筛选")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_dark']};
                border: 1px solid #444;
                color: #888;
                border-radius: 4px;
                padding: 6px;
                font-size: 12px;
            }}
            QPushButton:hover {{ color: #ddd; background-color: #333; }}
        """)
        self.btn_reset.clicked.connect(self.reset_filters)
        self.layout.addWidget(self.btn_reset)

        self._block_item_click = False
        self.roots = {}
        
        # 定义结构
        order = [
            ('stars', '⭐  评级'),
            ('colors', '🎨  颜色'),
            ('types', '📂  类型'),
            ('date_create', '📅  创建时间'),
            ('tags', '🏷️  标签'),
        ]
        
        font_header = self.tree.font()
        font_header.setBold(True)
        
        for key, label in order:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, label)
            item.setExpanded(True)
            item.setFlags(Qt.ItemIsEnabled) 
            item.setFont(0, font_header)
            item.setForeground(0, Qt.gray)
            self.roots[key] = item
            
        self._add_fixed_date_options('date_create')

    def _add_fixed_date_options(self, key):
        root = self.roots[key]
        options = [("today", "今日"), ("yesterday", "昨日"), ("week", "本周"), ("month", "本月")]
        for key_val, label in options:
            child = QTreeWidgetItem(root)
            child.setText(0, f"{label} (0)")
            child.setData(0, Qt.UserRole, key_val)
            child.setCheckState(0, Qt.Unchecked)

    def _on_item_changed(self, item, col):
        if self._block_item_click: return
        self.filterChanged.emit()

    def _on_item_clicked(self, item, column):
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
        for i in range(5, 0, -1):
            c = stats['stars'].get(i, 0)
            if c > 0: star_data.append((i, "★" * i, c))
        if stats['stars'].get(0, 0) > 0:
            star_data.append((0, "无评级", stats['stars'][0]))
        self._refresh_node('stars', star_data)

        color_data = []
        for c_hex, count in stats['colors'].items():
            if count > 0:
                color_data.append((c_hex, c_hex, count)) 
        self._refresh_node('colors', color_data, is_col=True)
        
        tag_data = []
        for name, count in stats.get('tags', []):
            tag_data.append((name, name, count))
        self._refresh_node('tags', tag_data)
        
        self._update_fixed_node('date_create', stats.get('date_create', {}))
        
        type_map = {'text': '文本', 'image': '图片', 'file': '文件'}
        type_data = []
        for t, count in stats.get('types', {}).items():
            if count > 0:
                type_data.append((t, type_map.get(t, t), count))
        self._refresh_node('types', type_data)
        
        self._block_item_click = False
        self.tree.blockSignals(False)

    def _refresh_node(self, key, data_list, is_col=False):
        root = self.roots[key]
        checked_map = {}
        for i in range(root.childCount()):
            child = root.child(i)
            val = child.data(0, Qt.UserRole)
            checked_map[val] = child.checkState(0)
            
        root.takeChildren()
        
        for value, label, count in data_list:
            child = QTreeWidgetItem(root)
            child.setText(0, f"{label} ({count})")
            child.setData(0, Qt.UserRole, value)
            child.setCheckState(0, checked_map.get(value, Qt.Unchecked))
            
            if is_col:
                child.setIcon(0, get_color_icon(value))
                child.setText(0, f" {count}") 

    def _update_fixed_node(self, key, stats_dict):
        root = self.roots[key]
        labels = {"today": "今日", "yesterday": "昨日", "week": "本周", "month": "本月"}
        for i in range(root.childCount()):
            child = root.child(i)
            val = child.data(0, Qt.UserRole) 
            count = stats_dict.get(val, 0)
            child.setText(0, f"{labels.get(val, val)} ({count})")

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

    # --- 拖拽与悬浮逻辑 ---
    def toggle_floating(self):
        if self._is_floating:
            # 变回停靠状态 -> 发射信号让主窗口接管
            self.dockRequest.emit()
            self._is_floating = False
            self.header.btn_float.setIcon(create_svg_icon("win_restore.svg", "#888"))
        else:
            # 变成悬浮状态
            self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.show()
            self._is_floating = True
            self.header.btn_float.setIcon(create_svg_icon("win_min.svg", "#888")) # 用这个图标表示“收回”

    def mousePressEvent(self, event):
        # 仅在头部区域触发拖拽
        if event.button() == Qt.LeftButton:
            if self.header.geometry().contains(event.pos()):
                self._drag_start_pos = event.pos()
            # 如果是悬浮窗，点击任意位置（非树）也可以拖动窗口
            elif self._is_floating:
                self._drag_start_pos = event.globalPos() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self._drag_start_pos is None:
            return

        # 悬浮窗模式：直接移动窗口
        if self._is_floating:
            self.move(event.globalPos() - self._drag_start_pos)
            event.accept()
            return

        # 停靠模式：触发 Drag 操作，允许拖入其他区域
        if (event.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-filter-panel", b"filter-panel")
        drag.setMimeData(mime)
        
        # 拖拽时的缩略图
        pixmap = self.grab()
        drag.setPixmap(pixmap.scaledToWidth(200, Qt.SmoothTransformation))
        drag.setHotSpot(event.pos())
        
        # 执行拖拽
        # 如果是 MoveAction，说明被接受了（被主窗口 DropEvent 处理了）
        action = drag.exec_(Qt.MoveAction)
        
        self._drag_start_pos = None

    def mouseReleaseEvent(self, event):
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)
    
    def closeEvent(self, event):
        # 如果是悬浮窗被关闭（比如按Alt+F4），视为请求停靠
        if self._is_floating:
            self.dockRequest.emit()
            self._is_floating = False
            event.ignore()
        else:
            super().closeEvent(event)