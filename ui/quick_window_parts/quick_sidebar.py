# -*- coding: utf-8 -*-
# ui/quick_window_parts/quick_sidebar.py

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QMenu, QMessageBox, QInputDialog, QColorDialog, 
                             QDialog, QLabel, QPushButton, QHBoxLayout,
                             QTreeWidgetItemIterator)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor, QIcon

from core.settings import load_setting, save_setting
from core.config import COLORS
from ui.utils import create_svg_icon
from ui.advanced_tag_selector import AdvancedTagSelector
from .widgets import DropTreeWidget
from PyQt5.QtWidgets import QLineEdit

# ClickableLineEdit is needed for the preset tags dialog
class ClickableLineEdit(QLineEdit):
    doubleClicked = pyqtSignal()
    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)

class Sidebar(QWidget):
    # Signals to communicate with the main window
    selection_changed = pyqtSignal(str, object) # type, value (e.g., 'category', 1)
    item_dropped_on_category = pyqtSignal(int, int) # idea_id, cat_id
    new_data_requested = pyqtSignal(int) # cat_id
    data_changed = pyqtSignal() # General signal to refresh data

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._init_ui()
        self.connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.system_tree = DropTreeWidget()
        self.system_tree.setHeaderHidden(True)
        self.system_tree.setFocusPolicy(Qt.NoFocus)
        self.system_tree.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.system_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.system_tree.setFixedHeight(150)
        
        self.partition_tree = DropTreeWidget()
        self.partition_tree.setHeaderHidden(True)
        self.partition_tree.setFocusPolicy(Qt.NoFocus)
        self.partition_tree.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.partition_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        layout.addWidget(self.system_tree)
        layout.addWidget(self.partition_tree)

    def connect_signals(self):
        self.system_tree.currentItemChanged.connect(self._on_system_selection_changed)
        self.partition_tree.currentItemChanged.connect(self._on_partition_selection_changed)

        self.system_tree.item_dropped.connect(self.item_dropped_on_category)
        self.partition_tree.item_dropped.connect(self.item_dropped_on_category)

        self.system_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.system_tree.customContextMenuRequested.connect(self._show_partition_context_menu)
        
        self.partition_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.partition_tree.customContextMenuRequested.connect(self._show_partition_context_menu)

        self.partition_tree.order_changed.connect(self._save_partition_order)

    def _on_system_selection_changed(self, current, previous):
        if current:
            self.partition_tree.blockSignals(True)
            self.partition_tree.clearSelection()
            self.partition_tree.setCurrentItem(None)
            self.partition_tree.blockSignals(False)
            
            data = current.data(0, Qt.UserRole)
            if data:
                p_type = data.get('type')
                p_val = data.get('id')
                if p_type == 'uncategorized':
                    self.selection_changed.emit('category', None)
                elif p_type in ['all', 'today', 'untagged', 'bookmark', 'trash']:
                    self.selection_changed.emit(p_type, None)

    def _on_partition_selection_changed(self, current, previous):
        if current:
            self.system_tree.blockSignals(True)
            self.system_tree.clearSelection()
            self.system_tree.setCurrentItem(None)
            self.system_tree.blockSignals(False)
            
            data = current.data(0, Qt.UserRole)
            if data and data.get('type') == 'partition':
                self.selection_changed.emit('category', data.get('id'))

    def refresh_ui(self):
        self._update_partition_tree()

    def _create_color_icon(self, color_str):
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(color_str or "#808080"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(2, 2, 12, 12, 4, 4)
        painter.end()
        return QIcon(pixmap)

    def _update_partition_tree(self):
        # 1. 在清空列表前，先保存当前选中项的数据，而不是引用
        selected_data = None
        current_sys_item = self.system_tree.currentItem()
        current_user_item = self.partition_tree.currentItem()
        if current_user_item:
            selected_data = current_user_item.data(0, Qt.UserRole)
        elif current_sys_item:
            selected_data = current_sys_item.data(0, Qt.UserRole)

        # 2. 清空并重新填充列表
        self.system_tree.clear()
        self.partition_tree.clear()

        counts = self.db.get_counts()
        
        # 填充系统树
        static_items = [
            ("全部数据", 'all', 'all_data.svg'), ("今日数据", 'today', 'today.svg'),
            ("未分类", 'uncategorized', 'uncategorized.svg'), ("未标签", 'untagged', 'untagged.svg'),
            ("书签", 'bookmark', 'bookmark.svg'), ("回收站", 'trash', 'trash.svg')
        ]
        for name, key, icon_filename in static_items:
            data = {'type': key, 'id': {'all': -1, 'today': -5, 'uncategorized': -15, 'untagged': -16, 'bookmark': -20, 'trash': -30}.get(key)}
            item = QTreeWidgetItem(self.system_tree, [f"{name} ({counts.get(key, 0)})"])
            item.setData(0, Qt.UserRole, data)
            item.setIcon(0, create_svg_icon(icon_filename))
            item.setFlags(item.flags() & ~Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)

        # 填充用户分区树
        partition_counts = counts.get('categories', {})
        user_partitions_root = QTreeWidgetItem(self.partition_tree, ["我的分区"])
        user_partitions_root.setIcon(0, create_svg_icon("branch.svg", "white"))
        user_partitions_root.setFlags(Qt.ItemIsEnabled | Qt.ItemIsDropEnabled)
        font = user_partitions_root.font(0); font.setBold(True); user_partitions_root.setFont(0, font)
        user_partitions_root.setForeground(0, QColor("#FFFFFF"))
        self._add_partition_recursive(self.db.get_partitions_tree(), user_partitions_root, partition_counts)
        self.partition_tree.expandAll()
        
        # 3. 使用保存的数据来恢复选中状态
        restored = False
        if selected_data:
            if self.select_item_by_data(self.partition_tree, selected_data):
                restored = True
            elif self.select_item_by_data(self.system_tree, selected_data):
                restored = True

        # 4. 如果没有恢复成功，则默认选中第一项
        if not restored and self.system_tree.topLevelItemCount() > 0:
            self.system_tree.setCurrentItem(self.system_tree.topLevelItem(0))

    def select_item_by_data(self, tree, data_to_match):
        if not data_to_match: return False
        it = QTreeWidgetItemIterator(tree)
        while it.value():
            item = it.value()
            item_data = item.data(0, Qt.UserRole)
            if item_data and item_data.get('id') == data_to_match.get('id') and item_data.get('type') == data_to_match.get('type'):
                tree.setCurrentItem(item)
                return True # 表示成功找到并选中
            it += 1
        return False # 表示未找到
            
    def _add_partition_recursive(self, partitions, parent_item, partition_counts):
        for partition in partitions:
            count = partition_counts.get(partition.id, 0)
            item = QTreeWidgetItem(parent_item, [f"{partition.name} ({count})"])
            item.setData(0, Qt.UserRole, {'type': 'partition', 'id': partition.id, 'color': partition.color})
            item.setIcon(0, self._create_color_icon(partition.color))
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
            if partition.children: self._add_partition_recursive(partition.children, item, partition_counts)

    def _save_partition_order(self):
        update_list = []
        def iterate_items(parent_item, parent_id):
            for i in range(parent_item.childCount()):
                item = parent_item.child(i)
                data = item.data(0, Qt.UserRole)
                if data and data.get('type') == 'partition':
                    cat_id = data.get('id')
                    update_list.append({'id': cat_id, 'parent_id': parent_id, 'sort_order': i})
                    if item.childCount() > 0: iterate_items(item, cat_id)
        iterate_items(self.partition_tree.invisibleRootItem(), None)
        if update_list: self.db.save_category_order(update_list)

    def get_current_selection_text(self):
        current_sys = self.system_tree.currentItem()
        current_user = self.partition_tree.currentItem()
        if current_sys: return current_sys.text(0).split(' (')[0]
        if current_user: return current_user.text(0).split(' (')[0]
        return "N/A"

    def get_current_selection_color(self):
        current_user = self.partition_tree.currentItem()
        if current_user:
            data = current_user.data(0, Qt.UserRole)
            if data and data.get('type') == 'partition':
                return data.get('color')
        return None
        
    def _show_partition_context_menu(self, pos):
        sender = self.sender()
        if not sender: return
        
        item = sender.itemAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet(f"background-color: {COLORS.get('bg_dark', '#2d2d2d')}; color: white; border: 1px solid #444;")
        
        if not item or item.text(0) == "我的分区":
            menu.addAction('➕ 新建分组', self._new_group)
            menu.exec_(sender.mapToGlobal(pos))
            return
            
        data = item.data(0, Qt.UserRole)
        if data and data.get('type') == 'partition':
            cat_id = data.get('id')
            current_name = item.text(0).split(' (')[0]
            
            menu.addAction('新建数据', lambda: self.new_data_requested.emit(cat_id))
            menu.addSeparator()
            menu.addAction('设置颜色', lambda: self._change_color(cat_id))
            menu.addAction('设置预设标签', lambda: self._set_preset_tags(cat_id))
            menu.addSeparator()
            menu.addAction('新建分组', self._new_group)
            menu.addAction('新建分区', lambda: self._new_zone(cat_id))
            menu.addAction('重命名', lambda: self._rename_category(cat_id, current_name))
            menu.addAction('删除', lambda: self._del_category(cat_id))
            
            menu.exec_(sender.mapToGlobal(pos))
        elif data and data.get('type') == 'trash':
            menu.addAction('清空回收站', self._empty_trash)
            menu.exec_(sender.mapToGlobal(pos))

    def _empty_trash(self):
        if QMessageBox.Yes == QMessageBox.warning(self, '清空回收站', '确定要清空回收站吗？\n此操作将永久删除所有内容，不可恢复！', QMessageBox.Yes | QMessageBox.No):
            self.db.empty_trash()
            self.data_changed.emit()

    def _new_group(self):
        self._add_category(parent_id=None, title='新建组', label='组名称:')

    def _new_zone(self, parent_id):
        self._add_category(parent_id=parent_id, title='新建区', label='区名称:')

    def _add_category(self, parent_id, title, label):
        text, ok = QInputDialog.getText(self, title, label)
        if ok and text:
            new_cat_id = self.db.add_category(text, parent_id=parent_id)
            if new_cat_id:
                recent_cats = load_setting('recent_categories', [])
                if new_cat_id in recent_cats: recent_cats.remove(new_cat_id)
                recent_cats.insert(0, new_cat_id)
                save_setting('recent_categories', recent_cats)
            self.data_changed.emit()
            
    def _rename_category(self, cat_id, old_name):
        text, ok = QInputDialog.getText(self, '重命名', '新名称:', text=old_name)
        if ok and text and text.strip():
            self.db.rename_category(cat_id, text.strip())
            self.data_changed.emit()

    def _del_category(self, cid):
        c = self.db.conn.cursor()
        c.execute("SELECT COUNT(*) FROM categories WHERE parent_id = ?", (cid,))
        child_count = c.fetchone()[0]
        msg = '确认删除此分类? (其中的内容将移至未分类)'
        if child_count > 0: msg = f'此组包含 {child_count} 个区，确认一并删除?\n(所有内容都将移至未分类)'
        
        if QMessageBox.Yes == QMessageBox.question(self, '确认删除', msg):
            c.execute("SELECT id FROM categories WHERE parent_id = ?", (cid,))
            child_ids = [row[0] for row in c.fetchall()]
            for child_id in child_ids: self.db.delete_category(child_id)
            self.db.delete_category(cid)
            self.data_changed.emit()

    def _change_color(self, cat_id):
        color = QColorDialog.getColor(Qt.gray, self, "选择分类颜色")
        if color.isValid():
            self.db.set_category_color(cat_id, color.name())
            self.data_changed.emit()

    def _set_preset_tags(self, cat_id):
        from PyQt5.QtWidgets import QLineEdit # Local import to avoid circular dependency if moved
        current_tags = self.db.get_category_preset_tags(cat_id)
        dlg = QDialog(self)
        dlg.setWindowTitle("设置预设标签")
        dlg.setStyleSheet(f"background-color: {COLORS.get('bg_dark', '#2d2d2d')}; color: #EEE;")
        dlg.setFixedSize(350, 150)
        
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)
        info = QLabel("拖入该分类时自动绑定以下标签：\n(双击输入框选择历史标签)")
        info.setStyleSheet("color: #888; font-size: 12px; margin-bottom: 5px;")
        layout.addWidget(info)
        
        inp = ClickableLineEdit()
        inp.setText(current_tags)
        inp.setPlaceholderText("例如: 工作, 重要 (逗号分隔)")
        inp.setStyleSheet(f"background-color: {COLORS.get('bg_mid', '#333')}; border: 1px solid #444; padding: 6px; border-radius: 4px; color: white;")
        layout.addWidget(inp)
        
        def open_tag_selector():
            initial_list = [t.strip() for t in inp.text().split(',') if t.strip()]
            selector = AdvancedTagSelector(self.db, idea_id=None, initial_tags=initial_list)
            def on_confirmed(tags): inp.setText(', '.join(tags))
            selector.tags_confirmed.connect(on_confirmed)
            selector.show_at_cursor()
            
        inp.doubleClicked.connect(open_tag_selector)
        
        btns = QHBoxLayout()
        btns.addStretch()
        btn_ok = QPushButton("完成")
        btn_ok.setStyleSheet(f"background-color: {COLORS.get('primary', '#0078D4')}; border:none; padding: 5px 15px; border-radius: 4px; font-weight:bold; color: white;")
        btn_ok.clicked.connect(dlg.accept)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)
        
        if dlg.exec_() == QDialog.Accepted:
            new_tags = inp.text().strip()
            self.db.set_category_preset_tags(cat_id, new_tags)
            tags_list = [t.strip() for t in new_tags.split(',') if t.strip()]
            if tags_list:
                self.db.apply_preset_tags_to_category_items(cat_id, tags_list)
            self.data_changed.emit()
