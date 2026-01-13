# ui/dialogs.py
import sys
from PyQt5.QtWidgets import QCompleter
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QHBoxLayout,
                              QLabel, QLineEdit, QTextEdit, QComboBox, QPushButton,
                              QProgressBar, QFrame, QApplication, QMessageBox, QShortcut,
                             QSpacerItem, QSizePolicy, QSplitter, QWidget, QScrollBar,
                             QGraphicsDropShadowEffect, QCheckBox)
from PyQt5.QtGui import QKeySequence, QColor, QCursor, QTextDocument, QTextCursor, QTextListFormat, QTextCharFormat, QPixmap, QImage
from PyQt5.QtCore import Qt, QPoint, QRect, QEvent, pyqtSignal
from PyQt5.QtWidgets import QDesktopWidget
from core.config import STYLES, COLORS
from core.settings import save_setting, load_setting
from .components.rich_text_edit import RichTextEdit
from ui.utils import create_svg_icon

class BaseDialog(QDialog):
    def __init__(self, parent=None, window_title="快速笔记"):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(window_title)
        self._setup_container()
    
    def _setup_container(self):
        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(15, 15, 15, 15)
        self.content_container = QWidget()
        self.content_container.setObjectName("DialogContainer")
        self.content_container.setStyleSheet(f"""
            #DialogContainer {{
                background-color: {COLORS['bg_dark']};
                border-radius: 12px;
            }}
        """ + STYLES['dialog'])
        self.outer_layout.addWidget(self.content_container)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(6)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.content_container.setGraphicsEffect(shadow)
        return self.content_container

class EditDialog(BaseDialog):
    RESIZE_MARGIN = 10
    data_saved = pyqtSignal()

    def __init__(self, db, idea_id=None, parent=None, category_id_for_new=None):
        window_title = "编辑笔记" if idea_id else "新建笔记"
        super().__init__(parent, window_title=window_title)
        self.db = db
        self.idea_id = idea_id
        
        saved_default = load_setting('user_default_color')
        if saved_default:
            self.selected_color = saved_default
            self.is_using_saved_default = True
        else:
            self.selected_color = COLORS['orange']
            self.is_using_saved_default = False
        
        self.category_id = None 
        self.category_id_for_new = category_id_for_new 
        
        self._resize_area = None
        self._drag_pos = None
        self._resize_start_pos = None
        self._resize_start_geometry = None
        
        self.setMouseTracking(True)
        
        self._init_ui()
        if idea_id: 
            self._load_data()
        elif category_id_for_new:
             idx = self.category_combo.findData(category_id_for_new)
             if idx >= 0: self.category_combo.setCurrentIndex(idx)
            
        self.title_inp.installEventFilter(self)
        self.tags_inp.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Down:
                if obj == self.title_inp:
                    self.tags_inp.setFocus()
                    return True
                elif obj == self.tags_inp:
                    self.content_inp.setFocus()
                    return True
            elif event.key() == Qt.Key_Up:
                if obj == self.tags_inp:
                    self.title_inp.setFocus()
                    return True
        return super().eventFilter(obj, event)
        
    def _init_ui(self):
        self.resize(950, 650)
        main_layout = QVBoxLayout(self.content_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(40)
        self.title_bar.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_mid']};
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                border-bottom: 1px solid {COLORS['bg_light']};
            }}
        """)
        tb_layout = QHBoxLayout(self.title_bar)
        tb_layout.setContentsMargins(15, 0, 10, 0)
        
        title_icon = QLabel()
        title_icon.setPixmap(create_svg_icon("action_edit.svg", COLORS['primary']).pixmap(14, 14))
        tb_layout.addWidget(title_icon)
        
        self.win_title = QLabel('记录灵感' if not self.idea_id else '编辑笔记')
        self.win_title.setStyleSheet("font-weight: bold; color: #ddd; font-size: 13px; border: none; background: transparent;")
        tb_layout.addWidget(self.win_title)
        
        tb_layout.addStretch()
        
        ctrl_btn_style = "QPushButton { background: transparent; border: none; border-radius: 4px; width: 30px; height: 30px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }"
        close_btn_style = "QPushButton { background: transparent; border: none; border-radius: 4px; width: 30px; height: 30px; } QPushButton:hover { background-color: #e74c3c; }"
        
        btn_min = QPushButton()
        btn_min.setIcon(create_svg_icon("win_min.svg", "#aaa"))
        btn_min.setStyleSheet(ctrl_btn_style)
        btn_min.clicked.connect(self.showMinimized)
        
        self.btn_max = QPushButton()
        self.btn_max.setIcon(create_svg_icon("win_max.svg", "#aaa"))
        self.btn_max.setStyleSheet(ctrl_btn_style)
        self.btn_max.clicked.connect(self._toggle_maximize)
        
        btn_close = QPushButton()
        btn_close.setIcon(create_svg_icon("win_close.svg", "#aaa"))
        btn_close.setStyleSheet(close_btn_style)
        btn_close.clicked.connect(self.close) 
        
        tb_layout.addWidget(btn_min); tb_layout.addWidget(self.btn_max); tb_layout.addWidget(btn_close)
        main_layout.addWidget(self.title_bar)
        
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {COLORS['bg_mid']}; width: 2px; margin: 0 5px; }} QSplitter::handle:hover {{ background-color: {COLORS['primary']}; }}")
        
        left_container = QWidget()
        left_panel = QVBoxLayout(left_container)
        left_panel.setContentsMargins(5, 5, 5, 5)
        left_panel.setSpacing(12)
        
        left_panel.addWidget(QLabel('分区'))
        self.category_combo = QComboBox()
        self.category_combo.setFixedHeight(40)
        self.category_combo.addItem("未分类", None)
        cats = self.db.get_categories()
        for c in cats: self.category_combo.addItem(f"{c[1]}", c[0])
        left_panel.addWidget(self.category_combo)

        left_panel.addWidget(QLabel('标题'))
        self.title_inp = QLineEdit()
        self.title_inp.setPlaceholderText("请输入灵感标题...")
        self.title_inp.setFixedHeight(40)
        left_panel.addWidget(self.title_inp)
        
        left_panel.addWidget(QLabel('标签 (智能补全)'))
        self.tags_inp = QLineEdit()
        self.tags_inp.setPlaceholderText("使用逗号分隔，如: 工作, 待办")
        self.tags_inp.setFixedHeight(40)
        self._init_completer()
        left_panel.addWidget(self.tags_inp)
        
        left_panel.addSpacing(10)
        left_panel.addWidget(QLabel('标记颜色'))
        color_layout = QGridLayout()
        color_layout.setSpacing(10)
        
        self.color_btns = []
        colors = [COLORS['orange'], COLORS['default_note'], COLORS['primary'], COLORS['success'], COLORS['danger'], COLORS['info']]
        for i, c in enumerate(colors):
            btn = QPushButton()
            btn.setFixedSize(34, 34)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"QPushButton {{ background-color: {c}; border-radius: 17px; border: 2px solid transparent; }}")
            btn.clicked.connect(lambda _, x=c: self._set_color(x))
            self.color_btns.append(btn)
            color_layout.addWidget(btn, i // 3, i % 3)
        left_panel.addLayout(color_layout)
        
        self.chk_set_default = QCheckBox("设为默认颜色")
        self.chk_set_default.setStyleSheet(f"QCheckBox {{ color: {COLORS['text_sub']}; font-size: 12px; margin-top: 5px; }} QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid #555; border-radius: 3px; background: transparent; }} QCheckBox::indicator:checked {{ background-color: {COLORS['primary']}; border-color: {COLORS['primary']}; }}")
        if self.is_using_saved_default: self.chk_set_default.setChecked(True)
        left_panel.addWidget(self.chk_set_default)
        
        left_panel.addStretch()
        self.save_btn = QPushButton('  保存 (Ctrl+S)')
        self.save_btn.setIcon(create_svg_icon("action_save.svg", "white"))
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setFixedHeight(50)
        self.save_btn.setStyleSheet(STYLES['btn_primary'])
        self.save_btn.clicked.connect(self._save_data)
        left_panel.addWidget(self.save_btn)
        
        right_container = QWidget()
        right_panel = QVBoxLayout(right_container)
        right_panel.setContentsMargins(5, 5, 5, 5)
        right_panel.setSpacing(10)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel('详细内容'))
        
        btn_style = "QPushButton { background: transparent; border: 1px solid #444; border-radius: 4px; margin-left: 2px; } QPushButton:hover { background-color: #444; }"
        
        def _create_tool_btn(text, tooltip, callback):
            btn = QPushButton(text)
            btn.setFixedSize(28, 28)
            btn.setToolTip(tooltip)
            btn.setStyleSheet(btn_style)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(callback)
            header_layout.addWidget(btn)
            return btn

        header_layout.addSpacing(10)
        # 撤销重做
        u = _create_tool_btn("", "撤销 (Ctrl+Z)", lambda: self.content_inp.undo()); u.setIcon(create_svg_icon("edit_undo.svg", '#ccc'))
        r = _create_tool_btn("", "重做 (Ctrl+Y)", lambda: self.content_inp.redo()); r.setIcon(create_svg_icon("edit_redo.svg", '#ccc'))
        header_layout.addSpacing(5)
        # 列表
        l1 = _create_tool_btn("", "无序列表", lambda: self.content_inp.toggle_list(QTextListFormat.ListDisc)); l1.setIcon(create_svg_icon("edit_list_ul.svg", '#ccc'))
        l2 = _create_tool_btn("", "有序列表", lambda: self.content_inp.toggle_list(QTextListFormat.ListDecimal)); l2.setIcon(create_svg_icon("edit_list_ol.svg", '#ccc'))
        
        # === 新增功能按钮 ===
        header_layout.addSpacing(5)
        # 待办事项
        btn_todo = QPushButton("Todo")
        btn_todo.setFixedSize(28, 28)
        btn_todo.setToolTip("插入待办事项")
        btn_todo.setStyleSheet(btn_style)
        btn_todo.clicked.connect(lambda: self.content_inp.insert_todo())
        header_layout.addWidget(btn_todo)
        
        # Markdown 预览
        btn_preview = QPushButton("Pre")
        btn_preview.setFixedSize(28, 28)
        btn_preview.setToolTip("切换 Markdown 预览/编辑")
        btn_preview.setStyleSheet(btn_style)
        btn_preview.clicked.connect(lambda: self.content_inp.toggle_markdown_preview())
        header_layout.addWidget(btn_preview)

        c = _create_tool_btn("", "清除格式", lambda: self.content_inp.setCurrentCharFormat(QTextCharFormat())); c.setIcon(create_svg_icon("edit_clear.svg", '#ccc'))

        header_layout.addStretch()
        
        highlight_colors = [('#c0392b', None), ('#d35400', None), ('#f1c40f', None), ('#27ae60', None), ('#2980b9', None), ('#8e44ad', None), (None, 'edit_clear.svg')]
        for color, icon in highlight_colors:
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.PointingHandCursor)
            if icon:
                btn.setIcon(create_svg_icon(icon, '#ccc'))
                btn.setToolTip("清除高亮")
                btn.setStyleSheet(btn_style)
            else:
                btn.setToolTip("高亮文字")
                btn.setStyleSheet(f"QPushButton {{ background-color: {color}; border: 1px solid #444; border-radius: 12px; margin-left: 2px; }} QPushButton:hover {{ border-color: white; }}")
            btn.clicked.connect(lambda _, c=color: self.content_inp.highlight_selection(c))
            header_layout.addWidget(btn)
            
        right_panel.addLayout(header_layout)

        self.search_bar = QWidget()
        self.search_bar.setVisible(False)
        self.search_bar.setStyleSheet(f"background-color: {COLORS['bg_mid']}; border-radius: 6px; padding: 2px;")
        sb_layout = QHBoxLayout(self.search_bar)
        sb_layout.setContentsMargins(5, 2, 5, 2)
        sb_layout.setSpacing(5)
        self.search_inp = QLineEdit()
        self.search_inp.setPlaceholderText("查找内容...")
        self.search_inp.setStyleSheet("border: none; background: transparent; color: #fff;")
        self.search_inp.returnPressed.connect(self._find_next)
        btn_prev = QPushButton(); btn_prev.setIcon(create_svg_icon("nav_prev.svg", "#ccc")); btn_prev.setFixedSize(24, 24); btn_prev.clicked.connect(self._find_prev); btn_prev.setStyleSheet("background: transparent; border: none;")
        btn_next = QPushButton(); btn_next.setIcon(create_svg_icon("nav_next.svg", "#ccc")); btn_next.setFixedSize(24, 24); btn_next.clicked.connect(self._find_next); btn_next.setStyleSheet("background: transparent; border: none;")
        btn_cls = QPushButton(); btn_cls.setIcon(create_svg_icon("win_close.svg", "#ccc")); btn_cls.setFixedSize(24, 24); btn_cls.clicked.connect(lambda: self.search_bar.hide()); btn_cls.setStyleSheet("background: transparent; border: none;")
        sb_layout.addWidget(self.search_inp); sb_layout.addWidget(btn_prev); sb_layout.addWidget(btn_next); sb_layout.addWidget(btn_cls)
        right_panel.addWidget(self.search_bar)

        self.content_inp = RichTextEdit()
        self.content_inp.setPlaceholderText("在这里记录详细内容（支持 Markdown 和粘贴图片）...")
        shortcut_search = QShortcut(QKeySequence("Ctrl+F"), self.content_inp)
        shortcut_search.activated.connect(self._toggle_search_bar)
        right_panel.addWidget(self.content_inp)
        
        self.splitter.addWidget(left_container); self.splitter.addWidget(right_container); self.splitter.setSizes([300, 650]); self.splitter.setStretchFactor(0, 0); self.splitter.setStretchFactor(1, 1)
        content_layout.addWidget(self.splitter)
        main_layout.addWidget(content_widget)
        
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_data)
        QShortcut(QKeySequence("Escape"), self, self.close)
        QShortcut(QKeySequence("Ctrl+W"), self, self.close)
        self._set_color(self.selected_color)

    def _get_resize_area(self, pos):
        x, y = pos.x(), pos.y(); w, h = self.width(), self.height(); m = self.RESIZE_MARGIN
        areas = []
        if x < m: areas.append('left')
        elif x > w - m: areas.append('right')
        if y < m: areas.append('top')
        elif y > h - m: areas.append('bottom')
        return areas

    def _set_cursor_for_resize(self, areas):
        if not areas: self.setCursor(Qt.ArrowCursor); return
        if 'left' in areas and 'top' in areas: self.setCursor(Qt.SizeFDiagCursor)
        elif 'right' in areas and 'bottom' in areas: self.setCursor(Qt.SizeFDiagCursor)
        elif 'left' in areas and 'bottom' in areas: self.setCursor(Qt.SizeBDiagCursor)
        elif 'right' in areas and 'top' in areas: self.setCursor(Qt.SizeBDiagCursor)
        elif 'left' in areas or 'right' in areas: self.setCursor(Qt.SizeHorCursor)
        elif 'top' in areas or 'bottom' in areas: self.setCursor(Qt.SizeVerCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            areas = self._get_resize_area(e.pos())
            if areas:
                self._resize_area = areas; self._resize_start_pos = e.globalPos(); self._resize_start_geometry = self.geometry(); self._drag_pos = None
            elif e.pos().y() < 60: 
                self._drag_pos = e.globalPos() - self.frameGeometry().topLeft(); self._resize_area = None
            e.accept()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.NoButton:
            self._set_cursor_for_resize(self._get_resize_area(e.pos())); return
        if e.buttons() == Qt.LeftButton:
            if self._resize_area:
                delta = e.globalPos() - self._resize_start_pos; rect = self._resize_start_geometry; min_w, min_h = 600, 400; new_rect = rect.adjusted(0,0,0,0)
                if 'left' in self._resize_area:
                    if rect.right() - (rect.left() + delta.x()) >= min_w: new_rect.setLeft(rect.left() + delta.x())
                if 'right' in self._resize_area:
                    if (rect.width() + delta.x()) >= min_w: new_rect.setWidth(rect.width() + delta.x())
                if 'top' in self._resize_area:
                    if rect.bottom() - (rect.top() + delta.y()) >= min_h: new_rect.setTop(rect.top() + delta.y())
                if 'bottom' in self._resize_area:
                    if (rect.height() + delta.y()) >= min_h: new_rect.setHeight(rect.height() + delta.y())
                self.setGeometry(new_rect)
            elif self._drag_pos: self.move(e.globalPos() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None; self._resize_area = None; self.setCursor(Qt.ArrowCursor)

    def mouseDoubleClickEvent(self, e):
        if e.pos().y() < 60: self._toggle_maximize()

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal(); self.btn_max.setIcon(create_svg_icon("win_max.svg", "#aaa")); self.outer_layout.setContentsMargins(15, 15, 15, 15)
            self.content_container.setStyleSheet(f"#DialogContainer {{ background-color: {COLORS['bg_dark']}; border-radius: 12px; }}" + STYLES['dialog'])
            self.title_bar.setStyleSheet(f"QWidget {{ background-color: {COLORS['bg_mid']}; border-top-left-radius: 12px; border-top-right-radius: 12px; border-bottom: 1px solid {COLORS['bg_light']}; }}")
        else:
            self.showMaximized(); self.btn_max.setIcon(create_svg_icon("win_restore.svg", "#aaa")); self.outer_layout.setContentsMargins(0, 0, 0, 0)
            self.content_container.setStyleSheet(f"#DialogContainer {{ background-color: {COLORS['bg_dark']}; border-radius: 0px; }}" + STYLES['dialog'])
            self.title_bar.setStyleSheet(f"QWidget {{ background-color: {COLORS['bg_mid']}; border-radius: 0px; border-bottom: 1px solid {COLORS['bg_light']}; }}")

    def _set_color(self, color):
        self.selected_color = color
        saved_default = load_setting('user_default_color')
        self.chk_set_default.setChecked(saved_default == color)
        for btn in self.color_btns:
            style = btn.styleSheet()
            if color in style: new_style = f"background-color: {color}; border-radius: 17px; border: 3px solid white;"
            else: bg = style.split('background-color:')[1].split(';')[0].strip(); new_style = f"background-color: {bg}; border-radius: 17px; border: 2px solid transparent;"
            btn.setStyleSheet(f"QPushButton {{ {new_style} }}")

    def _init_completer(self):
        all_tags = self.db.get_all_tags()
        self.completer = QCompleter(all_tags, self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.setWidget(self.tags_inp)
        self.completer.activated.connect(self._on_completion_activated)
        self.tags_inp.textEdited.connect(self._update_completion_prefix)

    def _update_completion_prefix(self, text):
        cursor_pos = self.tags_inp.cursorPosition()
        text_before = text[:cursor_pos]
        last_comma = text_before.rfind(',')
        prefix = text_before[last_comma+1:].strip() if last_comma != -1 else text_before.strip()
        if prefix:
            self.completer.setCompletionPrefix(prefix)
            if self.completer.completionCount() > 0:
                cr = self.tags_inp.cursorRect(); cr.setWidth(self.completer.popup().sizeHintForColumn(0) + self.completer.popup().verticalScrollBar().sizeHint().width())
                self.completer.complete(cr)
            else: self.completer.popup().hide()
        else: self.completer.popup().hide()

    def _on_completion_activated(self, text):
        current_text = self.tags_inp.text()
        cursor_pos = self.tags_inp.cursorPosition()
        text_before = current_text[:cursor_pos]
        last_comma = text_before.rfind(',')
        start_replace = last_comma + 1 if last_comma != -1 else 0
        prefix = current_text[:start_replace]
        suffix = current_text[cursor_pos:]
        new_text = prefix + text + ", " + suffix
        self.tags_inp.setText(new_text)
        self.tags_inp.setCursorPosition(len(prefix) + len(text) + 2)

    def _toggle_search_bar(self):
        self.search_bar.setVisible(not self.search_bar.isVisible())
        if self.search_bar.isVisible():
            self.search_inp.setFocus()
            sel = self.content_inp.textCursor().selectedText()
            if sel: self.search_inp.setText(sel)
        else: self.content_inp.setFocus()

    def _find_next(self):
        text = self.search_inp.text()
        if not text: return
        if not self.content_inp.find(text):
            curr = self.content_inp.textCursor(); self.content_inp.moveCursor(QTextCursor.Start)
            if not self.content_inp.find(text): self.content_inp.setTextCursor(curr)

    def _find_prev(self):
        text = self.search_inp.text()
        if not text: return
        if not self.content_inp.find(text, QTextDocument.FindBackward):
            curr = self.content_inp.textCursor(); self.content_inp.moveCursor(QTextCursor.End)
            if not self.content_inp.find(text, QTextDocument.FindBackward): self.content_inp.setTextCursor(curr)

    def _load_data(self):
        d = self.db.get_idea(self.idea_id, include_blob=True)
        if d:
            self.title_inp.setText(d[1])
            item_type = d[10] if len(d) > 10 else 'text'
            if item_type != 'image': self.content_inp.setText(d[2])
            else: self.content_inp.clear()
            self._set_color(d[3])
            self.category_id = d[8]
            if self.category_id is not None:
                idx = self.category_combo.findData(self.category_id)
                if idx >= 0: self.category_combo.setCurrentIndex(idx)
            data_blob = d[11] if len(d) > 11 else None
            if item_type == 'image' and data_blob: self.content_inp.set_image_data(data_blob)
            self.tags_inp.setText(','.join(self.db.get_tags(self.idea_id)))

    def _save_data(self):
        title = self.title_inp.text().strip()
        if not title: self.title_inp.setPlaceholderText("标题不能为空!"); self.title_inp.setFocus(); return
        tags = [t.strip() for t in self.tags_inp.text().split(',') if t.strip()]
        
        # 确保保存前退出 Markdown 预览模式，获取最新的纯文本源码
        if hasattr(self.content_inp, 'is_markdown_preview') and self.content_inp.is_markdown_preview:
            self.content_inp.toggle_markdown_preview()
            
        content = self.content_inp.toPlainText()
        color = self.selected_color
        if self.chk_set_default.isChecked(): save_setting('user_default_color', color)
        item_type = 'text'
        data_blob = self.content_inp.get_image_data()
        if data_blob: item_type = 'image'
        cat_id = self.category_combo.currentData()
        if self.idea_id: self.db.update_idea(self.idea_id, title, content, color, tags, cat_id, item_type, data_blob)
        else: self.db.add_idea(title, content, color, tags, cat_id, item_type, data_blob)
        self.data_saved.emit()
        self.accept()

# === 看板窗口 ===
class StatsDialog(BaseDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle('📊 数据看板')
        self.resize(550, 450)
        layout = QVBoxLayout(self.content_container)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        stats_header = QHBoxLayout()
        stats_header.setSpacing(8)
        header_icon = QLabel()
        header_icon.setPixmap(create_svg_icon("display.svg", COLORS['primary']).pixmap(20, 20))
        stats_header.addWidget(header_icon)
        stats_title = QLabel("数据看板")
        stats_title.setStyleSheet(f"color: {COLORS['primary']}; font-size: 16px; font-weight: bold;")
        stats_header.addWidget(stats_title)
        stats_header.addStretch()
        layout.addLayout(stats_header)

        counts = db.get_counts()
        grid = QGridLayout(); grid.setSpacing(15)
        grid.addWidget(self._box("总灵感", counts['all'], COLORS['primary']), 0, 0)
        grid.addWidget(self._box("今日新增", counts['today'], COLORS['success']), 0, 1)
        grid.addWidget(self._box("我的收藏", counts['favorite'], COLORS['warning']), 1, 0)
        grid.addWidget(self._box("待整理", counts['untagged'], COLORS['danger']), 1, 1)
        layout.addLayout(grid)
        layout.addSpacing(10); layout.addWidget(QLabel("热门标签 Top 5"))
        stats = db.get_top_tags()
        if not stats: layout.addWidget(QLabel("暂无标签数据", styleSheet="color:#666; font-style:italic; font-weight:normal;"))
        else:
            max_val = stats[0][1]
            for name, cnt in stats:
                h = QHBoxLayout()
                lbl = QLabel(f"#{name}"); lbl.setFixedWidth(80); lbl.setStyleSheet("color:#eee; font-weight:bold; margin:0;")
                h.addWidget(lbl)
                p = QProgressBar(); p.setMaximum(max_val); p.setValue(cnt); p.setFixedHeight(18); p.setFormat(f" {cnt}")
                p.setStyleSheet(f"QProgressBar {{ background-color: {COLORS['bg_mid']}; border: none; border-radius: 9px; color: white; text-align: center; }} QProgressBar::chunk {{ background-color: {COLORS['primary']}; border-radius: 9px; }}")
                h.addWidget(p); layout.addLayout(h)
        layout.addStretch()
        close_btn = QPushButton("关闭"); close_btn.setFixedHeight(40); close_btn.setStyleSheet(f"background-color:{COLORS['bg_mid']}; border:1px solid #444; color:#ccc; border-radius:5px;"); close_btn.clicked.connect(self.accept); layout.addWidget(close_btn)

    def _box(self, t, v, c):
        f = QFrame(); f.setStyleSheet(f"QFrame {{ background-color: {c}15; border: 1px solid {c}40; border-radius: 10px; }}")
        vl = QVBoxLayout(f); vl.setContentsMargins(15, 15, 15, 15)
        lbl_title = QLabel(t); lbl_title.setStyleSheet(f"color:{c}; font-size:13px; font-weight:bold; border:none; margin:0;")
        lbl_val = QLabel(str(v)); lbl_val.setStyleSheet(f"color:{c}; font-size:28px; font-weight:bold; border:none; margin-top:5px;")
        vl.addWidget(lbl_title); vl.addWidget(lbl_val)
        return f

# === 提取窗口 ===
class ExtractDialog(BaseDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle('📋 提取内容')
        self.resize(700, 600)
        layout = QVBoxLayout(self.content_container)
        layout.setContentsMargins(20, 20, 20, 20)
        
        extract_header = QHBoxLayout()
        extract_header.setSpacing(8)
        header_icon = QLabel()
        header_icon.setPixmap(create_svg_icon("action_export.svg", COLORS['primary']).pixmap(20, 20))
        extract_header.addWidget(header_icon)
        extract_title = QLabel("提取内容")
        extract_title.setStyleSheet(f"color: {COLORS['primary']}; font-size: 16px; font-weight: bold;")
        extract_header.addWidget(extract_title)
        extract_header.addStretch()
        layout.addLayout(extract_header)

        self.txt = QTextEdit(); self.txt.setReadOnly(True); self.txt.setPlaceholderText("暂无数据..."); layout.addWidget(self.txt)
        data = db.get_ideas('', 'all', None)
        text = '\n' + '-'*60 + '\n'; text += '\n'.join([f"【{d[1]}】\n{d[2]}\n" + '-'*60 for d in data])
        self.txt.setText(text)
        layout.addSpacing(10)
        btn = QPushButton('  复制全部到剪贴板'); btn.setIcon(create_svg_icon("action_export.svg", "white")); btn.setFixedHeight(45); btn.setStyleSheet(STYLES['btn_primary'])
        btn.clicked.connect(lambda: (QApplication.clipboard().setText(text), QMessageBox.information(self,'成功','内容已复制'))); layout.addWidget(btn)

# === 预览窗口 ===
class PreviewDialog(QDialog):
    def __init__(self, item_type, data, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._init_ui(item_type, data)
        QShortcut(QKeySequence(Qt.Key_Escape), self, self.close)
        QShortcut(QKeySequence(Qt.Key_Space), self, self.close)

    def _init_ui(self, item_type, data):
        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(0, 0, 0, 0)
        container = QWidget(); container.setStyleSheet(f"QWidget {{ background-color: {COLORS['bg_dark']}; border: 2px solid {COLORS['bg_mid']}; border-radius: 12px; }}")
        container_layout = QVBoxLayout(container); main_layout.addWidget(container)
        if item_type == 'text': self._setup_text_preview(container_layout, data)
        elif item_type == 'image': self._setup_image_preview(container_layout, data)

    def _setup_text_preview(self, layout, text_data):
        self.resize(600, 500)
        text_edit = QTextEdit(); text_edit.setReadOnly(True); text_edit.setText(text_data)
        text_edit.setStyleSheet("QTextEdit { background-color: transparent; border: none; padding: 15px; color: #ddd; font-size: 14px; }")
        layout.addWidget(text_edit)

    def _setup_image_preview(self, layout, image_data):
        pixmap = QPixmap(); pixmap.loadFromData(image_data)
        if pixmap.isNull():
            label = QLabel("无法加载图片"); label.setAlignment(Qt.AlignCenter); label.setStyleSheet("color: #E81123; font-size: 16px;")
            layout.addWidget(label); self.resize(300, 200); return
        label = QLabel(); label.setAlignment(Qt.AlignCenter); layout.addWidget(label)
        screen_geo = QDesktopWidget().availableGeometry(self)
        max_width = screen_geo.width() * 0.8; max_height = screen_geo.height() * 0.8
        scaled_pixmap = pixmap.scaled(int(max_width), int(max_height), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(scaled_pixmap)
        self.resize(scaled_pixmap.width() + 20, scaled_pixmap.height() + 20)

    def mousePressEvent(self, event): self.close()