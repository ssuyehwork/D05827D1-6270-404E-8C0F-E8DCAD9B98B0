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
    
    'bg_dark': '#1e1e1e',   # 窗口背景 (最深)
    'bg_mid':  '#252526',   # 侧边栏/输入框背景 (次深)
    'bg_light': '#333333',  # 边框/分割线
    
    'text':    '#cccccc',   # 主文本
    'text_sub': '#858585'   # 副文本
}

STYLES = {
    # === 主窗口结构 ===
    'main_window': f"""
        QWidget {{ background-color: {COLORS['bg_dark']}; color: {COLORS['text']}; font-family: "Microsoft YaHei", "Segoe UI", sans-serif; }}
        QSplitter::handle {{ background-color: {COLORS['bg_light']}; }}
        /* 滚动条美化 */
        QScrollBar:vertical {{ border: none; background: {COLORS['bg_dark']}; width: 10px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: #444; min-height: 20px; border-radius: 5px; }}
        QScrollBar::handle:vertical:hover {{ background: #555; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    """,
    
    # === 侧边栏 ===
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
    """,
    
    # === 弹窗通用样式 ===
    'dialog': f"""
        QDialog {{ background-color: {COLORS['bg_dark']}; color: {COLORS['text']}; }}
        QLabel {{
            color: {COLORS['text_sub']};
            font-size: 12px;
            font-weight: bold;
            margin-bottom: 4px;
        }}
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
        QComboBox {{ padding-right: 20px; }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left-width: 0px;
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
        }}
        QComboBox::down-arrow {{
            width: 0; 
            height: 0; 
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid #888;
            margin-right: 6px;
        }}
        QComboBox QAbstractItemView {{
            border: 1px solid {COLORS['primary']};
            background-color: {COLORS['bg_mid']};
            color: #eee;
            selection-background-color: {COLORS['primary']};
            selection-color: white;
            outline: none;
            padding: 4px;
        }}
    """,
    
    'btn_primary': f"""
        QPushButton {{
            background-color: {COLORS['primary']};
            border: none;
            color: white;
            padding: 8px 16px;
            border-radius: 4px;
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
            border-radius: 4px;
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
        QLineEdit::clear-button {{
            background: transparent;
            border-radius: 9px;
            margin-right: 4px;
        }}
        QLineEdit::clear-button:hover {{
            background: #555;
        }}
    """,
    
    'card_base': "border-radius: 12px;"
}
