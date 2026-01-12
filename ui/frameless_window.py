# -*- coding: utf-8 -*-
# ui/frameless_window.py

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QColor, QCursor

class FramelessWindow(QWidget):
    """
    A base class for creating frameless windows that support dragging and resizing.
    """
    RESIZE_MARGIN = 18

    def __init__(self, parent=None):
        super().__init__(parent)

        # Core attributes for frameless behavior
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        
        # --- Window dragging and resizing variables ---
        self._is_dragging = False
        self._drag_position = QPoint()
        self._resize_area = None
        self._resize_start_pos = None
        self._resize_start_geometry = None

        # --- Main layout and container for shadow effect ---
        # The root_layout allows the shadow to be outside the main container
        self.root_layout = QHBoxLayout(self)
        self.root_layout.setContentsMargins(15, 15, 15, 15)
        self.root_layout.setSpacing(0)
        
        # The container holds the actual content and receives the shadow
        self.container = QWidget()
        self.container.setObjectName("Container")
        self.root_layout.addWidget(self.container)
        
        # Apply shadow effect to the container
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 100))
        self.container.setGraphicsEffect(shadow)
        
        # Enable mouse tracking for the window and container
        self.setMouseTracking(True)
        self.container.setMouseTracking(True)


    def _get_resize_area(self, pos):
        """Determines which resize area the mouse cursor is in."""
        rect = self.rect()
        x, y = pos.x(), pos.y()
        w, h = rect.width(), rect.height()
        m = self.RESIZE_MARGIN
        
        areas = []
        if x < m: areas.append('left')
        elif x > w - m: areas.append('right')
        
        if y < m: areas.append('top')
        elif y > h - m: areas.append('bottom')

        # Special case: avoid resize conflicts with toolbar on the right
        # This assumes the toolbar is about 40px wide. A more robust solution
        # would be to have the toolbar explicitly block these events.
        if 'right' in areas and x < w - (m + 2): # leave a 2px gap
             if x > w - 40 and y > m and y < h - m:
                return []
            
        return areas

    def _set_cursor_shape(self, areas):
        """Sets the cursor shape based on the resize area."""
        if not areas:
            self.unsetCursor()
            return
            
        if 'left' in areas and 'top' in areas: self.setCursor(Qt.SizeFDiagCursor)
        elif 'right' in areas and 'bottom' in areas: self.setCursor(Qt.SizeFDiagCursor)
        elif 'left' in areas and 'bottom' in areas: self.setCursor(Qt.SizeBDiagCursor)
        elif 'right' in areas and 'top' in areas: self.setCursor(Qt.SizeBDiagCursor)
        elif 'left' in areas or 'right' in areas: self.setCursor(Qt.SizeHorCursor)
        elif 'top' in areas or 'bottom' in areas: self.setCursor(Qt.SizeVerCursor)
        else: self.unsetCursor()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            areas = self._get_resize_area(event.pos())
            if areas:
                self._resize_area = areas
                self._resize_start_pos = event.globalPos()
                self._resize_start_geometry = self.geometry()
                self._is_dragging = False
            else:
                self._resize_area = None
                self._is_dragging = True
                self._drag_position = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.NoButton:
            self._set_cursor_shape(self._get_resize_area(event.pos()))
            event.accept()
            return

        if event.buttons() == Qt.LeftButton:
            if self._resize_area:
                delta = event.globalPos() - self._resize_start_pos
                start_rect = self._resize_start_geometry
                
                x, y, w, h = start_rect.x(), start_rect.y(), start_rect.width(), start_rect.height()
                min_w, min_h = 200, 150 # Minimum window size

                if 'left' in self._resize_area:
                    new_w = w - delta.x()
                    if new_w > min_w:
                        x = start_rect.left() + delta.x()
                        w = new_w
                
                if 'right' in self._resize_area:
                    new_w = w + delta.x()
                    if new_w > min_w: w = new_w
                
                if 'top' in self._resize_area:
                    new_h = h - delta.y()
                    if new_h > min_h:
                        y = start_rect.top() + delta.y()
                        h = new_h
                
                if 'bottom' in self._resize_area:
                    new_h = h + delta.y()
                    if new_h > min_h: h = new_h

                self.setGeometry(x, y, w, h)
                event.accept()
            elif self._is_dragging:
                self.move(event.globalPos() - self._drag_position)
                event.accept()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        self._resize_area = None
        self.unsetCursor()
        event.accept()
