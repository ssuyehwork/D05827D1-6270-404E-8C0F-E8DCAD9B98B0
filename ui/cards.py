# -*- coding: utf-8 -*-
# ui/cards.py
import sys
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QApplication, QSizePolicy, QWidget
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData, QSize, QPoint
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
        
        # 布局策略：水平填满，垂直适应
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
        # 使用键名访问，确保 ID 获取正确
        self.id = data['id']
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
        # 强制换行策略
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

        # 3. 底部区域
        bot_layout = QHBoxLayout()
        bot_layout.setSpacing(6)
        
        self.time_label = QLabel()
        self.time_label.setStyleSheet("color:rgba(255,255,255,100); font-size:12px; background:transparent;")
        self.time_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
        bot_layout.addWidget(self.time_label)
        bot_layout.addStretch() 
        
        self.tags_layout = QHBoxLayout()
        self.tags_layout.setSpacing(4)
        bot_layout.addLayout(self.tags_layout)
        
        self.main_layout.addLayout(bot_layout)

    def _refresh_ui_content(self):
        # 使用键名访问，防止索引错位
        self.title_label.setText(self.data['title'])
        
        # 安全获取字段
        rating = self.data['rating'] if 'rating' in self.data.keys() else 0
        is_locked = self.data['is_locked'] if 'is_locked' in self.data.keys() else 0
        is_pinned = self.data['is_pinned']
        is_favorite = self.data['is_favorite']

        # 星级
        if rating and rating > 0:
            self.rating_label.setPixmap(self._generate_stars_pixmap(rating))
            self.rating_label.show()
        else:
            self.rating_label.hide()
            
        # 锁定 (绿色图标)
        if is_locked:
            self.lock_icon.setPixmap(create_svg_icon("lock.svg", COLORS['success']).pixmap(14, 14))
            self.lock_icon.show()
        else:
            self.lock_icon.hide()

        # 置顶 (红色实心图标)
        if is_pinned:
            self.pin_icon.setPixmap(create_svg_icon("pin_vertical.svg", "#e74c3c").pixmap(14, 14))
            self.pin_icon.show()
        else:
            self.pin_icon.hide()

        # 书签 (核心修复：背景是粉色，所以图标必须是白色，否则看不见)
        if is_favorite:
            self.fav_icon.setPixmap(create_svg_icon("bookmark.svg", "#ff6b81").pixmap(14, 14))
            self.fav_icon.show()
        else:
            self.fav_icon.hide()

        # 内容渲染
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        item_type = self.data['item_type'] or 'text'
        
        if item_type == 'image' and self.data['data_blob']:
            pixmap = QPixmap()
            pixmap.loadFromData(self.data['data_blob'])
            if not pixmap.isNull():
                img_label = QLabel()
                scaled_pixmap = pixmap.scaled(QSize(600, 300), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                img_label.setPixmap(scaled_pixmap)
                img_label.setStyleSheet("background: transparent;")
                img_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                self.content_layout.addWidget(img_label)
                
        elif self.data['content']:
            preview_text = self.data['content'].strip()[:300].replace('\n', ' ')
            if len(self.data['content']) > 300: preview_text += "..."
            content = QLabel(preview_text)
            content.setStyleSheet("color: rgba(255,255,255,180); margin-top: 4px; background: transparent; font-size: 13px; line-height: 1.5;")
            content.setWordWrap(True)
            content.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)
            self.content_layout.addWidget(content)

        # 时间 (带时钟符号)
        self.time_label.setText(f'{self.data["updated_at"][:16]}')
        
        # 标签
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        
        # 优先使用预加载的标签，避免 N+1 查询
        if 'tags' in self.data:
            tags = self.data['tags']
        else:
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
        bg_color = self.data['color']
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
        
        # [修正] 修正热点计算逻辑，精确控制快照在光标右上角的位置
        offset = 25
        # 热点是快照上与光标对齐的点。
        # 将其设置为(-offset, pixmap.height() + offset) 可以
        # 将快照的左下角精确定位在(光标.x + offset, 光标.y - offset)
        drag.setHotSpot(QPoint(-offset, pixmap.height() + offset))
        
        # [修改] 将操作类型改为CopyAction以显示"+"号光标
        drag.exec_(Qt.CopyAction)
        
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