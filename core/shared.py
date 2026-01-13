# -*- coding: utf-8 -*-
# core/shared.py
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtCore import Qt

_ICON_CACHE = {}

def get_color_icon(color_str):
    """
    根据颜色字符串生成一个QIcon。
    为了提高性能，相同颜色的图标会被缓存。
    """
    if not color_str:
        color_str = "#808080"
        
    if color_str in _ICON_CACHE:
        return _ICON_CACHE[color_str]

    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    color = QColor(color_str)
    painter.setBrush(color)
    painter.setPen(Qt.NoPen)
    
    # 在16x16的画布上绘制一个12x12的圆角矩形
    painter.drawRoundedRect(2, 2, 12, 12, 4, 4)
    painter.end()
    
    icon = QIcon(pixmap)
    _ICON_CACHE[color_str] = icon
    return icon