# -*- coding: utf-8 -*-
# ui/components/search_line_edit.py

from PyQt5.QtWidgets import (QLineEdit, QPushButton, QHBoxLayout, QWidget, 
                             QVBoxLayout, QApplication, QLabel, QLayout, 
                             QScrollArea, QFrame, QGraphicsDropShadowEffect, QSizePolicy)
from PyQt5.QtCore import Qt, QSettings, QPoint, QRect, QSize, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QFont, QCursor

# --- 1. 流式布局 ---
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

# --- 2. 历史记录气泡 ---
class HistoryChip(QFrame):
    clicked = pyqtSignal(str)
    deleted = pyqtSignal(str)

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("HistoryChip")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 4, 4)
        layout.setSpacing(6)
        
        lbl = QLabel(text)
        lbl.setStyleSheet("border: none; background: transparent; color: #DDD; font-size: 12px;")
        layout.addWidget(lbl)
        
        self.btn_del = QPushButton("×")
        self.btn_del.setFixedSize(16, 16)
        self.btn_del.setCursor(Qt.PointingHandCursor)
        self.btn_del.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #666;
                border-radius: 8px;
                font-weight: bold;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background-color: #E74C3C;
                color: white;
            }
        """)
        self.btn_del.clicked.connect(self._on_delete)
        layout.addWidget(self.btn_del)
        
        self.setStyleSheet("""
            #HistoryChip {
                background-color: #3A3A3E;
                border: 1px solid #555;
                border-radius: 12px;
            }
            #HistoryChip:hover {
                background-color: #454549;
                border-color: #4a90e2;
            }
        """)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and not self.btn_del.underMouse():
            self.clicked.emit(self.text)
        super().mousePressEvent(e)

    def _on_delete(self):
        self.deleted.emit(self.text)

# --- 3. 现代感弹窗 (完美对齐版) ---
class SearchHistoryPopup(QWidget):
    item_selected = pyqtSignal(str)
    
    def __init__(self, search_edit):
        super().__init__(search_edit.window()) 
        self.search_edit = search_edit
        self.settings = QSettings("KMain_V3", "SearchHistory")
        
        # 阴影边距设置 (左右下各留空间，上方少留一点)
        self.shadow_margin = 12 
        
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 使用根布局来管理边距，确保容器居中，阴影不被切
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(self.shadow_margin, self.shadow_margin, self.shadow_margin, self.shadow_margin)
        
        # 主容器
        self.container = QWidget()
        self.container.setObjectName("PopupContainer")
        self.container.setStyleSheet("""
            #PopupContainer {
                background-color: #252526;
                border: 1px solid #444;
                border-radius: 10px;
            }
        """)
        self.root_layout.addWidget(self.container)
        
        # 阴影
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.container.setGraphicsEffect(shadow)
        
        # 内容布局
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # 顶部栏
        top_layout = QHBoxLayout()
        lbl_title = QLabel("🕒 搜索历史")
        lbl_title.setStyleSheet("color: #888; font-weight: bold; font-size: 11px; background: transparent; border: none;")
        top_layout.addWidget(lbl_title)
        
        top_layout.addStretch()
        
        btn_clear = QPushButton("清空")
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.setStyleSheet("""
            QPushButton { background: transparent; color: #666; border: none; font-size: 11px; }
            QPushButton:hover { color: #E74C3C; }
        """)
        btn_clear.clicked.connect(self._clear_all)
        top_layout.addWidget(btn_clear)
        
        layout.addLayout(top_layout)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # 强制全透明背景
        scroll.setStyleSheet("""
            QScrollArea { background-color: transparent; border: none; }
            QScrollArea > QWidget > QWidget { background-color: transparent; }
        """)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.chips_widget = QWidget()
        self.chips_widget.setStyleSheet("background-color: transparent;")
        self.flow_layout = FlowLayout(self.chips_widget, margin=0, spacing=8)
        scroll.setWidget(self.chips_widget)
        
        layout.addWidget(scroll)
        
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        
        self.refresh_ui()

    def refresh_ui(self):
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        history = self.search_edit.get_history()
        
        # 【核心修正】强制宽度与输入框一致
        target_content_width = self.search_edit.width()
        
        if not history:
            lbl_empty = QLabel("暂无历史记录")
            lbl_empty.setAlignment(Qt.AlignCenter)
            lbl_empty.setStyleSheet("color: #555; font-style: italic; margin: 20px; background: transparent; border: none;")
            self.flow_layout.addWidget(lbl_empty)
            content_height = 100
        else:
            for text in history:
                chip = HistoryChip(text)
                chip.clicked.connect(self._on_chip_clicked)
                chip.deleted.connect(self._on_chip_deleted)
                self.flow_layout.addWidget(chip)
            
            # 计算高度：内容宽度 = 容器宽度 - 内部边距(24) - 滚动条预留(6)
            effective_width = target_content_width - 30
            flow_height = self.flow_layout.heightForWidth(effective_width)
            content_height = min(400, max(120, flow_height + 50)) # 加上顶部栏高度

        # 计算窗口总尺寸：内容尺寸 + 阴影边距
        total_width = target_content_width + (self.shadow_margin * 2)
        total_height = content_height + (self.shadow_margin * 2)
        
        self.resize(total_width, total_height)

    def _on_chip_clicked(self, text):
        self.item_selected.emit(text)
        self.close()

    def _on_chip_deleted(self, text):
        self.search_edit.remove_history_entry(text)
        self.refresh_ui()

    def _clear_all(self):
        self.search_edit.clear_history()
        self.refresh_ui()

    def show_animated(self):
        self.refresh_ui()
        
        # 【核心修正】坐标对齐逻辑
        # 1. 获取输入框左下角坐标
        pos = self.search_edit.mapToGlobal(QPoint(0, self.search_edit.height()))
        
        # 2. 偏移坐标：X轴减去阴影边距，Y轴加上间距并减去阴影边距
        # 这样 Container 的左边框就会和 Input 的左边框完全对齐
        x_pos = pos.x() - self.shadow_margin
        y_pos = pos.y() + 5 - self.shadow_margin # 5px 垂直间距
        
        self.move(x_pos, y_pos)
        
        self.setWindowOpacity(0)
        self.show()
        
        self.opacity_anim.setDuration(200)
        self.opacity_anim.setStartValue(0)
        self.opacity_anim.setEndValue(1)
        self.opacity_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.opacity_anim.start()

# --- 4. 搜索框本体 ---
class SearchLineEdit(QLineEdit):
    SETTINGS_KEY = "SearchHistoryList"
    MAX_HISTORY = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("KMain_V3", "KMain_V3")
        self.popup = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._show_popup()
        super().mouseDoubleClickEvent(event)

    def _show_popup(self):
        if self.popup and self.popup.isVisible():
            self.popup.close()
            return
            
        self.popup = SearchHistoryPopup(self)
        self.popup.item_selected.connect(self._on_history_selected)
        self.popup.show_animated()

    def _on_history_selected(self, text):
        self.setText(text)
        self.returnPressed.emit()

    def add_history_entry(self, text):
        if not text or not text.strip(): return
        text = text.strip()
        history = self.get_history()
        
        if text in history:
            history.remove(text)
        history.insert(0, text)
        
        if len(history) > self.MAX_HISTORY:
            history = history[:self.MAX_HISTORY]
            
        self.settings.setValue(self.SETTINGS_KEY, history)

    def remove_history_entry(self, text):
        history = self.get_history()
        if text in history:
            history.remove(text)
            self.settings.setValue(self.SETTINGS_KEY, history)

    def clear_history(self):
        self.settings.setValue(self.SETTINGS_KEY, [])

    def get_history(self):
        val = self.settings.value(self.SETTINGS_KEY, [])
        if not isinstance(val, list): return []
        return [str(v) for v in val]
