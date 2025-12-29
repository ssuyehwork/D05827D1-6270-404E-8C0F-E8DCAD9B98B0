# -*- coding: utf-8 -*-
# ui/main_window.py
import sys
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QLineEdit,
                               QPushButton, QLabel, QScrollArea, QShortcut, QMessageBox,
                               QApplication, QToolTip, QMenu, QFrame, QTextEdit, QDialog)
from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import QKeySequence, QCursor
from core.config import STYLES, COLORS
from core.settings import load_setting
from data.db_manager import DatabaseManager
from services.backup_service import BackupService
from ui.sidebar import Sidebar
from ui.cards import IdeaCard
from ui.dialogs import EditDialog
from ui.ball import FloatingBall
from ui.advanced_tag_selector import AdvancedTagSelector

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        print("[DEBUG] ========== MainWindow 初始化开始 ==========")
        self.db = DatabaseManager()
        self.curr_filter = ('all', None)
        self.selected_id = None
        self._drag_pos = None
        self.current_tag_filter = None
        
        self.setWindowFlags(Qt.FramelessWindowHint)
        self._setup_ui()
        self._load_data()
        
        self.ball = FloatingBall(self)
        
        # 加载悬浮球位置
        ball_pos = load_setting('floating_ball_pos')
        if ball_pos and isinstance(ball_pos, dict) and 'x' in ball_pos and 'y' in ball_pos:
            self.ball.move(ball_pos['x'], ball_pos['y'])
        else:
            # 如果没有保存的位置，则使用默认位置
            g = QApplication.desktop().screenGeometry()
            self.ball.move(g.width()-80, g.height()//2)
            
        self.ball.show()
        print("[DEBUG] MainWindow 初始化完成")

    def _setup_ui(self):
        self.setWindowTitle('RapidNotes Pro')
        self.resize(1300, 700)
        self.setStyleSheet(STYLES['main_window'])
        
        outer_layout = QVBoxLayout(self)
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
        QShortcut(QKeySequence("Delete"), self, self._handle_del_key)
        QShortcut(QKeySequence("Escape"), self, self._clear_tag_filter)

    def _create_titlebar(self):
        titlebar = QWidget()
        titlebar.setFixedHeight(40)
        titlebar.setStyleSheet(f"QWidget {{ background-color: {COLORS['bg_mid']}; border-bottom: 1px solid {COLORS['bg_light']}; }}")
        
        layout = QHBoxLayout(titlebar)
        layout.setContentsMargins(15, 0, 10, 0)
        layout.setSpacing(6)
        
        title = QLabel('💡 RapidNotes Pro')
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #4a90e2;")
        layout.addWidget(title)
        
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText('🔍 搜索灵感...')
        self.search.setFixedWidth(280)
        self.search.setFixedHeight(28)
        self.search.setStyleSheet(STYLES['input'] + "QLineEdit { border-radius: 14px; }")
        self.search.textChanged.connect(self._load_data)
        layout.addWidget(self.search)
        layout.addStretch()
        
        func_btn_style = f"QPushButton {{ background-color: {COLORS['primary']}; border: none; color: white; border-radius: 6px; font-size: 18px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; }} QPushButton:hover {{ background-color: #357abd; }}"
        ctrl_btn_style = f"QPushButton {{ background-color: transparent; border: none; color: #aaa; border-radius: 6px; font-size: 16px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; }} QPushButton:hover {{ background-color: rgba(255,255,255,0.1); color: white; }}"
        
        extract_btn = QPushButton('📤')
        extract_btn.setToolTip('批量提取全部')
        extract_btn.setStyleSheet(func_btn_style)
        extract_btn.clicked.connect(self._extract_all)
        layout.addWidget(extract_btn)
        
        new_btn = QPushButton('➕')
        new_btn.setToolTip('新建灵感 (Ctrl+N)')
        new_btn.setStyleSheet(func_btn_style)
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
                        ('del','🗑️',self._do_del), ('rest','♻️',self._do_restore), ('dest','❌',self._do_destroy)]:
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
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setAlignment(Qt.AlignTop)
        self.list_layout.setSpacing(10)
        self.list_layout.setContentsMargins(20, 5, 20, 15)
        scroll.setWidget(self.list_container)
        layout.addWidget(scroll)
        
        return panel

    def _create_tag_panel(self):
        panel = QWidget()
        panel.setStyleSheet(f"QWidget {{ background-color: {COLORS['bg_mid']}; border-left: 1px solid {COLORS['bg_light']}; }}")
        panel.setFixedWidth(220)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        header = QHBoxLayout()
        title = QLabel('🏷️ 标签云')
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #4a90e2;")
        header.addWidget(title)
        
        self.clear_tag_btn = QPushButton('✕')
        self.clear_tag_btn.setFixedSize(20, 20)
        self.clear_tag_btn.setStyleSheet(f"QPushButton {{ background-color: transparent; border: 1px solid #666; border-radius: 10px; color: #999; font-size: 12px; }} QPushButton:hover {{ background-color: {COLORS['danger']}; border-color: {COLORS['danger']}; color: white; }}")
        self.clear_tag_btn.setToolTip('清除标签筛选 (ESC)')
        self.clear_tag_btn.clicked.connect(self._clear_tag_filter)
        self.clear_tag_btn.hide()
        header.addWidget(self.clear_tag_btn)
        layout.addLayout(header)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background-color: {COLORS['bg_light']}; max-height: 1px;")
        layout.addWidget(line)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        self.tag_list_widget = QWidget()
        self.tag_list_layout = QVBoxLayout(self.tag_list_widget)
        self.tag_list_layout.setAlignment(Qt.AlignTop)
        self.tag_list_layout.setSpacing(6)
        self.tag_list_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll.setWidget(self.tag_list_widget)
        layout.addWidget(scroll)
        
        self._refresh_tag_panel()
        return panel

    def _refresh_tag_panel(self):
        while self.tag_list_layout.count():
            item = self.tag_list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        
        c = self.db.conn.cursor()
        c.execute('SELECT t.name, COUNT(it.idea_id) as cnt FROM tags t JOIN idea_tags it ON t.id = it.tag_id JOIN ideas i ON it.idea_id = i.id WHERE i.is_deleted = 0 GROUP BY t.id ORDER BY cnt DESC, t.name ASC')
        tags = c.fetchall()
        
        if not tags:
            empty = QLabel('暂无标签')
            empty.setStyleSheet("color: #666; font-style: italic; font-size: 12px;")
            empty.setAlignment(Qt.AlignCenter)
            self.tag_list_layout.addWidget(empty)
            return
            
        for tag_name, count in tags:
            is_active = (self.current_tag_filter == tag_name)
            btn = QPushButton(f'#{tag_name} ({count})')
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"QPushButton {{ background-color: {'#4a90e2' if is_active else 'rgba(74,144,226,0.15)'}; border: 1px solid {'#4a90e2' if is_active else 'rgba(74,144,226,0.3)'}; border-radius: 12px; padding: 6px 12px; text-align: left; color: {'white' if is_active else '#4a90e2'}; font-size: 12px; font-weight: {'bold' if is_active else 'normal'}; }} QPushButton:hover {{ background-color: #4a90e2; color: white; }}")
            btn.clicked.connect(lambda _, t=tag_name: self._filter_by_tag(t))
            self.tag_list_layout.addWidget(btn)

    def _filter_by_tag(self, tag_name):
        if self.current_tag_filter == tag_name:
            self._clear_tag_filter()
        else:
            self.current_tag_filter = tag_name
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

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and e.y() < 40:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(e.globalPos() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, e):
        if e.y() < 40: self._toggle_maximize()

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.max_btn.setText('□')
        else:
            self.showMaximized()
            self.max_btn.setText('❐')

    def quick_add_idea(self, text):
        """快速添加灵感（悬浮球拖拽触发）"""
        raw = text.strip()
        if not raw: return
        
        lines = raw.split('\n')
        title = lines[0][:25].strip() if lines else "快速记录"
        if len(lines) > 1 or len(lines[0]) > 25: title += "..."
        
        idea_id = self.db.add_idea(title, raw, COLORS['primary'], [], None)
        print(f"[DEBUG] 快速添加灵感成功，ID={idea_id}")
        
        self._show_tag_selector(idea_id)
        
        self._refresh_all()

    def _show_tag_selector(self, idea_id):
        """显示标签选择浮窗"""
        print(f"[DEBUG] 显示标签选择器，idea_id={idea_id}")
        
        tag_selector = AdvancedTagSelector(self.db, idea_id, self)
        tag_selector.tags_confirmed.connect(lambda tags: self._on_tags_confirmed(idea_id, tags))
        tag_selector.show_at_cursor()

    def _on_tags_confirmed(self, idea_id, tags):
        """标签确认后的回调"""
        print(f"[DEBUG] 标签已确认，idea_id={idea_id}, tags={tags}")
        self._show_tooltip(f'✅ 已记录并绑定 {len(tags)} 个标签', 2000)
        self._refresh_all()

    def _set_filter(self, f_type, val):
        self.curr_filter = (f_type, val)
        self.selected_id = None
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
        print("[DEBUG] ========== _load_data 开始 ==========")
        while self.list_layout.count():
            w = self.list_layout.takeAt(0).widget()
            if w: w.deleteLater()
            
        self.cards = {}
        data_list = self.db.get_ideas(self.search.text(), *self.curr_filter)
        print(f"[DEBUG] 查询到 {len(data_list)} 条数据")
        
        if self.current_tag_filter:
            filtered = []
            for d in data_list:
                if self.current_tag_filter in self.db.get_tags(d[0]):
                    filtered.append(d)
            data_list = filtered
            print(f"[DEBUG] 标签筛选后剩余 {len(data_list)} 条")
            
        if not data_list:
            self.list_layout.addWidget(QLabel("📭 空空如也", alignment=Qt.AlignCenter, styleSheet="color:#666;font-size:16px;margin-top:50px"))
            
        for d in data_list:
            c = IdeaCard(d, self.db)
            
            c.clicked.connect(self._on_select)
            print(f"[DEBUG] 卡片 ID={d[0]} clicked 信号连接完成")
            
            c.double_clicked.connect(self._extract_single)
            print(f"[DEBUG] 卡片 ID={d[0]} double_clicked 信号连接到 _extract_single")
            
            c.setContextMenuPolicy(Qt.CustomContextMenu)
            c.customContextMenuRequested.connect(lambda pos, iid=d[0]: self._show_card_menu(iid, pos))
            
            self.list_layout.addWidget(c)
            self.cards[d[0]] = c
            
        print(f"[DEBUG] 共创建 {len(self.cards)} 个卡片")
        self._update_ui_state()

    def _show_card_menu(self, idea_id, pos):
        self.selected_id = idea_id
        self._on_select(idea_id)
        
        data = self.db.get_idea(idea_id)
        if not data: return
        
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ background-color: {COLORS['bg_mid']}; color: white; border: 1px solid {COLORS['bg_light']}; border-radius: 6px; padding: 4px; }} QMenu::item {{ padding: 8px 20px; border-radius: 4px; }} QMenu::item:selected {{ background-color: {COLORS['primary']}; }} QMenu::separator {{ height: 1px; background: {COLORS['bg_light']}; margin: 4px 0px; }}")
        
        in_trash = (self.curr_filter[0] == 'trash')
        
        if not in_trash:
            menu.addAction('✏️ 编辑', self._do_edit)
            menu.addAction('📋 提取到剪贴板', lambda: self._extract_single(idea_id))
            menu.addSeparator()
            menu.addAction('📍 取消置顶' if data[4] else '📌 置顶', self._do_pin)
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
            menu.addAction('❌ 永久删除', self._do_destroy)
            
        card = self.cards.get(idea_id)
        if card: menu.exec_(card.mapToGlobal(pos))

    def _move_to_category(self, cat_id):
        if self.selected_id:
            self.db.move_category(self.selected_id, cat_id)
            self._refresh_all()
            self._show_tooltip('✅ 已移动分类')

    def _on_select(self, iid):
        print(f"[DEBUG] _on_select 被调用，idea_id={iid}")
        self.selected_id = iid
        for k, c in self.cards.items():
            c.update_selection(k == iid)
        self._update_ui_state()

    def _update_ui_state(self):
        in_trash = (self.curr_filter[0] == 'trash')
        has_sel = (self.selected_id is not None)
        
        for k in ['pin', 'fav', 'edit', 'del']:
            self.btns[k].setVisible(not in_trash)
            self.btns[k].setEnabled(has_sel)
            
        for k in ['rest', 'dest']:
            self.btns[k].setVisible(in_trash)
            self.btns[k].setEnabled(has_sel)
            
        if has_sel and not in_trash:
            d = self.db.get_idea(self.selected_id)
            if d:
                self.btns['pin'].setText('📍' if not d[4] else '📌')
                self.btns['fav'].setText('☆' if not d[5] else '⭐')

    def _show_tooltip(self, msg, dur=2000):
        QToolTip.showText(QCursor.pos(), msg, self)
        QTimer.singleShot(dur, QToolTip.hideText)

    def new_idea(self):
        print("[DEBUG] new_idea 被调用")
        if EditDialog(self.db).exec_(): self._refresh_all()

    def _do_edit(self):
        print(f"[DEBUG] ========== _do_edit 被调用 ========== selected_id={self.selected_id}")
        if self.selected_id and EditDialog(self.db, self.selected_id).exec_(): self._refresh_all()

    def _do_pin(self):
        if self.selected_id:
            self.db.toggle_field(self.selected_id, 'is_pinned')
            self._load_data()

    def _do_fav(self):
        if self.selected_id:
            self.db.toggle_field(self.selected_id, 'is_favorite')
            self._refresh_all()

    def _do_del(self):
        if self.selected_id:
            self.db.set_deleted(self.selected_id, True)
            self.selected_id = None
            self._refresh_all()

    def _do_restore(self):
        if self.selected_id:
            self.db.set_deleted(self.selected_id, False)
            self.selected_id = None
            self._refresh_all()

    def _do_destroy(self):
        if self.selected_id and QMessageBox.Yes == QMessageBox.warning(self, '⚠️ 警告', '确定永久删除？\n此操作不可恢复！', QMessageBox.Yes | QMessageBox.No):
            self.db.delete_permanent(self.selected_id)
            self.selected_id = None
            self._refresh_all()

    def _refresh_all(self):
        self._load_data()
        self.sidebar.refresh()
        self._update_ui_state()
        self._refresh_tag_panel()

    def _extract_single(self, idea_id):
        """双击直接提取正文内容到剪贴板"""
        print(f"[DEBUG] _extract_single 被调用，idea_id={idea_id}")
        
        data = self.db.get_idea(idea_id)
        if not data:
            self._show_tooltip('⚠️ 数据不存在', 1500)
            return
            
        # 直接提取笔记的全部正文内容
        content_to_copy = data[2] if data[2] else ""
        QApplication.clipboard().setText(content_to_copy)
        
        # 更新提示信息，显示正文预览
        preview = content_to_copy.replace('\n', ' ')[:40] + ('...' if len(content_to_copy) > 40 else '')
        self._show_tooltip(f'✅ 内容已提取到剪贴板\n\n📋 {preview}', 2500)
        
        print(f"[DEBUG] 纯文本内容已复制到剪贴板: {preview}...")

    def _extract_all(self):
        data = self.db.get_ideas('', 'all', None)
        if not data:
            self._show_tooltip('📭 暂无数据', 1500)
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
        self._show_tooltip(f'✅ 已提取 {len(data)} 条到剪贴板！', 2000)

    def _handle_del_key(self):
        self._do_destroy() if self.curr_filter[0] == 'trash' else self._do_del()

    def _handle_extract_key(self):
        """处理 Ctrl+T 快捷键，提取选中笔记的正文"""
        if self.selected_id:
            self._extract_single(self.selected_id)
        else:
            self._show_tooltip('⚠️ 请先选择一条笔记', 1500)

    def show_main_window(self):
        self.show()
        self.activateWindow()

    def quit_app(self):
        BackupService.run_backup()
        QApplication.quit()

    def closeEvent(self, e):
        BackupService.run_backup()
        self.hide()
        e.ignore()
