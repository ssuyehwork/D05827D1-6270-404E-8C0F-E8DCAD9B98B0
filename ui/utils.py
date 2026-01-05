# -*- coding: utf-8 -*-
# ui/utils.py
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QPainter, QColor, QIcon

def create_color_icon(color_str: str, size: int = 14) -> QIcon:
    """
    Creates a solid color, circular icon.

    Args:
        color_str: The color for the icon in hex format (e.g., "#FF0000").
        size: The dimension (width and height) of the icon.

    Returns:
        A QIcon object with the specified color.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # Use the provided color, or a default gray if it's invalid
    color = QColor(color_str if color_str else "#808080")
    
    painter.setBrush(color)
    painter.setPen(Qt.NoPen)
    
    # Draw a circle in the center of the pixmap
    painter.drawEllipse(1, 1, size - 2, size - 2)
    
    painter.end()
    return QIcon(pixmap)
