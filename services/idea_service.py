# services/idea_service.py
from core.enums import FilterType

class IdeaService:
    def __init__(self, idea_repo, tag_repo, category_repo):
        self.idea_repo = idea_repo
        self.tag_repo = tag_repo
        self.category_repo = category_repo

    def add_idea(self, title, content, color, tags, category_id=None, item_type='text', data_blob=None):
        idea_id = self.idea_repo.add(title, content, color, category_id, item_type, data_blob)
        self.tag_repo.update_tags_for_idea(idea_id, tags)
        return idea_id

    def update_idea(self, iid, title, content, color, tags, category_id=None, item_type='text', data_blob=None):
        self.idea_repo.update(iid, title, content, color, category_id, item_type, data_blob)
        self.tag_repo.update_tags_for_idea(iid, tags)

    def update_tags_for_idea(self, idea_id, tags):
        self.tag_repo.update_tags_for_idea(idea_id, tags)

    def get_ideas_for_filter(self, search_text: str, filter_type_str: str, filter_value):
        try:
            filter_type_enum = FilterType(filter_type_str)
        except ValueError:
            filter_type_enum = FilterType.ALL
        return self.idea_repo.get_all(search_text, filter_type_enum, filter_value)

    def toggle_favorite(self, idea_id):
        self.idea_repo.toggle_field(idea_id, 'is_favorite')

    def toggle_pinned(self, idea_id):
        self.idea_repo.toggle_field(idea_id, 'is_pinned')

    def move_to_trash(self, idea_ids):
        for iid in idea_ids:
            self.idea_repo.set_deleted(iid, True)
    
    def restore_from_trash(self, idea_ids):
        for iid in idea_ids:
            self.idea_repo.set_deleted(iid, False)

    def delete_permanently(self, idea_ids):
        for iid in idea_ids:
            self.idea_repo.delete_permanent(iid)

    def move_to_category(self, idea_ids, category_id):
        for iid in idea_ids:
            self.idea_repo.move_category(iid, category_id)

    # --- Pass-through methods to repositories ---
    
    def get_idea_with_blob(self, iid):
        return self.idea_repo.get_by_id(iid, include_blob=True)

    def get_idea_tags(self, iid):
        return self.tag_repo.get_tags_for_idea(iid)

    def get_all_categories(self):
        return self.category_repo.get_all()

    def get_category_tree(self):
        return self.category_repo.get_tree()

    def get_all_tags_with_counts(self):
        return self.tag_repo.get_all_tags_with_counts()

    def get_stats_counts(self):
        return self.idea_repo.get_counts()

    def add_category(self, name, parent_id=None):
        self.category_repo.add(name, parent_id)

    def rename_category(self, cat_id, new_name):
        self.category_repo.rename(cat_id, new_name)

    def delete_category(self, cat_id):
        self.category_repo.delete(cat_id)

    def save_category_order(self, order_list):
        self.category_repo.save_order(order_list)
