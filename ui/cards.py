# -*- coding: utf-8 -*-
# ui/cards.py
import sys
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QApplication
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData
from PyQt5.QtGui import QDrag
from core.config import STYLES

class IdeaCard(QFrame):
    selection_requested = pyqtSignal(int, bool)
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
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(6) # 稍微减小间距，让内容更紧凑
        
        # --- 顶部：标题 + 图标 ---
        top = QHBoxLayout()
        top.setSpacing(8)
        
        # 标题
        title = QLabel(self.data[1])
        title.setStyleSheet("font-size:15px; font-weight:bold; background:transparent; color:white;")
        title.setWordWrap(False) # 标题单行显示，超出显示省略号
        # 设置标题的 Elide 模式需要更复杂的处理，这里暂用样式表控制或默认行为
        top.addWidget(title, stretch=1)
        
        # 图标区域 (置顶/收藏)
        icon_layout = QHBoxLayout()
        icon_layout.setSpacing(4)
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
        
        # --- 中部：内容预览 ---
        if self.data[2]:
            content_str = self.data[2].strip()
            
            # 【修复逻辑】不再暴力截断第一行，而是获取一段较长的文本，让 Label 自动换行
            # 将换行符替换为空格，以便在卡片中连续显示
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
            content.setWordWrap(True) # 允许自动换行
            content.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            layout.addWidget(content)
            
        # --- 底部：时间 + 标签 ---
        bot = QHBoxLayout()
        bot.setSpacing(6)
        
        # 时间
        time_str = self.data[7][:16] # YYYY-MM-DD HH:mm
        time_label = QLabel(f'{time_str}')
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
        mime.setData('application/x-idea-id', str(self.id).encode())
        drag.setMimeData(mime)
        
        pixmap = self.grab().scaledToWidth(200, Qt.SmoothTransformation)
        drag.setPixmap(pixmap)
        drag.setHotSpot(e.pos())
        
        drag.exec_(Qt.MoveAction)
        
    def mouseReleaseEvent(self, e):
        if self._is_potential_click and e.button() == Qt.LeftButton:
            is_ctrl_pressed = QApplication.keyboardModifiers() == Qt.ControlModifier
            self.selection_requested.emit(self.id, is_ctrl_pressed)

        self._drag_start_pos = None
        self._is_potential_click = False
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.double_clicked.emit(self.id)
        super().mouseDoubleClickEvent(e)