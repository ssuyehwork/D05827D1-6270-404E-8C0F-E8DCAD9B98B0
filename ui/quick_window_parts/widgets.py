# -*- coding: utf-8 -*-
# ui/quick_window_parts/widgets.py

from PyQt5.QtWidgets import QListWidget, QTreeWidget, QAbstractItemView
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData
from PyQt5.QtGui import QDrag

class DraggableListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item: return
        data = item.data(Qt.UserRole)
        if not data: return
        idea_id = data['id']
        
        mime = QMimeData()
        mime.setData('application/x-idea-id', str(idea_id).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec_(Qt.MoveAction)

class DropTreeWidget(QTreeWidget):
    item_dropped = pyqtSignal(int, int)
    order_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDropIndicatorShown(True)

    def dragEnterEvent(self, event):
        # 优先允许自身拖拽（排序）
        if event.source() == self:
            super().dragEnterEvent(event)
            event.accept()
        elif event.mimeData().hasFormat('application/x-idea-id'):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        # 自身拖拽（排序）：必须调用 super() 且 accept()，否则不显示插入线
        if event.source() == self:
            super().dragMoveEvent(event)
            event.accept()
            return
            
        # 外部拖拽（归档笔记）
        if event.mimeData().hasFormat('application/x-idea-id'):
            item = self.itemAt(event.pos())
            if item:
                data = item.data(0, Qt.UserRole)
                # 只有具备 drop 权限的节点才允许放入
                if item.flags() & Qt.ItemIsDropEnabled:
                    # 额外检查：如果是 user root 或者是具体分类
                    if data and data.get('type') in ['partition', 'favorite', 'trash', 'uncategorized']:
                        event.accept()
                        return
            event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        # 情况1：拖入笔记 -> 归档
        if event.mimeData().hasFormat('application/x-idea-id'):
            try:
                idea_id = int(event.mimeData().data('application/x-idea-id'))
                item = self.itemAt(event.pos())
                if item:
                    data = item.data(0, Qt.UserRole)
                    # 允许拖入各类容器
                    if data and data.get('type') in ['partition', 'favorite', 'trash', 'uncategorized']:
                        cat_id = data.get('id')
                        self.item_dropped.emit(idea_id, cat_id)
                        event.acceptProposedAction()
            except Exception as e:
                pass
        # 情况2：自身拖拽 -> 排序
        elif event.source() == self:
            # 调用父类完成树节点的移动
            super().dropEvent(event)
            # 发出信号保存顺序
            self.order_changed.emit()
            event.accept()
