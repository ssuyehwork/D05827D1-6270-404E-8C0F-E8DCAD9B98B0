# -*- coding: utf-8 -*-
# ui/components/quick_toolbar.py

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLineEdit, QLabel
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QIntValidator, QTransform

from core.config import COLORS
from ui.utils import create_svg_icon

class QuickToolbar(QWidget):
    """
    A vertical toolbar for the QuickWindow, containing window controls,
    actions like pinning, and pagination controls.
    """
    # Signals to notify the parent window of user actions
    close_requested = pyqtSignal()
    maximize_requested = pyqtSignal()
    minimize_requested = pyqtSignal()
    pin_toggled = pyqtSignal(bool)
    toggle_sidebar_requested = pyqtSignal()
    prev_page_requested = pyqtSignal()
    next_page_requested = pyqtSignal()
    page_jump_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()

    def _create_rotated_icon(self, icon_name, color, angle):
        """Creates a QIcon with a rotated SVG."""
        icon = create_svg_icon(icon_name, color)
        pixmap = icon.pixmap(24, 24)
        transform = QTransform().rotate(angle)
        rotated_pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)
        return QIcon(rotated_pixmap)

    def _init_ui(self):
        self.setObjectName("RightToolbar")
        self.setFixedWidth(40)
        
        # Set style properties directly on the widget without using a selector.
        # This is a more robust way to style the component itself and avoids
        # selector specificity issues with parent stylesheets.
        self.setStyleSheet("""
            background-color: #252526;
            border-top-right-radius: 8px;
            border-bottom-right-radius: 8px;
            border-left: 1px solid #333333;
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignHCenter)

        btn_size = 28

        # 1. Window Controls
        self.btn_close = QPushButton()
        self.btn_close.setIcon(create_svg_icon('win_close.svg', '#aaa'))
        self.btn_close.setObjectName("CloseButton")
        self.btn_close.setToolTip("关闭")
        self.btn_close.setFixedSize(btn_size, btn_size)
        layout.addWidget(self.btn_close)

        self.btn_open_full = QPushButton()
        self.btn_open_full.setIcon(create_svg_icon('win_max.svg', '#aaa'))
        self.btn_open_full.setObjectName("MaxButton")
        self.btn_open_full.setToolTip("切换主程序界面")
        self.btn_open_full.setFixedSize(btn_size, btn_size)
        layout.addWidget(self.btn_open_full)

        self.btn_minimize = QPushButton()
        self.btn_minimize.setIcon(create_svg_icon('win_min.svg', '#aaa'))
        self.btn_minimize.setObjectName("MinButton")
        self.btn_minimize.setToolTip("最小化")
        self.btn_minimize.setFixedSize(btn_size, btn_size)
        layout.addWidget(self.btn_minimize)
        
        # 2. Action Buttons
        self.btn_stay_top = QPushButton()
        self.btn_stay_top.setIcon(create_svg_icon('pin_tilted.svg', '#aaa'))
        self.btn_stay_top.setObjectName("PinButton")
        self.btn_stay_top.setToolTip("保持置顶")
        self.btn_stay_top.setCheckable(True)
        self.btn_stay_top.setFixedSize(btn_size, btn_size)
        layout.addWidget(self.btn_stay_top)

        self.btn_toggle_side = QPushButton()
        self.btn_toggle_side.setIcon(create_svg_icon('action_eye.svg', '#aaa'))
        self.btn_toggle_side.setObjectName("ToolButton")
        self.btn_toggle_side.setToolTip("显示/隐藏侧边栏")
        self.btn_toggle_side.setFixedSize(btn_size, btn_size)
        layout.addWidget(self.btn_toggle_side)

        layout.addSpacing(10)

        # 3. Pagination Controls
        self.btn_prev_page = QPushButton()
        self.btn_prev_page.setObjectName("PageButton")
        self.btn_prev_page.setIcon(self._create_rotated_icon("nav_prev.svg", "#aaa", 90))
        self.btn_prev_page.setFixedSize(btn_size, btn_size)
        self.btn_prev_page.setToolTip("上一页")
        self.btn_prev_page.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.btn_prev_page)

        self.txt_page_input = QLineEdit("1")
        self.txt_page_input.setObjectName("PageInput")
        self.txt_page_input.setAlignment(Qt.AlignCenter)
        self.txt_page_input.setFixedWidth(28)
        self.txt_page_input.setValidator(QIntValidator(1, 9999))
        layout.addWidget(self.txt_page_input)
        
        self.lbl_total_pages = QLabel("1")
        self.lbl_total_pages.setObjectName("TotalPageLabel")
        self.lbl_total_pages.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_total_pages)

        self.btn_next_page = QPushButton()
        self.btn_next_page.setObjectName("PageButton")
        self.btn_next_page.setIcon(self._create_rotated_icon("nav_next.svg", "#aaa", 90))
        self.btn_next_page.setFixedSize(btn_size, btn_size)
        self.btn_next_page.setToolTip("下一页")
        self.btn_next_page.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.btn_next_page)

        layout.addStretch()

        # 4. Vertical Title
        lbl_vertical_title = QLabel("快\n速\n笔\n记")
        lbl_vertical_title.setObjectName("VerticalTitle")
        lbl_vertical_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_vertical_title)

        layout.addStretch()

        # 5. Logo
        title_icon = QLabel()
        title_icon.setPixmap(create_svg_icon("zap.svg", COLORS['primary']).pixmap(20, 20))
        title_icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_icon)

    def _connect_signals(self):
        """Connect internal widget signals to the component's public signals."""
        self.btn_close.clicked.connect(self.close_requested)
        self.btn_open_full.clicked.connect(self.maximize_requested)
        self.btn_minimize.clicked.connect(self.minimize_requested)
        self.btn_stay_top.toggled.connect(self.pin_toggled)
        self.btn_toggle_side.clicked.connect(self.toggle_sidebar_requested)
        self.btn_prev_page.clicked.connect(self.prev_page_requested)
        self.btn_next_page.clicked.connect(self.next_page_requested)
        self.txt_page_input.returnPressed.connect(self._on_jump_to_page)
        
    def _on_jump_to_page(self):
        """Handle the returnPressed signal from the page input field."""
        text = self.txt_page_input.text()
        if text.isdigit():
            page = int(text)
            self.page_jump_requested.emit(page)

    # --- Public Methods ---

    def set_pin_status(self, is_pinned):
        """Sets the visual state of the pin button."""
        self.btn_stay_top.setChecked(is_pinned)

    def update_page_info(self, current_page, total_pages):
        """Updates the pagination controls with the latest page numbers."""
        self.txt_page_input.setText(str(current_page))
        self.lbl_total_pages.setText(str(total_pages))
        
        self.btn_prev_page.setDisabled(current_page <= 1)
        self.btn_next_page.setDisabled(current_page >= total_pages)
