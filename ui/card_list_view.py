# -*- coding: utf-8 -*-
# ui/card_list_view.py

from PyQt5.QtWidgets import QWidget, QScrollArea, QLabel, QVBoxLayout, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal
from ui.cards import IdeaCard

class ContentContainer(QWidget):
    """
    内部容器，用于捕获点击空白处的事件
    """
    cleared = pyqtSignal()

    def mousePressEvent(self, e):
        if self.childAt(e.pos()) is None:
            self.cleared.emit()
            e.accept()
        else:
            super().mousePressEvent(e)

class CardListView(QScrollArea):
    """
    智能卡片列表视图 (垂直列表模式 - 全宽自适应)
    """
    
    selection_cleared = pyqtSignal()
    card_selection_requested = pyqtSignal(int, bool, bool) 
    card_double_clicked = pyqtSignal(int)
    card_context_menu_requested = pyqtSignal(int, object)

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.cards = {}
        self.ordered_ids = []
        
        self.setWidgetResizable(True)
        # 强制关闭水平滚动条，配合 cards.py 中的 Ignored 策略，迫使文字换行
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
        
        # 容器本身允许水平压缩和伸展
        self.container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(10, 10, 10, 10) 
        self.layout.setSpacing(12) 
        
        self.setWidget(self.container)

    def clear(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.spacerItem():
                pass
        self.cards = {}
        self.ordered_ids = []

    def render_cards(self, data_list):
        self.clear()
        
        if not data_list:
            lbl = QLabel("🔭 空空如也")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color:#666;font-size:16px;margin-top:50px")
            self.layout.addWidget(lbl)
            self.layout.addStretch(1) 
            return

        for d in data_list:
            c = IdeaCard(d, self.db)
            c.selection_requested.connect(self.card_selection_requested)
            c.double_clicked.connect(self.card_double_clicked)
            c.setContextMenuPolicy(Qt.CustomContextMenu)
            c.customContextMenuRequested.connect(lambda pos, iid=d['id']: self.card_context_menu_requested.emit(iid, pos))
            
            self.layout.addWidget(c)
            self.cards[d['id']] = c
            self.ordered_ids.append(d['id'])
            
        self.layout.addStretch(1) 

    def get_card(self, idea_id):
        return self.cards.get(idea_id)

    def remove_card(self, idea_id):
        if idea_id in self.cards:
            card = self.cards.pop(idea_id)
            if idea_id in self.ordered_ids:
                self.ordered_ids.remove(idea_id)
            self.layout.removeWidget(card)
            card.hide()
            card.deleteLater()

    def update_all_selections(self, selected_ids):
        for iid, card in self.cards.items():
            card.update_selection(iid in selected_ids)
            card.get_selected_ids_func = lambda: list(selected_ids)

    def recalc_layout(self):
        pass