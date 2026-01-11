# -*- coding: utf-8 -*-
# services/idea_service.py
from core.config import COLORS
from core.signals import app_signals
import hashlib
import os

class IdeaService:
    def __init__(self, idea_repo, category_repo, tag_repo):
        self.idea_repo = idea_repo
        self.category_repo = category_repo
        self.tag_repo = tag_repo
        self.conn = self.idea_repo.db.conn # 用于暴露给需要直接访问 conn 的旧代码(如 AdvancedTagSelector)

    # --- Idea Operations ---
    def get_ideas(self, search, f_type, f_val, page=1, page_size=100, tag_filter=None, filter_criteria=None):
        return self.idea_repo.get_list_by_filter(search, f_type, f_val, page, page_size, tag_filter, filter_criteria)

    def get_ideas_count(self, search, f_type, f_val, tag_filter=None, filter_criteria=None):
        return self.idea_repo.get_count_by_filter(search, f_type, f_val, tag_filter, filter_criteria)

    # --- Smart Caching Methods ---
    def get_metadata(self, search, f_type, f_val):
        return self.idea_repo.get_metadata_by_filter(search, f_type, f_val)
        
    def get_details(self, id_list):
        return self.idea_repo.get_details_by_ids(id_list)
    # -----------------------------

    def get_idea(self, iid, include_blob=False):
        return self.idea_repo.get_by_id(iid, include_blob)

    def add_idea(self, title, content, color, tags, category_id=None, item_type='text', data_blob=None):
        if color is None: color = COLORS['default_note']
        iid = self.idea_repo.add(title, content, color, category_id, item_type, data_blob)
        self.tag_repo.update_tags(iid, tags)
        app_signals.data_changed.emit()
        return iid

    def update_idea(self, iid, title, content, color, tags, category_id=None, item_type='text', data_blob=None):
        self.idea_repo.update(iid, title, content, color, category_id, item_type, data_blob)
        self.tag_repo.update_tags(iid, tags)
        app_signals.data_changed.emit()

    def update_field(self, iid, field, value):
        self.idea_repo.update_field(iid, field, value)
        app_signals.data_changed.emit()

    def toggle_field(self, iid, field):
        self.idea_repo.toggle_field(iid, field)
        app_signals.data_changed.emit()

    def set_favorite(self, iid, state):
        self.idea_repo.update_field(iid, 'is_favorite', 1 if state else 0)
        app_signals.data_changed.emit()

    def set_deleted(self, iid, state):
        val = 1 if state else 0
        self.idea_repo.update_field(iid, 'is_deleted', val)
        if state:
            self.idea_repo.update_field(iid, 'category_id', None)
            self.idea_repo.update_field(iid, 'color', COLORS['trash'])
        else:
            self.idea_repo.update_field(iid, 'color', COLORS['uncategorized'])
        app_signals.data_changed.emit()

    def set_rating(self, iid, rating):
        self.idea_repo.update_field(iid, 'rating', rating)
        app_signals.data_changed.emit()

    def delete_permanent(self, iid):
        self.idea_repo.delete_permanent(iid)
        app_signals.data_changed.emit()

    def move_category(self, iid, cat_id):
        self.idea_repo.update_field(iid, 'category_id', cat_id)
        self.idea_repo.update_field(iid, 'is_deleted', 0)
        # 如果移动到分类，应应用分类颜色（略）
        app_signals.data_changed.emit()

    def get_lock_status(self, ids):
        return self.idea_repo.get_lock_status(ids)

    def set_locked(self, ids, state):
        self.idea_repo.set_locked(ids, state)
        app_signals.data_changed.emit()

    def get_filter_stats(self, search, f_type, f_val):
        return self.idea_repo.get_filter_stats(search, f_type, f_val)
        
    def empty_trash(self):
        c = self.idea_repo.db.get_cursor()
        c.execute('DELETE FROM idea_tags WHERE idea_id IN (SELECT id FROM ideas WHERE is_deleted=1)')
        c.execute('DELETE FROM ideas WHERE is_deleted=1')
        self.idea_repo.db.commit()
        app_signals.data_changed.emit()

    # --- Clipboard Logic (Ported from db_manager) ---
    def add_clipboard_item(self, item_type, content, data_blob=None, category_id=None):
        hasher = hashlib.sha256()
        if item_type == 'text' or item_type == 'file':
            hasher.update(content.encode('utf-8'))
        elif item_type == 'image' and data_blob:
            hasher.update(data_blob)
        content_hash = hasher.hexdigest()

        existing = self.idea_repo.find_by_hash(content_hash)
        if existing:
            # 【修复】使用专门的时间戳更新方法
            self.idea_repo.update_timestamp(existing[0])
            app_signals.data_changed.emit()
            return existing[0], False
        else:
            if item_type == 'text': title = content.strip().split('\n')[0][:50]
            elif item_type == 'image': title = "[图片]"
            elif item_type == 'file': title = f"[文件] {os.path.basename(content.split(';')[0])}"
            else: title = "未命名"
            
            iid = self.idea_repo.add(title, content, COLORS['default_note'], category_id, item_type, data_blob, content_hash)
            app_signals.data_changed.emit()
            return iid, True

    # --- Tag Operations ---
    def get_tags(self, iid):
        return self.tag_repo.get_by_idea(iid)
    
    def get_all_tags(self):
        return self.tag_repo.get_all()

    def add_tags_to_multiple_ideas(self, idea_ids, tags):
        self.tag_repo.add_to_multiple(idea_ids, tags)
        app_signals.data_changed.emit()
        
    def remove_tag_from_multiple_ideas(self, idea_ids, tag_name):
        self.tag_repo.remove_from_multiple(idea_ids, tag_name)
        app_signals.data_changed.emit()
        
    def get_top_tags(self):
        return self.tag_repo.get_top_tags()

    # --- Category Operations ---
    def get_categories(self):
        return self.category_repo.get_all()

    def get_partitions_tree(self):
        return self.category_repo.get_tree()

    def get_counts(self):
        return self.idea_repo.get_counts()
        
    def add_category(self, name, parent_id=None):
        new_id = self.category_repo.add(name, parent_id)
        app_signals.data_changed.emit()
        return new_id
        
    def rename_category(self, cat_id, new_name):
        self.category_repo.rename(cat_id, new_name)
        app_signals.data_changed.emit()
        
    def delete_category(self, cat_id):
        self.category_repo.delete(cat_id)
        app_signals.data_changed.emit()
        
    def set_category_color(self, cat_id, color):
        self.category_repo.set_color(cat_id, color)
        app_signals.data_changed.emit()
        
    def set_category_preset_tags(self, cat_id, tags):
        self.category_repo.set_preset_tags(cat_id, tags)
        app_signals.data_changed.emit()
        
    def get_category_preset_tags(self, cat_id):
        return self.category_repo.get_preset_tags(cat_id)
        
    def apply_preset_tags_to_category_items(self, cat_id, tags_list):
        # 复杂逻辑：先找 idea ids，再加 tags
        c = self.idea_repo.db.get_cursor()
        c.execute('SELECT id FROM ideas WHERE category_id=? AND is_deleted=0', (cat_id,))
        ids = [r[0] for r in c.fetchall()]
        self.tag_repo.add_to_multiple(ids, tags_list)
        app_signals.data_changed.emit()
        
    def save_category_order(self, update_list):
        self.category_repo.save_order(update_list)
        app_signals.data_changed.emit()