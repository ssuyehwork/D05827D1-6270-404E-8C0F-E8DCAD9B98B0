# -*- coding: utf-8 -*-
# ui/sidebar.py

import random
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QAbstractItemView, QMenu, QColorDialog, QInputDialog, 
                             QMessageBox, QDialog, QLabel, QLineEdit, QPushButton, QHBoxLayout,
                             QTreeWidgetItemIterator, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap, QCursor

from core.config import COLORS
from core.settings import load_setting, save_setting
from ui.utils import create_svg_icon
from ui.advanced_tag_selector import AdvancedTagSelector

class ClickableLineEdit(QLineEdit):
    doubleClicked = pyqtSignal()
    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)

class DropTreeWidget(QTreeWidget):
    items_dropped_on_category = pyqtSignal(list, object)
    order_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDropIndicatorShown(True)
        self.setHeaderHidden(True)
        self.setIndentation(16)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFrameShape(QFrame.NoFrame) 
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def dragEnterEvent(self, event):
        if event.source() == self:
            super().dragEnterEvent(event)
            event.accept()
            return
        if event.mimeData().hasFormat('application/x-idea-ids') or event.mimeData().hasFormat('application/x-idea-id'):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.source() == self:
            super().dragMoveEvent(event)
            event.accept()
            return
        if event.mimeData().hasFormat('application/x-idea-ids') or event.mimeData().hasFormat('application/x-idea-id'):
            item = self.itemAt(event.pos())
            if item:
                data = item.data(0, Qt.UserRole)
                if item.flags() & Qt.ItemIsDropEnabled:
                    if isinstance(data, dict) and data.get('type') in ['category', 'partition', 'bookmark', 'trash', 'uncategorized']:
                        self.setCurrentItem(item)
                        event.accept()
                        return
            event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasFormat('application/x-idea-ids') or event.mimeData().hasFormat('application/x-idea-id'):
            ids = []
            if event.mimeData().hasFormat('application/x-idea-ids'):
                try:
                    raw = event.mimeData().data('application/x-idea-ids').data().decode('utf-8')
                    ids = [int(x) for x in raw.split(',') if x]
                except: pass
            if not ids and event.mimeData().hasFormat('application/x-idea-id'):
                try:
                    ids = [int(event.mimeData().data('application/x-idea-id'))]
                except: pass
            
            if ids:
                item = self.itemAt(event.pos())
                if item:
                    data = item.data(0, Qt.UserRole)
                    if isinstance(data, dict):
                        target_val = data.get('id')
                        target_type = data.get('type')
                        self.items_dropped_on_category.emit(ids, (target_type, target_val))
                        event.acceptProposedAction()
                        return

        elif event.source() == self:
            super().dropEvent(event)
            self.order_changed.emit()
            event.accept()

class Sidebar(QWidget):
    filter_changed = pyqtSignal(str, object)
    data_changed = pyqtSignal()
    new_data_requested = pyqtSignal(int)
    items_moved = pyqtSignal(list)

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.db = service
        self._init_ui()
        self._connect_signals()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 1. 系统树
        self.system_tree = DropTreeWidget()
        # 高度动态计算
        self.system_tree.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.system_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.system_tree.setDragEnabled(False) 
        
        # 2. 分区树
        self.partition_tree = DropTreeWidget()
        
        # --- 样式 ---
        common_style = f"""
            QTreeWidget {{
                background-color: {COLORS['bg_mid']};
                color: #e0e0e0;
                border: none;
                font-size: 13px;
                padding: 0px; 
                outline: none;
            }}
            QTreeWidget::item {{
                height: 25px;
                padding-left: 4px;
                border: none;
                border-bottom: 1px solid #2A2A2A; 
                margin: 0px; 
            }}
            QTreeWidget::item:hover {{
                background-color: #2a2d2e;
            }}
            QTreeWidget::item:selected {{
                background-color: #37373d;
                color: white;
                border-bottom: 1px solid #2A2A2A;
            }}
            QScrollBar:vertical {{ border: none; background: transparent; width: 6px; margin: 0px; }}
            QScrollBar::handle:vertical {{ background: #444; border-radius: 3px; min-height: 20px; }}
            QScrollBar::handle:vertical:hover {{ background: #555; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """
        self.system_tree.setStyleSheet(common_style)
        self.partition_tree.setStyleSheet(common_style)
        
        layout.addWidget(self.system_tree)
        layout.addWidget(self.partition_tree)

    def _connect_signals(self):
        self.system_tree.itemClicked.connect(self._on_system_clicked)
        self.partition_tree.itemClicked.connect(self._on_partition_clicked)
        self.system_tree.items_dropped_on_category.connect(self._handle_items_dropped)
        self.partition_tree.items_dropped_on_category.connect(self._handle_items_dropped)
        self.partition_tree.order_changed.connect(self._save_partition_order)
        
        self.system_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.system_tree.customContextMenuRequested.connect(self._show_context_menu)
        self.partition_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.partition_tree.customContextMenuRequested.connect(self._show_context_menu)

    def refresh(self):
        QTimer.singleShot(10, self.refresh_sync)

    def refresh_sync(self):
        curr_sys = self.system_tree.currentItem()
        curr_part = self.partition_tree.currentItem()
        selected_data = None
        if curr_sys: selected_data = curr_sys.data(0, Qt.UserRole)
        if curr_part: selected_data = curr_part.data(0, Qt.UserRole)
        
        self.system_tree.blockSignals(True)
        self.partition_tree.blockSignals(True)
        
        try:
            self.system_tree.clear()
            self.partition_tree.clear()
            counts = self.db.get_counts()
            
            # 系统项列表
            sys_items = [
                ("全部数据", 'all', 'all_data.svg'),
                ("今日数据", 'today', 'today.svg'),
                ("未分类", 'uncategorized', 'uncategorized.svg'),
                ("未标签", 'untagged', 'untagged.svg'),
                ("书签", 'bookmark', 'bookmark.svg'),
                ("回收站", 'trash', 'trash.svg')
            ]
            
            # 动态计算高度
            item_height = 25
            total_height = len(sys_items) * item_height
            self.system_tree.setFixedHeight(total_height)
            self.system_tree.verticalScrollBar().setRange(0, 0)
            
            for label, key, icon in sys_items:
                data = {'type': key, 'id': None}
                item = QTreeWidgetItem(self.system_tree)
                item.setText(0, f"{label} ({counts.get(key, 0)})")
                item.setIcon(0, create_svg_icon(icon))
                item.setData(0, Qt.UserRole, data)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDropEnabled)
            
            # 用户分区
            user_root = QTreeWidgetItem(self.partition_tree, ["我的分区"])
            user_root.setIcon(0, create_svg_icon("branch.svg", "white"))
            user_root.setFlags(Qt.ItemIsEnabled | Qt.ItemIsDropEnabled)
            font = user_root.font(0); font.setBold(True); user_root.setFont(0, font)
            user_root.setForeground(0, QColor("#FFFFFF"))
            
            partition_counts = counts.get('categories', {})
            tree_data = self.db.get_partitions_tree()
            self._add_partition_recursive(tree_data, user_root, partition_counts)
            
            self.partition_tree.expandAll()
            
            if selected_data:
                self._restore_selection(selected_data)
            elif not curr_sys and not curr_part and self.system_tree.topLevelItemCount() > 0:
                self.system_tree.setCurrentItem(self.system_tree.topLevelItem(0))
                
        finally:
            self.system_tree.blockSignals(False)
            self.partition_tree.blockSignals(False)

    def _add_partition_recursive(self, partitions, parent_item, counts):
        for p in partitions:
            count = counts.get(p.id, 0)
            item = QTreeWidgetItem(parent_item, [f"{p.name} ({count})"])
            item.setIcon(0, self._create_color_icon(p.color))
            data = {'type': 'category', 'id': p.id, 'color': p.color, 'parent_id': p.parent_id}
            item.setData(0, Qt.UserRole, data)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
            if p.children:
                self._add_partition_recursive(p.children, item, counts)

    def _create_color_icon(self, color_str):
        pixmap = QPixmap(14, 14)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        c = QColor(color_str if color_str else "#808080")
        painter.setBrush(c)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(1, 1, 12, 12)
        painter.end()
        return QIcon(pixmap)

    def _on_system_clicked(self, item, col):
        self.partition_tree.blockSignals(True)
        self.partition_tree.clearSelection()
        self.partition_tree.setCurrentItem(None)
        self.partition_tree.blockSignals(False)
        
        data = item.data(0, Qt.UserRole)
        if data:
            f_type = data.get('type')
            if f_type == 'uncategorized':
                self.filter_changed.emit('category', None)
            else:
                self.filter_changed.emit(f_type, None)

    def _on_partition_clicked(self, item, col):
        if item.text(0) == "我的分区": return
        self.system_tree.blockSignals(True)
        self.system_tree.clearSelection()
        self.system_tree.setCurrentItem(None)
        self.system_tree.blockSignals(False)
        
        data = item.data(0, Qt.UserRole)
        if data:
            self.filter_changed.emit('category', data.get('id'))

    def _restore_selection(self, target_data):
        target_type = target_data.get('type')
        target_id = target_data.get('id')
        it = QTreeWidgetItemIterator(self.system_tree)
        while it.value():
            item = it.value()
            d = item.data(0, Qt.UserRole)
            if d and d.get('type') == target_type:
                self.system_tree.setCurrentItem(item); return
            it += 1
        it = QTreeWidgetItemIterator(self.partition_tree)
        while it.value():
            item = it.value()
            d = item.data(0, Qt.UserRole)
            if d and d.get('type') == target_type and d.get('id') == target_id:
                self.partition_tree.setCurrentItem(item); return
            it += 1

    def _handle_items_dropped(self, idea_ids, target_info):
        target_type, target_val = target_info
        if target_type == 'trash':
            status_map = self.db.get_lock_status(idea_ids)
            valid_ids = [iid for iid in idea_ids if not status_map.get(iid, 0)]
            if not valid_ids: return 
            for iid in valid_ids: self.db.set_deleted(iid, True, emit_signal=False)
        elif target_type == 'bookmark':
            for iid in idea_ids: self.db.set_favorite(iid, True)
        elif target_type == 'uncategorized':
            for iid in idea_ids: self.db.move_category(iid, None, emit_signal=False)
        elif target_type == 'category':
            cat_id = target_val
            if cat_id is not None:
                recent = load_setting('recent_categories', [])
                if cat_id in recent: recent.remove(cat_id)
                recent.insert(0, cat_id)
                save_setting('recent_categories', recent)
            for iid in idea_ids: self.db.move_category(iid, cat_id, emit_signal=False)
        self.items_moved.emit(idea_ids)
        self.refresh()

    def _save_partition_order(self):
        update_list = []
        def iterate_items(parent_item, parent_id):
            for i in range(parent_item.childCount()):
                item = parent_item.child(i)
                data = item.data(0, Qt.UserRole)
                if data and data.get('type') == 'category':
                    cat_id = data.get('id')
                    update_list.append({'id': cat_id, 'parent_id': parent_id, 'sort_order': i})
                    if item.childCount() > 0: iterate_items(item, cat_id)
        root = self.partition_tree.topLevelItem(0)
        if root:
            iterate_items(root, None)
            if update_list: self.db.save_category_order(update_list)

    def _show_context_menu(self, pos):
        sender_tree = self.sender()
        item = sender_tree.itemAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ background-color: {COLORS['bg_dark']}; color: white; border: 1px solid #444; }} QMenu::item {{ padding: 6px 20px; }} QMenu::item:selected {{ background-color: {COLORS['primary']}; }}")

        # [功能] 刷新
        menu.addAction('刷新', self.refresh)
        menu.addSeparator()

        if not item or item.text(0) == "我的分区":
            menu.addAction('➕ 新建分组', self._new_group)
            menu.exec_(sender_tree.mapToGlobal(pos))
            return

        data = item.data(0, Qt.UserRole)
        if not data: return
        dtype = data.get('type')
        
        if dtype == 'trash':
            menu.addAction('清空回收站', self._empty_trash)
        elif dtype == 'category':
            cat_id = data.get('id')
            current_name = item.text(0).split(' (')[0]
            menu.addAction('新建灵感', lambda: self.new_data_requested.emit(cat_id))
            menu.addSeparator()
            menu.addAction('设置颜色', lambda: self._change_color(cat_id))
            # [功能] 找回随机颜色
            menu.addAction('随机颜色', lambda: self._set_random_color(cat_id))
            menu.addAction('设置预设标签', lambda: self._set_preset_tags(cat_id))
            menu.addSeparator()
            menu.addAction('新建分组', self._new_group)
            menu.addAction('新建分区', lambda: self._new_zone(cat_id))
            menu.addAction('重命名', lambda: self._rename_category(cat_id, current_name))
            menu.addAction('删除', lambda: self._del_category(cat_id))
        menu.exec_(sender_tree.mapToGlobal(pos))

    def _empty_trash(self):
        if QMessageBox.Yes == QMessageBox.warning(self, '警告', '清空回收站不可恢复，确定吗？', QMessageBox.Yes | QMessageBox.No):
            self.db.empty_trash(); self.refresh(); self.data_changed.emit()

    def _new_group(self): self._add_category(None, '新建组', '组名称:')
    def _new_zone(self, parent_id): self._add_category(parent_id, '新建区', '区名称:')

    def _add_category(self, parent_id, title, label):
        text, ok = QInputDialog.getText(self, title, label)
        if ok and text:
            self.db.add_category(text, parent_id=parent_id)
            self.refresh(); self.data_changed.emit()

    def _rename_category(self, cat_id, old_name):
        text, ok = QInputDialog.getText(self, '重命名', '新名称:', text=old_name)
        if ok and text:
            self.db.rename_category(cat_id, text.strip())
            self.refresh(); self.data_changed.emit()

    def _del_category(self, cid):
        if QMessageBox.Yes == QMessageBox.question(self, '删除', '确认删除此分类？(内容将移至未分类)'):
            self.db.delete_category(cid); self.refresh(); self.data_changed.emit()

    def _change_color(self, cat_id):
        color = QColorDialog.getColor(Qt.gray, self, "选择颜色")
        if color.isValid():
            self.db.set_category_color(cat_id, color.name())
            self.refresh(); self.data_changed.emit()

    # [功能] 随机颜色实现
    def _set_random_color(self, cat_id):
        r = random.randint(0, 255)
        g = random.randint(0, 255)
        b = random.randint(0, 255)
        color = QColor(r, g, b)
        # 确保颜色不太亮，适合暗色主题
        while color.lightness() < 80: 
            r = random.randint(0, 255); g = random.randint(0, 255); b = random.randint(0, 255)
            color = QColor(r, g, b)
        
        self.db.set_category_color(cat_id, color.name())
        self.refresh()
        self.data_changed.emit()

    def _set_preset_tags(self, cat_id):
        current = self.db.get_category_preset_tags(cat_id)
        dlg = QDialog(self)
        dlg.setWindowTitle("预设标签")
        dlg.setFixedSize(300, 120)
        dlg.setStyleSheet(f"background: {COLORS['bg_dark']}; color: #eee;")
        l = QVBoxLayout(dlg)
        l.addWidget(QLabel("自动绑定的标签 (逗号分隔):"))
        inp = ClickableLineEdit(); inp.setText(current); inp.setStyleSheet(f"background:{COLORS['bg_mid']}; border:1px solid #555; padding:4px;")
        l.addWidget(inp)
        def open_selector():
            initial = [t.strip() for t in inp.text().split(',') if t.strip()]
            sel = AdvancedTagSelector(self.db, idea_id=None, initial_tags=initial)
            sel.tags_confirmed.connect(lambda tags: inp.setText(', '.join(tags)))
            sel.show_at_cursor()
        inp.doubleClicked.connect(open_selector)
        btn = QPushButton("确定"); btn.clicked.connect(dlg.accept); btn.setStyleSheet(f"background:{COLORS['primary']}; border:none; padding:4px;")
        l.addWidget(btn)
        if dlg.exec_() == QDialog.Accepted:
            self.db.set_category_preset_tags(cat_id, inp.text().strip()); self.data_changed.emit()
            
    # [功能] 补全辅助方法
    def get_current_selection_color(self):
        item = self.partition_tree.currentItem()
        if item:
            data = item.data(0, Qt.UserRole)
            if data and data.get('type') == 'category': return data.get('color')
        return None
        
    def get_current_selection_text(self):
        sys_item = self.system_tree.currentItem()
        part_item = self.partition_tree.currentItem()
        if sys_item: return sys_item.text(0).split(' (')[0]
        if part_item: return part_item.text(0).split(' (')[0]
        return "全部数据"