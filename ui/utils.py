# -*- coding: utf-8 -*-
# ui/utils.py

import os
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtCore import Qt, QByteArray
from PyQt5.QtGui import QPalette, QIcon, QPixmap, QPainter
from PyQt5.QtWidgets import QApplication

# ==========================================
# 🎨 专业配色方案 (用于 Icon 智能着色)
# ==========================================
_icon_theme_colors = {
    'all_data.svg':      '#3498db',
    'today.svg':         '#2ecc71',
    'uncategorized.svg': '#e67e22',
    'untagged.svg':      '#95a5a6',
    'bookmark.svg':      '#ff6b81',
    'trash.svg':         '#e74c3c',
    'select.svg':        '#1abc9c',
    'lock.svg':          '#e74c3c', 
    'star_filled.svg':   '#f39c12',
    'action_fav_filled.svg': '#ff6b81', 
    'pencil.svg':        '#aaaaaa',
    'clock.svg':         '#aaaaaa',
    
    # 分支/分组图标配色
    'branch.svg':        '#9b59b6', 
    
    'pin_tilted.svg':    '#aaaaaa', 
    'pin_vertical.svg':  '#e74c3c',  
    
    'display.svg': '#81D4FA', 
    'coffee.svg': '#BCAAA4',   
    'grid.svg': '#90A4AE',     
    'book.svg': '#9FA8DA',     
    'leaf.svg': '#A5D6A7',     
    'book-open.svg': '#FFCC80',
    'zap.svg': '#FFEB3B',      
    'monitor.svg': '#B0BEC5',  
    'action_add.svg': '#C5E1A5',
    'tag.svg': '#FFAB91',      
    'power.svg': '#EF9A9A'     
}

# ==========================================
# 💎 内置 SVG 图标数据
# ==========================================
_system_icons = {
    # [核心] 分支图标 (替代文件夹): 体现节点结构
    'branch.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="5" r="3"></circle>
        <path d="M12 8v5"></path>
        <path d="M12 13l-5 4"></path>
        <path d="M12 13l5 4"></path>
        <circle cx="7" cy="19" r="3"></circle>
        <circle cx="17" cy="19" r="3"></circle>
    </svg>""",

    # [核心] 未分类 (Inbox/收纳盒风格): 替代之前的文件夹样式
    'uncategorized.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="22 12 16 12 14 15 10 15 8 12 2 12"></polyline>
        <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"></path>
    </svg>""",

    # [兼容] 如果有代码还在调用 folder.svg，强制指向分支样式，彻底消灭文件夹图标
    'folder.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="5" r="3"></circle>
        <path d="M12 8v5"></path>
        <path d="M12 13l-5 4"></path>
        <path d="M12 13l5 4"></path>
        <circle cx="7" cy="19" r="3"></circle>
        <circle cx="17" cy="19" r="3"></circle>
    </svg>""",

    'select.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>""",
    'all_data.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>""",
    'today.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>""",
    
    'untagged.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>""",
    'bookmark.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>""",
    'trash.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>""",
    'win_close.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>""",
    'win_max.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/></svg>""",
    'win_restore.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="10" height="10" rx="1"/><rect x="11" y="3" width="10" height="10" rx="1"/></svg>""",
    'win_min.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/></svg>""",
    'win_sidebar.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="3" x2="9" y2="21"/></svg>""",
    'sidebar_right.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="15" y1="3" x2="15" y2="21"/></svg>""",
    'action_add.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>""",
    'action_edit.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>""",
    'pin_tilted.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" transform="rotate(45 12 12)"><path d="M16 12V8H8v4l-2 2v2h5v6l1 1 1-1v-6h5v-2l-2-2z"></path></svg>""",
    'pin_vertical.svg': """<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M16 9V4h1c.55 0 1-.45 1-1s-.45-1-1-1H7c-.55 0-1 .45-1 1s.45 1 1 1h1v5c0 1.66-1.34 3-3 3v2h5.97v7l1.03 1 1.03-1v-7H19v-2c-1.66 0-3-1.34-3-3z"></path></svg>""",
    'action_fav.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>""",
    'action_fav_filled.svg': """<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>""",
    'action_eye.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>""",
    'action_restore.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>""",
    'action_delete.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>""",
    'action_export.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>""",
    'action_save.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>""",
    'edit_undo.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/></svg>""",
    'edit_redo.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 7v6h-6"/><path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3l3 2.7"/></svg>""",
    'edit_list_ul.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>""",
    'edit_list_ol.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="10" y1="6" x2="21" y2="6"/><line x1="10" y1="12" x2="21" y2="12"/><line x1="10" y1="18" x2="21" y2="18"/><path d="M4 6h1v4"/><path d="M4 10h2"/><path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1"/></svg>""",
    'edit_clear.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>""",
    'nav_first.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="11 17 6 12 11 7"/><polyline points="18 17 13 12 18 7"/></svg>""",
    'nav_prev.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>""",
    'nav_next.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>""",
    'nav_last.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="13 17 18 12 13 7"/><polyline points="6 17 11 12 6 7"/></svg>""",
    'tag.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>""",
    'calendar.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>""",
    'clock.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>""",
    'star.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>""",
    'star_filled.svg': """<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>""",
    'pin.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>""",
    'lock.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>""",
    'pencil.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg>""",
    'display.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="12" rx="2" ry="2"/><line x1="3" y1="21" x2="21" y2="21"/><line x1="12" y1="15" x2="12" y2="21"/></svg>""",
    'coffee.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8h1a4 4 0 0 1 0 8h-1"/><path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"/><line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/></svg>""",
    'grid.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/><line x1="15" y1="3" x2="15" y2="21"/></svg>""",
    'book.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20v2H6.5A2.5 2.5 0 0 1 4 19.5z"/><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v2H6.5A2.5 2.5 0 0 1 4 5.5z"/></svg>""",
    'leaf.svg':"""<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12c0-4.42-3.58-8-8-8S4 7.58 4 12s3.58 8 8 8 8-3.58 8-8z"/><path d="M12 2a10 10 0 0 0-10 10h20a10 10 0 0 0-10-10z"/></svg>""",
    'book-open.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>""",
    'zap.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>""",
    'monitor.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>""",
    'power.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg>""",
    'palette.svg': """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="13.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="10.5" r="2.5"/><circle cx="8.5" cy="7.5" r="2.5"/><circle cx="6.5" cy="12.5" r="2.5"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/></svg>""",
    'grip_diagonal.svg': """<svg viewBox="0 0 20 20" fill="currentColor">
        <circle cx="18" cy="18" r="1.2"/><circle cx="14" cy="18" r="1.2"/><circle cx="10" cy="18" r="1.2"/><circle cx="6" cy="18" r="1.2"/><circle cx="2" cy="18" r="1.2"/>
        <circle cx="18" cy="14" r="1.2"/><circle cx="14" cy="14" r="1.2"/><circle cx="10" cy="14" r="1.2"/><circle cx="6" cy="14" r="1.2"/>
        <circle cx="18" cy="10" r="1.2"/><circle cx="14" cy="10" r="1.2"/><circle cx="10" cy="10" r="1.2"/>
        <circle cx="18" cy="6" r="1.2"/><circle cx="14" cy="6" r="1.2"/>
        <circle cx="18" cy="2" r="1.2"/>
    </svg>"""
}

# 全局图标缓存
_icon_cache = {}

def create_svg_icon(icon_name, color=None):
    """
    创建一个基于 SVG 的 QIcon，具有智能着色和缓存功能。
    :param icon_name: SVG 图标的文件名 (例如 'all_data.svg')
    :param color: 强制指定颜色 (Hex 字符串)，否则使用智能配色或默认色
    :return: QIcon 对象
    """
    # 默认使用当前应用程序调色板的文本颜色
    default_color = QApplication.palette().color(QPalette.WindowText).name()
    
    if color:
        render_color = color
    else:
        # 智能着色：检查是否有预定义的专业配色
        render_color = _icon_theme_colors.get(icon_name, default_color)

    cache_key = (icon_name, render_color)

    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    svg_data = ""
    if icon_name in _system_icons:
        svg_data = _system_icons[icon_name]
    
    if not svg_data:
        # 作为备用，尝试从文件系统加载
        icon_path = os.path.join("ui", "icons", icon_name)
        if os.path.exists(icon_path):
            try:
                with open(icon_path, 'r', encoding='utf-8') as f:
                    svg_data = f.read()
            except Exception:
                pass

    if not svg_data:
        return QIcon()  # 返回一个空图标

    # 将 SVG 中的 "currentColor" 替换为我们指定的颜色
    svg_data = svg_data.replace("currentColor", render_color)

    renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
    
    # 增加渲染尺寸以提高高分屏清晰度
    render_size = 64
    pixmap = QPixmap(render_size, render_size)
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    icon = QIcon(pixmap)
    _icon_cache[cache_key] = icon
    return icon

def create_clear_button_icon():
    """
    专门为 QLineEdit 的 clearButton 生成一个经典的 '×' 图标,
    并返回其文件路径, 供 QSS 使用。
    """
    import tempfile
    
    # 定义一个经典的 '×' SVG
    svg_data = """
    <svg viewBox="0 0 24 24" fill="none" stroke="#999999" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"/>
        <line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
    """
    
    # 检查缓存
    temp_dir = tempfile.gettempdir()
    icon_path = os.path.join(temp_dir, "clear_icon.png")
    
    if os.path.exists(icon_path):
        return icon_path.replace("\\", "/") # 确保路径格式正确
        
    renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    
    pixmap.save(icon_path, "PNG")
    
    # 确保 QSS 能正确使用路径
    return icon_path.replace("\\", "/")