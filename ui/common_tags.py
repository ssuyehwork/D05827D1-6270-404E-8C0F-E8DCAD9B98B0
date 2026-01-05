# -*- coding: utf-8 -*-
# ui/common_tags.py

from PyQt5.QtWidgets import (QWidget, QPushButton, QMenu, QInputDialog, 
                             QSizePolicy, QHBoxLayout)
from PyQt5.QtCore import Qt, pyqtSignal
from core.config import COLORS
from core.settings import load_setting, save_setting

class CommonTags(QWidget):
    # 修改信号：传递 (标签名, 是否选中)
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
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)
        
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def reload_tags(self):
        # 清理旧组件
        while self.layout.count():
            item = self.layout.takeAt(0)
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
            # --- 核心修改：启用 Checkable (开关模式) ---
            btn.setCheckable(True) 
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(26)
            
            # --- 样式逻辑：增加 :checked 状态 ---
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(255, 255, 255, 0.08);
                    color: #CCC;
                    border: 1px solid rgba(255, 255, 255, 0.15);
                    border-radius: 13px;
                    padding: 0px 12px;
                    font-size: 12px;
                    font-family: "Segoe UI", "Microsoft YaHei";
                }}
                /* 悬停 */
                QPushButton:hover {{
                    background-color: rgba(255, 255, 255, 0.15);
                    color: #FFF;
                    border: 1px solid rgba(255, 255, 255, 0.3);
                }}
                /* --- 选中高亮状态 (蓝色) --- */
                QPushButton:checked {{
                    background-color: {COLORS['primary']}; 
                    border: 1px solid {COLORS['primary']}; 
                    color: white;
                    font-weight: bold;
                }}
            """)
            
            # 连接 Toggle 信号
            btn.toggled.connect(lambda checked, n=name: self.tag_toggled.emit(n, checked))
            
            self.layout.addWidget(btn)
            self.tag_buttons.append(btn)

        # 管理按钮
        btn_edit = QPushButton("⚙")
        btn_edit.setToolTip("管理标签")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.setFixedSize(26, 26)
        btn_edit.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: #666;
                border: none;
                border-radius: 13px;
                font-size: 16px;
                padding-bottom: 1px;
            }}
            QPushButton:hover {{
                background-color: rgba(255,255,255,0.1);
                color: #EEE;
            }}
        """)
        btn_edit.clicked.connect(self.manager_requested.emit)
        self.layout.addWidget(btn_edit)
        
        self.refresh_requested.emit()

    def reset_selection(self):
        """重置所有按钮为未选中状态（防止下一个弹窗继承上一个的状态）"""
        for btn in self.tag_buttons:
            # 阻断信号，防止重置时触发数据库操作
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)

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