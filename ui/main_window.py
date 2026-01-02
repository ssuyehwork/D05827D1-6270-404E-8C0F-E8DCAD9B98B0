# -*- coding: utf-8 -*-
# ui/main_window.py
import sys
import math
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QLineEdit,
                               QPushButton, QLabel, QScrollArea, QShortcut, QMessageBox,
                               QApplication, QToolTip, QMenu, QFrame, QTextEdit, QDialog,
                               QGraphicsDropShadowEffect, QLayout, QSizePolicy, QInputDialog)
from PyQt5.QtCore import Qt, QTimer, QPoint, pyqtSignal, QRect, QSize
from PyQt5.QtGui import QKeySequence, QCursor, QColor, QIntValidator
from core.config import STYLES, COLORS
from core.settings import load_setting, save_setting
from data.db_manager import DatabaseManager
from services.backup_service import BackupService
from ui.sidebar import Sidebar
from ui.cards import IdeaCard
from ui.dialogs import EditDialog
from ui.ball import FloatingBall
from ui.advanced_tag_selector import AdvancedTagSelector
from ui.components.search_line_edit import SearchLineEdit
from services.preview_service import PreviewService

# --- 辅助类：流式布局 ---
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

class ContentContainer(QWidget):
    cleared = pyqtSignal()

    def mousePressEvent(self, e):
        if self.childAt(e.pos()) is None:
            self.cleared.emit()
        super().mousePressEvent(e)

# 可双击的输入框
class ClickableLineEdit(QLineEdit):
    doubleClicked = pyqtSignal()
    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)

class MainWindow(QWidget):
    closing = pyqtSignal()
    RESIZE_MARGIN = 8

    def __init__(self):
        super().__init__()
        QApplication.setQuitOnLastWindowClosed(False)
        self.db = DatabaseManager()
        self.preview_service = PreviewService(self.db, self)
        
        self.curr_filter = ('all', None)
        self.selected_ids = set()
        self._drag_pos = None
        self.current_tag_filter = None
        self.last_clicked_id = None 
        self.card_ordered_ids = []  
        self._resize_area = None
        self._resize_start_pos = None
        self._resize_start_geometry = None
        
        # 分页状态
        self.current_page = 1
        self.page_size = 20
        self.total_pages = 1
        
        self.open_dialogs = [] # 存储打开的窗口
        
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.Window | 
            Qt.WindowSystemMenuHint | 
            Qt.WindowMinimizeButtonHint | 
            Qt.WindowMaximizeButtonHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        
        self._setup_ui()
        self._load_data()
    def _setup_ui(self):
        self.setWindowTitle('数据管理')
        # self.resize(1300, 700) # Replaced by restore
        self._restore_window_state()
        
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        
        self.container = QWidget()
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet(STYLES['main_window'])
        root_layout.addWidget(self.container)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 100))
        self.container.setGraphicsEffect(shadow)
        
        outer_layout = QVBoxLayout(self.container)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        
        titlebar = self._create_titlebar()
        outer_layout.addWidget(titlebar)
        
        main_content = QWidget()
        main_layout = QHBoxLayout(main_content)
        main_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal)
        
        self.sidebar = Sidebar(self.db)
        self.sidebar.filter_changed.connect(self._set_filter)
        self.sidebar.data_changed.connect(self._load_data)
        self.sidebar.new_data_requested.connect(self._on_new_data_in_category_requested)
        splitter.addWidget(self.sidebar)
        
        middle_panel = self._create_middle_panel()
        splitter.addWidget(middle_panel)
        
        self.tag_panel = self._create_tag_panel()
        splitter.addWidget(self.tag_panel)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 1)
        
        main_layout.addWidget(splitter)
        outer_layout.addWidget(main_content)
        
        QShortcut(QKeySequence("Ctrl+T"), self, self._handle_extract_key)
        QShortcut(QKeySequence("Ctrl+N"), self, self.new_idea)
        QShortcut(QKeySequence("Ctrl+W"), self, self.close)
        QShortcut(QKeySequence("Ctrl+A"), self, self._select_all)
        QShortcut(QKeySequence("Ctrl+F"), self, self.search.setFocus)
        QShortcut(QKeySequence("Ctrl+E"), self, self._do_fav)
        QShortcut(QKeySequence("Ctrl+B"), self, self._do_edit)
        QShortcut(QKeySequence("Ctrl+P"), self, self._do_pin)
        QShortcut(QKeySequence("Delete"), self, self._handle_del_key)
        QShortcut(QKeySequence("Escape"), self, self._clear_tag_filter)
        
        self.space_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.space_shortcut.setContext(Qt.WindowShortcut)
        self.space_shortcut.activated.connect(lambda: self.preview_service.toggle_preview(self.selected_ids))

    def _select_all(self):
        if not self.cards: return
        if len(self.selected_ids) == len(self.cards):
            self.selected_ids.clear()
        else:
            self.selected_ids = set(self.cards.keys())
        self._update_all_card_selections()
        self._update_ui_state()

    def _clear_all_selections(self):
        if not self.selected_ids: return
        self.selected_ids.clear()
        self.last_clicked_id = None
        self._update_all_card_selections()
        self._update_ui_state()

    def _create_titlebar(self):
        titlebar = QWidget()
        titlebar.setFixedHeight(40)
        titlebar.setStyleSheet(f"QWidget {{ background-color: {COLORS['bg_mid']}; border-bottom: 1px solid {COLORS['bg_light']}; border-top-left-radius: 8px; border-top-right-radius: 8px; }}")
        
        layout = QHBoxLayout(titlebar)
        layout.setContentsMargins(15, 0, 10, 0)
        layout.setSpacing(6)
        
        title = QLabel('💡 快速笔记')
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #4a90e2;")
        layout.addWidget(title)
        
        self.search = SearchLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText('🔍 搜索灵感 (双击查看历史)')
        self.search.setFixedWidth(280)
        self.search.setFixedHeight(28)
        self.search.setStyleSheet(STYLES['input'] + """
            QLineEdit { border-radius: 14px; padding-right: 25px; }
            QLineEdit::clear-button { image: url(assets/clear.png); subcontrol-position: right; margin-right: 5px; }
        """)
        self.search.textChanged.connect(lambda: self._set_page(1))
        self.search.returnPressed.connect(self._add_search_to_history)
        layout.addWidget(self.search)
        
        layout.addSpacing(10)
        
        # --- 分页控件区域 ---
        page_btn_style = """
            QPushButton { background-color: transparent; border: 1px solid #444; color: #aaa; border-radius: 4px; font-size: 11px; padding: 2px 8px; min-width: 20px; }
            QPushButton:hover { background-color: #333; color: white; border-color: #666; }
            QPushButton:disabled { color: #444; border-color: #333; }
        """
        
        self.btn_first = QPushButton("<<")
        self.btn_first.setStyleSheet(page_btn_style)
        self.btn_first.setToolTip("首页")
        self.btn_first.clicked.connect(lambda: self._set_page(1))
        
        self.btn_prev = QPushButton("<")
        self.btn_prev.setStyleSheet(page_btn_style)
        self.btn_prev.setToolTip("上一页")
        self.btn_prev.clicked.connect(lambda: self._set_page(self.current_page - 1))
        
        self.page_input = QLineEdit()
        self.page_input.setFixedWidth(40)
        self.page_input.setAlignment(Qt.AlignCenter)
        self.page_input.setValidator(QIntValidator(1, 9999))
        self.page_input.setStyleSheet("background-color: #2D2D2D; border: 1px solid #444; color: #DDD; border-radius: 4px; padding: 2px;")
        self.page_input.returnPressed.connect(self._jump_to_page)
        
        self.total_page_label = QLabel("/ 1")
        self.total_page_label.setStyleSheet("color: #888; font-size: 12px; margin-left: 2px; margin-right: 5px;")
        
        self.btn_next = QPushButton(">")
        self.btn_next.setStyleSheet(page_btn_style)
        self.btn_next.setToolTip("下一页")
        self.btn_next.clicked.connect(lambda: self._set_page(self.current_page + 1))
        
        self.btn_last = QPushButton(">>")
        self.btn_last.setStyleSheet(page_btn_style)
        self.btn_last.setToolTip("末页")
        self.btn_last.clicked.connect(lambda: self._set_page(self.total_pages))
        
        layout.addWidget(self.btn_first)
        layout.addWidget(self.btn_prev)
        layout.addWidget(self.page_input)
        layout.addWidget(self.total_page_label)
        layout.addWidget(self.btn_next)
        layout.addWidget(self.btn_last)
        
        layout.addStretch()
        
        ctrl_btn_style = f"QPushButton {{ background-color: transparent; border: none; color: #aaa; border-radius: 6px; font-size: 16px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; }} QPushButton:hover {{ background-color: rgba(255,255,255,0.1); color: white; }}"
        
        extract_btn = QPushButton('📤')
        extract_btn.setToolTip('批量提取全部')
        extract_btn.setStyleSheet(f"QPushButton {{ background-color: {COLORS['primary']}; border: none; color: white; border-radius: 6px; font-size: 18px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; }} QPushButton:hover {{ background-color: #357abd; }}")
        # 确保这里调用了 self._extract_all
        extract_btn.clicked.connect(self._extract_all)
        layout.addWidget(extract_btn)
        
        new_btn = QPushButton('➕')
        new_btn.setToolTip('新建灵感 (Ctrl+N)')
        new_btn.setStyleSheet(f"QPushButton {{ background-color: {COLORS['primary']}; border: none; color: white; border-radius: 6px; font-size: 18px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; }} QPushButton:hover {{ background-color: #357abd; }}")
        new_btn.clicked.connect(self.new_idea)
        layout.addWidget(new_btn)
        layout.addSpacing(4)
        
        min_btn = QPushButton('─')
        min_btn.setStyleSheet(ctrl_btn_style)
        min_btn.clicked.connect(self.showMinimized)
        layout.addWidget(min_btn)
        
        self.max_btn = QPushButton('□')
        self.max_btn.setStyleSheet(ctrl_btn_style)
        self.max_btn.clicked.connect(self._toggle_maximize)
        layout.addWidget(self.max_btn)
        
        close_btn = QPushButton('✕')
        close_btn.setStyleSheet(ctrl_btn_style + "QPushButton:hover { background-color: #e74c3c; color: white; }")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        return titlebar

    # --- 分页逻辑 ---
    def _set_page(self, page_num):
        if page_num < 1: page_num = 1
        self.current_page = page_num
        self._load_data()

    def _jump_to_page(self):
        text = self.page_input.text().strip()
        if text.isdigit():
            page = int(text)
            self._set_page(page)
        else:
            self.page_input.setText(str(self.current_page))

    def _update_pagination_ui(self):
        self.page_input.setText(str(self.current_page))
        self.total_page_label.setText(f"/ {self.total_pages}")
        
        is_first = (self.current_page <= 1)
        is_last = (self.current_page >= self.total_pages)
        
        self.btn_first.setDisabled(is_first)
        self.btn_prev.setDisabled(is_first)
        self.btn_next.setDisabled(is_last)
        self.btn_last.setDisabled(is_last)

    def _create_middle_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        act_bar = QHBoxLayout()
        act_bar.setSpacing(4)
        act_bar.setContentsMargins(20, 10, 20, 10)
        
        self.header_label = QLabel('全部数据')
        self.header_label.setStyleSheet("font-size:18px;font-weight:bold;")
        act_bar.addWidget(self.header_label)
        
        self.tag_filter_label = QLabel()
        self.tag_filter_label.setStyleSheet(f"background-color: {COLORS['primary']}; color: white; border-radius: 10px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
        self.tag_filter_label.hide()
        act_bar.addWidget(self.tag_filter_label)
        act_bar.addStretch()
        
        self.btns = {}
        for k, i, f in [('pin','📌',self._do_pin), ('fav','⭐',self._do_fav), ('edit','✏️',self._do_edit),
                        ('del','🗑️',self._do_del), ('rest','♻️',self._do_restore), ('dest','🗑️',self._do_destroy)]:
            b = QPushButton(i)
            b.setStyleSheet(STYLES['btn_icon'])
            b.clicked.connect(f)
            b.setEnabled(False)
            act_bar.addWidget(b)
            self.btns[k] = b
        layout.addLayout(act_bar)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none")
        self.list_container = ContentContainer()
        self.list_container.cleared.connect(self._clear_all_selections)
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setAlignment(Qt.AlignTop)
        self.list_layout.setSpacing(10)
        self.list_layout.setContentsMargins(20, 5, 20, 15)
        scroll.setWidget(self.list_container)
        layout.addWidget(scroll)
        
        return panel

    def _create_tag_panel(self):
        panel = QWidget()
        panel.setObjectName("RightPanel")
        panel.setStyleSheet(f"#RightPanel {{ background-color: {COLORS['bg_mid']}; }}")
        panel.setFixedWidth(220)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 1. 标题区
        header = QHBoxLayout()
        self.tag_panel_title = QLabel('🏷️ 最近标签')
        self.tag_panel_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #4a90e2;")
        header.addWidget(self.tag_panel_title)
        
        self.clear_tag_btn = QPushButton('✕')
        self.clear_tag_btn.setFixedSize(20, 20)
        self.clear_tag_btn.setStyleSheet(f"QPushButton {{ background-color: transparent; border: 1px solid #666; border-radius: 10px; color: #999; font-size: 12px; }} QPushButton:hover {{ background-color: {COLORS['danger']}; border-color: {COLORS['danger']}; color: white; }}")
        self.clear_tag_btn.setToolTip('清除标签筛选 (ESC)')
        self.clear_tag_btn.clicked.connect(self._clear_tag_filter)
        self.clear_tag_btn.hide()
        header.addWidget(self.clear_tag_btn)
        layout.addLayout(header)
        
        # 2. 顶部输入框
        self.tag_input = ClickableLineEdit()
        self.tag_input.setPlaceholderText("🔍 搜索...")
        self.tag_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #2D2D2D; 
                border: 1px solid #444;
                border-radius: 16px; /* 全圆角胶囊 */
                padding: 6px 12px; 
                font-size: 12px; 
                color: #EEE;
            }}
            QLineEdit:focus {{ 
                border-color: {COLORS['primary']}; 
                background-color: #38383C;
            }}
        """)
        self.tag_input.returnPressed.connect(self._handle_tag_input_return)
        self.tag_input.doubleClicked.connect(self._open_tag_selector_for_selection)
        layout.addWidget(self.tag_input)
        
        # 3. 分割线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)
        line.setStyleSheet(f"background-color: #505050; border: none; max-height: 1px; margin-top: 5px; margin-bottom: 5px;")
        layout.addWidget(line)
        
        # 4. 标签列表区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QWidget { background: transparent; }
            QScrollBar:vertical {
                border: none; background: #222; width: 6px; margin: 0;
            }
            QScrollBar::handle:vertical { background: #555; border-radius: 3px; }
        """)
        
        self.tag_list_widget = QWidget()
        # 使用流式布局
        self.tag_list_layout = FlowLayout(self.tag_list_widget, margin=0, spacing=8)
        
        scroll.setWidget(self.tag_list_widget)
        layout.addWidget(scroll)
        
        self._refresh_tag_panel()
        return panel

    def _handle_tag_input_return(self):
        text = self.tag_input.text().strip()
        if not text: return
        
        if self.selected_ids:
            self._add_tag_to_selection([text])
            self.tag_input.clear()
        else:
            self._refresh_tag_panel()

    def _open_tag_selector_for_selection(self):
        if self.selected_ids:
            selector = AdvancedTagSelector(self.db, idea_id=None, initial_tags=[])
            selector.tags_confirmed.connect(self._add_tag_to_selection)
            selector.show_at_cursor()

    def _add_tag_to_selection(self, tags):
        if not self.selected_ids or not tags: return
        self.db.add_tags_to_multiple_ideas(list(self.selected_ids), tags)
        self._show_tooltip(f"✅ 已添加 {len(tags)} 个标签到 {len(self.selected_ids)} 项")
        self._refresh_all()

    def _remove_tag_from_selection(self, tag_name):
        if not self.selected_ids: return
        self.db.remove_tag_from_multiple_ideas(list(self.selected_ids), tag_name)
        self._refresh_all()

    # 【核心逻辑】显示右键菜单
    def _show_tag_context_menu(self, pos, tag_name):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background-color: #2D2D2D; color: #EEE; border: 1px solid #444; }}
            QMenu::item {{ padding: 6px 20px; }}
            QMenu::item:selected {{ background-color: {COLORS['primary']}; }}
        """)
        
        menu.addAction("✏️ 重命名", lambda: self._rename_tag_action(tag_name))
        menu.addSeparator()
        menu.addAction("🗑️ 删除该标签 (全局)", lambda: self._delete_tag_action(tag_name))
        
        menu.exec_(QCursor.pos())

    def _rename_tag_action(self, old_name):
        new_name, ok = self._show_custom_input_dialog("重命名标签", "请输入新名称:", old_name)
        if ok and new_name and new_name.strip():
            self.db.rename_tag(old_name, new_name.strip())
            self._refresh_all()

    def _delete_tag_action(self, tag_name):
        if self._show_custom_confirm_dialog("删除标签", f"确定要彻底删除标签 #{tag_name} 吗？\n所有引用该标签的数据都将解除关联。"):
            self.db.delete_tag(tag_name)
            self._refresh_all()

    def _show_custom_input_dialog(self, title, label_text, default_text=""):
        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        dlg.setAttribute(Qt.WA_TranslucentBackground)
        dlg.setFixedSize(320, 160)
        
        container = QWidget(dlg)
        container.setGeometry(0, 0, 320, 160)
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_mid']};
                border: 1px solid #444;
                border-radius: 8px;
            }}
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #DDD; font-size: 14px; font-weight: bold; border: none;")
        layout.addWidget(lbl)
        
        inp = QLineEdit(default_text)
        inp.setStyleSheet(f"""
            QLineEdit {{
                background-color: #1E1E1E;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 6px;
                color: #EEE;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border: 1px solid {COLORS['primary']}; }}
        """)
        inp.selectAll()
        layout.addWidget(inp)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("取消")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton { background: transparent; color: #AAA; border: none; font-size: 13px; }
            QPushButton:hover { color: #EEE; }
        """)
        btn_cancel.clicked.connect(dlg.reject)
        
        btn_ok = QPushButton("确定")
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setStyleSheet(f"""
            QPushButton {{ 
                background-color: {COLORS['primary']}; 
                color: white; 
                border-radius: 4px; 
                padding: 6px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #357ABD; }}
        """)
        btn_ok.clicked.connect(dlg.accept)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)
        
        if dlg.exec_() == QDialog.Accepted:
            return inp.text(), True
        return "", False

    def _show_custom_confirm_dialog(self, title, msg):
        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        dlg.setAttribute(Qt.WA_TranslucentBackground)
        dlg.setFixedSize(340, 180)
        
        container = QWidget(dlg)
        container.setGeometry(0, 0, 340, 180)
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_mid']};
                border: 1px solid #444;
                border-radius: 8px;
            }}
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(25, 25, 25, 20)
        layout.setSpacing(15)
        
        title_lbl = QLabel(f"⚠️  {title}")
        title_lbl.setStyleSheet(f"color: {COLORS['danger']}; font-size: 15px; font-weight: bold; border: none;")
        layout.addWidget(title_lbl)
        
        content_lbl = QLabel(msg)
        content_lbl.setWordWrap(True)
        content_lbl.setStyleSheet("color: #CCC; font-size: 13px; border: none; line-height: 1.4;")
        layout.addWidget(content_lbl)
        
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("取消")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton { background: transparent; color: #AAA; border: none; font-size: 13px; }
            QPushButton:hover { color: #EEE; }
        """)
        btn_cancel.clicked.connect(dlg.reject)
        
        btn_del = QPushButton("删除")
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setStyleSheet(f"""
            QPushButton {{ 
                background-color: {COLORS['danger']}; 
                color: white; 
                border-radius: 4px; 
                padding: 6px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #C0392B; }}
        """)
        btn_del.clicked.connect(dlg.accept)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_del)
        layout.addLayout(btn_layout)
        
        return dlg.exec_() == QDialog.Accepted

    def _refresh_tag_panel(self):
        while self.tag_list_layout.count():
            item = self.tag_list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        if self.selected_ids:
            self.tag_panel_title.setText(f"🖊️ 标签管理 ({len(self.selected_ids)})")
            self.tag_input.setPlaceholderText("输入添加... (双击更多)")
            self.clear_tag_btn.hide()
            
            tags = self.db.get_union_tags(list(self.selected_ids))
            
            if not tags:
                lbl = QLabel("无标签")
                lbl.setStyleSheet("color:#666; font-style:italic; margin-top:10px;")
                lbl.setAlignment(Qt.AlignCenter)
                self.tag_list_layout.addItem(self.tag_list_layout.takeAt(0)) 
                self.tag_list_widget.layout().addWidget(lbl)
            else:
                for tag_name in tags:
                    btn = QPushButton(f"{tag_name}  ✕")
                    btn.setCursor(Qt.PointingHandCursor)
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: #383838;
                            color: #DDD;
                            border: 1px solid #4D4D4D;
                            border-radius: 14px;
                            padding: 5px 12px;
                            text-align: center;
                            font-size: 12px;
                            font-family: "Segoe UI", "Microsoft YaHei";
                        }}
                        QPushButton:hover {{
                            background-color: {COLORS['danger']};
                            border-color: {COLORS['danger']};
                            color: white;
                        }}
                    """)
                    btn.clicked.connect(lambda _, t=tag_name: self._remove_tag_from_selection(t))
                    self.tag_list_layout.addWidget(btn)
                    
        else:
            self.tag_panel_title.setText("🏷️ 最近标签")
            self.tag_input.setPlaceholderText("🔍 搜索...")
            if self.current_tag_filter:
                self.clear_tag_btn.show()
            else:
                self.clear_tag_btn.hide()
                
            c = self.db.conn.cursor()
            search_term = self.tag_input.text().strip()
            sql = '''
                SELECT t.name, COUNT(it.idea_id) as cnt, MAX(i.updated_at) as last_used
                FROM tags t 
                JOIN idea_tags it ON t.id = it.tag_id 
                JOIN ideas i ON it.idea_id = i.id 
                WHERE i.is_deleted = 0 
            '''
            params = []
            if search_term:
                sql += " AND t.name LIKE ?"
                params.append(f"%{search_term}%")
            
            sql += ' GROUP BY t.id ORDER BY last_used DESC, cnt DESC, t.name ASC'
            
            c.execute(sql, params)
            tags = c.fetchall()
            
            if not tags:
                return
                
            for row in tags:
                tag_name = row[0]
                count = row[1]
                is_active = (self.current_tag_filter == tag_name)
                icon = "✓" if is_active else "🕒"
                
                btn = QPushButton(f'{icon} {tag_name}')
                btn.setCursor(Qt.PointingHandCursor)
                
                btn.setContextMenuPolicy(Qt.CustomContextMenu)
                btn.customContextMenuRequested.connect(lambda pos, n=tag_name: self._show_tag_context_menu(pos, n))
                
                bg_color = COLORS['primary'] if is_active else '#333333'
                border_color = COLORS['primary'] if is_active else '#444444'
                text_color = 'white' if is_active else '#CCCCCC'
                
                btn.setStyleSheet(f"""
                    QPushButton {{ 
                        background-color: {bg_color}; 
                        border: 1px solid {border_color}; 
                        border-radius: 14px; 
                        padding: 5px 12px; 
                        text-align: center; 
                        color: {text_color}; 
                        font-size: 12px;
                        font-family: "Segoe UI", "Microsoft YaHei";
                    }} 
                    QPushButton:hover {{ 
                        background-color: {COLORS['primary']};
                        border-color: {COLORS['primary']}; 
                        color: white; 
                    }}
                """)
                btn.clicked.connect(lambda _, t=tag_name: self._filter_by_tag(t))
                self.tag_list_layout.addWidget(btn)

    def _filter_by_tag(self, tag_name):
        if self.current_tag_filter == tag_name:
            self._clear_tag_filter()
        else:
            self.current_tag_filter = tag_name
            self._set_page(1)
            self.tag_filter_label.setText(f'🏷️ {tag_name}')
            self.tag_filter_label.show()
            self.clear_tag_btn.show()
            self._load_data()
            self._refresh_tag_panel()

    def _clear_tag_filter(self):
        self.current_tag_filter = None
        self.tag_filter_label.hide()
        self.clear_tag_btn.hide()
        self._load_data()
        self._refresh_tag_panel()

    # ==================== 调整大小逻辑 ====================
    def _get_resize_area(self, pos):
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = self.RESIZE_MARGIN
        
        areas = []
        if x < m: areas.append('left')
        elif x > w - m: areas.append('right')
        if y < m: areas.append('top')
        elif y > h - m: areas.append('bottom')
        return areas
    
    def _set_cursor_for_resize(self, areas):
        if not areas:
            self.setCursor(Qt.ArrowCursor)
            return
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
                self._resize_area = areas
                self._resize_start_pos = e.globalPos()
                self._resize_start_geometry = self.geometry()
                self._drag_pos = None
            elif e.y() < 40:
                self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()
                self._resize_area = None
            else:
                self._drag_pos = None
                self._resize_area = None
            e.accept()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.NoButton:
            areas = self._get_resize_area(e.pos())
            self._set_cursor_for_resize(areas)
            e.accept()
            return
        
        if e.buttons() == Qt.LeftButton:
            if self._resize_area:
                delta = e.globalPos() - self._resize_start_pos
                rect = self._resize_start_geometry
                new_rect = rect.adjusted(0, 0, 0, 0)
                if 'left' in self._resize_area:
                    new_left = rect.left() + delta.x()
                    if rect.right() - new_left >= 600:
                        new_rect.setLeft(new_left)
                if 'right' in self._resize_area:
                    new_width = rect.width() + delta.x()
                    if new_width >= 600:
                        new_rect.setWidth(new_width)
                if 'top' in self._resize_area:
                    new_top = rect.top() + delta.y()
                    if rect.bottom() - new_top >= 400:
                        new_rect.setTop(new_top)
                if 'bottom' in self._resize_area:
                    new_height = rect.height() + delta.y()
                    if new_height >= 400:
                        new_rect.setHeight(new_height)
                
                self.setGeometry(new_rect)
                e.accept()
            elif self._drag_pos:
                self.move(e.globalPos() - self._drag_pos)
                e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        self._resize_area = None
        self.setCursor(Qt.ArrowCursor)

    def mouseDoubleClickEvent(self, e):
        if e.y() < 40: self._toggle_maximize()

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.max_btn.setText('□')
        else:
            self.showMaximized()
            self.max_btn.setText('❐')

    def _add_search_to_history(self):
        search_text = self.search.text().strip()
        if search_text:
            self.search.add_history_entry(search_text)

    def quick_add_idea(self, text):
        raw = text.strip()
        if not raw: return
        lines = raw.split('\n')
        title = lines[0][:25].strip() if lines else "快速记录"
        if len(lines) > 1 or len(lines[0]) > 25: title += "..."
        idea_id = self.db.add_idea(title, raw, COLORS['default_note'], [], None)
        self._show_tag_selector(idea_id)
        self._refresh_all()

    def _show_tag_selector(self, idea_id):
        tag_selector = AdvancedTagSelector(self.db, idea_id, None, self)
        tag_selector.tags_confirmed.connect(lambda tags: self._on_tags_confirmed(idea_id, tags))
        tag_selector.show_at_cursor()

    def _on_tags_confirmed(self, idea_id, tags):
        self._show_tooltip(f'✅ 已记录并绑定 {len(tags)} 个标签', 2000)
        self._refresh_all()

    def _set_filter(self, f_type, val):
        self.curr_filter = (f_type, val)
        self.selected_ids.clear()
        self.last_clicked_id = None
        self.current_tag_filter = None
        self.tag_filter_label.hide()
        self.clear_tag_btn.hide()
        titles = {'all':'全部数据','today':'今日数据','trash':'回收站','favorite':'我的收藏'}
        if f_type == 'category':
            cat = next((c for c in self.db.get_categories() if c[0] == val), None)
            self.header_label.setText(f"📂 {cat[1]}" if cat else '文件夹')
        else:
            self.header_label.setText(titles.get(f_type, '灵感列表'))
        self._load_data()
        self._update_ui_state()
        self._refresh_tag_panel()

    def _load_data(self):
        while self.list_layout.count():
            w = self.list_layout.takeAt(0).widget()
            if w: w.deleteLater()
        self.cards = {}
        self.card_ordered_ids = []
        
        # 【核心补充】此处必须先计算总数，否则分页控件全是 1/1
        total_items = self.db.get_ideas_count(self.search.text(), *self.curr_filter)
        self.total_pages = math.ceil(total_items / self.page_size) if total_items > 0 else 1
        
        # 修正页码范围
        if self.current_page > self.total_pages: self.current_page = self.total_pages
        if self.current_page < 1: self.current_page = 1

        data_list = self.db.get_ideas(self.search.text(), *self.curr_filter, page=self.current_page, page_size=self.page_size)
        
        if self.current_tag_filter:
            filtered = []
            for d in data_list:
                if self.current_tag_filter in self.db.get_tags(d[0]): filtered.append(d)
            data_list = filtered
        if not data_list:
            self.list_layout.addWidget(QLabel("🔭 空空如也", alignment=Qt.AlignCenter, styleSheet="color:#666;font-size:16px;margin-top:50px"))
        for d in data_list:
            c = IdeaCard(d, self.db)
            c.get_selected_ids_func = lambda: list(self.selected_ids)
            c.selection_requested.connect(self._handle_selection_request)
            c.double_clicked.connect(self._extract_single)
            c.setContextMenuPolicy(Qt.CustomContextMenu)
            c.customContextMenuRequested.connect(lambda pos, iid=d[0]: self._show_card_menu(iid, pos))
            self.list_layout.addWidget(c)
            self.cards[d[0]] = c
            self.card_ordered_ids.append(d[0])
            
        self._update_pagination_ui() # 刷新页码显示
        self._update_ui_state()

    def _show_card_menu(self, idea_id, pos):
        if idea_id not in self.selected_ids:
            self.selected_ids = {idea_id}
            self.last_clicked_id = idea_id
            self._update_all_card_selections()
            self._update_ui_state()
        data = self.db.get_idea(idea_id)
        if not data: return
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ background-color: {COLORS['bg_mid']}; color: white; border: 1px solid {COLORS['bg_light']}; border-radius: 6px; padding: 4px; }} QMenu::item {{ padding: 8px 20px; border-radius: 4px; }} QMenu::item:selected {{ background-color: {COLORS['primary']}; }} QMenu::separator {{ height: 1px; background: {COLORS['bg_light']}; margin: 4px 0px; }}")
        in_trash = (self.curr_filter[0] == 'trash')
        if not in_trash:
            menu.addAction('✏️ 编辑', self._do_edit)
            menu.addAction('📋 提取(Ctrl+T)', lambda: self._extract_single(idea_id))
            menu.addSeparator()
            menu.addAction('📌 取消置顶' if data[4] else '📌 置顶', self._do_pin)
            menu.addAction('☆ 取消收藏' if data[5] else '⭐ 收藏', self._do_fav)
            menu.addSeparator()
            cat_menu = menu.addMenu('📂 移动到分类')
            cat_menu.addAction('⚠️ 未分类', lambda: self._move_to_category(None))
            for cat in self.db.get_categories():
                cat_menu.addAction(f'📂 {cat[1]}', lambda cid=cat[0]: self._move_to_category(cid))
            menu.addSeparator()
            menu.addAction('🗑️ 移至回收站', self._do_del)
        else:
            menu.addAction('♻️ 恢复', self._do_restore)
            menu.addAction('🗑️ 永久删除', self._do_destroy)
        card = self.cards.get(idea_id)
        if card: menu.exec_(card.mapToGlobal(pos))

    def _move_to_category(self, cat_id):
        if self.selected_ids:
            for iid in self.selected_ids:
                self.db.move_category(iid, cat_id)
            self._refresh_all()
            self._show_tooltip(f'✅ 已移动 {len(self.selected_ids)} 项')

    def _handle_selection_request(self, iid, is_ctrl, is_shift):
        if is_shift and self.last_clicked_id is not None:
            try:
                start_index = self.card_ordered_ids.index(self.last_clicked_id)
                end_index = self.card_ordered_ids.index(iid)
                min_idx = min(start_index, end_index)
                max_idx = max(start_index, end_index)
                if not is_ctrl: self.selected_ids.clear()
                for idx in range(min_idx, max_idx + 1):
                    self.selected_ids.add(self.card_ordered_ids[idx])
            except ValueError:
                self.selected_ids.clear()
                self.selected_ids.add(iid)
                self.last_clicked_id = iid
        elif is_ctrl:
            if iid in self.selected_ids: self.selected_ids.remove(iid)
            else: self.selected_ids.add(iid)
            self.last_clicked_id = iid
        else:
            self.selected_ids.clear()
            self.selected_ids.add(iid)
            self.last_clicked_id = iid
        self._update_all_card_selections()
        self._update_ui_state()

    def _update_all_card_selections(self):
        for iid, card in self.cards.items():
            card.update_selection(iid in self.selected_ids)

    def _update_ui_state(self):
        in_trash = (self.curr_filter[0] == 'trash')
        selection_count = len(self.selected_ids)
        has_selection = selection_count > 0
        is_single_selection = selection_count == 1
        for k in ['pin', 'fav', 'del']: self.btns[k].setVisible(not in_trash)
        for k in ['rest', 'dest']: self.btns[k].setVisible(in_trash)
        self.btns['edit'].setVisible(not in_trash)
        self.btns['edit'].setEnabled(is_single_selection)
        for k in ['pin', 'fav', 'del', 'rest', 'dest']: self.btns[k].setEnabled(has_selection)
        if is_single_selection and not in_trash:
            idea_id = list(self.selected_ids)[0]
            d = self.db.get_idea(idea_id)
            if d:
                self.btns['pin'].setText('📍' if not d[4] else '📌')
                self.btns['fav'].setText('☆' if not d[5] else '⭐')
        else:
            self.btns['pin'].setText('📌')
            self.btns['fav'].setText('⭐')
        self._refresh_tag_panel()

    def _on_new_data_in_category_requested(self, cat_id):
        self._open_edit_dialog(category_id_for_new=cat_id)

    def _open_edit_dialog(self, idea_id=None, category_id_for_new=None):
        # 检查是否已存在此ID的窗口
        for dialog in self.open_dialogs:
            if hasattr(dialog, 'idea_id') and dialog.idea_id == idea_id and idea_id is not None:
                dialog.activateWindow()
                return

        dialog = EditDialog(self.db, idea_id=idea_id, category_id_for_new=category_id_for_new, parent=None)
        dialog.setAttribute(Qt.WA_DeleteOnClose) # 确保关闭时删除
        
        dialog.accepted.connect(self._refresh_all)
        dialog.finished.connect(lambda: self.open_dialogs.remove(dialog))

        self.open_dialogs.append(dialog)
        dialog.show()
        dialog.activateWindow()

    def _show_tooltip(self, msg, dur=2000):
        QToolTip.showText(QCursor.pos(), msg, self)
        QTimer.singleShot(dur, QToolTip.hideText)

    def new_idea(self):
        self._open_edit_dialog()

    def _do_edit(self):
        if len(self.selected_ids) == 1:
            idea_id = list(self.selected_ids)[0]
            self._open_edit_dialog(idea_id=idea_id)

    def _do_pin(self):
        if self.selected_ids:
            for iid in self.selected_ids: self.db.toggle_field(iid, 'is_pinned')
            self._load_data()

    def _do_fav(self):
        if self.selected_ids:
            for iid in self.selected_ids: self.db.toggle_field(iid, 'is_favorite')
            self._refresh_all()

    def _do_del(self):
        if self.selected_ids:
            for iid in self.selected_ids: self.db.set_deleted(iid, True)
            self.selected_ids.clear()
            self._refresh_all()

    def _do_restore(self):
        if self.selected_ids:
            for iid in self.selected_ids: self.db.set_deleted(iid, False)
            self.selected_ids.clear()
            self._refresh_all()

    def _do_destroy(self):
        if self.selected_ids and QMessageBox.Yes == QMessageBox.warning(self, '⚠️ 警告', f'确定永久删除选中的 {len(self.selected_ids)} 项?\n此操作不可恢复!', QMessageBox.Yes | QMessageBox.No):
            for iid in self.selected_ids: self.db.delete_permanent(iid)
            self.selected_ids.clear()
            self._refresh_all()

    def _refresh_all(self):
        self._load_data()
        self.sidebar.refresh()
        self._update_ui_state()
        self._refresh_tag_panel()

    def _extract_single(self, idea_id):
        data = self.db.get_idea(idea_id)
        if not data:
            self._show_tooltip('⚠️ 数据不存在', 1500)
            return
        content_to_copy = data[2] if data[2] else ""
        QApplication.clipboard().setText(content_to_copy)
        preview = content_to_copy.replace('\n', ' ')[:40] + ('...' if len(content_to_copy) > 40 else '')
        self._show_tooltip(f'✅ 内容已提取到剪贴板\n\n📋 {preview}', 2500)

    # 【补充方法】_extract_all
    def _extract_all(self):
        data = self.db.get_ideas('', 'all', None)
        if not data:
            self._show_tooltip('🔭 暂无数据', 1500)
            return
        lines = ['='*60, '💡 灵感闪记 - 内容导出', '='*60, '']
        for d in data:
            lines.append(f"【{d[1]}】")
            if d[4]: lines.append('📌 已置顶')
            if d[5]: lines.append('⭐ 已收藏')
            tags = self.db.get_tags(d[0])
            if tags: lines.append(f"标签: {', '.join(tags)}")
            lines.append(f"时间: {d[6]}")
            if d[2]: lines.append(f"\n{d[2]}")
            lines.append('\n'+'-'*60+'\n')
        text = '\n'.join(lines)
        QApplication.clipboard().setText(text)
        self._show_tooltip(f'✅ 已提取 {len(data)} 条到剪贴板!', 2000)

    def _handle_del_key(self):
        self._do_destroy() if self.curr_filter[0] == 'trash' else self._do_del()

    def _handle_extract_key(self):
        if len(self.selected_ids) == 1:
            self._extract_single(list(self.selected_ids)[0])
        elif len(self.selected_ids) > 1:
            self._show_tooltip('⚠️ 请选择一条笔记进行提取', 1500)
        else:
            self._show_tooltip('⚠️ 请先选择一条笔记', 1500)

    def show_main_window(self):
        self.show()
        self.activateWindow()

    def quit_app(self):
        BackupService.run_backup()
        QApplication.quit()

    def closeEvent(self, event):
        self.closing.emit()
        self.hide()
        event.ignore()