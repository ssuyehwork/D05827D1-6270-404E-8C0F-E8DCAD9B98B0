# -*- coding: utf-8 -*-
# ui/main_window.py
import sys
import math
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QSplitter, 
                               QLabel, QFrame, QMessageBox, QApplication, 
                               QToolTip, QMenu, QGraphicsDropShadowEffect, QPushButton,
                               QShortcut)
from PyQt5.QtCore import Qt, QTimer, QPoint, pyqtSignal, QByteArray, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QKeySequence, QCursor, QColor

from core.config import STYLES, COLORS
from core.settings import load_setting, save_setting
from ui.sidebar import Sidebar
from ui.card_list_view import CardListView 
from ui.dialogs import EditDialog
from services.preview_service import PreviewService
from ui.utils import create_svg_icon
from ui.filter_panel import FilterPanel 

# 引用组件
from ui.main_window_parts.header_bar import HeaderBar
from ui.main_window_parts.metadata_panel import MetadataPanel

class MainWindow(QWidget):
    closing = pyqtSignal()
    RESIZE_MARGIN = 8

    def __init__(self, service):
        super().__init__()
        QApplication.setQuitOnLastWindowClosed(False)
        self.service = service
        self.preview_service = PreviewService(self.service, self)
        
        self.curr_filter = ('all', None)
        self.selected_ids = set()
        self.current_tag_filter = None
        self.last_clicked_id = None 
        self.card_ordered_ids = []
        
        # 缓存与分页
        self.cached_metadata = []
        self.filtered_ids = []
        self.cards_cache = {}
        self.current_page = 1
        self.page_size = 100
        self.total_pages = 1
        
        # 文件夹数据缓存
        self.current_sub_folders = []
        
        # [新增] 递归显示模式状态
        self.is_recursive_mode = False
        
        self.open_dialogs = []
        self.is_metadata_panel_visible = False
        
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
        
        # === 1. 顶部标题栏 ===
        self.header = HeaderBar(self)
        self.header.search_changed.connect(lambda: self._set_page(1))
        self.header.search_changed.connect(self._rebuild_filter_panel)
        self.header.search_history_added.connect(self._add_search_to_history)
        self.header.page_changed.connect(self._set_page)
        self.header.window_minimized.connect(self.showMinimized)
        self.header.window_maximized.connect(self._toggle_maximize)
        self.header.window_closed.connect(self.close)
        self.header.toggle_filter.connect(self._toggle_filter_panel)
        self.header.toggle_metadata.connect(self._toggle_metadata_panel_state)
        self.header.new_idea_requested.connect(self.new_idea)
        self.header.refresh_requested.connect(self._refresh_all)
        
        outer_layout.addWidget(self.header)
        
        # === 2. 中央内容区 (Splitter) ===
        central_content = QWidget()
        central_layout = QHBoxLayout(central_content)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        
        # 左侧边栏
        self.sidebar = Sidebar(self.service)
        self.sidebar.filter_changed.connect(self._set_filter)
        self.sidebar.data_changed.connect(self._load_data)
        self.sidebar.new_data_requested.connect(self._on_new_data_in_category_requested)
        self.sidebar.items_moved.connect(self._handle_items_moved)
        self.sidebar.setMinimumWidth(200)
        
        # 中间卡片区 (包含操作栏)
        middle_panel = self._create_middle_panel()

        # 右侧元数据面板 (使用新组件)
        self.metadata_panel = MetadataPanel(self.service)
        self.metadata_panel.setMinimumWidth(0)
        self.metadata_panel.hide()
        
        # 连接元数据面板信号
        self.metadata_panel.title_changed.connect(self._handle_title_change)
        self.metadata_panel.tag_added.connect(self._handle_tag_add)

        # 组装 Splitter
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
        
        # 3. 悬浮筛选器
        self.filter_panel = FilterPanel()
        self.filter_panel.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.filter_panel.setAttribute(Qt.WA_TranslucentBackground)
        self.filter_panel.filterChanged.connect(self._on_filter_criteria_changed)
        self.filter_panel.hide()
        
        self._setup_shortcuts()
        self._restore_window_state()

    # --- 逻辑处理 ---
    def _handle_title_change(self, idea_id, new_title):
        self.service.update_field(idea_id, 'title', new_title)
        card = self.card_list_view.get_card(idea_id)
        if card:
            data = self.service.get_idea(idea_id, include_blob=True)
            if data: card.update_data(data)

    def _handle_tag_add(self, tags):
        if not self.selected_ids or not tags: return
        self.service.add_tags_to_multiple_ideas(list(self.selected_ids), tags)
        self._refresh_all()

    def _handle_items_moved(self, idea_ids):
        """轻量级处理器，仅从视图中移除卡片"""
        if not idea_ids: return
        for iid in idea_ids:
            self.card_list_view.remove_card(iid)
            if iid in self.selected_ids:
                self.selected_ids.remove(iid)
        self._update_ui_state()

    def _set_page(self, page_num):
        if page_num < 1: page_num = 1
        self.current_page = page_num
        self._load_data()

    def _update_pagination_ui(self):
        self.header.update_pagination(self.current_page, self.total_pages)

    def _create_middle_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        act_bar = QHBoxLayout()
        act_bar.setSpacing(4)
        act_bar.setContentsMargins(20, 10, 20, 10)
        
        self.header_icon = QLabel()
        self.header_icon.setPixmap(create_svg_icon("all_data.svg", COLORS['primary']).pixmap(20, 20))
        act_bar.addWidget(self.header_icon)
        
        self.header_label = QLabel('全部数据')
        self.header_label.setStyleSheet("font-size:18px;font-weight:bold;")
        act_bar.addWidget(self.header_label)
        
        self.tag_filter_label = QLabel()
        self.tag_filter_label.setStyleSheet(f"background-color: {COLORS['primary']}; color: white; border-radius: 10px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
        self.tag_filter_label.hide()
        act_bar.addWidget(self.tag_filter_label)
        act_bar.addStretch()

        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("color: #444;")
        act_bar.addWidget(separator)
        
        self.btns = {}
        btn_defs = [
            ('pin', 'action_pin.svg', self._do_pin),
            ('fav', 'action_fav.svg', self._do_fav),
            ('edit', 'action_edit.svg', self._do_edit),
            ('extract', 'action_export.svg', self._do_extract_selected), 
            ('del', 'action_delete.svg', self._do_del),
            ('rest', 'action_restore.svg', self._do_restore),
            ('dest', 'action_delete.svg', self._do_destroy)
        ]
        
        style = f"QPushButton {{ background-color: {COLORS['bg_light']}; border: 1px solid #444; border-radius: 6px; min-width: 32px; min-height: 32px; }} QPushButton:hover {{ background-color: #505050; border: 1px solid #999; }} QPushButton:pressed {{ background-color: #222; }} QPushButton:disabled {{ background-color: transparent; border: 1px solid #2d2d2d; opacity: 0.5; }}"
        
        for k, icon_name, f in btn_defs:
            b = QPushButton()
            b.setIcon(create_svg_icon(icon_name, '#aaa'))
            b.setStyleSheet(style)
            b.clicked.connect(f)
            b.setEnabled(False)
            act_bar.addWidget(b)
            self.btns[k] = b
            
        layout.addLayout(act_bar)
        
        self.card_list_view = CardListView(self.service, self)
        self.card_list_view.selection_cleared.connect(self._clear_all_selections)
        self.card_list_view.card_selection_requested.connect(self._handle_selection_request)
        self.card_list_view.card_double_clicked.connect(self._extract_single)
        self.card_list_view.card_context_menu_requested.connect(self._show_card_menu)
        
        # 连接点击文件夹的信号，实现导航
        self.card_list_view.folder_clicked.connect(self._on_folder_clicked)
        # [新增] 连接递归模式切换信号
        self.card_list_view.recursive_mode_changed.connect(self._on_recursive_mode_changed)
        
        layout.addWidget(self.card_list_view)
        return panel

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+T"), self, self._handle_extract_key)
        QShortcut(QKeySequence("Ctrl+N"), self, self.new_idea)
        QShortcut(QKeySequence("Ctrl+W"), self, self.close)
        QShortcut(QKeySequence("Ctrl+A"), self, self._select_all)
        QShortcut(QKeySequence("Ctrl+F"), self, self.header.search.setFocus)
        self.sidebar.filter_changed.connect(self._rebuild_filter_panel)
        self.header.search_changed.connect(self._rebuild_filter_panel)
        QShortcut(QKeySequence("Ctrl+B"), self, self._toggle_sidebar)
        QShortcut(QKeySequence("Ctrl+I"), self, self._toggle_metadata_panel)
        QShortcut(QKeySequence("Ctrl+G"), self, self._toggle_filter_panel)
        QShortcut(QKeySequence("Delete"), self, self._handle_del_key)
        QShortcut(QKeySequence("Ctrl+S"), self, self._do_lock)
        QShortcut(QKeySequence("Ctrl+E"), self, self._do_fav)
        QShortcut(QKeySequence("Ctrl+P"), self, self._do_pin)
        for i in range(6): QShortcut(QKeySequence(f"Ctrl+{i}"), self, lambda r=i: self._do_set_rating(r))
        self.space_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.space_shortcut.setContext(Qt.WindowShortcut)
        self.space_shortcut.activated.connect(lambda: self.preview_service.toggle_preview(self.selected_ids))

    def _on_recursive_mode_changed(self, enabled):
        """处理递归模式切换"""
        self.is_recursive_mode = enabled
        self._load_data() # 重新加载数据

    def _get_all_descendant_ids(self, root_id, all_categories):
        """递归获取所有子孙分类 ID"""
        ids = []
        children = [c for c in all_categories if c[2] == root_id] # c[2] is parent_id
        for child in children:
            child_id = child[0]
            ids.append(child_id)
            ids.extend(self._get_all_descendant_ids(child_id, all_categories))
        return ids

    def _load_data(self):
        self.cards_cache.clear()
        
        # 1. 获取基础元数据（当前层级）
        self.cached_metadata = self.service.get_metadata(self.header.search.text(), self.curr_filter[0], self.curr_filter[1])
        
        # [关键修复] 递归逻辑：必须确保当前选中的是具体分类（ID不为None），避免“未分类”显示所有内容
        if self.is_recursive_mode and self.curr_filter[0] == 'category' and self.curr_filter[1] is not None:
            current_cat_id = self.curr_filter[1]
            all_categories = self.service.get_categories()
            
            # 获取所有子孙 ID
            descendant_ids = self._get_all_descendant_ids(current_cat_id, all_categories)
            
            # 循环获取子孙分类的数据并合并
            for sub_id in descendant_ids:
                sub_data = self.service.get_metadata(self.header.search.text(), 'category', sub_id)
                self.cached_metadata.extend(sub_data)
        
        # 2. 获取子文件夹
        self.current_sub_folders = []
        # [关键修复] 只有在浏览“具体分类”时才显示子文件夹。
        # 如果是“未分类”（ID为None），坚决不加载顶级文件夹。
        if self.curr_filter[0] == 'category' and self.curr_filter[1] is not None:
            current_cat_id = self.curr_filter[1]
            all_categories = self.service.get_categories() 
            all_counts = self.service.get_counts().get('categories', {})
            
            for cat in all_categories:
                if cat[2] == current_cat_id:
                    count = all_counts.get(cat[0], 0)
                    self.current_sub_folders.append((cat, count))
                    
        # 3. 标签筛选
        if self.current_tag_filter:
            new_cache = []
            for item in self.cached_metadata:
                if self.current_tag_filter in item['tags']: new_cache.append(item)
            self.cached_metadata = new_cache
            
        self._apply_filters_and_render()
        if self.is_metadata_panel_visible: self._rebuild_filter_panel()

    def _apply_filters_and_render(self):
        criteria = self.filter_panel.get_checked_criteria()
        matched_ids = []
        for item in self.cached_metadata:
            match = True
            if criteria:
                if 'stars' in criteria and item['rating'] not in criteria['stars']: match = False
                if match and 'colors' in criteria and item['color'] not in criteria['colors']: match = False
                if match and 'types' in criteria and (item['item_type'] or 'text') not in criteria['types']: match = False
                if match and 'tags' in criteria:
                    if not any(tag in item['tags'] for tag in criteria['tags']): match = False
                if match and 'date_create' in criteria:
                    from datetime import datetime, timedelta
                    created_dt = datetime.strptime(item['created_at'], "%Y-%m-%d %H:%M:%S")
                    created_date = created_dt.date(); now_date = datetime.now().date()
                    date_match = False
                    for d_opt in criteria['date_create']:
                        if d_opt == 'today' and created_date == now_date: date_match = True
                        elif d_opt == 'yesterday' and created_date == now_date - timedelta(days=1): date_match = True
                        elif d_opt == 'week' and created_date >= now_date - timedelta(days=6): date_match = True
                        elif d_opt == 'month' and created_date.year == now_date.year and created_date.month == now_date.month: date_match = True
                    if not date_match: match = False
            if match: matched_ids.append(item['id'])
                
        self.filtered_ids = matched_ids
        total_items = len(self.filtered_ids)
        self.total_pages = math.ceil(total_items / self.page_size) if total_items > 0 else 1
        if self.current_page > self.total_pages: self.current_page = self.total_pages
        if self.current_page < 1: self.current_page = 1
        self._render_current_page()

    def _render_current_page(self):
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = start_idx + self.page_size
        page_ids = self.filtered_ids[start_idx:end_idx]
        ids_to_fetch = [iid for iid in page_ids if iid not in self.cards_cache]
        if ids_to_fetch:
            new_details = self.service.get_details(ids_to_fetch)
            for d in new_details: self.cards_cache[d['id']] = d
        data_list = [self.cards_cache[iid] for iid in page_ids if iid in self.cards_cache]
        
        # 将子文件夹数据传给 CardListView
        # 注意：只有第一页才显示子文件夹
        folders_to_show = self.current_sub_folders if self.current_page == 1 else []
        self.card_list_view.render_cards(data_list, sub_folders=folders_to_show)
        
        self.card_ordered_ids = [d['id'] for d in data_list]
        self._update_pagination_ui()
        self._update_ui_state()

    def _on_folder_clicked(self, cat_id):
        """点击卡片区域的文件夹时，跳转到该分类"""
        self._set_filter('category', cat_id)
        # 切换分类时，重置递归状态
        self.is_recursive_mode = False
        self.card_list_view.set_recursive_mode(False) 

    def _on_filter_criteria_changed(self):
        self.current_page = 1
        self._apply_filters_and_render()

    def _toggle_sidebar(self):
        is_collapsed = self.sidebar.width() == 60
        target_width = 280 if is_collapsed else 60
        self.sidebar_animation = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self.sidebar_animation.setDuration(300)
        self.sidebar_animation.setStartValue(self.sidebar.width())
        self.sidebar_animation.setEndValue(target_width)
        self.sidebar_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.sidebar_animation.start()

    def _toggle_metadata_panel_state(self, checked):
        if checked: self._show_metadata_panel()
        else: self._hide_metadata_panel()

    def _show_metadata_panel(self):
        if self.is_metadata_panel_visible: return
        self.is_metadata_panel_visible = True
        self.header.set_metadata_active(True)
        save_setting("metadata_panel_visible", True)
        self.metadata_panel.show()
        self.metadata_panel.setMaximumWidth(0)
        self.metadata_animation = QPropertyAnimation(self.metadata_panel, b"maximumWidth")
        self.metadata_animation.setDuration(250)
        self.metadata_animation.setStartValue(0)
        self.metadata_animation.setEndValue(240)
        self.metadata_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.metadata_animation.valueChanged.connect(lambda v: self.metadata_panel.setMinimumWidth(v))
        self.metadata_animation.finished.connect(lambda: self.card_list_view.recalc_layout())
        self.metadata_animation.start()

    def _hide_metadata_panel(self):
        if not self.is_metadata_panel_visible: return
        self.is_metadata_panel_visible = False
        self.header.set_metadata_active(False)
        save_setting("metadata_panel_visible", False)
        self.metadata_animation = QPropertyAnimation(self.metadata_panel, b"maximumWidth")
        self.metadata_animation.setDuration(250)
        self.metadata_animation.setStartValue(self.metadata_panel.width())
        self.metadata_animation.setEndValue(0)
        self.metadata_animation.setEasingCurve(QEasingCurve.InCubic)
        self.metadata_animation.valueChanged.connect(lambda v: self.metadata_panel.setMinimumWidth(v))
        self.metadata_animation.finished.connect(self.metadata_panel.hide)
        self.metadata_animation.finished.connect(lambda: self.card_list_view.recalc_layout())
        self.metadata_animation.start()

    def _toggle_metadata_panel(self):
        if self.is_metadata_panel_visible: self._hide_metadata_panel()
        else: self._show_metadata_panel()

    def _toggle_filter_panel(self):
        if self.filter_panel.isVisible():
            self.filter_panel.hide()
            self.header.set_filter_active(False)
        else:
            saved_size = load_setting('filter_panel_size')
            if saved_size and 'width' in saved_size: self.filter_panel.resize(saved_size['width'], saved_size['height'])
            main_geo = self.geometry()
            x = main_geo.right() - self.filter_panel.width() - 20
            y = main_geo.bottom() - self.filter_panel.height() - 20
            self.filter_panel.move(x, y)
            self.filter_panel.show(); self.filter_panel.raise_(); self.filter_panel.activateWindow()
            self.header.set_filter_active(True)
            self._rebuild_filter_panel()

    def _rebuild_filter_panel(self):
        stats = self.service.get_filter_stats(self.header.search.text(), self.curr_filter[0], self.curr_filter[1])
        self.filter_panel.update_stats(stats)

    def _add_search_to_history(self):
        search_text = self.header.search.text().strip()
        if search_text: self.header.search.add_history_entry(search_text)
        
    def new_idea(self): self._open_edit_dialog()
        
    def _do_edit(self):
        if len(self.selected_ids) == 1:
            idea_id = list(self.selected_ids)[0]
            status = self.service.get_lock_status([idea_id])
            if status.get(idea_id, 0): return
            self._open_edit_dialog(idea_id=idea_id)
            
    def _open_edit_dialog(self, idea_id=None, category_id_for_new=None):
        for dialog in self.open_dialogs:
            if hasattr(dialog, 'idea_id') and dialog.idea_id == idea_id and idea_id is not None:
                dialog.activateWindow(); return
        dialog = EditDialog(self.service, idea_id=idea_id, category_id_for_new=category_id_for_new, parent=None)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.data_saved.connect(self._refresh_all)
        dialog.finished.connect(lambda: self.open_dialogs.remove(dialog) if dialog in self.open_dialogs else None)
        self.open_dialogs.append(dialog)
        dialog.show(); dialog.activateWindow()
        
    def _extract_single(self, idea_id):
        data = self.service.get_idea(idea_id)
        if not data: self._show_tooltip('数据不存在', 1500); return
        content = data['content'] or ""
        QApplication.clipboard().setText(content)
        preview = content.replace('\n', ' ')[:40] + ('...' if len(content)>40 else '')
        self._show_tooltip(f'内容已提取到剪贴板\n\n{preview}', 2500)

    def _do_extract_selected(self):
        if not self.selected_ids: return
        ideas = []
        for iid in self.selected_ids:
            data = self.service.get_idea(iid)
            if data: ideas.append(data)
        if not ideas: return
        if len(ideas) == 1: self._extract_single(ideas[0]['id'])
        else:
            text = '\n'.join([f"【{d['title']}】\n{d['content']}\n{'-'*60}" for d in ideas])
            QApplication.clipboard().setText(text)
            self._show_tooltip(f'已提取 {len(ideas)} 条选中笔记到剪贴板!', 2000)
        
    def _handle_extract_key(self):
        if len(self.selected_ids) == 1: self._extract_single(list(self.selected_ids)[0])
        else: self._show_tooltip('请选择一条笔记', 1500)
        
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
        if self.curr_filter == (f_type, val): return
        self.curr_filter = (f_type, val)
        self.selected_ids.clear()
        self.last_clicked_id = None
        self.current_tag_filter = None
        self.tag_filter_label.hide()
        self.cards_cache.clear()
        self.card_list_view.clear_all()
        
        self.is_recursive_mode = False
        self.card_list_view.set_recursive_mode(False) 

        # ==========================================
        # 【修复】切换分类时，强制重置高级筛选器
        # ==========================================
        if hasattr(self, 'filter_panel'):
            self.filter_panel.blockSignals(True) # 暂时屏蔽信号，避免触发多余的刷新
            self.filter_panel.reset_filters()
            self.filter_panel.blockSignals(False)
        
        titles = {'all':'全部数据','today':'今日数据','trash':'回收站','favorite':'我的收藏'}
        cat_name = '文件夹'
        if f_type == 'category':
            for c in self.service.get_categories():
                if c['id'] == val: cat_name = c['name']; break
        self.header_label.setText(f"{cat_name}" if f_type=='category' else titles.get(f_type, '灵感列表'))
        icon_map = {'all': 'all_data.svg', 'today': 'today.svg', 'uncategorized': 'uncategorized.svg', 'untagged': 'untagged.svg', 'bookmark': 'bookmark.svg', 'trash': 'trash.svg', 'category': 'folder.svg'}
        self.header_icon.setPixmap(create_svg_icon(icon_map.get(f_type, 'all_data.svg'), COLORS['primary']).pixmap(20, 20))
        
        self._refresh_all()
        QTimer.singleShot(10, self._rebuild_filter_panel)
    
    def _on_new_data_in_category_requested(self, cat_id):
        self._open_edit_dialog(category_id_for_new=cat_id)
    
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
        if len(self.selected_ids) == len(self.card_ordered_ids): self.selected_ids.clear()
        else: self.selected_ids = set(self.card_ordered_ids)
        self._update_all_card_selections()
        self._update_ui_state()

    def _do_pin(self):
        if self.selected_ids:
            for iid in self.selected_ids: self.service.toggle_field(iid, 'is_pinned')
            self._load_data()

    def _do_fav(self):
        if self.selected_ids:
            any_not_favorited = any(not self.service.get_idea(iid)['is_favorite'] for iid in self.selected_ids)
            for iid in self.selected_ids: self.service.set_favorite(iid, any_not_favorited)
            self._load_data(); self._update_ui_state(); self.sidebar.refresh()

    def _do_del(self):
        if not self.selected_ids: return
        valid_ids = self._get_valid_ids_ignoring_locked(self.selected_ids)
        if not valid_ids: self._show_tooltip("🔒 锁定项目无法删除", 1500); return
        
        for iid in valid_ids:
            self.service.set_deleted(iid, True, emit_signal=False)
            self.card_list_view.remove_card(iid)
            
        self.selected_ids.clear()
        self._update_ui_state()
        self.sidebar.refresh()

    def _do_restore(self):
        if self.selected_ids:
            for iid in self.selected_ids:
                self.service.set_deleted(iid, False)
                self.card_list_view.remove_card(iid)
            self.selected_ids.clear()
            self._update_ui_state()
            self.sidebar.refresh()

    def _do_destroy(self):
        if self.selected_ids:
            if QMessageBox.Yes == QMessageBox.question(self, "永久删除", f'确定永久删除选中的 {len(self.selected_ids)} 项?\n此操作不可恢复!'):
                for iid in self.selected_ids:
                    self.service.delete_permanent(iid)
                    self.card_list_view.remove_card(iid)
                self.selected_ids.clear()
                self._update_ui_state()
                self.sidebar.refresh()

    def _do_set_rating(self, rating):
        if not self.selected_ids: return
        for idea_id in self.selected_ids:
            self.service.set_rating(idea_id, rating)
            card = self.card_list_view.get_card(idea_id)
            if card: card.update_data(self.service.get_idea(idea_id, include_blob=True))

    def _do_lock(self):
        if not self.selected_ids: return
        status_map = self.service.get_lock_status(list(self.selected_ids))
        any_unlocked = any(not locked for locked in status_map.values())
        self.service.set_locked(list(self.selected_ids), 1 if any_unlocked else 0)
        for iid in self.selected_ids:
            card = self.card_list_view.get_card(iid)
            if card: card.update_data(self.service.get_idea(iid, include_blob=True))
        self._update_ui_state()

    def _get_valid_ids_ignoring_locked(self, ids):
        status_map = self.service.get_lock_status(list(ids))
        return [iid for iid in ids if not status_map.get(iid, 0)]

    def _move_to_category(self, cat_id):
        if not self.selected_ids: return
        
        if cat_id is not None:
            recent_cats = load_setting('recent_categories', [])
            if cat_id in recent_cats: recent_cats.remove(cat_id)
            recent_cats.insert(0, cat_id)
            save_setting('recent_categories', recent_cats)

        ids_to_move = list(self.selected_ids)
        for iid in ids_to_move:
            self.service.move_category(iid, cat_id, emit_signal=False)
            self.card_list_view.remove_card(iid)
        
        self.selected_ids.clear()
        self._update_ui_state()
        self.sidebar.refresh()

    def _update_ui_state(self):
        in_trash = (self.curr_filter[0] == 'trash')
        selection_count = len(self.selected_ids)
        has_selection = selection_count > 0
        is_single = selection_count == 1
        
        for k in ['pin', 'fav', 'extract', 'del']: self.btns[k].setVisible(not in_trash)
        for k in ['rest', 'dest']: self.btns[k].setVisible(in_trash)
        self.btns['edit'].setVisible(not in_trash)
        self.btns['edit'].setEnabled(is_single)
        for k in ['pin', 'fav', 'extract', 'del', 'rest', 'dest']: self.btns[k].setEnabled(has_selection)
        
        if is_single and not in_trash:
            idea_id = list(self.selected_ids)[0]
            d = self.service.get_idea(idea_id)
            if d: self.btns['pin'].setIcon(create_svg_icon('pin_vertical.svg', '#e74c3c') if d['is_pinned'] else create_svg_icon('pin_tilted.svg', '#aaaaaa'))
        else:
            self.btns['pin'].setIcon(create_svg_icon('pin_tilted.svg', '#aaaaaa'))
            
        self.metadata_panel.refresh_state(self.selected_ids)

    def _handle_selection_request(self, iid, is_ctrl, is_shift):
        if is_shift and self.last_clicked_id is not None:
            try:
                start_index = self.card_ordered_ids.index(self.last_clicked_id)
                end_index = self.card_ordered_ids.index(iid)
                min_idx = min(start_index, end_index); max_idx = max(start_index, end_index)
                if not is_ctrl: self.selected_ids.clear()
                for idx in range(min_idx, max_idx + 1): self.selected_ids.add(self.card_ordered_ids[idx])
            except ValueError:
                self.selected_ids.clear(); self.selected_ids.add(iid); self.last_clicked_id = iid
        elif is_ctrl:
            if iid in self.selected_ids: self.selected_ids.remove(iid)
            else: self.selected_ids.add(iid)
            self.last_clicked_id = iid
        else:
            self.selected_ids.clear(); self.selected_ids.add(iid); self.last_clicked_id = iid
            
        self._update_all_card_selections()
        QTimer.singleShot(0, self._update_ui_state)

    def _show_card_menu(self, idea_id, pos):
        if idea_id not in self.selected_ids:
            self.selected_ids = {idea_id}
            self.last_clicked_id = idea_id
            self._update_all_card_selections()
            self._update_ui_state()
            
        data = self.service.get_idea(idea_id)
        if not data: return
        
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ background-color: {COLORS['bg_mid']}; color: white; border: 1px solid {COLORS['bg_light']}; border-radius: 6px; padding: 4px; }} QMenu::item {{ padding: 6px 10px 6px 5px; border-radius: 4px; }} QMenu::item:selected {{ background-color: {COLORS['primary']}; }} QMenu::separator {{ height: 1px; background: {COLORS['bg_light']}; margin: 4px 0px; }} QMenu::icon {{ position: absolute; left: 6px; top: 6px; }}")
        
        in_trash = (self.curr_filter[0] == 'trash')
        is_locked = data['is_locked']
        rating = data['rating']
        
        if not in_trash:
            menu.addAction(create_svg_icon('action_edit.svg', '#4a90e2'), '编辑', self._do_edit)
            menu.addAction(create_svg_icon('action_export.svg', '#1abc9c'), '提取(Ctrl+T)', lambda: self._extract_single(idea_id))
            menu.addSeparator()
            
            from PyQt5.QtWidgets import QAction, QActionGroup
            rating_menu = menu.addMenu(create_svg_icon('star.svg', '#f39c12'), "设置星级")
            star_group = QActionGroup(self)
            star_group.setExclusive(True)
            for i in range(1, 6):
                action = QAction(f"{'★'*i}", self, checkable=True)
                action.triggered.connect(lambda _, r=i: self._do_set_rating(r))
                if rating == i: action.setChecked(True)
                rating_menu.addAction(action); star_group.addAction(action)
            rating_menu.addSeparator()
            rating_menu.addAction("清除评级").triggered.connect(lambda: self._do_set_rating(0))
            
            menu.addAction(create_svg_icon('lock.svg', COLORS['success']) if is_locked else create_svg_icon('lock.svg', '#aaaaaa'), '解锁' if is_locked else '锁定 (Ctrl+S)', self._do_lock)
            menu.addSeparator()
            menu.addAction(create_svg_icon('pin_vertical.svg', '#e74c3c') if data['is_pinned'] else create_svg_icon('pin_tilted.svg', '#aaaaaa'), '取消置顶' if data['is_pinned'] else '置顶', self._do_pin)
            menu.addAction(create_svg_icon('bookmark.svg', '#ff6b81'), '取消书签' if data['is_favorite'] else '添加书签', self._do_fav)
            menu.addSeparator()
            cat_menu = menu.addMenu('移动到分类')
            
            # [优化] 仅显示最近使用的 15 个分类
            recent_cats = load_setting('recent_categories', [])
            all_cats = {c['id']: c for c in self.service.get_categories()}
            
            # 添加固定的“未分类”选项
            action_uncategorized = cat_menu.addAction(create_svg_icon('uncategorized.svg'), '未分类')
            action_uncategorized.triggered.connect(lambda: self._move_to_category(None))

            # 添加最近使用且仍然存在的分类
            count = 0
            for cat_id in recent_cats:
                if count >= 15: break
                if cat_id in all_cats:
                    cat = all_cats[cat_id]
                    color = cat.get('color') or '#cccccc'
                    action = cat_menu.addAction(create_svg_icon('branch.svg', color=color), cat['name'])
                    action.triggered.connect(lambda _, cid=cat['id']: self._move_to_category(cid))
                    count += 1
            menu.addSeparator()
            if not is_locked: menu.addAction(create_svg_icon('action_delete.svg', '#e74c3c'), '移至回收站', self._do_del)
            else: act = menu.addAction(create_svg_icon('action_delete.svg', '#555555'), '移至回收站 (已锁定)'); act.setEnabled(False)
        else:
            menu.addAction(create_svg_icon('action_restore.svg', '#2ecc71'), '恢复', self._do_restore)
            menu.addAction(create_svg_icon('trash.svg', '#e74c3c'), '永久删除', self._do_destroy)
            
        card = self.card_list_view.get_card(idea_id)
        if card: menu.exec_(card.mapToGlobal(pos))

    # --- 窗口拖拽与调整大小逻辑 ---
    def _get_resize_area(self, pos):
        x, y = pos.x(), pos.y(); w, h = self.width(), self.height(); m = self.RESIZE_MARGIN
        areas = []
        if x < m: areas.append('left')
        elif x > w - m: areas.append('right')
        if y < m: areas.append('top')
        elif y > h - m: areas.append('bottom')
        return areas
        
    def _set_cursor_for_resize(self, a):
        if not a: self.setCursor(Qt.ArrowCursor); return
        if 'left' in a and 'top' in a: self.setCursor(Qt.SizeFDiagCursor)
        elif 'right' in a and 'bottom' in a: self.setCursor(Qt.SizeFDiagCursor)
        elif 'left' in a and 'bottom' in a: self.setCursor(Qt.SizeBDiagCursor)
        elif 'right' in a and 'top' in a: self.setCursor(Qt.SizeBDiagCursor)
        elif 'left' in a or 'right' in a: self.setCursor(Qt.SizeHorCursor)
        elif 'top' in a or 'bottom' in a: self.setCursor(Qt.SizeVerCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            areas = self._get_resize_area(event.pos())
            if areas: self.resize_area = areas; self.resize_start_pos = event.globalPos(); self.resize_start_geometry = self.geometry(); self._drag_pos = None
            elif event.y() < 40: self._drag_pos = event.globalPos() - self.frameGeometry().topLeft(); self.resize_area = None
            else: self._drag_pos = None; self.resize_area = None
            event.accept()
            
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.NoButton:
            self._set_cursor_for_resize(self._get_resize_area(event.pos()))
            event.accept(); return
        if event.buttons() == Qt.LeftButton:
            if self.resize_area:
                d = event.globalPos() - self.resize_start_pos; r = self.resize_start_geometry; nr = r.adjusted(0,0,0,0)
                if 'left' in self.resize_area: 
                    nl = r.left() + d.x()
                    if r.right() - nl >= 600: nr.setLeft(nl)
                if 'right' in self.resize_area: 
                    nw = r.width() + d.x()
                    if nw >= 600: nr.setWidth(nw)
                if 'top' in self.resize_area:
                    nt = r.top() + d.y()
                    if r.bottom() - nt >= 400: nr.setTop(nt)
                if 'bottom' in self.resize_area:
                    nh = r.height() + d.y()
                    if nh >= 400: nr.setHeight(nh)
                self.setGeometry(nr)
                event.accept()
            elif self._drag_pos:
                self.move(event.globalPos() - self._drag_pos); event.accept()
                
    def mouseReleaseEvent(self, event):
        self._drag_pos = None; self.resize_area = None; self.setCursor(Qt.ArrowCursor)
        
    def mouseDoubleClickEvent(self, event):
        if event.y() < 40: self._toggle_maximize()
        
    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.header.set_maximized_state(False)
        else:
            self.showMaximized()
            self.header.set_maximized_state(True)

    def closeEvent(self, event):
        self._save_window_state(); self.closing.emit(); self.hide(); event.ignore()
        
    def _save_window_state(self):
        save_setting("main_window_geometry_hex", self.saveGeometry().toHex().data().decode())
        save_setting("main_window_maximized", self.isMaximized())
        if hasattr(self, "sidebar"): save_setting("sidebar_width", self.sidebar.width())

    def refresh_logo(self):
        """刷新标题栏 Logo"""
        self.header.refresh_logo()

    def save_state(self):
        self._save_window_state()
    
    def _restore_window_state(self):
        geo = load_setting("main_window_geometry_hex")
        if geo: 
            try: self.restoreGeometry(QByteArray.fromHex(geo.encode()))
            except: self.resize(1000, 500)
        else: self.resize(1000, 500)
        
        if load_setting("main_window_maximized", False): 
            self.showMaximized()
            self.header.set_maximized_state(True)
        else: 
            self.header.set_maximized_state(False)
            
        sw = load_setting("sidebar_width")
        if sw and hasattr(self, "main_splitter"): QTimer.singleShot(0, lambda: self.main_splitter.setSizes([int(sw), self.width()-int(sw)]))

        # Restore metadata panel visibility
        if load_setting("metadata_panel_visible", False):
            self._show_metadata_panel()

    def show_main_window(self): self.show(); self.activateWindow()