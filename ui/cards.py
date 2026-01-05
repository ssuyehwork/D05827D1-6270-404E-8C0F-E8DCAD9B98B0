# -*- coding: utf-8 -*-
# ui/cards.py
import sys
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QApplication, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData, QSize
from PyQt5.QtGui import QDrag, QPixmap, QImage
from core.config import STYLES

class IdeaCard(QFrame):
    # (id, is_ctrl, is_shift)
    selection_requested = pyqtSignal(int, bool, bool)
    double_clicked = pyqtSignal(int)

    def __init__(self, data, db, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground)
        
        self.data = data
        self.db = db
        self.id = data[0]
        self.setCursor(Qt.PointingHandCursor)
        
        # --- 状态变量 ---
        self._drag_start_pos = None
        self._is_potential_click = False
        
        # 这是一个占位符，会在 main_window 中被赋值
        self.get_selected_ids_func = None
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(8) # 增加一点内部间距
        
        # --- 1. 顶部：标题 + 图标 ---
        top = QHBoxLayout()
        top.setSpacing(8)
        
        # 标题 (对于图片，如果标题是默认的"[图片]"，可以显示得淡一点，或者保持原样)
        title_text = self.data[1]
        title = QLabel(title_text)
        title.setStyleSheet("font-size:15px; font-weight:bold; background:transparent; color:white;")
        title.setWordWrap(False)
        top.addWidget(title, stretch=1)
        
        # 图标区域 (置顶/收藏/锁定)
        icon_layout = QHBoxLayout()
        icon_layout.setSpacing(4)
        
        # 锁定状态判断: 数据列最后一位是 is_locked
        # 假设数据列顺序: 0-id ... 13-is_locked (如果表结构是新建的)
        # 为稳健起见，尝试获取最后一位，如果是 1 则显示锁
        is_locked = False
        if len(self.data) >= 14:
            is_locked = self.data[13]
        
        if is_locked:
            lock_icon = QLabel('🔒')
            lock_icon.setStyleSheet("background:transparent; font-size:12px;")
            icon_layout.addWidget(lock_icon)

        if self.data[4]:  # is_pinned
            pin_icon = QLabel('📌')
            pin_icon.setStyleSheet("background:transparent; font-size:12px;")
            icon_layout.addWidget(pin_icon)
        if self.data[5]:  # is_favorite
            fav_icon = QLabel('⭐')
            fav_icon.setStyleSheet("background:transparent; font-size:12px;")
            icon_layout.addWidget(fav_icon)
            
        top.addLayout(icon_layout)
        layout.addLayout(top)
        
        # --- 2. 中部：内容预览 (文本 或 图片) ---
        # 解析数据类型
        # data结构: 0:id, 1:title, 2:content ... 10:item_type, 11:data_blob
        item_type = self.data[10] if len(self.data) > 10 and self.data[10] else 'text'
        
        if item_type == 'image':
            # === 图片模式 ===
            blob_data = self.data[11] if len(self.data) > 11 else None
            if blob_data:
                pixmap = QPixmap()
                pixmap.loadFromData(blob_data)
                
                if not pixmap.isNull():
                    img_label = QLabel()
                    # 限制最大显示高度，防止卡片过大
                    max_height = 160
                    if pixmap.height() > max_height:
                        pixmap = pixmap.scaledToHeight(max_height, Qt.SmoothTransformation)
                    
                    # 如果宽度也太宽，限制宽度
                    if pixmap.width() > 400: # 假设卡片大概这么宽
                        pixmap = pixmap.scaledToWidth(400, Qt.SmoothTransformation)
                        
                    img_label.setPixmap(pixmap)
                    img_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                    img_label.setStyleSheet("background: transparent; border-radius: 4px;")
                    layout.addWidget(img_label)
                else:
                    err_label = QLabel("[图片无法加载]")
                    err_label.setStyleSheet("color: #666; font-style: italic;")
                    layout.addWidget(err_label)
        else:
            # === 文本/文件模式 ===
            if self.data[2]:
                content_str = self.data[2].strip()
                
                # 获取一段较长的文本，让 Label 自动换行
                preview_text = content_str[:300].replace('\n', ' ').replace('\r', '')
                if len(content_str) > 300:
                    preview_text += "..."
                    
                content = QLabel(preview_text)
                content.setStyleSheet("""
                    color: rgba(255,255,255,180); 
                    margin-top: 2px; 
                    background: transparent; 
                    font-size: 13px;
                    line-height: 1.4;
                """)
                content.setWordWrap(True)
                content.setAlignment(Qt.AlignTop | Qt.AlignLeft)
                # 限制高度，大概显示 3 行文字的高度
                content.setMaximumHeight(65) 
                layout.addWidget(content)
            
        # --- 3. 底部：时间 + 标签 ---
        bot = QHBoxLayout()
        bot.setSpacing(6)
        
        # 时间
        time_str = self.data[7][:16] # YYYY-MM-DD HH:mm
        time_label = QLabel(f'🕒 {time_str}')
        time_label.setStyleSheet("color:rgba(255,255,255,100); font-size:11px; background:transparent;")
        bot.addWidget(time_label)
        
        bot.addStretch()
        
        # 标签
        tags = self.db.get_tags(self.id)
        visible_tags = tags[:3]
        remaining = len(tags) - 3
        
        for tag in visible_tags:
            tag_label = QLabel(f"#{tag}")
            tag_label.setStyleSheet("""
                background: rgba(255,255,255,0.1); 
                border-radius: 4px; 
                padding: 2px 6px; 
                font-size: 10px; 
                color: rgba(255,255,255,180);
            """)
            bot.addWidget(tag_label)
            
        if remaining > 0:
            more_label = QLabel(f'+{remaining}')
            more_label.setStyleSheet("""
                background: rgba(74,144,226,0.3); 
                border-radius: 4px; 
                padding: 2px 6px; 
                font-size: 10px; 
                color: #4a90e2;
                font-weight:bold;
            """)
            bot.addWidget(more_label)
            
        layout.addLayout(bot)
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
