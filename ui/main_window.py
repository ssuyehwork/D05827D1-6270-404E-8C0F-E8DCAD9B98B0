# -*- coding: utf-8 -*-
# ui/main_window.py
import sys
import math
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QLineEdit,
                               QPushButton, QLabel, QShortcut, QMessageBox,
                               QApplication, QToolTip, QMenu, QFrame, QDialog,
                               QGraphicsDropShadowEffect, QLayout, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer, QPoint, pyqtSignal, QRect, QSize, QByteArray, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QKeySequence, QCursor, QColor, QIntValidator
from core.config import STYLES, COLORS
from core.settings import load_setting, save_setting
from data.db_manager import DatabaseManager
from ui.sidebar import Sidebar
from ui.card_list_view import CardListView 
from ui.dialogs import EditDialog
from ui.advanced_tag_selector import AdvancedTagSelector
from ui.components.search_line_edit import SearchLineEdit
from services.preview_service import PreviewService
from ui.utils import create_svg_icon
from ui.filter_panel import FilterPanel 

class ClickableLineEdit(QLineEdit):
    doubleClicked = pyqtSignal()
    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)

class TagChipWidget(QWidget):
    deleted = pyqtSignal(str)
    def __init__(self, tag_name, parent=None):
        super().__init__(parent)
        self.tag_name = tag_name
        self.setObjectName("TagChip")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 5, 5, 5)
        layout.setSpacing(6)
        self.label = QLabel(tag_name)
        self.label.setStyleSheet("border: none; background: transparent; color: #DDD; font-size: 12px;")
        self.delete_btn = QPushButton()
        self.delete_btn.setIcon(create_svg_icon("win_close.svg", "#AAA"))
        self.delete_btn.setFixedSize(16, 16)
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setStyleSheet(f"QPushButton {{ background-color: transparent; border: none; border-radius: 8px; }} QPushButton:hover {{ background-color: {COLORS['danger']}; }}")
        layout.addWidget(self.label)
        layout.addWidget(self.delete_btn)
        self.setStyleSheet("#TagChip { background-color: #383838; border: 1px solid #4D4D4D; border-radius: 14px; }")
        self.delete_btn.clicked.connect(self._emit_delete)
    def _emit_delete(self):
        self.deleted.emit(self.tag_name)

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

    def _add_row(self, label, value):
        row = QWidget()
        row.setObjectName("CapsuleRow")
        row.setAttribute(Qt.WA_StyledBackground, True)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 8, 12, 8) 
        row_layout.setSpacing(10)
        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 11px; color: #AAA; border: none; min-width: 45px; background: transparent;")
        row_layout.addWidget(lbl)
        val = QLabel(value)
        val.setWordWrap(True)
        val.setStyleSheet("font-size: 12px; color: #FFF; border: none; font-weight: bold; background: transparent;") 
        row_layout.addWidget(val)
        row.setStyleSheet(f"QWidget {{ background-color: transparent; }} #CapsuleRow {{ background-color: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; }}")
        self.layout.addWidget(row)

    def update_data(self, data, tags, category_name):
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        if not data: return
        self._add_row("创建于", data['created_at'][:16])
        self._add_row("更新于", data['updated_at'][:16])
        self._add_row("分类", category_name if category_name else "未分类")
        states = []
        if data['is_pinned']: states.append("置顶")
        if data['is_locked']: states.append("锁定")
        if data['is_favorite']: states.append("书签")
        self._add_row("状态", ", ".join(states) if states else "无")
        rating_str = '★' * data['rating'] + '☆' * (5 - data['rating'])
        self._add_row("星级", rating_str)
        self._add_row("标签", ", ".join(tags) if tags else "无")

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
        self.current_tag_filter = None
        self.last_clicked_id = None 
        self.card_ordered_ids = []
        
        self._drag_pos = None
        self._resize_area = None
        self._resize_start_pos = None
        self._resize_start_geometry = None
        self.is_metadata_panel_visible = False
        
        self.current_page = 1
        self.page_size = 100
        self.total_pages = 1
        
        self.open_dialogs = []
        
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.Window | 
            Qt.WindowSystemMenuHint | 
            Qt.WindowMinimizeButtonHint | 
            Qt.WindowMaximizeButtonHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        self.setWindowTitle('数据管理')
        
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
        
        # --- 中央内容区 ---
        central_content = QWidget()
        central_layout = QHBoxLayout(central_content)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        
        # 1. 侧边栏
        self.sidebar = Sidebar(self.db)
        self.sidebar.filter_changed.connect(self._set_filter)
        self.sidebar.data_changed.connect(self._load_data)
        self.sidebar.new_data_requested.connect(self._on_new_data_in_category_requested)
        self.sidebar.setMinimumWidth(200)
        
        # 2. 中间卡片区 (包含 Header 和 CardListView)
        middle_panel = self._create_middle_panel()

        # 3. 右侧元数据面板
        self.metadata_panel = self._create_metadata_panel()
        self.metadata_panel.setMinimumWidth(0)
        self.metadata_panel.hide()

        # Splitter 布局
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self.sidebar)

        right_container = QWidget()
        right_layout = QHBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(middle_panel, 1)
        right_layout.addWidget(self.metadata_panel)

        self.main_splitter.addWidget(right_container)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([280, 100])
        self.main_splitter.splitterMoved.connect(lambda: self.card_list_view.recalc_layout())
        
        central_layout.addWidget(self.main_splitter)
        outer_layout.addWidget(central_content, 1)
        
        # 4. 独立悬浮筛选器
        self.filter_panel = FilterPanel()
        self.filter_panel.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.filter_panel.setAttribute(Qt.WA_TranslucentBackground)
        self.filter_panel.filterChanged.connect(self._on_filter_criteria_changed)
        self.filter_panel.hide()
        
        self._setup_shortcuts()
        self._restore_window_state()

    def _create_middle_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 顶部操作栏
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
        # 注意: 这里只是一些顶部快捷按钮的定义, 右键菜单逻辑在 _show_card_menu
        btn_defs = [
            ('pin', 'action_pin.svg', self._do_pin),
            ('fav', 'action_fav.svg', self._do_fav),
            ('edit', 'action_edit.svg', self._do_edit),
            ('del', 'action_delete.svg', self._do_del),
            ('rest', 'action_restore.svg', self._do_restore),
            ('dest', 'action_delete.svg', self._do_destroy)
        ]
        
        for k, icon_name, f in btn_defs:
            b = QPushButton()
            b.setIcon(create_svg_icon(icon_name, '#aaa'))
            b.setStyleSheet(STYLES['btn_icon'])
            b.clicked.connect(f)
            b.setEnabled(False)
            act_bar.addWidget(b)
            self.btns[k] = b
            
        layout.addLayout(act_bar)
        
        self.card_list_view = CardListView(self.db, self)
        
        self.card_list_view.selection_cleared.connect(self._clear_all_selections)
        self.card_list_view.card_selection_requested.connect(self._handle_selection_request)
        self.card_list_view.card_double_clicked.connect(self._extract_single)
        self.card_list_view.card_context_menu_requested.connect(self._show_card_menu)
        
        layout.addWidget(self.card_list_view)
        
        return panel

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+T"), self, self._handle_extract_key)
        QShortcut(QKeySequence("Ctrl+N"), self, self.new_idea)
        QShortcut(QKeySequence("Ctrl+W"), self, self.close)
        QShortcut(QKeySequence("Ctrl+A"), self, self._select_all)
        QShortcut(QKeySequence("Ctrl+F"), self, self.search.setFocus)
        self.sidebar.filter_changed.connect(self._rebuild_filter_panel)
        self.search.textChanged.connect(self._rebuild_filter_panel)
        QShortcut(QKeySequence("Ctrl+B"), self, self._toggle_sidebar)
        QShortcut(QKeySequence("Ctrl+I"), self, self._toggle_metadata_panel)
        QShortcut(QKeySequence("Ctrl+G"), self, self._toggle_filter_panel)
        QShortcut(QKeySequence("Delete"), self, self._handle_del_key)
        QShortcut(QKeySequence("Ctrl+S"), self, self._do_lock)

        for i in range(6):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, lambda r=i: self._do_set_rating(r))
        
        self.space_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.space_shortcut.setContext(Qt.WindowShortcut)
        self.space_shortcut.activated.connect(lambda: self.preview_service.toggle_preview(self.selected_ids))

    def _load_data(self):
        criteria = self.filter_panel.get_checked_criteria()
        
        total_items = self.db.get_ideas_count(
            self.search.text(), 
            *self.curr_filter, 
            tag_filter=self.current_tag_filter,
            filter_criteria=criteria
        )
        self.total_pages = math.ceil(total_items / self.page_size) if total_items > 0 else 1
        
        if self.current_page > self.total_pages: self.current_page = self.total_pages
        if self.current_page < 1: self.current_page = 1

        data_list = self.db.get_ideas(
            self.search.text(), 
            *self.curr_filter, 
            page=self.current_page, 
            page_size=self.page_size, 
            tag_filter=self.current_tag_filter,
            filter_criteria=criteria
        )
        
        self.card_list_view.render_cards(data_list)
        self.card_ordered_ids = [d['id'] for d in data_list]
        
        self._update_pagination_ui()
        self._update_ui_state()

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
        QTimer.singleShot(0, self._update_ui_state)

    def _update_all_card_selections(self):
        self.card_list_view.update_all_selections(self.selected_ids)

    def _clear_all_selections(self):
        if not self.selected_ids: return
        self.selected_ids.clear()
        self.last_clicked_id = None
        self._update_all_card_selections()
        self._update_ui_state()
        
    def _select_all(self):
        if not self.card_ordered_ids: return
        if len(self.selected_ids) == len(self.card_ordered_ids):
            self.selected_ids.clear()
        else:
            self.selected_ids = set(self.card_ordered_ids)
        self._update_all_card_selections()
        self._update_ui_state()

    def _do_pin(self):
        if self.selected_ids:
            for iid in self.selected_ids: self.db.toggle_field(iid, 'is_pinned')
            self._load_data()

    def _do_fav(self):
        if self.selected_ids:
            any_not_favorited = False
            for iid in self.selected_ids:
                data = self.db.get_idea(iid)
                if data and not data['is_favorite']:
                    any_not_favorited = True
                    break
            target_state = True if any_not_favorited else False
            for iid in self.selected_ids:
                self.db.set_favorite(iid, target_state)
            
            for iid in self.selected_ids:
                card = self.card_list_view.get_card(iid)
                if card:
                    new_data = self.db.get_idea(iid, include_blob=True)
                    if new_data: card.update_data(new_data)
            
            self._update_ui_state()
            self.sidebar.refresh()

    def _do_del(self):
        if self.selected_ids:
            # 锁定只针对删除生效
            valid_ids = self._get_valid_ids_ignoring_locked(self.selected_ids)
            if not valid_ids: 
                # 可以选择提示用户
                self._show_tooltip("🔒 锁定项目无法删除", 1500)
                return
            
            for iid in valid_ids:
                self.db.set_deleted(iid, True)
                self.card_list_view.remove_card(iid)
            
            self.selected_ids.clear()
            self._update_ui_state()
            self.sidebar.refresh()

    def _do_restore(self):
        if self.selected_ids:
            for iid in self.selected_ids:
                self.db.set_deleted(iid, False)
                self.card_list_view.remove_card(iid)
            self.selected_ids.clear()
            self._update_ui_state()
            self.sidebar.refresh()

    def _do_destroy(self):
        if self.selected_ids:
            msg = f'确定永久删除选中的 {len(self.selected_ids)} 项?\n此操作不可恢复!'
            if QMessageBox.Yes == QMessageBox.question(self, "永久删除", msg):
                for iid in self.selected_ids:
                    self.db.delete_permanent(iid)
                    self.card_list_view.remove_card(iid)
                self.selected_ids.clear()
                self._update_ui_state()
                self.sidebar.refresh()

    def _do_set_rating(self, rating):
        if not self.selected_ids: return
        for idea_id in self.selected_ids:
            self.db.set_rating(idea_id, rating)
            card = self.card_list_view.get_card(idea_id)
            if card:
                new_data = self.db.get_idea(idea_id, include_blob=True)
                if new_data: card.update_data(new_data)

    def _do_lock(self):
        if not self.selected_ids: return
        status_map = self.db.get_lock_status(list(self.selected_ids))
        any_unlocked = any(not locked for locked in status_map.values())
        target_state = 1 if any_unlocked else 0
        self.db.set_locked(list(self.selected_ids), target_state)
        for iid in self.selected_ids:
            card = self.card_list_view.get_card(iid)
            if card:
                new_data = self.db.get_idea(iid, include_blob=True)
                if new_data: card.update_data(new_data)
        self._update_ui_state()

    def _get_valid_ids_ignoring_locked(self, ids):
        valid = []
        status_map = self.db.get_lock_status(list(ids))
        for iid in ids:
            if not status_map.get(iid, 0):
                valid.append(iid)
        return valid

    def _move_to_category(self, cat_id):
        if self.selected_ids:
            # 锁定不应阻止移动
            # valid_ids = self._get_valid_ids_ignoring_locked(self.selected_ids) 
            # 改为允许移动:
            valid_ids = list(self.selected_ids)
            
            if not valid_ids: return
            for iid in valid_ids:
                self.db.move_category(iid, cat_id)
                self.card_list_view.remove_card(iid)
            self.selected_ids.clear()
            self._update_ui_state()
            self.sidebar.refresh()

    def _update_ui_state(self):
        in_trash = (self.curr_filter[0] == 'trash')
        selection_count = len(self.selected_ids)
        has_selection = selection_count > 0
        is_single = selection_count == 1
        
        for k in ['pin', 'fav', 'del']: self.btns[k].setVisible(not in_trash)
        for k in ['rest', 'dest']: self.btns[k].setVisible(in_trash)
        self.btns['edit'].setVisible(not in_trash)
        self.btns['edit'].setEnabled(is_single)
        for k in ['pin', 'fav', 'del', 'rest', 'dest']: self.btns[k].setEnabled(has_selection)
        
        if is_single and not in_trash:
            idea_id = list(self.selected_ids)[0]
            d = self.db.get_idea(idea_id)
            if d:
                self.btns['pin'].setIcon(create_svg_icon('action_pin_off.svg' if d['is_pinned'] else 'action_pin.svg', '#aaa'))
        else:
            self.btns['pin'].setIcon(create_svg_icon('action_pin.svg', '#aaa'))
            
        QTimer.singleShot(0, self._refresh_metadata_panel)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = self.width()
        if width < 1200: self._hide_metadata_panel()
        if width < 900 and self.sidebar.width() == 280: self._toggle_sidebar()

    def _show_card_menu(self, idea_id, pos):
        if idea_id not in self.selected_ids:
            self.selected_ids = {idea_id}
            self.last_clicked_id = idea_id
            self._update_all_card_selections()
            self._update_ui_state()
            
        data = self.db.get_idea(idea_id)
        if not data: return
        
        # --- 菜单样式优化：紧凑 + 修正图标对齐 ---
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ 
                background-color: {COLORS['bg_mid']}; 
                color: white; 
                border: 1px solid {COLORS['bg_light']}; 
                border-radius: 6px; 
                padding: 4px; 
            }} 
            QMenu::item {{ 
                padding: 6px 10px 6px 28px; /* 紧凑布局 */
                border-radius: 4px; 
            }} 
            QMenu::item:selected {{ 
                background-color: {COLORS['primary']}; 
            }} 
            QMenu::separator {{ 
                height: 1px; 
                background: {COLORS['bg_light']}; 
                margin: 4px 0px; 
            }}
            QMenu::icon {{
                position: absolute;
                left: 6px;
                top: 6px;
            }}
        """)
        
        in_trash = (self.curr_filter[0] == 'trash')
        is_locked = data['is_locked']
        rating = data['rating']
        
        if not in_trash:
            # 1. 编辑 (即使锁定也允许，图标为蓝色)
            menu.addAction(create_svg_icon('action_edit.svg', '#4a90e2'), '编辑', self._do_edit)
            
            # 2. 提取 (绿色)
            menu.addAction(create_svg_icon('action_export.svg', '#1abc9c'), '提取(Ctrl+T)', lambda: self._extract_single(idea_id))
            menu.addSeparator()
            
            # 3. 星级 (黄色)
            from PyQt5.QtWidgets import QAction, QActionGroup
            rating_menu = menu.addMenu(create_svg_icon('star.svg', '#f39c12'), "设置星级")
            star_group = QActionGroup(self)
            star_group.setExclusive(True)
            for i in range(1, 6):
                action = QAction(f"{'★'*i}", self, checkable=True)
                action.triggered.connect(lambda _, r=i: self._do_set_rating(r))
                if rating == i: action.setChecked(True)
                rating_menu.addAction(action)
                star_group.addAction(action)
            rating_menu.addSeparator()
            rating_menu.addAction("清除评级").triggered.connect(lambda: self._do_set_rating(0))
            
            # 4. 锁定 (绿色/灰色)
            if is_locked:
                menu.addAction(create_svg_icon('lock.svg', COLORS['success']), '解锁', self._do_lock)
            else:
                menu.addAction(create_svg_icon('lock.svg', '#aaaaaa'), '锁定 (Ctrl+S)', self._do_lock)
                
            menu.addSeparator()
            
            # 5. 置顶 (蓝色)
            pin_icon = 'action_pin_off.svg' if data['is_pinned'] else 'action_pin.svg'
            menu.addAction(create_svg_icon(pin_icon, '#3498db'), '取消置顶' if data['is_pinned'] else '置顶', self._do_pin)
            
            # 6. 书签 (粉色)
            menu.addAction(create_svg_icon('bookmark.svg', '#ff6b81'), '取消书签' if data['is_favorite'] else '添加书签', self._do_fav)
            menu.addSeparator()
            
            # 7. 移动与删除
            cat_menu = menu.addMenu(create_svg_icon('folder.svg', '#cccccc'), '移动到分类')
            cat_menu.addAction('⚠️ 未分类', lambda: self._move_to_category(None))
            for cat in self.db.get_categories():
                cat_menu.addAction(f'📂 {cat["name"]}', lambda cid=cat["id"]: self._move_to_category(cid))
            
            menu.addSeparator()
            
            # 删除 (红色，若锁定则禁用)
            if not is_locked:
                menu.addAction(create_svg_icon('action_delete.svg', '#e74c3c'), '移至回收站', self._do_del)
            else:
                # 锁定状态下，禁用删除
                act = menu.addAction(create_svg_icon('action_delete.svg', '#555555'), '移至回收站 (已锁定)')
                act.setEnabled(False)
        else:
            menu.addAction(create_svg_icon('action_restore.svg', '#2ecc71'), '恢复', self._do_restore)
            menu.addAction(create_svg_icon('trash.svg', '#e74c3c'), '永久删除', self._do_destroy)
            
        card = self.card_list_view.get_card(idea_id)
        if card: menu.exec_(card.mapToGlobal(pos))

    # (其余代码保持不变)
    def _create_titlebar(self):
        titlebar = QWidget()
        titlebar.setFixedHeight(40)
        titlebar.setStyleSheet(f"QWidget {{ background-color: {COLORS['bg_mid']}; border-bottom: 1px solid {COLORS['bg_light']}; border-top-left-radius: 8px; border-top-right-radius: 8px; }}")
        layout = QHBoxLayout(titlebar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)
        
        self.sidebar_toggle_btn = QPushButton("☰")
        self.sidebar_toggle_btn.setFixedSize(30, 30)
        self.sidebar_toggle_btn.setStyleSheet("QPushButton { font-size: 16px; color: #AAA; background-color: transparent; border: none; border-radius: 6px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }")
        self.sidebar_toggle_btn.clicked.connect(self._toggle_sidebar)
        layout.addWidget(self.sidebar_toggle_btn)
        
        title = QLabel('💡 快速笔记')
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #4a90e2;")
        layout.addWidget(title)
        
        self.search = SearchLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText('🔍 搜索灵感 (双击查看历史)')
        self.search.setFixedWidth(280)
        self.search.setFixedHeight(28)
        self.search.setStyleSheet(STYLES['input'] + "QLineEdit { border-radius: 14px; padding-right: 25px; } QLineEdit::clear-button { image: url(assets/clear.png); subcontrol-position: right; margin-right: 5px; }")
        self.search.textChanged.connect(lambda: self._set_page(1))
        self.search.returnPressed.connect(self._add_search_to_history)
        layout.addWidget(self.search)
        
        layout.addSpacing(10)
        
        page_btn_style = "QPushButton { background-color: transparent; border: 1px solid #444; border-radius: 4px; padding: 2px 8px; min-width: 24px; min-height: 20px; } QPushButton:hover { background-color: #333; border-color: #666; } QPushButton:disabled { border-color: #333; }"
        
        self.btn_first = QPushButton()
        self.btn_first.setIcon(create_svg_icon('nav_first.svg', '#aaa'))
        self.btn_first.setStyleSheet(page_btn_style)
        self.btn_first.clicked.connect(lambda: self._set_page(1))
        
        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(create_svg_icon('nav_prev.svg', '#aaa'))
        self.btn_prev.setStyleSheet(page_btn_style)
        self.btn_prev.clicked.connect(lambda: self._set_page(self.current_page - 1))
        
        self.page_input = QLineEdit()
        self.page_input.setFixedWidth(40)
        self.page_input.setAlignment(Qt.AlignCenter)
        self.page_input.setValidator(QIntValidator(1, 9999))
        self.page_input.setStyleSheet("background-color: #2D2D2D; border: 1px solid #444; color: #DDD; border-radius: 4px; padding: 2px;")
        self.page_input.returnPressed.connect(self._jump_to_page)
        
        self.total_page_label = QLabel("/ 1")
        self.total_page_label.setStyleSheet("color: #888; font-size: 12px; margin-left: 2px; margin-right: 5px;")
        
        self.btn_next = QPushButton()
        self.btn_next.setIcon(create_svg_icon('nav_next.svg', '#aaa'))
        self.btn_next.setStyleSheet(page_btn_style)
        self.btn_next.clicked.connect(lambda: self._set_page(self.current_page + 1))
        
        self.btn_last = QPushButton()
        self.btn_last.setIcon(create_svg_icon('nav_last.svg', '#aaa'))
        self.btn_last.setStyleSheet(page_btn_style)
        self.btn_last.clicked.connect(lambda: self._set_page(self.total_pages))
        
        layout.addWidget(self.btn_first); layout.addWidget(self.btn_prev); layout.addWidget(self.page_input); layout.addWidget(self.total_page_label); layout.addWidget(self.btn_next); layout.addWidget(self.btn_last)
        layout.addStretch()
        
        ctrl_btn_style = "QPushButton { background-color: transparent; border: none; border-radius: 6px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; } QPushButton:hover { background-color: rgba(255,255,255,0.1); }"
        
        filter_btn = QPushButton()
        filter_btn.setIcon(create_svg_icon('select.svg', '#FFF'))
        filter_btn.setStyleSheet(f"QPushButton {{ background-color: {COLORS['primary']}; border: none; border-radius: 6px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; }} QPushButton:hover {{ background-color: #357abd; }}")
        filter_btn.clicked.connect(self._toggle_filter_panel)
        layout.addWidget(filter_btn)
        
        extract_btn = QPushButton()
        extract_btn.setIcon(create_svg_icon('action_export.svg', '#FFF'))
        extract_btn.setStyleSheet(filter_btn.styleSheet())
        extract_btn.clicked.connect(self._extract_all)
        layout.addWidget(extract_btn)
        
        new_btn = QPushButton()
        new_btn.setIcon(create_svg_icon('action_add.svg', '#FFF'))
        new_btn.setStyleSheet(filter_btn.styleSheet())
        new_btn.clicked.connect(self.new_idea)
        layout.addWidget(new_btn)
        
        layout.addSpacing(4)
        
        min_btn = QPushButton(); min_btn.setIcon(create_svg_icon('win_min.svg', '#aaa')); min_btn.setStyleSheet(ctrl_btn_style); min_btn.clicked.connect(self.showMinimized)
        layout.addWidget(min_btn)
        
        self.max_btn = QPushButton(); self.max_btn.setIcon(create_svg_icon('win_max.svg', '#aaa')); self.max_btn.setStyleSheet(ctrl_btn_style); self.max_btn.clicked.connect(self._toggle_maximize)
        layout.addWidget(self.max_btn)
        
        close_btn = QPushButton(); close_btn.setIcon(create_svg_icon('win_close.svg', '#aaa')); close_btn.setStyleSheet(ctrl_btn_style + "QPushButton:hover { background-color: #e74c3c; }"); close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        return titlebar

    def _set_page(self, page_num):
        if page_num < 1: page_num = 1
        self.current_page = page_num
        self._load_data()
    def _jump_to_page(self):
        text = self.page_input.text().strip()
        if text.isdigit(): self._set_page(int(text))
        else: self.page_input.setText(str(self.current_page))
    def _update_pagination_ui(self):
        self.page_input.setText(str(self.current_page))
        self.total_page_label.setText(f"/ {self.total_pages}")
        self.btn_first.setDisabled(self.current_page <= 1)
        self.btn_prev.setDisabled(self.current_page <= 1)
        self.btn_next.setDisabled(self.current_page >= self.total_pages)
        self.btn_last.setDisabled(self.current_page >= self.total_pages)
        
    def _create_metadata_panel(self):
        panel = QWidget()
        panel.setObjectName("RightPanel")
        panel.setStyleSheet(f"#RightPanel {{ background-color: {COLORS['bg_mid']}; }}")
        panel.setFixedWidth(240)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        title_container = QWidget(); title_container.setStyleSheet("background-color: transparent;")
        title_layout = QHBoxLayout(title_container); title_layout.setContentsMargins(0, 0, 0, 0); title_layout.setSpacing(6)
        icon = QLabel(); icon.setPixmap(create_svg_icon('all_data.svg', '#4a90e2').pixmap(18, 18)); icon.setStyleSheet("background: transparent; border: none;")
        lbl = QLabel("元数据"); lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #4a90e2; background: transparent; border: none;")
        title_layout.addWidget(icon); title_layout.addWidget(lbl); title_layout.addStretch()
        layout.addWidget(title_container)

        self.info_stack = QWidget(); self.info_stack.setStyleSheet("background-color: transparent;")
        self.info_stack_layout = QVBoxLayout(self.info_stack); self.info_stack_layout.setContentsMargins(0,0,0,0)
        self.no_selection_widget = InfoWidget('select.svg', "未选择项目", "请选择一个项目以查看其元数据")
        self.multi_selection_widget = InfoWidget('all_data.svg', "已选择多个项目", "请仅选择一项以查看其元数据")
        self.metadata_display = MetadataDisplay()
        self.info_stack_layout.addWidget(self.no_selection_widget); self.info_stack_layout.addWidget(self.multi_selection_widget); self.info_stack_layout.addWidget(self.metadata_display)
        layout.addWidget(self.info_stack)

        self.title_input = QLineEdit(); self.title_input.setPlaceholderText("标题"); self.title_input.setObjectName("CapsuleInput")
        self.title_input.setStyleSheet(f"#CapsuleInput {{ background-color: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; color: #EEE; font-size: 13px; font-weight: bold; padding: 8px 12px; margin-top: 10px; }} #CapsuleInput:focus {{ border: 1px solid {COLORS['primary']}; background-color: rgba(255, 255, 255, 0.08); }}")
        self.title_input.editingFinished.connect(self._save_title_from_sidebar)
        self.title_input.returnPressed.connect(self.title_input.clearFocus)
        layout.addWidget(self.title_input)

        layout.addStretch(1)
        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setFrameShadow(QFrame.Plain); line.setStyleSheet("background-color: #505050; border: none; max-height: 1px; margin-bottom: 5px;"); layout.addWidget(line)

        self.tag_input = ClickableLineEdit(); self.tag_input.setPlaceholderText("输入标签添加... (双击更多)"); self.tag_input.setObjectName("CapsuleTagInput")
        self.tag_input.setStyleSheet(f"#CapsuleTagInput {{ background-color: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 8px 12px; font-size: 12px; color: #EEE; }} #CapsuleTagInput:focus {{ border-color: {COLORS['primary']}; background-color: rgba(255, 255, 255, 0.08); }} #CapsuleTagInput:disabled {{ background-color: transparent; border: 1px solid #333; color: #666; }}")
        self.tag_input.returnPressed.connect(self._handle_tag_input_return)
        self.tag_input.doubleClicked.connect(self._open_tag_selector_for_selection)
        layout.addWidget(self.tag_input)
        
        return panel

    def _save_title_from_sidebar(self):
        if len(self.selected_ids) != 1: return
        new_title = self.title_input.text().strip()
        if not new_title: return
        idea_id = list(self.selected_ids)[0]
        self.db.update_field(idea_id, 'title', new_title)
        card = self.card_list_view.get_card(idea_id)
        if card:
            data = self.db.get_idea(idea_id, include_blob=True)
            if data: card.update_data(data)

    def _handle_tag_input_return(self):
        text = self.tag_input.text().strip()
        if not text: return
        if self.selected_ids:
            self._add_tag_to_selection([text])
            self.tag_input.clear()

    def _open_tag_selector_for_selection(self):
        if self.selected_ids:
            selector = AdvancedTagSelector(self.db, idea_id=None, initial_tags=[])
            selector.tags_confirmed.connect(self._add_tag_to_selection)
            selector.show_at_cursor()

    def _add_tag_to_selection(self, tags):
        if not self.selected_ids or not tags: return
        self.db.add_tags_to_multiple_ideas(list(self.selected_ids), tags)
        self._refresh_all()

    def _refresh_metadata_panel(self):
        num_selected = len(self.selected_ids)
        if num_selected == 0:
            self.no_selection_widget.show(); self.multi_selection_widget.hide(); self.metadata_display.hide(); self.title_input.hide(); self.tag_input.setEnabled(False); self.tag_input.setPlaceholderText("请先选择一个项目"); self._hide_metadata_panel()
        elif num_selected == 1:
            self._show_metadata_panel(); self.no_selection_widget.hide(); self.multi_selection_widget.hide(); self.metadata_display.show(); self.title_input.show(); self.tag_input.setEnabled(True); self.tag_input.setPlaceholderText("输入标签添加... (双击更多)")
            idea_id = list(self.selected_ids)[0]
            data = self.db.get_idea(idea_id)
            if data:
                self.title_input.setText(data['title'])
                tags = self.db.get_tags(idea_id)
                category_name = ""
                if data['category_id']:
                    all_categories = self.db.get_categories()
                    cat = next((c for c in all_categories if c['id'] == data['category_id']), None)
                    if cat: category_name = cat['name']
                self.metadata_display.update_data(data, tags, category_name)
        else:
            self._hide_metadata_panel(); self.no_selection_widget.hide(); self.multi_selection_widget.show(); self.metadata_display.hide(); self.title_input.hide(); self.tag_input.setEnabled(False); self.tag_input.setPlaceholderText("请仅选择一项以查看元数据")

    def _toggle_sidebar(self):
        is_collapsed = self.sidebar.width() == 60
        target_width = 280 if is_collapsed else 60
        self.sidebar_animation = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self.sidebar_animation.setDuration(300)
        self.sidebar_animation.setStartValue(self.sidebar.width())
        self.sidebar_animation.setEndValue(target_width)
        self.sidebar_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.sidebar_animation.start()

    def _show_metadata_panel(self):
        if self.is_metadata_panel_visible: return
        self.is_metadata_panel_visible = True
        self.metadata_panel.show()
        self.metadata_animation = QPropertyAnimation(self.metadata_panel, b"minimumWidth")
        self.metadata_animation.setDuration(300)
        self.metadata_animation.setStartValue(0)
        self.metadata_animation.setEndValue(240)
        self.metadata_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.metadata_animation.finished.connect(lambda: self.card_list_view.recalc_layout())
        self.metadata_animation.start()

    def _hide_metadata_panel(self):
        if not self.is_metadata_panel_visible: return
        self.is_metadata_panel_visible = False
        self.metadata_animation = QPropertyAnimation(self.metadata_panel, b"minimumWidth")
        self.metadata_animation.setDuration(300)
        self.metadata_animation.setStartValue(self.metadata_panel.width())
        self.metadata_animation.setEndValue(0)
        self.metadata_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.metadata_animation.finished.connect(self.metadata_panel.hide)
        self.metadata_animation.finished.connect(lambda: self.card_list_view.recalc_layout())
        self.metadata_animation.start()

    def _toggle_metadata_panel(self):
        if self.is_metadata_panel_visible: self._hide_metadata_panel()
        else: self._show_metadata_panel()

    def _toggle_filter_panel(self):
        if self.filter_panel.isVisible(): self.filter_panel.hide()
        else:
            saved_size = load_setting('filter_panel_size')
            if saved_size and 'width' in saved_size: self.filter_panel.resize(saved_size['width'], saved_size['height'])
            main_geo = self.geometry()
            x = main_geo.right() - self.filter_panel.width() - 20
            y = main_geo.bottom() - self.filter_panel.height() - 20
            self.filter_panel.move(x, y)
            self.filter_panel.show(); self.filter_panel.raise_(); self.filter_panel.activateWindow()
            self._rebuild_filter_panel()

    def _rebuild_filter_panel(self):
        stats = self.db.get_filter_stats(self.search.text(), self.curr_filter[0], self.curr_filter[1])
        self.filter_panel.update_stats(stats)
        
    def _add_search_to_history(self):
        search_text = self.search.text().strip()
        if search_text: self.search.add_history_entry(search_text)
        
    def new_idea(self):
        self._open_edit_dialog()
        
    def _do_edit(self):
        if len(self.selected_ids) == 1:
            idea_id = list(self.selected_ids)[0]
            status = self.db.get_lock_status([idea_id])
            if status.get(idea_id, 0): return
            self._open_edit_dialog(idea_id=idea_id)
            
    def _open_edit_dialog(self, idea_id=None, category_id_for_new=None):
        for dialog in self.open_dialogs:
            if hasattr(dialog, 'idea_id') and dialog.idea_id == idea_id and idea_id is not None:
                dialog.activateWindow(); return
        dialog = EditDialog(self.db, idea_id=idea_id, category_id_for_new=category_id_for_new, parent=None)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.data_saved.connect(self._refresh_all)
        dialog.finished.connect(lambda: self.open_dialogs.remove(dialog) if dialog in self.open_dialogs else None)
        self.open_dialogs.append(dialog)
        dialog.show(); dialog.activateWindow()
        
    def _extract_single(self, idea_id):
        data = self.db.get_idea(idea_id)
        if not data: self._show_tooltip('⚠️ 数据不存在', 1500); return
        content = data['content'] or ""
        QApplication.clipboard().setText(content)
        preview = content.replace('\n', ' ')[:40] + ('...' if len(content)>40 else '')
        self._show_tooltip(f'✅ 内容已提取到剪贴板\n\n📋 {preview}', 2500)
        
    def _extract_all(self):
        data = self.db.get_ideas('', 'all', None)
        if not data: self._show_tooltip('🔭 暂无数据', 1500); return
        text = '\n'.join([f"【{d['title']}】\n{d['content']}\n{'-'*60}" for d in data])
        QApplication.clipboard().setText(text)
        self._show_tooltip(f'✅ 已提取 {len(data)} 条到剪贴板!', 2000)
        
    def _handle_extract_key(self):
        if len(self.selected_ids) == 1: self._extract_single(list(self.selected_ids)[0])
        else: self._show_tooltip('⚠️ 请选择一条笔记', 1500)
        
    def _handle_del_key(self):
        self._do_destroy() if self.curr_filter[0] == 'trash' else self._do_del()
        
    def _refresh_all(self):
        if not self.isVisible(): return
        QTimer.singleShot(10, self._load_data)
        QTimer.singleShot(10, self.sidebar.refresh)
        QTimer.singleShot(10, self._update_ui_state)
        
    def _show_tooltip(self, msg, dur=2000):
        QToolTip.showText(QCursor.pos(), msg, self)
        QTimer.singleShot(dur, QToolTip.hideText)
        
    def _set_filter(self, f_type, val):
        self.curr_filter = (f_type, val)
        self.selected_ids.clear()
        self.last_clicked_id = None
        self.current_tag_filter = None
        self.tag_filter_label.hide()
        titles = {'all':'全部数据','today':'今日数据','trash':'回收站','favorite':'我的收藏'}
        self.header_label.setText(f"📂 {next((c['name'] for c in self.db.get_categories() if c['id']==val), '文件夹')}" if f_type=='category' else titles.get(f_type, '灵感列表'))
        self._refresh_all()
        QTimer.singleShot(10, self._rebuild_filter_panel)
        
    def _on_filter_criteria_changed(self):
        self.current_page = 1
        self._load_data()
        
    def _on_new_data_in_category_requested(self, cat_id):
        self._open_edit_dialog(category_id_for_new=cat_id)
        
    # --- 窗口拖拽与调整大小逻辑 ---
    def _get_resize_area(self, pos):
        x, y = pos.x(), pos.y(); w, h = self.width(), self.height(); m = self.RESIZE_MARGIN
        areas = []
        if x < m: areas.append('left')
        elif x > w - m: areas.append('right')
        if y < m: areas.append('top')
        elif y > h - m: areas.append('bottom')
        return areas
        
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            areas = self._get_resize_area(e.pos())
            if areas: self._resize_area = areas; self._resize_start_pos = e.globalPos(); self._resize_start_geometry = self.geometry(); self._drag_pos = None
            elif e.y() < 40: self._drag_pos = e.globalPos() - self.frameGeometry().topLeft(); self._resize_area = None
            else: self._drag_pos = None; self._resize_area = None
            e.accept()
            
    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.NoButton:
            self._set_cursor_for_resize(self._get_resize_area(e.pos()))
            e.accept(); return
        if e.buttons() == Qt.LeftButton:
            if self._resize_area:
                d = e.globalPos() - self._resize_start_pos; r = self._resize_start_geometry; nr = r.adjusted(0,0,0,0)
                if 'left' in self._resize_area: 
                    nl = r.left() + d.x()
                    if r.right() - nl >= 600: nr.setLeft(nl)
                if 'right' in self._resize_area: 
                    nw = r.width() + d.x()
                    if nw >= 600: nr.setWidth(nw)
                if 'top' in self._resize_area:
                    nt = r.top() + d.y()
                    if r.bottom() - nt >= 400: nr.setTop(nt)
                if 'bottom' in self._resize_area:
                    nh = r.height() + d.y()
                    if nh >= 400: nr.setHeight(nh)
                self.setGeometry(nr)
                e.accept()
            elif self._drag_pos:
                self.move(e.globalPos() - self._drag_pos); e.accept()
                
    def mouseReleaseEvent(self, e):
        self._drag_pos = None; self._resize_area = None; self.setCursor(Qt.ArrowCursor)
        
    def _set_cursor_for_resize(self, a):
        if not a: self.setCursor(Qt.ArrowCursor); return
        if 'left' in a and 'top' in a: self.setCursor(Qt.SizeFDiagCursor)
        elif 'right' in a and 'bottom' in a: self.setCursor(Qt.SizeFDiagCursor)
        elif 'left' in a and 'bottom' in a: self.setCursor(Qt.SizeBDiagCursor)
        elif 'right' in a and 'top' in a: self.setCursor(Qt.SizeBDiagCursor)
        elif 'left' in a or 'right' in a: self.setCursor(Qt.SizeHorCursor)
        elif 'top' in a or 'bottom' in a: self.setCursor(Qt.SizeVerCursor)
        
    def mouseDoubleClickEvent(self, e):
        if e.y() < 40: self._toggle_maximize()
        
    def _toggle_maximize(self):
        if self.isMaximized(): self.showNormal(); self.max_btn.setIcon(create_svg_icon("win_max.svg", "#aaa"))
        else: self.showMaximized(); self.max_btn.setIcon(create_svg_icon("win_restore.svg", "#aaa"))

    def closeEvent(self, event):
        self._save_window_state(); self.closing.emit(); self.hide(); event.ignore()
        
    def _save_window_state(self):
        save_setting("main_window_geometry_hex", self.saveGeometry().toHex().data().decode())
        save_setting("main_window_maximized", self.isMaximized())
        if hasattr(self, "sidebar"): save_setting("sidebar_width", self.sidebar.width())

    def save_state(self): self._save_window_state()
    
    def _restore_window_state(self):
        geo = load_setting("main_window_geometry_hex")
        if geo: 
            try: self.restoreGeometry(QByteArray.fromHex(geo.encode()))
            except: self.resize(1000, 500)
        else: self.resize(1000, 500)
        if load_setting("main_window_maximized", False): self.showMaximized(); self.max_btn.setIcon(create_svg_icon("win_restore.svg", "#aaa"))
        else: self.max_btn.setIcon(create_svg_icon("win_max.svg", "#aaa"))
        sw = load_setting("sidebar_width")
        if sw and hasattr(self, "main_splitter"): QTimer.singleShot(0, lambda: self.main_splitter.setSizes([int(sw), self.width()-int(sw)]))

    def show_main_window(self): self.show(); self.activateWindow()