# -*- coding: utf-8 -*-
# ui/common_tags.py

from PyQt5.QtWidgets import (QWidget, QPushButton, QMenu, QInputDialog, 
                             QLayout, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal, QRect, QSize, QPoint
from core.config import COLORS
from core.settings import load_setting, save_setting

# --- 核心组件：流式布局 ---
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

# --- 主类 ---
class CommonTags(QWidget):
    tag_toggled = pyqtSignal(str, bool) 
    manager_requested = pyqtSignal()
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.limit = load_setting('common_tags_limit', 5)
        self.tag_buttons = [] 
        
        self._init_ui()
        self.reload_tags()

    def _init_ui(self):
        # 【核心修复】重命名变量为 flow_layout，避免遮挡 QWidget.layout() 方法
        self.flow_layout = FlowLayout(self, margin=0, spacing=6)
        
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.setMinimumWidth(320) 
        self.setMaximumWidth(380) 
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def reload_tags(self):
        # 【核心修复】安全的清理逻辑
        if self.flow_layout:
            while self.flow_layout.count():
                item = self.flow_layout.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()
        
        self.tag_buttons.clear()

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
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("tag_name", name)
            
            self._update_btn_style(btn)
            
            btn.toggled.connect(lambda checked, b=btn, n=name: self._on_btn_toggled(b, n, checked))
            
            self.flow_layout.addWidget(btn)
            self.tag_buttons.append(btn)

        btn_edit = QPushButton("⚙")
        btn_edit.setToolTip("管理标签")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.05);
                color: #666;
                border: none;
                border-radius: 10px;
                width: 20px;
                height: 20px;
                padding: 0px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.1);
                color: {COLORS['primary']};
            }}
        """)
        btn_edit.clicked.connect(self.manager_requested.emit)
        self.flow_layout.addWidget(btn_edit)
        
        self.refresh_requested.emit()

    def reset_selection(self):
        for btn in self.tag_buttons:
            btn.blockSignals(True)
            btn.setChecked(False)
            self._update_btn_style(btn)
            btn.blockSignals(False)

    def _on_btn_toggled(self, btn, name, checked):
        self._update_btn_style(btn)
        self.tag_toggled.emit(name, checked)

    def _update_btn_style(self, btn):
        checked = btn.isChecked()
        name = btn.property("tag_name")
        
        if checked:
            btn.setText(f"✓ {name}")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['primary']};
                    color: white;
                    border: 1px solid {COLORS['primary']};
                    border-radius: 12px;
                    padding: 3px 10px;
                    font-size: 11px;
                    font-family: "Microsoft YaHei", sans-serif;
                    font-weight: bold;
                }}
            """)
        else:
            btn.setText(name)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(255, 255, 255, 0.08);
                    color: #CCC;
                    border: 1px solid transparent;
                    border-radius: 12px;
                    padding: 3px 10px;
                    font-size: 11px;
                    font-family: "Microsoft YaHei", sans-serif;
                }}
                QPushButton:hover {{
                    background-color: rgba(255, 255, 255, 0.15);
                    border: 1px solid #555;
                    color: white;
                }}
            """)
        
        # 【核心修复】移除 adjustSize()，防止在布局过程中触发重绘循环导致崩溃
        # 流式布局会自动处理大小

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background-color: #2D2D2D; color: #EEE; border: 1px solid #444; border-radius: 6px; padding: 4px; }}
            QMenu::item {{ padding: 6px 20px; border-radius: 4px; }}
            QMenu::item:selected {{ background-color: {COLORS['primary']}; color: white; }}
        """)
        action_set_num = menu.addAction(f"🔢 显示数量 (当前: {self.limit})")
        action_set_num.triggered.connect(self._set_tag_limit)
        menu.exec_(self.mapToGlobal(pos))

    def _set_tag_limit(self):
        num, ok = QInputDialog.getInt(self, "设置", "显示数量:", value=self.limit, min=1, max=20)
        if ok:
            self.limit = num
            save_setting('common_tags_limit', num)
            self.reload_tags()