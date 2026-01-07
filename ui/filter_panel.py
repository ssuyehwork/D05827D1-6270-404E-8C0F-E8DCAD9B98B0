# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from core.shared import get_color_icon
import logging

log = logging.getLogger("FilterPanel")

class FilterPanel(QWidget):
    filterChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 移除所有内联样式，由全局主题控制
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0) # 保持 0 边距以支持高亮全宽
        self.layout.setSpacing(0)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(20) # 始终保持 20px 缩进以确保层级清晰
        self.tree.setFocusPolicy(Qt.NoFocus)
        self.tree.setRootIsDecorated(True) # 显式恢复层级箭头显示
        self.tree.setUniformRowHeights(True)
        self.tree.setAnimated(True)
        self.tree.setAllColumnsShowFocus(True) # 核心：让选中高亮横向铺满
        
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.layout.addWidget(self.tree)
        
        # 添加重置按钮
        self.btn_reset = QPushButton("重置勾选")
        self.btn_reset.clicked.connect(self.reset_filters)
        self.layout.addWidget(self.btn_reset)

        self._block_item_click = False
        self.roots = {}
        
        # 定义结构
        order = [
            ('stars', '⭐  评级筛选'),
            ('colors', '🎨  颜色标记'),
            ('types', '📂  文件类型'),
            ('date_create', '📅  创建时间'),
            ('date_modify', '📝  修改时间'),
            ('tags', '🏷️  标签云'),
        ]
        
        font_header = self.tree.font()
        font_header.setBold(True)
        font_header.setPointSize(10) # 稍微小一点的标题字
        
        for key, label in order:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, label)
            item.setExpanded(True)
            item.setFlags(Qt.ItemIsEnabled) # 根节点不可选中，只作为标题
            
            # 设置标题样式 (稍微暗一点的颜色)
            item.setFont(0, font_header)
            
            # 增加一点间距 (通过添加空的子节点占位或者CSS margin)
            # 这里依赖CSS margin-top 实现分组感
            
            self.roots[key] = item
            
        self._add_fixed_date_options('date_create')
        self._add_fixed_date_options('date_modify')

    def _add_fixed_date_options(self, key):
        root = self.roots[key]
        options = ["今日", "昨日", "周内", "两周", "本月", "上月"]
        for opt in options:
            child = QTreeWidgetItem(root)
            child.setText(0, opt)
            child.setData(0, Qt.UserRole, opt)
            child.setCheckState(0, Qt.Unchecked)

    def _on_item_changed(self, item, col):
        """勾选变化时，发射信号通知主窗口应用前端过滤"""
        # === 核心修改：只发射信号，不做其他操作 ===
        self.filterChanged.emit()
        
        # 保留点击锁定逻辑（防止意外触发）
        self._block_item_click = True
        QTimer.singleShot(100, lambda: setattr(self, '_block_item_click', False))

    def _on_item_clicked(self, item, column):
        if self._block_item_click: return
        
        # 如果点击的是根节点（主分类），则切换其展开/折叠状态
        if item.parent() is None:
            item.setExpanded(not item.isExpanded())
        # 如果点击的是子节点，则切换其复选框状态
        elif item.flags() & Qt.ItemIsUserCheckable:
            state = item.checkState(0)
            item.setCheckState(0, Qt.Unchecked if state == Qt.Checked else Qt.Checked)

    def update_stats(self, stats):
        self.tree.blockSignals(True)
        
        # 1. 星级
        star_data = []
        for i in range(5, 0, -1):
            star_data.append((i, "★" * i, stats['stars'].get(i, 0)))
        if 0 in stats['stars']: star_data.append((0, "无星级", stats['stars'][0]))
        self._refresh('stars', star_data)

        # 2. 颜色
        self._refresh('colors', [(c, c.upper(), count) for c, count in stats['colors'].items()], is_col=True)
        
        # 3. 标签
        self._refresh('tags', stats.get('tags', []), is_tag=True)
        
        # 4. 日期
        self._refresh_date('date_create', stats.get('date_create', {}))
        self._refresh_date('date_modify', stats.get('date_modify', {}))
        
        # 5. 类型 (简单处理)
        type_labels = {'text': '文本', 'url': '链接', 'folder': '文件夹', 'image': '图片', 'file': '文件'}
        type_data = []
        for t, count in stats.get('types', {}).items():
            label = type_labels.get(t, t.upper())
            type_data.append((t, label, count))
        self._refresh('types', type_data)
        
        self.tree.blockSignals(False)

    def _refresh(self, key, data, is_tag=False, is_col=False):
        root = self.roots[key]
        checked = {root.child(i).data(0, Qt.UserRole) for i in range(root.childCount()) if root.child(i).checkState(0) == Qt.Checked}
        root.takeChildren()
        
        if not data:
            # 不显示"空"，直接保持空白更清爽
            return

        for item_data in data:
            if is_tag:
                if isinstance(item_data, tuple): v, c = item_data; l = v
                else: v = l = item_data; c = 0
            else:
                v, l, c = item_data
            
            # 数量为0且未选中的不显示
            if c == 0 and v not in checked: continue
            
            child = QTreeWidgetItem(root)
            # 格式化文本： 左侧名称 ...... 右侧数量
            # 由于QTreeWidget单列不支持对齐，我们直接写在一起
            child.setText(0, f"{l}  ({c})") 
            child.setData(0, Qt.UserRole, v)
            child.setCheckState(0, Qt.Checked if v in checked else Qt.Unchecked)
            if is_col: child.setIcon(0, get_color_icon(v))

    def _refresh_date(self, key, stats):
        root = self.roots[key]
        for i in range(root.childCount()):
            item = root.child(i)
            label = item.data(0, Qt.UserRole)
            count = stats.get(label, 0)
            item.setText(0, f"{label}  ({count})")
            # 数量为0置灰 (通过CSS不易控制单个Item颜色，这里略过)

    def get_checked(self, key):
        root = self.roots.get(key)
        return [root.child(i).data(0, Qt.UserRole) for i in range(root.childCount()) if root.child(i).checkState(0) == Qt.Checked]

    def reset_filters(self):
        """清空所有筛选器的勾选状态"""
        self.tree.blockSignals(True)
        for key, root_item in self.roots.items():
            for i in range(root_item.childCount()):
                child = root_item.child(i)
                child.setCheckState(0, Qt.Unchecked)
        self.tree.blockSignals(False)
        self.filterChanged.emit() # 手动触发一次更新
