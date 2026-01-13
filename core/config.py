# core/config.py
DB_NAME = 'ideas.db'
BACKUP_DIR = 'backups'

COLORS = {
    'primary': '#4a90e2',   # 核心蓝
    'success': '#2ecc71',   # 成功绿
    'warning': '#f39c12',   # 警告黄
    'danger':  '#e74c3c',   # 危险红
    'info':    '#9b59b6',   # 信息紫
    'teal':    '#1abc9c',   # 青色
    'orange':  '#FF8C00',   # 深橙色
    'default_note': '#2d2d2d', 
    'trash': '#2d2d2d',
    'uncategorized': '#0A362F',
    'bg_dark': '#1e1e1e',   # 窗口背景
    'bg_mid':  '#252526',   # 侧边栏/输入框背景
    'bg_light': '#333333',  # 边框/分割线
    'text':    '#cccccc',   # 主文本
    'text_sub': '#858585'   # 副文本
}

# --- 全局通用样式组件 ---

# 1. 现代滚动条 (极简、无箭头按钮)
GLOBAL_SCROLLBAR = f"""
    QScrollBar:vertical {{
        border: none;
        background: transparent;
        width: 8px;
        margin: 0px; 
    }}
    QScrollBar::handle:vertical {{
        background: #444;
        min-height: 30px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #555; }}
    QScrollBar::handle:vertical:pressed {{ background: {COLORS['primary']}; }}
    
    /* 隐藏上下箭头按钮 */
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
        subcontrol-position: top;
        subcontrol-origin: margin;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

    QScrollBar:horizontal {{
        border: none;
        background: transparent;
        height: 8px;
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background: #444;
        min-width: 30px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: #555; }}
    QScrollBar::handle:horizontal:pressed {{ background: {COLORS['primary']}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
"""

# 2. 现代 Tooltip
MODERN_TOOLTIP = f"""
    QToolTip {{
        color: #ffffff;
        background-color: #2D2D2D;
        border: 1px solid #444;
        border-radius: 4px;
        padding: 4px;
        font-family: "Microsoft YaHei";
        font-size: 12px;
    }}
"""

STYLES = {
    'main_window': f"""
        QWidget {{ background-color: {COLORS['bg_dark']}; color: {COLORS['text']}; font-family: "Microsoft YaHei", "Segoe UI", sans-serif; }}
        QSplitter::handle {{ background-color: {COLORS['bg_light']}; }}
        {GLOBAL_SCROLLBAR}
        {MODERN_TOOLTIP}
    """,
    
    'sidebar': f"""
        QTreeWidget {{
            background-color: {COLORS['bg_mid']};
            color: #ddd;
            border: none;
            font-size: 13px;
            padding: 8px;
            outline: none;
        }}
        QTreeWidget::item {{
            height: 30px;
            padding: 2px 4px;
            border-radius: 4px;
            margin-bottom: 2px;
        }}
        QTreeWidget::item:hover {{ background-color: #2a2d2e; }}
        QTreeWidget::item:selected {{ background-color: #37373d; color: white; }}
        {GLOBAL_SCROLLBAR}
    """,
    
    'dialog': f"""
        QDialog {{ background-color: {COLORS['bg_dark']}; color: {COLORS['text']}; }}
        QLabel {{ color: {COLORS['text_sub']}; font-size: 12px; font-weight: bold; margin-bottom: 4px; }}
        QLineEdit, QTextEdit, QComboBox {{
            background-color: {COLORS['bg_mid']};
            border: 1px solid #333;
            border-radius: 4px;
            padding: 8px;
            color: #eee;
            font-size: 13px;
            selection-background-color: {COLORS['primary']};
        }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
            border: 1px solid {COLORS['primary']};
            background-color: #2a2a2a;
        }}
        {GLOBAL_SCROLLBAR}
        {MODERN_TOOLTIP}
    """,
    
    'btn_primary': f"""
        QPushButton {{
            background-color: {COLORS['primary']};
            border: none;
            color: white;
            padding: 0px 16px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 13px;
        }}
        QPushButton:hover {{ background-color: #357abd; }}
        QPushButton:pressed {{ background-color: #2a5d8f; }}
    """,

    'btn_icon': f"""
        QPushButton {{
            background-color: {COLORS['bg_light']};
            border: 1px solid #444;
            border-radius: 6px;
            min-width: 32px;
            min-height: 32px;
        }}
        QPushButton:hover {{ background-color: {COLORS['primary']}; border-color: {COLORS['primary']}; }}
        QPushButton:pressed {{ background-color: #2a5d8f; }}
        QPushButton:disabled {{ background-color: #252526; color: #555; border-color: #333; }}
    """,
    
    'input': f"""
        QLineEdit {{
            background-color: {COLORS['bg_mid']};
            border: 1px solid {COLORS['bg_light']};
            border-radius: 16px;
            padding: 6px 12px;
            color: #eee;
            font-size: 13px;
        }}
        QLineEdit:focus {{ border: 1px solid {COLORS['primary']}; }}
    """,
    
    'card_base': "border-radius: 12px;"
}