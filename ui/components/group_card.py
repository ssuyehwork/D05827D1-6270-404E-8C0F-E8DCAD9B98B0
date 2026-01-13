# -*- coding: utf-8 -*-
# ui/components/group_card.py

from PyQt5.QtWidgets import QFrame, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QCursor
from ui.utils import create_svg_icon

class GroupCard(QFrame):
    clicked = pyqtSignal(int)  # 发送 category_id

    def __init__(self, data, count, parent=None):
        """
        data: categories 表中的一行数据 (id, name, parent_id, color, ...)
        count: 该分组下的笔记数量
        """
        super().__init__(parent)
        self.data = data
        self.cat_id = data[0]
        self.name = data[1]
        self.color = data[3] if len(data) > 3 and data[3] else "#555"
        self.count = count
        
        self.setCursor(QCursor(Qt.PointingHandCursor))
        # 保持之前的尺寸设计
        self.setFixedSize(160, 100) 
        
        self._init_ui()

    def _init_ui(self):
        # 样式：深色背景，圆角
        self.setStyleSheet(f"""
            GroupCard {{
                background-color: #2D2D2D;
                border: 1px solid #3A3A3A;
                border-radius: 8px;
            }}
            GroupCard:hover {{
                background-color: #383838;
                border: 1px solid {self.color};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 顶部：大图标 (使用 branch.svg 体现分支/分组概念，颜色跟随分组颜色)
        icon_label = QLabel()
        icon_label.setPixmap(create_svg_icon("branch.svg", self.color).pixmap(32, 32))
        layout.addWidget(icon_label, alignment=Qt.AlignLeft)
        
        layout.addStretch()
        
        # 底部：名称
        name_label = QLabel(self.name)
        name_label.setStyleSheet("color: #EEE; font-size: 14px; font-weight: bold; border: none; background: transparent;")
        name_label.setWordWrap(False) 
        layout.addWidget(name_label)
        
        # 底部：数量
        count_text = f"{self.count} 项内容"
        count_label = QLabel(count_text)
        count_label.setStyleSheet("color: #888; font-size: 11px; border: none; background: transparent;")
        layout.addWidget(count_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.cat_id)
        super().mousePressEvent(event)