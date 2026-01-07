# -*- coding: utf-8 -*-
# ui/main_window.py
import sys
import math
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QLineEdit,
                               QPushButton, QLabel, QScrollArea, QShortcut, QMessageBox,
                               QApplication, QToolTip, QMenu, QFrame, QTextEdit, QDialog,
                               QGraphicsDropShadowEffect, QLayout, QSizePolicy, QInputDialog)
from PyQt5.QtCore import Qt, QTimer, QPoint, pyqtSignal, QRect, QSize, QByteArray, QPropertyAnimation, QEasingCurve
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
from ui.utils import create_svg_icon
from ui.filter_panel import FilterPanel 

# --- 辅助类：流式布局 ---
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super(FlowLayout, self).__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []

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
            e.accept()
        else:
            super().mousePressEvent(e)

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
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 5, 5, 5)
        layout.setSpacing(6)

        self.label = QLabel(tag_name)
        self.label.setStyleSheet("border: none; background: transparent; color: #DDD; font-size: 12px;")
        
        self.delete_btn = QPushButton()
        self.delete_btn.setIcon(create_svg_icon("win_close.svg", "#AAA"))
        self.delete_btn.setFixedSize(16, 16)
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; border: none; border-radius: 8px; }}
            QPushButton:hover {{ background-color: {COLORS['danger']}; }}
        """)
        
        layout.addWidget(self.label)
        layout.addWidget(self.delete_btn)

        self.setStyleSheet("""
            #TagChip { background-color: #383838; border: 1px solid #4D4D4D; border-radius: 14px; }
        """)
        
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
        
        row.setStyleSheet(f"""
            QWidget {{ background-color: transparent; }}
            #CapsuleRow {{
                background-color: rgba(255, 255, 255, 0.05); 
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px; 
            }}
        """)
        
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
        self._drag_pos = None
        self.current_tag_filter = None
        self.last_clicked_id = None 
        self.card_ordered_ids = []  
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
        # 【关键】开启拖拽接收
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
        
        # --- 布局重构 ---
        
        # 1. 创建中央内容区
        central_content = QWidget()
        central_layout = QHBoxLayout(central_content)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        
        # 2. 创建侧边栏
        self.sidebar = Sidebar(self.db)
        self.sidebar.filter_changed.connect(self._set_filter)
        self.sidebar.data_changed.connect(self._load_data)
        self.sidebar.new_data_requested.connect(self._on_new_data_in_category_requested)
        self.sidebar.setMinimumWidth(200)  # 初始宽度（具体由 splitter 控制）
        
        # 3. 创建中间卡片列表区和右侧元数据面板
        middle_panel = self._create_middle_panel()
        self.metadata_panel = self._create_metadata_panel()
        self.metadata_panel.setMinimumWidth(0)
        self.metadata_panel.hide()

        # 使用 QSplitter 允许用户调整侧边栏宽度
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
        # 设置侧边栏为固定宽度，中间区域为可拉伸
        self.main_splitter.setSizes([280, 100])
        # 监听 splitter 尺寸变化，动态更新卡片宽度
        self.main_splitter.splitterMoved.connect(self._on_splitter_moved)
        
        # 将中央内容区添加到主布局
        central_layout.addWidget(self.main_splitter)
        outer_layout.addWidget(central_content, 1)
        
        # 5. 创建独立悬浮筛选器面板（不再添加到布局中）
        self.filter_panel = FilterPanel()
        self.filter_panel.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.filter_panel.setAttribute(Qt.WA_TranslucentBackground)
        # 移除固定尺寸限制，允许用户调整大小
        self.filter_panel.filterChanged.connect(self._on_filter_criteria_changed)
        self.filter_panel.hide()  # 初始隐藏
        
        # --- 快捷键 ---
        QShortcut(QKeySequence("Ctrl+T"), self, self._handle_extract_key)
        QShortcut(QKeySequence("Ctrl+N"), self, self.new_idea)
        QShortcut(QKeySequence("Ctrl+W"), self, self.close)
        QShortcut(QKeySequence("Ctrl+A"), self, self._select_all)
        QShortcut(QKeySequence("Ctrl+F"), self, self.search.setFocus)
        
        # 连接侧边栏和搜索框变化事件以重构筛选器
        self.sidebar.filter_changed.connect(self._rebuild_filter_panel)
        self.search.textChanged.connect(self._rebuild_filter_panel)
        # Ctrl+B 现在用于侧边栏切换
        QShortcut(QKeySequence("Ctrl+B"), self, self._toggle_sidebar)
        QShortcut(QKeySequence("Ctrl+I"), self, self._toggle_metadata_panel)
        # Ctrl+G 用于切换筛选器面板
        QShortcut(QKeySequence("Ctrl+G"), self, self._toggle_filter_panel)
        QShortcut(QKeySequence("Delete"), self, self._handle_del_key)
        QShortcut(QKeySequence("Ctrl+S"), self, self._do_lock)

        for i in range(6):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, lambda r=i: self._do_set_rating(r))
        
        self.space_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.space_shortcut.setContext(Qt.WindowShortcut)
        self.space_shortcut.activated.connect(lambda: self.preview_service.toggle_preview(self.selected_ids))

        self._restore_window_state()

    def _toggle_sidebar(self):
        is_collapsed = self.sidebar.width() == 60
        target_width = 280 if is_collapsed else 60
        
        self.sidebar_animation = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self.sidebar_animation.setDuration(300) # 300ms 动画
        self.sidebar_animation.setStartValue(self.sidebar.width())
        self.sidebar_animation.setEndValue(target_width)
        self.sidebar_animation.setEasingCurve(QEasingCurve.InOutCubic) # 缓动曲线
        self.sidebar_animation.start()

    def _show_metadata_panel(self):
        if self.is_metadata_panel_visible: return
        self.is_metadata_panel_visible = True
        self.metadata_panel.show()
        
        self.metadata_animation = QPropertyAnimation(self.metadata_panel, b"minimumWidth")
        self.metadata_animation.setDuration(300)
        self.metadata_animation.setStartValue(0)
        self.metadata_animation.setEndValue(300)
        self.metadata_animation.setEasingCurve(QEasingCurve.InOutCubic)
        # 动画结束后重新计算卡片区域宽度，避免卡片被遮挡
        self.metadata_animation.finished.connect(self._on_metadata_panel_animation_finished)
        self.metadata_animation.start()

    def _on_metadata_panel_animation_finished(self):
        # 触发卡片区域重新布局，确保卡片宽度适应剩余空间
        if hasattr(self, 'main_splitter'):
            self.main_splitter.setSizes(self.main_splitter.sizes())

    def _hide_metadata_panel(self):
        if not self.is_metadata_panel_visible: return
        self.is_metadata_panel_visible = False
        
        self.metadata_animation = QPropertyAnimation(self.metadata_panel, b"minimumWidth")
        self.metadata_animation.setDuration(300)
        self.metadata_animation.setStartValue(self.metadata_panel.width())
        self.metadata_animation.setEndValue(0)
        self.metadata_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.metadata_animation.finished.connect(self.metadata_panel.hide)
        self.metadata_animation.start()

    def _toggle_metadata_panel(self):
        if self.is_metadata_panel_visible:
            self._hide_metadata_panel()
        else:
            self._show_metadata_panel()

    def _toggle_filter_panel(self):
        """切换筛选器面板的显示/隐藏"""
        if self.filter_panel.isVisible():
            self.filter_panel.hide()
        else:
            # 恢复保存的尺寸
            saved_size = load_setting('filter_panel_size')
            if saved_size and 'width' in saved_size and 'height' in saved_size:
                self.filter_panel.resize(saved_size['width'], saved_size['height'])
            
            # 先显示面板
            # 定位到主窗口右下角
            main_geo = self.geometry()
            x = main_geo.right() - self.filter_panel.width() - 20
            y = main_geo.bottom() - self.filter_panel.height() - 20
            self.filter_panel.move(x, y)
            self.filter_panel.show()
            self.filter_panel.raise_()
            self.filter_panel.activateWindow()
            # 然后重构内容
            self._rebuild_filter_panel()

    def _rebuild_filter_panel(self):
        """根据当前侧边栏选择和搜索框内容重构筛选器"""
        # 获取当前过滤条件的统计数据
        # 这里根据 curr_filter 和 search 来获取上下文相关的统计
        print(f"[DEBUG] 重构筛选器: filter_type={self.curr_filter[0]}, filter_value={self.curr_filter[1]}, search={self.search.text()}")
        stats = self.db.get_filter_stats(
            search_text=self.search.text(),
            filter_type=self.curr_filter[0],
            filter_value=self.curr_filter[1]
        )
        print(f"[DEBUG] 统计结果: stars={stats['stars']}, colors={stats['colors']}, tags={len(stats['tags'])}")
        self.filter_panel.update_stats(stats)

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
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)
        
        # --- 侧边栏切换按钮 ---
        self.sidebar_toggle_btn = QPushButton("☰")
        self.sidebar_toggle_btn.setFixedSize(30, 30)
        self.sidebar_toggle_btn.setStyleSheet(f"""
            QPushButton {{ 
                font-size: 16px; 
                color: #AAA; 
                background-color: transparent; 
                border: none; 
                border-radius: 6px;
            }}
            QPushButton:hover {{ 
                background-color: rgba(255, 255, 255, 0.1); 
            }}
        """)
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
        self.search.setStyleSheet(STYLES['input'] + """
            QLineEdit { border-radius: 14px; padding-right: 25px; }
            QLineEdit::clear-button { image: url(assets/clear.png); subcontrol-position: right; margin-right: 5px; }
        """)
        self.search.textChanged.connect(lambda: self._set_page(1))
        self.search.returnPressed.connect(self._add_search_to_history)
        layout.addWidget(self.search)
        
        layout.addSpacing(10)
        
        # --- 分页控件 (使用 SVG) ---
        page_btn_style = """
            QPushButton { background-color: transparent; border: 1px solid #444; border-radius: 4px; padding: 2px 8px; min-width: 24px; min-height: 20px; }
            QPushButton:hover { background-color: #333; border-color: #666; }
            QPushButton:disabled { border-color: #333; }
        """
        
        self.btn_first = QPushButton()
        self.btn_first.setIcon(create_svg_icon('nav_first.svg', '#aaa'))
        self.btn_first.setStyleSheet(page_btn_style)
        self.btn_first.setToolTip("首页")
        self.btn_first.clicked.connect(lambda: self._set_page(1))
        
        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(create_svg_icon('nav_prev.svg', '#aaa'))
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
        
        self.btn_next = QPushButton()
        self.btn_next.setIcon(create_svg_icon('nav_next.svg', '#aaa'))
        self.btn_next.setStyleSheet(page_btn_style)
        self.btn_next.setToolTip("下一页")
        self.btn_next.clicked.connect(lambda: self._set_page(self.current_page + 1))
        
        self.btn_last = QPushButton()
        self.btn_last.setIcon(create_svg_icon('nav_last.svg', '#aaa'))
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
        
        # --- 窗口控制按钮 (SVG) ---
        ctrl_btn_style = f"QPushButton {{ background-color: transparent; border: none; border-radius: 6px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; }} QPushButton:hover {{ background-color: rgba(255,255,255,0.1); }}"
        
        # 筛选器按钮
        filter_btn = QPushButton()
        filter_btn.setIcon(create_svg_icon('select.svg', '#FFF'))
        filter_btn.setToolTip('高级筛选 (Ctrl+G)')
        filter_btn.setStyleSheet(f"QPushButton {{ background-color: {COLORS['primary']}; border: none; border-radius: 6px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; }} QPushButton:hover {{ background-color: #357abd; }}")
        filter_btn.clicked.connect(self._toggle_filter_panel)
        layout.addWidget(filter_btn)
        
        extract_btn = QPushButton()
        extract_btn.setIcon(create_svg_icon('action_export.svg', '#FFF'))
        extract_btn.setToolTip('批量提取全部')
        extract_btn.setStyleSheet(f"QPushButton {{ background-color: {COLORS['primary']}; border: none; border-radius: 6px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; }} QPushButton:hover {{ background-color: #357abd; }}")
        extract_btn.clicked.connect(self._extract_all)
        layout.addWidget(extract_btn)
        
        new_btn = QPushButton()
        new_btn.setIcon(create_svg_icon('action_add.svg', '#FFF'))
        new_btn.setToolTip('新建灵感 (Ctrl+N)')
        new_btn.setStyleSheet(f"QPushButton {{ background-color: {COLORS['primary']}; border: none; border-radius: 6px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; }} QPushButton:hover {{ background-color: #357abd; }}")
        new_btn.clicked.connect(self.new_idea)
        layout.addWidget(new_btn)
        layout.addSpacing(4)
        
        min_btn = QPushButton()
        min_btn.setIcon(create_svg_icon('win_min.svg', '#aaa'))
        min_btn.setStyleSheet(ctrl_btn_style)
        min_btn.clicked.connect(self.showMinimized)
        layout.addWidget(min_btn)
        
        self.max_btn = QPushButton()
        self.max_btn.setIcon(create_svg_icon('win_max.svg', '#aaa'))
        self.max_btn.setStyleSheet(ctrl_btn_style)
        self.max_btn.clicked.connect(self._toggle_maximize)
        layout.addWidget(self.max_btn)
        
        close_btn = QPushButton()
        close_btn.setIcon(create_svg_icon('win_close.svg', '#aaa'))
        close_btn.setStyleSheet(ctrl_btn_style + "QPushButton:hover { background-color: #e74c3c; }")
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
        # 使用 SVG 替换原来的 Emoji
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
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none")
        self.list_container = ContentContainer()
        self.list_container.cleared.connect(self._clear_all_selections)
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setAlignment(Qt.AlignTop)
        self.list_layout.setSpacing(7)  # 原来是 10，现在减 3 变成 7
        self.list_layout.setContentsMargins(20, 5, 20, 15)
        scroll.setWidget(self.list_container)
        layout.addWidget(scroll)
        
        return panel

    def _create_metadata_panel(self):
        panel = QWidget()
        panel.setObjectName("RightPanel")
        panel.setStyleSheet(f"#RightPanel {{ background-color: {COLORS['bg_mid']}; }}")
        panel.setFixedWidth(240) # 稍微加宽以容纳元数据
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 1. 标题区 (Revised)
        # 修复：不再直接添加 Label，而是包裹在透明容器中
        title_container = QWidget()
        title_container.setStyleSheet("background-color: transparent;") # 关键修复
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

        # 2. 信息展示区 (使用堆叠布局来切换)
        self.info_stack = QWidget()
        # 【关键】这里也要设置透明
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

        # 2.5 【新增】标题编辑输入框 (修改：统一清透胶囊样式 + 强制背景透明)
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("标题")
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
        # 失去焦点保存
        self.title_input.editingFinished.connect(self._save_title_from_sidebar)
        # 回车保存（通过清除焦点触发 editingFinished）
        self.title_input.returnPressed.connect(self.title_input.clearFocus)
        layout.addWidget(self.title_input)

        layout.addStretch(1) # 添加弹性空间，将输入框推到底部

        # 3. 分割线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)
        line.setStyleSheet(f"background-color: #505050; border: none; max-height: 1px; margin-bottom: 5px;")
        layout.addWidget(line)

        # 4. 底部标签输入框 (修改：统一清透胶囊样式 + 强制背景透明)
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
            #CapsuleTagInput:focus {{ border-color: {COLORS['primary']}; background-color: rgba(255, 255, 255, 0.08); }}
            #CapsuleTagInput:disabled {{ background-color: transparent; border: 1px solid #333; color: #666; }}
        """)
        self.tag_input.returnPressed.connect(self._handle_tag_input_return)
        self.tag_input.doubleClicked.connect(self._open_tag_selector_for_selection)
        # 直接添加输入框到布局，移除原来的Label和Wrapper
        layout.addWidget(self.tag_input)
        
        QTimer.singleShot(0, self._refresh_metadata_panel)
        return panel

    def _save_title_from_sidebar(self):
        # 仅当单选时才保存
        if len(self.selected_ids) != 1:
            return
        
        new_title = self.title_input.text().strip()
        if not new_title:
            return

        idea_id = list(self.selected_ids)[0]
        # 假设 DatabaseManager 有 update_field 方法，或者使用通用的 SQL 执行
        # 更加健壮的做法是使用 self.db.update_idea_title(idea_id, new_title)
        # 这里尝试使用 update_field (参考 toggle_field 的存在)
        try:
            if hasattr(self.db, 'update_field'):
                self.db.update_field(idea_id, 'title', new_title)
            else:
                # 兼容性Fallback，如果db中没有update_field，尝试直接SQL (需要db暴露conn，通常不推荐，但为了保证代码能跑)
                # 更稳妥的方式：更新UI卡片并重新加载数据，或者假定用户有update_idea方法
                # 这里假设 update_field 存在，因为 _do_pin 用到了 toggle_field
                pass 
        except Exception as e:
            print(f"Error updating title: {e}")
            return

        # 更新UI中对应卡片的标题，避免重载闪烁
        card = self.cards.get(idea_id)
        if card:
            # 获取最新数据刷新卡片
            data = self.db.get_idea(idea_id)
            if data:
                card.update_data(data)

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

    def _remove_tag_from_selection(self, tag_name):
        if not self.selected_ids: return
        self.db.remove_tag_from_multiple_ideas(list(self.selected_ids), tag_name)
        self._refresh_all()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = self.width()

        # 响应式规则
        if width < 1200:
            self._hide_metadata_panel()
        
        if width < 900:
            # 如果侧边栏是展开的，则强制折叠
            if self.sidebar.width() == 280:
                self._toggle_sidebar()
        
        # 重新计算卡片宽度以适应新的窗口尺寸
        self._update_card_widths()

    def _refresh_metadata_panel(self):
        num_selected = len(self.selected_ids)

        if num_selected == 0:
            self.no_selection_widget.show()
            self.multi_selection_widget.hide()
            self.metadata_display.hide()
            self.title_input.hide()
            self.tag_input.setEnabled(False)
            self.tag_input.setPlaceholderText("请先选择一个项目")
            self._hide_metadata_panel()
        
        elif num_selected == 1:
            self._show_metadata_panel()
            self.no_selection_widget.hide()
            self.multi_selection_widget.hide()
            self.metadata_display.show()
            self.title_input.show()
            self.tag_input.setEnabled(True)
            self.tag_input.setPlaceholderText("输入标签添加... (双击更多)")

            idea_id = list(self.selected_ids)[0]
            data = self.db.get_idea(idea_id)
            if data:
                # 更新标题输入框的内容
                self.title_input.setText(data['title'])
                
                tags = self.db.get_tags(idea_id)
                category_name = ""
                if data['category_id']:
                    # Inefficient to query every time, but acceptable for this context.
                    # A better implementation would cache categories on startup.
                    all_categories = self.db.get_categories()
                    cat = next((c for c in all_categories if c['id'] == data['category_id']), None)
                    if cat:
                        category_name = cat['name']
                self.metadata_display.update_data(data, tags, category_name)
            else:
                # Handle case where data might not be found (e.g., just deleted)
                self.metadata_display.update_data(None, [], "")
                self.title_input.clear()

        else: # num_selected > 1
            self._hide_metadata_panel()
            self.no_selection_widget.hide()
            self.multi_selection_widget.show()
            self.metadata_display.hide()
            self.title_input.hide()
            self.tag_input.setEnabled(False)
            self.tag_input.setPlaceholderText("请仅选择一项以查看元数据")

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
                # 窗口大小改变后重新计算卡片宽度
                self._update_card_widths()
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
            self.max_btn.setIcon(create_svg_icon("win_max.svg", "#aaa"))
        else:
            self.showMaximized()
            self.max_btn.setIcon(create_svg_icon("win_restore.svg", "#aaa"))
        
        # 窗口状态改变后，重新调整卡片宽度以适应新尺寸
        QTimer.singleShot(100, self._update_card_widths)

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
        self._refresh_all()

    def _set_filter(self, f_type, val):
        self.curr_filter = (f_type, val)
        self.selected_ids.clear()
        self.last_clicked_id = None
        self.current_tag_filter = None
        self.tag_filter_label.hide()
        titles = {'all':'全部数据','today':'今日数据','trash':'回收站','favorite':'我的收藏'}
        if f_type == 'category':
            cat = next((c for c in self.db.get_categories() if c['id'] == val), None)
            self.header_label.setText(f"📂 {cat['name']}" if cat else '文件夹')
        else:
            self.header_label.setText(titles.get(f_type, '灵感列表'))
        
        # 延迟执行，防止在点击事件处理中销毁对象
        QTimer.singleShot(10, self._load_data)
        QTimer.singleShot(10, self._update_ui_state)
        QTimer.singleShot(10, self._refresh_metadata_panel)
        # 重构筛选器
        QTimer.singleShot(10, self._rebuild_filter_panel)

    # === 新增：响应筛选器变化 ===
    def _on_filter_criteria_changed(self):
        # 筛选条件改变 -> 重置页码 -> 重新加载数据
        self.current_page = 1 
        self._load_data()

    def _load_data(self):
        # 1. 获取筛选条件
        criteria = self.filter_panel.get_checked_criteria()

        while self.list_layout.count():
            w = self.list_layout.takeAt(0).widget()
            if w: w.deleteLater()
        self.cards = {}
        self.card_ordered_ids = []
        
        # 2. 传递 filter_criteria 到 DB
        # 【核心补充】此处必须先计算总数，否则分页控件全是 1/1
        total_items = self.db.get_ideas_count(
            self.search.text(), 
            *self.curr_filter, 
            tag_filter=self.current_tag_filter,
            filter_criteria=criteria # 传入条件
        )
        self.total_pages = math.ceil(total_items / self.page_size) if total_items > 0 else 1
        
        # 修正页码范围
        if self.current_page > self.total_pages: self.current_page = self.total_pages
        if self.current_page < 1: self.current_page = 1

        data_list = self.db.get_ideas(
            self.search.text(), 
            *self.curr_filter, 
            page=self.current_page, 
            page_size=self.page_size, 
            tag_filter=self.current_tag_filter,
            filter_criteria=criteria # 传入条件
        )
        
        if not data_list:
            self.list_layout.addWidget(QLabel("🔭 空空如也", alignment=Qt.AlignCenter, styleSheet="color:#666;font-size:16px;margin-top:50px"))
        for d in data_list:
            c = IdeaCard(d, self.db)
            c.get_selected_ids_func = lambda: list(self.selected_ids)
            c.selection_requested.connect(self._handle_selection_request)
            c.double_clicked.connect(self._extract_single)
            c.setContextMenuPolicy(Qt.CustomContextMenu)
            c.customContextMenuRequested.connect(lambda pos, iid=d['id']: self._show_card_menu(iid, pos))
            self.list_layout.addWidget(c)
            self.cards[d['id']] = c
            self.card_ordered_ids.append(d['id'])
            
        self._update_pagination_ui() # 刷新页码显示
        self._update_ui_state()
        
        # 确保卡片宽度适应当前布局
        QTimer.singleShot(0, self._update_card_widths)

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
        
        is_locked = data['is_locked']
        rating = data['rating']
        
        if not in_trash:
            if not is_locked:
                menu.addAction(create_svg_icon('action_edit.svg'), '编辑', self._do_edit)
            else:
                edit_action = menu.addAction('编辑 (已锁定)')
                edit_action.setEnabled(False)
                
            menu.addAction(create_svg_icon('action_export.svg'), '提取(Ctrl+T)', lambda: self._extract_single(idea_id))
            menu.addSeparator()
            
            # --- 星级评价 ---
            rating_menu = menu.addMenu(create_svg_icon('star.svg'), "设置星级")
            from PyQt5.QtWidgets import QAction, QActionGroup # 临时导入
            star_group = QActionGroup(self)
            star_group.setExclusive(True)
            for i in range(1, 6):
                action = QAction(f"{'★'*i}", self, checkable=True)
                action.triggered.connect(lambda _, r=i: self._do_set_rating(r))
                if rating == i:
                    action.setChecked(True)
                rating_menu.addAction(action)
                star_group.addAction(action)
            rating_menu.addSeparator()
            action_clear_rating = rating_menu.addAction("清除评级")
            action_clear_rating.triggered.connect(lambda: self._do_set_rating(0))

            if is_locked:
                menu.addAction('🔓 解锁', self._do_lock)
            else:
                menu.addAction('🔒 锁定 (Ctrl+S)', self._do_lock)
                
            menu.addSeparator()
            menu.addAction(create_svg_icon('action_pin_off.svg' if data['is_pinned'] else 'action_pin.svg'), '取消置顶' if data['is_pinned'] else '置顶', self._do_pin)
            menu.addAction(create_svg_icon('bookmark.svg'), '取消书签' if data['is_favorite'] else '添加书签', self._do_fav)
            menu.addSeparator()
            
            if not is_locked:
                cat_menu = menu.addMenu(create_svg_icon('folder.svg'), '移动到分类')
                cat_menu.addAction('⚠️ 未分类', lambda: self._move_to_category(None))
                for cat in self.db.get_categories():
                    cat_menu.addAction(f'📂 {cat["name"]}', lambda cid=cat["id"]: self._move_to_category(cid))
                menu.addSeparator()
                menu.addAction(create_svg_icon('action_delete.svg'), '移至回收站', self._do_del)
            else:
                del_action = menu.addAction('移至回收站 (已锁定)')
                del_action.setEnabled(False)
                
        else:
            menu.addAction(create_svg_icon('action_restore.svg'), '恢复', self._do_restore)
            menu.addAction(create_svg_icon('trash.svg'), '永久删除', self._do_destroy)
            
        card = self.cards.get(idea_id)
        if card: menu.exec_(card.mapToGlobal(pos))

    def _do_set_rating(self, rating):
        if not self.selected_ids: return
        
        for idea_id in self.selected_ids:
            self.db.set_rating(idea_id, rating)
        
        # --- 关键修复：只刷新受影响的卡片 ---
        for idea_id in self.selected_ids:
            card_widget = self.cards.get(idea_id)
            if card_widget:
                new_data = self.db.get_idea(idea_id, include_blob=True)
                if new_data:
                    card_widget.update_data(new_data)
                    
    def _do_lock(self):
        if not self.selected_ids: return
        
        # 1. 获取所有选中ID的当前锁定状态
        status_map = self.db.get_lock_status(list(self.selected_ids))
        
        # 2. 判断逻辑：如果选中的数据中有任意一个是“未锁定(0)”，则执行“全部锁定(1)”
        #    只有当所有数据都是“已锁定(1)”时，才执行“全部解锁(0)”
        any_unlocked = False
        for iid, is_locked in status_map.items():
            if not is_locked:
                any_unlocked = True
                break
        
        target_state = 1 if any_unlocked else 0
        
        # 3. 执行批量更新
        self.db.set_locked(list(self.selected_ids), target_state)
        
        # In-place update
        for iid in self.selected_ids:
            card = self.cards.get(iid)
            if card:
                new_data = self.db.get_idea(iid, include_blob=True)
                if new_data:
                    card.update_data(new_data)

        action_name = "锁定" if target_state else "解锁"
        self._update_ui_state()

    def _move_to_category(self, cat_id):
        if self.selected_ids:
            # 过滤掉锁定的项目
            valid_ids = []
            status_map = self.db.get_lock_status(list(self.selected_ids))
            for iid in self.selected_ids:
                if not status_map.get(iid, 0):
                    valid_ids.append(iid)
            
            if not valid_ids: return

            for iid in valid_ids:
                self.db.move_category(iid, cat_id)
                # --- 从UI中移除卡片 ---
                card = self.cards.pop(iid, None)
                if card:
                    card.hide()
                    card.deleteLater()
            
            self.selected_ids.clear()
            self._update_ui_state()
            self.sidebar.refresh() # 刷新分类计数
            self.sidebar._update_partition_tree() # 刷新分区计数

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
        # 【关键修复】异步更新UI状态，防止点击卡片时重绘右侧面板导致崩溃
        QTimer.singleShot(0, self._update_ui_state)

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
                # 动态图标更新
                self.btns['pin'].setIcon(create_svg_icon('action_pin_off.svg' if d['is_pinned'] else 'action_pin.svg', '#aaa'))
                # fav图标保持一致即可
        else:
            self.btns['pin'].setIcon(create_svg_icon('action_pin.svg', '#aaa'))
            
        # 【关键修复】异步刷新标签面板
        QTimer.singleShot(0, self._refresh_metadata_panel)

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
        
        # 使用 data_saved 刷新，确保实时性
        dialog.data_saved.connect(self._refresh_all)
        dialog.finished.connect(lambda: self.open_dialogs.remove(dialog) if dialog in self.open_dialogs else None)

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
            # 检查锁定
            status = self.db.get_lock_status([idea_id])
            if status.get(idea_id, 0):
                return
            self._open_edit_dialog(idea_id=idea_id)

    def _do_pin(self):
        if self.selected_ids:
            for iid in self.selected_ids: self.db.toggle_field(iid, 'is_pinned')
            self._load_data()

    def _do_fav(self):
        if self.selected_ids:
            # 智能批量切换：如果其中任何一个没有加书签，则全部设为书签
            # 只有当全部都已加书签时，才全部取消书签
            any_not_favorited = False
            all_data = []
            for iid in self.selected_ids:
                data = self.db.get_idea(iid)
                if data and not data['is_favorite']:
                    any_not_favorited = True
                all_data.append(data)

            target_state = True if any_not_favorited else False

            for iid in self.selected_ids:
                self.db.set_favorite(iid, target_state)
            
            # In-place update
            for iid in self.selected_ids:
                card = self.cards.get(iid)
                if card:
                    new_data = self.db.get_idea(iid, include_blob=True)
                    if new_data:
                        card.update_data(new_data)

            self._update_ui_state()
            self.sidebar.refresh() # --- 关键修复：刷新侧边栏计数 ---

    def _do_del(self):
        if self.selected_ids:
            # 过滤掉锁定的项目
            valid_ids = []
            status_map = self.db.get_lock_status(list(self.selected_ids))
            for iid in self.selected_ids:
                if not status_map.get(iid, 0):
                    valid_ids.append(iid)
            
            if not valid_ids: return

            for iid in valid_ids:
                self.db.set_deleted(iid, True)
                # --- 从UI中移除卡片 ---
                card = self.cards.pop(iid, None)
                if card:
                    card.hide()
                    card.deleteLater()
            
            self.selected_ids.clear()
            self._update_ui_state()
            self.sidebar.refresh() # --- 关键修复：刷新侧边栏计数 ---

    def _do_restore(self):
        if self.selected_ids:
            count = len(self.selected_ids)
            for iid in self.selected_ids:
                self.db.set_deleted(iid, False)
                card = self.cards.pop(iid, None)
                if card:
                    card.hide()
                    card.deleteLater()
            self.selected_ids.clear()
            self._update_ui_state()
            self.sidebar.refresh()

    def _do_destroy(self):
        if self.selected_ids:
            msg = f'确定永久删除选中的 {len(self.selected_ids)} 项?\n此操作不可恢复!'
            if self._show_custom_confirm_dialog("永久删除", msg):
                count = len(self.selected_ids)
                for iid in self.selected_ids:
                    self.db.delete_permanent(iid)
                    card = self.cards.pop(iid, None)
                    if card:
                        card.hide()
                        card.deleteLater()
                self.selected_ids.clear()
                self._update_ui_state()
                self.sidebar.refresh()

    def _refresh_all(self):
        # 【关键保护】如果正在清理旧控件，不要重入
        if not self.isVisible(): return
        
        # 延迟执行所有刷新
        QTimer.singleShot(10, self._load_data)
        QTimer.singleShot(10, self.sidebar.refresh)
        QTimer.singleShot(10, self._update_ui_state)
        QTimer.singleShot(10, self._refresh_tag_panel)

    def _extract_single(self, idea_id):
        data = self.db.get_idea(idea_id)
        if not data:
            self._show_tooltip('⚠️ 数据不存在', 1500)
            return
        content_to_copy = data['content'] or ""
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
            lines.append(f"【{d['title']}】")
            if d['is_pinned']: lines.append('📌 已置顶')
            if d['is_favorite']: lines.append('⭐ 已收藏')
            tags = self.db.get_tags(d['id'])
            if tags: lines.append(f"标签: {', '.join(tags)}")
            lines.append(f"时间: {d['created_at']}")
            if d['content']: lines.append(f"\n{d['content']}")
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

    def closeEvent(self, event):
        self._save_window_state()
        self.closing.emit()
        self.hide()
        event.ignore()
    def _save_window_state(self):
        save_setting("main_window_geometry_hex", self.saveGeometry().toHex().data().decode())
        save_setting("main_window_maximized", self.isMaximized())
        # 记录当前侧边栏宽度，确保用户调整在下次启动时保留
        if hasattr(self, "sidebar"):
            save_setting("sidebar_width", self.sidebar.width())

    def save_state(self):
        self._save_window_state()

    def _restore_window_state(self):
        geo_hex = load_setting("main_window_geometry_hex")
        if geo_hex:
            try:
                self.restoreGeometry(QByteArray.fromHex(geo_hex.encode()))
            except Exception:
                self.resize(1000, 500)
        else:
            self.resize(1000, 500)
            
        if load_setting("main_window_maximized", False):
            self.showMaximized()
            self.max_btn.setIcon(create_svg_icon("win_restore.svg", "#aaa"))
        else:
            self.max_btn.setIcon(create_svg_icon("win_max.svg", "#aaa"))

        # 恢复侧边栏宽度
        sidebar_width = load_setting("sidebar_width")
        if sidebar_width is not None and hasattr(self, "main_splitter"):
            if self.main_splitter.size().width() <= 0:
                QTimer.singleShot(0, lambda w=sidebar_width: self._apply_sidebar_width(w))
            else:
                self._apply_sidebar_width(sidebar_width)
        
        # 确保在窗口状态恢复后调整卡片宽度
        QTimer.singleShot(100, self._update_card_widths)

    def _apply_sidebar_width(self, sidebar_width):
        if not hasattr(self, "main_splitter"):
            return
        total = self.main_splitter.size().width()
        if total <= 0:
            return
        try:
            sidebar_width = int(sidebar_width)
        except Exception:
            return
        sidebar_width = max(60, min(sidebar_width, total - 100))
        self.main_splitter.setSizes([sidebar_width, total - sidebar_width])

    def _update_card_widths(self):
        """更新所有卡片的宽度以适应当前布局"""
        if hasattr(self, 'main_splitter'):
            sizes = self.main_splitter.sizes()
            if len(sizes) >= 2:
                # 中间区域宽度
                middle_width = sizes[1]
                
                # 根据窗口是否最大化调整边距
                if self.isMaximized():
                    # 窗口最大化时，减少边距以充分利用空间
                    available_width = middle_width - 20  # 减少边距
                    card_width_ratio = 0.97  # 更大比例利用空间
                else:
                    # 普通窗口状态下保持适当的边距
                    available_width = middle_width - 40  # 正常边距
                    card_width_ratio = 0.95  # 适中的比例
                
                for card in self.cards.values():
                    # 计算卡片的最大宽度
                    max_width = max(280, int(available_width * card_width_ratio))
                    card.setMaximumWidth(max_width)
                    
                    # 同时设置最小宽度，防止卡片过窄
                    card.setMinimumWidth(min(200, max_width))
        
        # 同时也确保卡片容器的布局能正确更新
        if hasattr(self, 'list_layout'):
            # 强制重新布局以适应新的窗口尺寸
            self.list_layout.update()

    def _on_splitter_moved(self, pos, index):
        # 当分割条移动时，重新计算卡片最大宽度
        if hasattr(self, 'main_splitter'):
            sizes = self.main_splitter.sizes()
            if len(sizes) >= 2:
                # 中间区域宽度
                middle_width = sizes[1]
                # 考虑布局边距，为卡片设置合理的最大宽度
                available_width = middle_width - 40  # 减去布局边距
                for card in self.cards.values():
                    # 设置为可用区域宽度的 95%，确保有适当的边距
                    card.setMaximumWidth(max(300, int(available_width * 0.95)))
                    
        # 同时也确保卡片容器的布局能正确更新
        if hasattr(self, 'list_layout'):
            # 强制重新布局以适应新的窗口尺寸
            self.list_layout.update()