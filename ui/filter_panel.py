# -*- coding: utf-8 -*-
# ui/filter_panel.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                             QTreeWidgetItem, QPushButton, QLabel, QFrame, QApplication, QMenu, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QMimeData, QPoint
from PyQt5.QtGui import QDrag, QPixmap, QPainter, QCursor, QColor, QPen
from core.config import COLORS
from core.shared import get_color_icon
from ui.utils import create_svg_icon, get_svg_path
import logging

log = logging.getLogger("FilterPanel")

class FilterPanel(QWidget):
    filterChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.resize_margin = 8
        self._block_item_click = False
        
        # Init member variables for resize
        self._drag_start_pos = None
        self._resize_start_pos = None
        self._resize_start_geometry = None
        self._resize_edge = None
        
        self.setMouseTracking(True)
        self.setMinimumSize(250, 350)
        
        # 初始化 UI
        self._init_ui()
        
        # 初始化数据
        self.roots = {}
        self._init_tree_structure()
        
    def _init_ui(self):
        # 主布局，带内边距以容纳边框和阴影
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 容器 Frame (用于实现圆角背景和边框，解决 TranslucentBackground 下的问题)
        self.container = QFrame()
        self.container.setObjectName("FilterPanelContainer")
        self.container.setStyleSheet(f"""
            QFrame#FilterPanelContainer {{
                background-color: {COLORS['bg_mid']};
                border: 1px solid {COLORS['bg_light']};
                border-radius: 8px;
            }}
            QTreeWidget {{
                background-color: transparent;
                border: none;
                outline: none;
            }}
            QTreeWidget::item {{
                height: 28px;
                padding-left: 5px;
            }}
            QTreeWidget::item:hover {{
                background-color: #2a2d2e;
                border-radius: 4px;
            }}
            QTreeWidget::item:selected {{
                background-color: #37373d;
                color: {COLORS['text']};
            }}
            QTreeWidget::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #666;
            }}
            QTreeWidget::indicator:checked {{
                background-color: {COLORS['primary']};
                border-color: {COLORS['primary']};
                image: url({get_svg_path('select.svg', 'white')}); 
            }}
        """)
        
        # 顶部标题栏 + 重置按钮
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(12, 12, 12, 8)
        
        self.header = QLabel("高级筛选")
        self.header.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLORS['text']};")
        self.header.setCursor(Qt.SizeAllCursor)
        
        self.btn_reset = QPushButton("重置")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet(f"""
            QPushButton {{
                color: {COLORS['text_sub']};
                background: transparent;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #2a2d2e;
                color: {COLORS['text']};
            }}
        """)
        self.btn_reset.clicked.connect(self.reset_filters)
        
        header_layout.addWidget(self.header)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_reset)
        
        # 中间树形列表
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setFocusPolicy(Qt.NoFocus)
        self.tree.setIndentation(20)
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setAnimated(True)
        self.tree.setAllColumnsShowFocus(True)
        self.tree.clicked.connect(self._on_item_clicked)
        self.tree.itemChanged.connect(self._on_item_changed)
        
        # 滚动条样式
        self.tree.setStyleSheet(f"""
            QScrollBar:vertical {{ border: none; background: transparent; width: 6px; margin: 0px; }}
            QScrollBar::handle:vertical {{ background: #444; border-radius: 3px; min-height: 20px; }}
            QScrollBar::handle:vertical:hover {{ background: #555; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """)
        
        # 底部调整大小手柄
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 4, 4)
        bottom_layout.addStretch()
        
        self.resize_handle = QLabel("◢")
        self.resize_handle.setFixedSize(20, 20)
        self.resize_handle.setAlignment(Qt.AlignCenter)
        self.resize_handle.setCursor(Qt.SizeFDiagCursor)
        self.resize_handle.setStyleSheet(f"""
            QLabel {{
                color: #666;
                font-size: 16px;
                background: transparent;
            }}
            QLabel:hover {{
                color: {COLORS['primary']};
            }}
        """)
        
        bottom_layout.addWidget(self.resize_handle)
        
        # 组装
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addLayout(header_layout)
        container_layout.addWidget(self.tree)
        container_layout.addLayout(bottom_layout)
        
        main_layout.addWidget(self.container)
        
        # 添加阴影效果 (Translucent 背景下的标配)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

    def _init_tree_structure(self):
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
            # 设置 Header 图标
            if key in header_icons:
                icon_name, icon_color = header_icons[key]
                item.setIcon(0, create_svg_icon(icon_name, icon_color))
            
            item.setExpanded(True)
            item.setFlags(Qt.ItemIsEnabled) 
            item.setFont(0, font_header)
            item.setForeground(0, Qt.gray)
            self.roots[key] = item
            
        # 添加具体的子项逻辑 (评级)
        self._add_fixed_star_options('stars')
        # 添加时间子项
        self._add_fixed_date_options('date_create')

    def _add_fixed_star_options(self, key):
        root = self.roots[key]
        for i in range(5, 0, -1):
            child = QTreeWidgetItem(root)
            child.setText(0, "★" * i)
            child.setData(0, Qt.UserRole, i)
            child.setCheckState(0, Qt.Unchecked)

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

    def update_stats(self, stats):
        """更新统计数字"""
        self._block_item_click = True
        try:
            # 更新颜色
            color_root = self.roots.get('colors')
            if color_root:
                color_root.takeChildren()
                for color_info in stats.get('colors', []):
                    # color_info: {'color': '#hex', 'count': N}
                    child = QTreeWidgetItem(color_root)
                    child.setText(0, f"{color_info['color']} ({color_info['count']})")
                    child.setData(0, Qt.UserRole, color_info['color'])
                    child.setCheckState(0, Qt.Unchecked)
                    # 使用小方块图标
                    child.setIcon(0, get_color_icon(color_info['color'], 14))

            # 更新类型
            type_root = self.roots.get('types')
            if type_root:
                type_root.takeChildren()
                for type_info in stats.get('types', []):
                    # type_info: {'type': 'text', 'count': N}
                    name = type_info['type'].upper()
                    child = QTreeWidgetItem(type_root)
                    child.setText(0, f"{name} ({type_info['count']})")
                    child.setData(0, Qt.UserRole, type_info['type'])
                    child.setCheckState(0, Qt.Unchecked)
            
            # 更新标签
            tag_root = self.roots.get('tags')
            if tag_root:
                tag_root.takeChildren()
                for tag_info in stats.get('tags', []):
                    # tag_info: {'name': 'xxx', 'count': N}
                    child = QTreeWidgetItem(tag_root)
                    child.setText(0, f"{tag_info['name']} ({tag_info['count']})")
                    child.setData(0, Qt.UserRole, tag_info['name'])
                    child.setCheckState(0, Qt.Unchecked)
        finally:
            self._block_item_click = False

    def get_checked_criteria(self):
        """获取当前所有选中的过滤条件"""
        filters = {
            'stars': [],
            'colors': [],
            'types': [],
            'dates': [],
            'tags': []
        }
        
        # 遍历树
        for key, root in self.roots.items():
            for i in range(root.childCount()):
                child = root.child(i)
                if child.checkState(0) == Qt.Checked:
                    val = child.data(0, Qt.UserRole)
                    if key == 'date_create':
                        filters['dates'].append(val)
                    else:
                        filters[key].append(val)
        return filters

    def reset_filters(self):
        """重置所有过滤条件"""
        self._block_item_click = True
        for root in self.roots.values():
            for i in range(root.childCount()):
                root.child(i).setCheckState(0, Qt.Unchecked)
        self._block_item_click = False
        self.filterChanged.emit()

    def _on_item_changed(self, item, col):
        if self._block_item_click: return
        self._last_changed_item = item
        QTimer.singleShot(100, lambda: setattr(self, '_last_changed_item', None))
        self.filterChanged.emit()

    def _on_item_clicked(self, item, column):
        if not item: return
        if getattr(self, '_last_changed_item', None) == item: return
        # 点击非根节点切换勾选状态
        if item.parent():
            state = Qt.Checked if item.checkState(0) == Qt.Unchecked else Qt.Unchecked
            item.setCheckState(0, state)

    # --- Resize & Drag Logic ---
    def _get_resize_edge(self, pos):
        m = self.resize_margin
        w, h = self.width(), self.height()
        if pos.x() > w - m and pos.y() > h - m: return Qt.BottomRightSection
        if pos.x() > w - m: return Qt.RightSection
        if pos.y() > h - m: return Qt.BottomSection
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            edge = self._get_resize_edge(event.pos())
            if edge:
                self._resize_edge = edge
                self._resize_start_pos = event.globalPos()
                self._resize_start_geometry = self.geometry()
            else:
                self._drag_start_pos = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._resize_edge:
            diff = event.globalPos() - self._resize_start_pos
            geo = self._resize_start_geometry
            if self._resize_edge == Qt.RightSection:
                self.resize(geo.width() + diff.x(), geo.height())
            elif self._resize_edge == Qt.BottomSection:
                self.resize(geo.width(), geo.height() + diff.y())
            elif self._resize_edge == Qt.BottomRightSection:
                self.resize(geo.width() + diff.x(), geo.height() + diff.y())
        elif self._drag_start_pos:
            self.move(event.globalPos() - self._drag_start_pos)
        else:
            edge = self._get_resize_edge(event.pos())
            if edge == Qt.BottomRightSection: self.setCursor(Qt.SizeFDiagCursor)
            elif edge == Qt.RightSection: self.setCursor(Qt.SizeHorCursor)
            elif edge == Qt.BottomSection: self.setCursor(Qt.SizeVerCursor)
            else: self.setCursor(Qt.ArrowCursor)
        event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_start_pos = None
        self._resize_edge = None
        self.setCursor(Qt.ArrowCursor)
        event.accept()