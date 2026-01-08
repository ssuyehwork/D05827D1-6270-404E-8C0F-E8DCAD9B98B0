# -*- coding: utf-8 -*-
# ui/cards.py
import sys
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QApplication, QSizePolicy, QWidget
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData, QSize
from PyQt5.QtGui import QDrag, QPixmap, QImage, QPainter
from core.config import STYLES, COLORS
from ui.utils import create_svg_icon

class IdeaCard(QFrame):
    selection_requested = pyqtSignal(int, bool, bool)
    double_clicked = pyqtSignal(int)

    def __init__(self, data, db, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground)
        self.db = db
        self.setCursor(Qt.PointingHandCursor)
        
        # 水平 Expanding (占满父容器), 垂直 Minimum (适应内容高度)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        self.setMinimumWidth(0)
        self.setMaximumWidth(16777215)
        
        self.setMinimumHeight(80)
        
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
        self.main_layout.setSpacing(6)

        # 1. 顶部区域
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)
        
        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size:15px; font-weight:bold; background:transparent; color:white;")
        self.title_label.setWordWrap(True) 
        self.title_label.setContentsMargins(0, 0, 5, 0)
        
        # 使用 Ignored 策略，强制文字换行
        self.title_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        
        top_layout.addWidget(self.title_label, 1) # 权重1
        
        self.icon_layout = QHBoxLayout()
        self.icon_layout.setSpacing(4)
        
        self.rating_label = QLabel()
        self.lock_icon = QLabel()
        self.pin_icon = QLabel()
        self.fav_icon = QLabel()
        
        for icon in [self.rating_label, self.lock_icon, self.pin_icon, self.fav_icon]:
            icon.setStyleSheet("background: transparent; border: none;")
            icon.setAlignment(Qt.AlignCenter)
            self.icon_layout.addWidget(icon)
            
        top_layout.addLayout(self.icon_layout)
        self.main_layout.addLayout(top_layout)

        # 2. 中间内容区域
        self.content_widget = QFrame()
        self.content_widget.setStyleSheet("background:transparent; border:none;")
        self.content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0,0,0,0)
        self.main_layout.addWidget(self.content_widget)

        # 3. 底部区域 (时间 + 标签)
        bot_layout = QHBoxLayout()
        bot_layout.setSpacing(6)
        
        # 【修改】移除了单独的 time_icon QLabel
        # 直接使用 time_label 显示图标和时间
        
        self.time_label = QLabel()
        self.time_label.setStyleSheet("color:rgba(255,255,255,100); font-size:12px; background:transparent;")
        self.time_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
        bot_layout.addWidget(self.time_label)
        
        # 弹簧
        bot_layout.addStretch() 
        
        self.tags_layout = QHBoxLayout()
        self.tags_layout.setSpacing(4)
        bot_layout.addLayout(self.tags_layout)
        
        self.main_layout.addLayout(bot_layout)

    def _refresh_ui_content(self):
        self.title_label.setText(self.data[1])
        
        rating = self.data[14] if len(self.data) > 14 else 0
        is_locked = self.data[13] if len(self.data) > 13 else 0
        is_pinned = self.data[4]
        is_favorite = self.data[5]

        if rating > 0:
            self.rating_label.setPixmap(self._generate_stars_pixmap(rating))
            self.rating_label.show()
        else:
            self.rating_label.hide()
            
        if is_locked:
            self.lock_icon.setPixmap(create_svg_icon("lock.svg", COLORS['success']).pixmap(14, 14))
            self.lock_icon.show()
        else:
            self.lock_icon.hide()

        if is_pinned:
            self.pin_icon.setPixmap(create_svg_icon("action_pin.svg", "#cccccc").pixmap(14, 14))
            self.pin_icon.show()
        else:
            self.pin_icon.hide()

        if is_favorite:
            self.fav_icon.setPixmap(create_svg_icon("bookmark.svg", "#ff6b81").pixmap(14, 14))
            self.fav_icon.show()
        else:
            self.fav_icon.hide()

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
                # 限制图片最大显示尺寸
                scaled_pixmap = pixmap.scaled(QSize(600, 300), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                img_label.setPixmap(scaled_pixmap)
                img_label.setStyleSheet("background: transparent;")
                img_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                self.content_layout.addWidget(img_label)
                
        elif self.data[2]:
            preview_text = self.data[2].strip()[:300].replace('\n', ' ')
            if len(self.data[2]) > 300: preview_text += "..."
            content = QLabel(preview_text)
            content.setStyleSheet("color: rgba(255,255,255,180); margin-top: 4px; background: transparent; font-size: 13px; line-height: 1.5;")
            content.setWordWrap(True)
            content.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)
            self.content_layout.addWidget(content)

        # 【核心修改】直接在文本中添加时钟符号
        # 使用 \ufe0e 尝试强制文本显示模式 (防止变成彩色 Emoji)
        self.time_label.setText(f'🕒 {self.data[7][:16]}')
        
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        
        tags = self.db.get_tags(self.id)
        limit = 6 
        for i, tag in enumerate(tags):
            if i >= limit:
                more_label = QLabel(f'+{len(tags) - limit}')
                more_label.setStyleSheet(f"background: rgba(74,144,226,0.3); border-radius: 4px; padding: 2px 6px; font-size: 10px; color: {COLORS['primary']}; font-weight:bold;")
                self.tags_layout.addWidget(more_label)
                break
            tag_label = QLabel(f"#{tag}")
            tag_label.setStyleSheet("background: rgba(255,255,255,0.1); border-radius: 4px; padding: 2px 6px; font-size: 10px; color: rgba(255,255,255,180);")
            self.tags_layout.addWidget(tag_label)

        self.update_selection(False)

    def _generate_stars_pixmap(self, rating):
        star_size = 12
        spacing = 2
        total_width = (star_size * rating) + (spacing * (rating - 1))
        pixmap = QPixmap(total_width, star_size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        star_icon = create_svg_icon("star_filled.svg", COLORS['warning'])
        for i in range(rating):
            x = i * (star_size + spacing)
            star_icon.paint(painter, x, 0, star_size, star_size)
        painter.end()
        return pixmap

    def update_selection(self, selected):
        bg_color = self.data[3]
        base_style = f"""
            IdeaCard {{
                background-color: {bg_color};
                border-radius: 8px;
                padding: 0px;
            }}
            QLabel {{
                background-color: transparent;
                border: none;
            }}
        """
        if selected:
            border_style = "border: 2px solid white;"
        else:
            border_style = "border: 1px solid rgba(255,255,255,0.05);"
            
        final_style = base_style + f"""
            IdeaCard {{ {border_style} }}
            IdeaCard:hover {{
                border: 1px solid rgba(255,255,255,0.3);
            }}
        """
        if selected:
            final_style += "IdeaCard:hover { border: 2px solid white; }"
            
        self.setStyleSheet(final_style)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_start_pos = e.pos()
            self._is_potential_click = True
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not (e.buttons() & Qt.LeftButton) or not self._drag_start_pos: return
        if (e.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance(): return
        self._is_potential_click = False
        drag = QDrag(self)
        mime = QMimeData()
        ids_to_move = [self.id]
        if self.get_selected_ids_func:
            selected_ids = self.get_selected_ids_func()
            if self.id in selected_ids: ids_to_move = selected_ids
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