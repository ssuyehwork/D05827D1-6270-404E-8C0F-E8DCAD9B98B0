# -*- coding: utf-8 -*-
# ui/quick_window_parts/widgets.py

import os
from PyQt5.QtWidgets import QListWidget, QTreeWidget, QAbstractItemView
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData, QUrl, QPoint
from PyQt5.QtGui import QDrag, QImage, QPixmap, QRegion, QPainter, QPen, QColor

class DraggableListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)

    def startDrag(self, supportedActions):
        items = self.selectedItems()
        if not items: return
        
        # 收集数据
        ids = []
        urls = []
        texts = []
        
        for item in items:
            data = item.data(Qt.UserRole)
            if not data: continue
            
            try:
                ids.append(str(data['id']))
                item_type = data['item_type'] if data['item_type'] else 'text'
                content = data['content'] if data['content'] else ''
                
                # 收集文本
                if content:
                    texts.append(content)
                
                # 收集文件路径
                if item_type != 'text' and content:
                    paths = [p.strip() for p in content.split(';') if p.strip()]
                    for path in paths:
                        if os.path.exists(path):
                            urls.append(QUrl.fromLocalFile(path))
            except (KeyError, IndexError, TypeError):
                continue
                
        if not ids: return

        mime = QMimeData()
        
        # 1. 内部专用格式 (ID 列表，逗号分隔)
        mime.setData('application/x-idea-ids', ",".join(ids).encode())
        # 兼容旧格式（取第一个）
        mime.setData('application/x-idea-id', ids[0].encode())
        
        # 2. 外部通用格式
        if urls:
            mime.setUrls(urls)
        
        if texts:
            full_text = "\n---\n".join(texts)
            mime.setText(full_text)
            mime.setHtml(full_text.replace('\n', '<br>'))

        drag = QDrag(self)
        drag.setMimeData(mime)
        
        # 3. 视觉反馈
        w, h = 20, 10
        pixmap = QPixmap(w + 2, h + 2) 
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        pen = QPen(QColor(255, 255, 255, 200))
        pen.setStyle(Qt.DashLine)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(0, 0, w, h)
        
        # 如果多选，画个叠层效果
        if len(items) > 1:
            painter.drawRect(2, 2, w, h)
            
        painter.end()
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(-15, -30))
        
        drag.exec_(Qt.CopyAction | Qt.MoveAction, Qt.CopyAction)

class DropTreeWidget(QTreeWidget):
    item_dropped = pyqtSignal(int, int)
    order_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dragging_external = False
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDropIndicatorShown(True)

    def dragEnterEvent(self, event):
        if event.source() != self:
            self._is_dragging_external = True

        if event.source() == self:
            super().dragEnterEvent(event)
            event.accept()
            return

        if event.mimeData().hasFormat('application/x-idea-id') or event.mimeData().hasFormat('application/x-idea-ids'):
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._is_dragging_external = False
        super().dragLeaveEvent(event)

    def dragMoveEvent(self, event):
        if event.source() == self:
            super().dragMoveEvent(event)
            event.accept()
            return
            
        if event.mimeData().hasFormat('application/x-idea-id') or event.mimeData().hasFormat('application/x-idea-ids'):
            event.setDropAction(Qt.MoveAction)
            item = self.itemAt(event.pos())
            if item:
                data = item.data(0, Qt.UserRole)
                if item.flags() & Qt.ItemIsDropEnabled:
                    if isinstance(data, dict) and data.get('type') in ['partition', 'bookmark', 'trash', 'uncategorized']:
                        self.setCurrentItem(item)
                        event.accept()
                        return
            event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        self._is_dragging_external = False # Reset flag on drop
        # 1. 笔记归档 (支持多选)
        if event.mimeData().hasFormat('application/x-idea-ids'):
            try:
                raw_data = event.mimeData().data('application/x-idea-ids').data().decode('utf-8')
                ids = [int(x) for x in raw_data.split(',') if x]
                
                item = self.itemAt(event.pos())
                if item:
                    data = item.data(0, Qt.UserRole)
                    if isinstance(data, dict) and data.get('type') in ['partition', 'bookmark', 'trash', 'uncategorized']:
                        cat_id = data.get('id')
                        # 循环触发信号
                        for iid in ids:
                            self.item_dropped.emit(iid, cat_id)
                        
                        event.setDropAction(Qt.MoveAction)
                        event.accept()
            except Exception as e:
                print(f"Drop error: {e}")
                event.ignore()
        
        # 兼容单选拖拽
        elif event.mimeData().hasFormat('application/x-idea-id'):
            try:
                idea_id = int(event.mimeData().data('application/x-idea-id'))
                item = self.itemAt(event.pos())
                if item:
                    data = item.data(0, Qt.UserRole)
                    if isinstance(data, dict) and data.get('type') in ['partition', 'bookmark', 'trash', 'uncategorized']:
                        cat_id = data.get('id')
                        self.item_dropped.emit(idea_id, cat_id)
                        event.setDropAction(Qt.MoveAction)
                        event.accept()
            except Exception:
                event.ignore()
                
        # 2. 自身排序
        elif event.source() == self:
            super().dropEvent(event)
            self.order_changed.emit()
            event.accept()