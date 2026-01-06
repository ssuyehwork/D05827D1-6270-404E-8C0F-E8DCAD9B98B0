# -*- coding: utf-8 -*-
# ui/cards.py
import sys
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QApplication, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData, QSize
from PyQt5.QtGui import QDrag, QPixmap, QImage
from core.config import STYLES, COLORS

class IdeaCard(QFrame):
    selection_requested = pyqtSignal(int, bool, bool)
    double_clicked = pyqtSignal(int)

    def __init__(self, data, db, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground)
        self.db = db
        self.setCursor(Qt.PointingHandCursor)
        
        self._drag_start_pos = None
        self._is_potential_click = False
        self.get_selected_ids_func = None
        
        self._setup_ui_structure()
        self.update_data(data)

    def update_data(self, data):
        self.data = data
        self.id = data[0]
        self._refresh_ui_content()

    def _setup_ui_structure(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 12, 15, 12)
        self.main_layout.setSpacing(8)

        # 1. Top Section
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)
        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size:15px; font-weight:bold; background:transparent; color:white;")
        self.title_label.setWordWrap(False)
        top_layout.addWidget(self.title_label, stretch=1)
        
        self.icon_layout = QHBoxLayout()
        self.icon_layout.setSpacing(4)
        self.rating_label = QLabel()
        self.lock_icon = QLabel('🔒\uFE0E')
        self.pin_icon = QLabel('📌')
        self.fav_icon = QLabel('🌟')
        for icon in [self.rating_label, self.lock_icon, self.pin_icon, self.fav_icon]:
            self.icon_layout.addWidget(icon)
        top_layout.addLayout(self.icon_layout)
        self.main_layout.addLayout(top_layout)

        # 2. Middle Section (Content)
        self.content_widget = QFrame() # Placeholder for text or image
        self.content_widget.setStyleSheet("background:transparent; border:none;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0,0,0,0)
        self.main_layout.addWidget(self.content_widget)

        # 3. Bottom Section
        bot_layout = QHBoxLayout()
        bot_layout.setSpacing(6)
        self.time_label = QLabel()
        self.time_label.setStyleSheet("color:rgba(255,255,255,100); font-size:11px; background:transparent;")
        bot_layout.addWidget(self.time_label)
        bot_layout.addStretch()
        self.tags_layout = QHBoxLayout()
        self.tags_layout.setSpacing(4)
        bot_layout.addLayout(self.tags_layout)
        self.main_layout.addLayout(bot_layout)

    def _refresh_ui_content(self):
        # 1. Refresh Top
        self.title_label.setText(self.data[1])
        
        rating = self.data[14] if len(self.data) > 14 else 0
        is_locked = self.data[13] if len(self.data) > 13 else 0
        is_pinned = self.data[4]
        is_favorite = self.data[5]

        if rating > 0:
            self.rating_label.setText(f"{'★'*rating}")
            self.rating_label.setStyleSheet(f"background:transparent; font-size:12px; color: {COLORS['warning']};")
            self.rating_label.show()
        else:
            self.rating_label.hide()
            
        self.lock_icon.setStyleSheet(f"background:transparent; font-size:12px; color: {COLORS['success']};")
        self.lock_icon.setVisible(bool(is_locked))
        self.pin_icon.setStyleSheet("background:transparent; font-size:12px;")
        self.pin_icon.setVisible(bool(is_pinned))
        self.fav_icon.setText("🔖")
        self.fav_icon.setStyleSheet("background:transparent; font-size:12px;")
        self.fav_icon.setVisible(bool(is_favorite))

        # 2. Refresh Middle
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        item_type = self.data[10] if len(self.data) > 10 and self.data[10] else 'text'
        if item_type == 'image' and self.data[11]:
            pixmap = QPixmap()
            pixmap.loadFromData(self.data[11])
            if not pixmap.isNull():
                img_label = QLabel()
                max_h = 160
                if pixmap.height() > max_h: pixmap = pixmap.scaledToHeight(max_h, Qt.SmoothTransformation)
                if pixmap.width() > 400: pixmap = pixmap.scaledToWidth(400, Qt.SmoothTransformation)
                img_label.setPixmap(pixmap)
                self.content_layout.addWidget(img_label)
        elif self.data[2]:
            preview_text = self.data[2].strip()[:300].replace('\n', ' ')
            if len(self.data[2]) > 300: preview_text += "..."
            content = QLabel(preview_text)
            content.setStyleSheet("color: rgba(255,255,255,180); margin-top: 2px; background: transparent; font-size: 13px; line-height: 1.4;")
            content.setWordWrap(True)
            content.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            content.setMaximumHeight(65) 
            self.content_layout.addWidget(content)

        # 3. Refresh Bottom
        self.time_label.setText(f'🕒 {self.data[7][:16]}')
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        
        tags = self.db.get_tags(self.id)
        for i, tag in enumerate(tags):
            if i >= 3:
                more_label = QLabel(f'+{len(tags) - 3}')
                more_label.setStyleSheet(f"background: rgba(74,144,226,0.3); border-radius: 4px; padding: 2px 6px; font-size: 10px; color: {COLORS['primary']}; font-weight:bold;")
                self.tags_layout.addWidget(more_label)
                break
            tag_label = QLabel(f"#{tag}")
            tag_label.setStyleSheet("background: rgba(255,255,255,0.1); border-radius: 4px; padding: 2px 6px; font-size: 10px; color: rgba(255,255,255,180);")
            self.tags_layout.addWidget(tag_label)

        self.update_selection(False)

    def update_selection(self, selected):
        bg_color = self.data[3]
        
        # 基础样式
        base_style = f"""
            IdeaCard {{
                background-color: {bg_color};
                {STYLES['card_base']}
                padding: 0px;
            }}
            QLabel {{
                background-color: transparent;
                border: none;
            }}
        """

        if selected:
            # 选中状态：白色粗边框
            border_style = "border: 2px solid white;"
        else:
            # 未选中状态：透明微弱边框，悬停变亮
            border_style = """
                border: 1px solid rgba(255,255,255,0.1);
            """
            
        # 合并 hover 效果到样式表中
        final_style = base_style + f"""
            IdeaCard {{ {border_style} }}
            IdeaCard:hover {{
                border: 2px solid rgba(255,255,255,0.4);
            }}
        """
        
        # 如果选中了，需要覆盖 hover 样式，保持选中状态的边框
        if selected:
            final_style += """
                IdeaCard:hover {
                    border: 2px solid white;
                }
            """
            
        self.setStyleSheet(final_style)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_start_pos = e.pos()
            self._is_potential_click = True
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not (e.buttons() & Qt.LeftButton) or not self._drag_start_pos:
            return
        
        if (e.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return
        
        # 拖拽开始，取消点击判定
        self._is_potential_click = False
        
        drag = QDrag(self)
        mime = QMimeData()
        
        # --- 批量拖拽支持 ---
        ids_to_move = [self.id]
        if self.get_selected_ids_func:
            selected_ids = self.get_selected_ids_func()
            if self.id in selected_ids:
                ids_to_move = selected_ids
        
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
