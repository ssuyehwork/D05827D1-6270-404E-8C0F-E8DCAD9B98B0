# -*- coding: utf-8 -*-
# ui/card_list_view.py

from PyQt5.QtWidgets import QWidget, QScrollArea, QLabel, QVBoxLayout, QSizePolicy, QFrame, QHBoxLayout, QCheckBox
from PyQt5.QtCore import Qt, pyqtSignal
from ui.cards import IdeaCard
from ui.components.group_card import GroupCard
from ui.flow_layout import FlowLayout
from ui.utils import create_svg_icon
from core.config import COLORS

class ContentContainer(QWidget):
    cleared = pyqtSignal()
    def mousePressEvent(self, e):
        # 点击空白处清除选中
        if self.childAt(e.pos()) is None: 
            self.cleared.emit()
            e.accept()
        else: 
            super().mousePressEvent(e)

class CardListView(QScrollArea):
    selection_cleared = pyqtSignal()
    card_selection_requested = pyqtSignal(int, bool, bool)
    card_double_clicked = pyqtSignal(int)
    card_context_menu_requested = pyqtSignal(int, object)
    
    # 点击文件夹时触发（现在是双击）
    folder_clicked = pyqtSignal(int)
    
    # 递归模式切换信号
    recursive_mode_changed = pyqtSignal(bool)

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.db = service 
        self.cards = {}
        self.ordered_ids = []
        
        self._recursive_checked = False
        
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
        self.layout.setContentsMargins(20, 20, 20, 20) 
        self.layout.setSpacing(10) 
        
        self.setWidget(self.container)

    def set_recursive_mode(self, checked):
        """外部调用，设置复选框状态"""
        self._recursive_checked = checked

    def clear_all(self):
        """完全清空并销毁所有组件"""
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
                item.layout().deleteLater()
                
        self.cards = {}
        self.ordered_ids = []

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def clear(self):
        """刷新时调用"""
        self.clear_all()

    def render_cards(self, data_list, sub_folders=None):
        """
        渲染内容：
        1. 顶部的分组区域 (GroupCard) + 复选框
        2. 底部的笔记区域 (IdeaCard)
        """
        self.clear()
        
        has_content = False
        
        # --- 1. 渲染子分组 (Group Area) ---
        if sub_folders and len(sub_folders) > 0:
            has_content = True
            
            # 头部布局：左侧标题，右侧复选框
            header_layout = QHBoxLayout()
            header_layout.setContentsMargins(0, 0, 0, 0)
            
            group_header = QLabel(f"分组 ({len(sub_folders)})")
            group_header.setStyleSheet("color: #888; font-size: 12px; font-weight: bold;")
            header_layout.addWidget(group_header)
            
            header_layout.addStretch()
            
            self.chk_recursive = QCheckBox("显示子文件夹内容")
            self.chk_recursive.setCursor(Qt.PointingHandCursor)
            self.chk_recursive.setChecked(self._recursive_checked)
            self.chk_recursive.setStyleSheet(f"""
                QCheckBox {{ color: #888; font-size: 12px; }}
                QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid #555; border-radius: 3px; background: transparent; }}
                QCheckBox::indicator:checked {{ background-color: {COLORS['primary']}; border-color: {COLORS['primary']}; }}
                QCheckBox:hover {{ color: #ccc; }}
            """)
            self.chk_recursive.toggled.connect(self._on_recursive_toggled)
            header_layout.addWidget(self.chk_recursive)
            
            self.layout.addLayout(header_layout)
            
            # 分组容器 (FlowLayout)
            group_container = QWidget()
            group_container.setStyleSheet("background: transparent;")
            group_flow = FlowLayout(group_container, margin=0, spacing=15)
            
            for folder_data, count in sub_folders:
                g_card = GroupCard(folder_data, count)
                # [修改] 连接 double_clicked 信号
                g_card.double_clicked.connect(self.folder_clicked.emit)
                group_flow.addWidget(g_card)
                
            self.layout.addWidget(group_container)
            
            # 分割线
            if data_list:
                line = QFrame()
                line.setFrameShape(QFrame.HLine)
                line.setStyleSheet("background-color: #444; border: none; min-height: 1px; max-height: 1px; margin-top: 10px; margin-bottom: 10px;")
                self.layout.addWidget(line)

        # --- 2. 渲染笔记内容 (Idea Area) ---
        if data_list:
            has_content = True
            
            content_header = QLabel(f"内容 ({len(data_list)})")
            content_header.setStyleSheet("color: #888; font-size: 12px; font-weight: bold; margin-bottom: 5px;")
            self.layout.addWidget(content_header)
            
            for d in data_list:
                iid = d['id']
                c = IdeaCard(d, self.db)
                c.selection_requested.connect(self.card_selection_requested)
                c.double_clicked.connect(self.card_double_clicked)
                c.setContextMenuPolicy(Qt.CustomContextMenu)
                c.customContextMenuRequested.connect(lambda pos, iid=iid: self.card_context_menu_requested.emit(iid, pos))
                self.cards[iid] = c
                self.layout.addWidget(c)
                self.ordered_ids.append(iid)
                
        # --- 3. 空状态 ---
        if not has_content:
            empty_container = QWidget()
            empty_layout = QVBoxLayout(empty_container)
            empty_layout.setAlignment(Qt.AlignCenter)
            empty_layout.setContentsMargins(0, 50, 0, 0)
            
            icon_lbl = QLabel()
            icon_lbl.setPixmap(create_svg_icon("all_data.svg", "#444").pixmap(48, 48))
            icon_lbl.setAlignment(Qt.AlignCenter)
            
            lbl = QLabel("此分组为空")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color:#666;font-size:16px;")
            
            empty_layout.addWidget(icon_lbl)
            empty_layout.addWidget(lbl)
            
            self.layout.addWidget(empty_container)
            
        self.layout.addStretch(1) 

    def _on_recursive_toggled(self, checked):
        self._recursive_checked = checked
        self.recursive_mode_changed.emit(checked)

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