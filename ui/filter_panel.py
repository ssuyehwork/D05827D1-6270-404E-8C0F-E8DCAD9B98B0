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