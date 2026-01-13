# -*- coding: utf-8 -*-
# ui/main_window_parts/metadata_panel.py

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
                             QLineEdit, QDialog, QPushButton, QTextEdit, 
                             QGraphicsDropShadowEffect, QApplication) # Added QApplication
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QCursor, QColor
from core.config import COLORS
from ui.utils import create_svg_icon
from ui.advanced_tag_selector import AdvancedTagSelector

# ==========================================
# 辅助组件 (从 MainWindow 移出)
# ==========================================

class ClickableLineEdit(QLineEdit):
    doubleClicked = pyqtSignal()
    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)

class InfoWidget(QWidget):
    def __init__(self, icon_name, title, subtitle, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 40, 20, 20)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignCenter)
        icon_label = QLabel()
        icon_label.setPixmap(create_svg_icon(icon_name).pixmap(64, 64))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(icon_label)
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e0e0e0; border: none; background: transparent;")
        layout.addWidget(title_label)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("font-size: 12px; color: #888; border: none; background: transparent;")
        layout.addWidget(subtitle_label)
        layout.addStretch(1)

class MetadataDisplay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: transparent;")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 5, 0, 5)
        self.layout.setSpacing(8)
        self.layout.setAlignment(Qt.AlignTop)
        self.rows = {}
        self._create_all_rows()

    def _create_all_rows(self):
        row_configs = [
            ('created', '创建于'),
            ('updated', '更新于'),
            ('category', '分类'),
            ('status', '状态'),
            ('rating', '星级'),
            ('tags', '标签')
        ]
        for key, label_text in row_configs:
            row = QWidget()
            row.setObjectName("CapsuleRow")
            row.setAttribute(Qt.WA_StyledBackground, True)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 8, 12, 8)
            row_layout.setSpacing(10)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 11px; color: #AAA; border: none; min-width: 45px; background: transparent;")
            val = QLabel()
            val.setWordWrap(True)
            val.setStyleSheet("font-size: 12px; color: #FFF; border: none; font-weight: bold; background: transparent;")
            row_layout.addWidget(lbl)
            row_layout.addWidget(val)
            row.setStyleSheet(f"QWidget {{ background-color: transparent; }} #CapsuleRow {{ background-color: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; }}")
            self.layout.addWidget(row)
            self.rows[key] = val

    def update_data(self, data, tags, category_name):
        if not data: return
        self.setUpdatesEnabled(False)
        self.rows['created'].setText(data['created_at'][:16])
        self.rows['updated'].setText(data['updated_at'][:16])
        self.rows['category'].setText(category_name if category_name else "未分类")
        states = []
        if data['is_pinned']: states.append("置顶")
        if data['is_locked']: states.append("锁定")
        if data['is_favorite']: states.append("书签")
        self.rows['status'].setText(", ".join(states) if states else "无")
        rating_str = '★' * data['rating'] + '☆' * (5 - data['rating'])
        self.rows['rating'].setText(rating_str)
        self.rows['tags'].setText(", ".join(tags) if tags else "无")
        self.setUpdatesEnabled(True)

class TitleEditorDialog(QDialog):
    def __init__(self, current_text, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(320, 180)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.container = QWidget()
        self.container.setStyleSheet(f"QWidget {{ background-color: {COLORS['bg_dark']}; border: 2px solid {COLORS['primary']}; border-radius: 8px; }}")
        inner_layout = QVBoxLayout(self.container)
        inner_layout.setContentsMargins(15, 15, 15, 15)
        title_header = QHBoxLayout()
        title_header.setSpacing(6)
        title_icon = QLabel()
        title_icon.setPixmap(create_svg_icon("action_edit.svg", COLORS['primary']).pixmap(14, 14))
        title_header.addWidget(title_icon)
        label = QLabel("编辑标题")
        label.setStyleSheet("color: #AAA; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        title_header.addWidget(label)
        title_header.addStretch()
        inner_layout.addLayout(title_header)
        self.text_edit = QTextEdit()
        self.text_edit.setText(current_text)
        self.text_edit.setPlaceholderText("请输入标题...")
        self.text_edit.setStyleSheet(f"QTextEdit {{ background-color: {COLORS['bg_mid']}; border: 1px solid #444; border-radius: 6px; color: white; font-size: 14px; padding: 8px; }} QTextEdit:focus {{ border: 1px solid {COLORS['primary']}; }}")
        inner_layout.addWidget(self.text_edit)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_save = QPushButton("保存")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet(f"QPushButton {{ background-color: {COLORS['primary']}; color: white; border: none; border-radius: 4px; padding: 6px 16px; font-weight: bold; }} QPushButton:hover {{ background-color: #357abd; }}")
        self.btn_save.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_save)
        inner_layout.addLayout(btn_layout)
        layout.addWidget(self.container)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.container.setGraphicsEffect(shadow)

    def get_text(self): return self.text_edit.toPlainText().strip()

    def show_at_cursor(self):
        pos = QCursor.pos()
        self.move(pos.x() - 300, pos.y() - 20)
        self.show()
        self.text_edit.setFocus()
        self.text_edit.selectAll()

# ==========================================
# 主面板类
# ==========================================

class MetadataPanel(QWidget):
    # 信号定义
    title_changed = pyqtSignal(int, str) # idea_id, new_title
    tag_added = pyqtSignal(list) # [tag_names] (注意这里是 tags list, 不是单个 tag)
    # Changed from tag_added = pyqtSignal(list) to tag_added = pyqtSignal(list)
    # The original was likely meant to emit [idea_id, tag_name], but
    # AdvancedTagSelector.tags_confirmed emits list of tags.
    # The receiver in MainWindow._handle_tag_add will then get a list of tags.

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.current_selected_ids = set()
        
        self.setObjectName("RightPanel")
        self.setStyleSheet(f"#RightPanel {{ background-color: {COLORS['bg_mid']}; }}")
        self.setFixedWidth(240)
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 顶部标题
        title_container = QWidget()
        title_container.setStyleSheet("background-color: transparent;")
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(6)
        icon = QLabel()
        icon.setPixmap(create_svg_icon('all_data.svg', '#4a90e2').pixmap(18, 18))
        icon.setStyleSheet("background: transparent; border: none;")
        lbl = QLabel("元数据")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #4a90e2; background: transparent; border: none;")
        title_layout.addWidget(icon)
        title_layout.addWidget(lbl)
        title_layout.addStretch()
        layout.addWidget(title_container)

        # 状态栈 (无选择 / 多选 / 单选详情)
        self.info_stack = QWidget()
        self.info_stack.setStyleSheet("background-color: transparent;")
        self.info_stack_layout = QVBoxLayout(self.info_stack)
        self.info_stack_layout.setContentsMargins(0,0,0,0)
        
        self.no_selection_widget = InfoWidget('select.svg', "未选择项目", "请选择一个项目以查看其元数据")
        self.multi_selection_widget = InfoWidget('all_data.svg', "已选择多个项目", "请仅选择一项以查看其元数据")
        self.metadata_display = MetadataDisplay()
        
        self.info_stack_layout.addWidget(self.no_selection_widget)
        self.info_stack_layout.addWidget(self.multi_selection_widget)
        self.info_stack_layout.addWidget(self.metadata_display)
        layout.addWidget(self.info_stack)

        # 标题输入框
        self.title_input = ClickableLineEdit()
        self.title_input.setPlaceholderText("标题")
        self.title_input.setAlignment(Qt.AlignLeft)
        self.title_input.setObjectName("CapsuleInput")
        self.title_input.setStyleSheet(f"""
            #CapsuleInput {{
                background-color: rgba(255, 255, 255, 0.05); 
                border: 1px solid rgba(255, 255, 255, 0.1); 
                border-radius: 10px; 
                color: #EEE; 
                font-size: 13px; 
                font-weight: bold; 
                padding: 8px 12px; 
                margin-top: 10px;
            }}
            #CapsuleInput:focus {{
                border: 1px solid {COLORS['primary']}; 
                background-color: rgba(255, 255, 255, 0.08);
            }}
        """)
        self.title_input.editingFinished.connect(self._save_title)
        self.title_input.returnPressed.connect(self.title_input.clearFocus)
        self.title_input.doubleClicked.connect(self._open_expanded_title_editor)
        layout.addWidget(self.title_input)

        layout.addStretch(1)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)
        line.setStyleSheet("background-color: #505050; border: none; max-height: 1px; margin-bottom: 5px;")
        layout.addWidget(line)

        # 标签输入框
        self.tag_input = ClickableLineEdit()
        self.tag_input.setPlaceholderText("输入标签添加... (双击更多)")
        self.tag_input.setObjectName("CapsuleTagInput")
        self.tag_input.setStyleSheet(f"""
            #CapsuleTagInput {{ 
                background-color: rgba(255, 255, 255, 0.05); 
                border: 1px solid rgba(255, 255, 255, 0.1); 
                border-radius: 10px; 
                padding: 8px 12px; 
                font-size: 12px; 
                color: #EEE; 
            }} 
            #CapsuleTagInput:focus {{ 
                border-color: {COLORS['primary']}; 
                background-color: rgba(255, 255, 255, 0.08); 
            }} 
            #CapsuleTagInput:disabled {{ 
                background-color: transparent; 
                border: 1px solid #333; 
                color: #666; 
            }}
        """)
        self.tag_input.returnPressed.connect(self._handle_tag_input)
        self.tag_input.doubleClicked.connect(self._open_tag_selector)
        layout.addWidget(self.tag_input)

    def refresh_state(self, selected_ids):
        """外部调用的主要入口，根据选中项更新面板状态"""
        self.current_selected_ids = selected_ids
        num_selected = len(selected_ids)
        
        if num_selected == 0:
            self.no_selection_widget.show()
            self.multi_selection_widget.hide()
            self.metadata_display.hide()
            self.title_input.hide()
            self.tag_input.setEnabled(False)
            self.tag_input.setPlaceholderText("请先选择一个项目")
        elif num_selected == 1:
            self.no_selection_widget.hide()
            self.multi_selection_widget.hide()
            self.metadata_display.show()
            self.title_input.show()
            self.tag_input.setEnabled(True)
            self.tag_input.setPlaceholderText("输入标签添加... (双击更多)")
            
            idea_id = list(selected_ids)[0]
            data = self.service.get_idea(idea_id)
            if data:
                self.title_input.setText(data['title'])
                self.title_input.setCursorPosition(0)
                tags = self.service.get_tags(idea_id)
                category_name = ""
                if data['category_id']:
                    all_categories = self.service.get_categories()
                    cat = next((c for c in all_categories if c['id'] == data['category_id']), None)
                    if cat: category_name = cat['name']
                self.metadata_display.update_data(data, tags, category_name)
        else: # num_selected > 1
            self.no_selection_widget.hide()
            self.multi_selection_widget.show()
            self.metadata_display.hide()
            self.title_input.hide()
            self.tag_input.setEnabled(False)
            self.tag_input.setPlaceholderText("请仅选择一项以查看元数据")

    def _save_title(self):
        if len(self.current_selected_ids) != 1: return
        new_title = self.title_input.text().strip()
        if not new_title: return
        idea_id = list(self.current_selected_ids)[0]
        self.title_changed.emit(idea_id, new_title)

    def _open_expanded_title_editor(self):
        if len(self.current_selected_ids) != 1: return
        idea_id = list(self.current_selected_ids)[0]
        data = self.service.get_idea(idea_id)
        if not data: return
        
        dialog = TitleEditorDialog(data['title'], self)
        # 确保 QDialog 有父窗口，否则 show_at_cursor 可能出现问题
        dialog.setParent(QApplication.activeWindow()) 
        if dialog.exec_():
            new_title = dialog.get_text()
            if new_title and new_title != data['title']:
                self.title_input.setText(new_title)
                self.title_input.setCursorPosition(0)
                self.title_changed.emit(idea_id, new_title)

    def _handle_tag_input(self):
        text = self.tag_input.text().strip()
        if not text: return
        if self.current_selected_ids:
            # emit tags as a list, consistent with AdvancedTagSelector's signal
            self.tag_added.emit([text])
            self.tag_input.clear()

    def _open_tag_selector(self):
        if len(self.current_selected_ids) == 0: return # AdvancedTagSelector needs a selected item context or initial tags
        
        # If multiple selected, AdvancedTagSelector should get union tags
        # If single selected, get its tags.
        # For this refactoring step, let's simplify: if multiple, show empty for now,
        # otherwise show current idea's tags. (The current implementation in main_window
        # always adds to ALL selected, so this is okay)
        
        initial_tags_list = []
        if len(self.current_selected_ids) == 1:
            idea_id = list(self.current_selected_ids)[0]
            initial_tags_list = self.service.get_tags(idea_id) # Get current tags for the single idea
        else: # multiple selected, or no single focus. For this flow, we'll start with common tags or empty
            # If AdvancedTagSelector can handle showing common tags without a specific idea, it can be passed here.
            # For simplicity, if multiple selected, we'll give it no initial tags, and it adds to all selected.
            pass

        selector = AdvancedTagSelector(self.service, idea_id=None, initial_tags=initial_tags_list) # idea_id=None for selection mode
        # 连接信号，当选择器确认时，触发 tag_added 信号 (注意这里 emit 的是 list of tags)
        selector.tags_confirmed.connect(self.tag_added.emit)
        selector.show_at_cursor()