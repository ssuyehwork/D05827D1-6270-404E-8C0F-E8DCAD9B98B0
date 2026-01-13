# -*- coding: utf-8 -*-
# data/repositories/category_repository.py
import random

class CategoryRepository:
    def __init__(self, db_context):
        self.db = db_context

    def get_all(self):
        c = self.db.get_cursor()
        c.execute('SELECT * FROM categories ORDER BY sort_order ASC, name ASC')
        return c.fetchall()

    def add(self, name, parent_id=None):
        c = self.db.get_cursor()
        if parent_id is None:
            c.execute("SELECT MAX(sort_order) FROM categories WHERE parent_id IS NULL")
        else:
            c.execute("SELECT MAX(sort_order) FROM categories WHERE parent_id = ?", (parent_id,))
        max_order = c.fetchone()[0]
        new_order = (max_order or 0) + 1
        
        palette = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEEAD',
            '#D4A5A5', '#9B59B6', '#3498DB', '#E67E22', '#2ECC71'
        ]
        chosen_color = random.choice(palette)
        
        c.execute(
            'INSERT INTO categories (name, parent_id, sort_order, color) VALUES (?, ?, ?, ?)', 
            (name, parent_id, new_order, chosen_color)
        )
        new_id = c.lastrowid
        self.db.commit()
        return new_id

    def rename(self, cat_id, new_name):
        c = self.db.get_cursor()
        c.execute('UPDATE categories SET name=? WHERE id=?', (new_name, cat_id))
        self.db.commit()

    def set_color(self, cat_id, color):
        c = self.db.get_cursor()
        try:
            find_ids_query = """
                WITH RECURSIVE category_tree(id) AS (
                    SELECT ?
                    UNION ALL
                    SELECT c.id FROM categories c JOIN category_tree ct ON c.parent_id = ct.id
                )
                SELECT id FROM category_tree;
            """
            c.execute(find_ids_query, (cat_id,))
            all_ids = [row[0] for row in c.fetchall()]

            if all_ids:
                placeholders = ','.join('?' * len(all_ids))
                c.execute(f"UPDATE ideas SET color = ? WHERE category_id IN ({placeholders})", (color, *all_ids))
                c.execute(f"UPDATE categories SET color = ? WHERE id IN ({placeholders})", (color, *all_ids))
                self.db.commit()
        except:
            self.db.conn.rollback()

    def delete(self, cid):
        c = self.db.get_cursor()
        c.execute('UPDATE ideas SET category_id=NULL WHERE category_id=?', (cid,))
        c.execute('DELETE FROM categories WHERE id=?', (cid,))
        self.db.commit()

    def set_preset_tags(self, cat_id, tags_str):
        c = self.db.get_cursor()
        c.execute('UPDATE categories SET preset_tags=? WHERE id=?', (tags_str, cat_id))
        self.db.commit()

    def get_preset_tags(self, cat_id):
        c = self.db.get_cursor()
        c.execute('SELECT preset_tags FROM categories WHERE id=?', (cat_id,))
        res = c.fetchone()
        return res[0] if res else ""

    def save_order(self, update_list):
        c = self.db.get_cursor()
        try:
            c.execute("BEGIN TRANSACTION")
            for item in update_list:
                c.execute(
                    "UPDATE categories SET sort_order = ?, parent_id = ? WHERE id = ?",
                    (item['sort_order'], item['parent_id'], item['id'])
                )
            c.execute("COMMIT")
        except:
            c.execute("ROLLBACK")
        finally:
            self.db.commit()

    def get_tree(self):
        class Partition:
            def __init__(self, id, name, color, parent_id, sort_order):
                self.id = id; self.name = name; self.color = color
                self.parent_id = parent_id; self.sort_order = sort_order; self.children = []

        c = self.db.get_cursor()
        c.execute("SELECT id, name, color, parent_id, sort_order FROM categories ORDER BY sort_order ASC, name ASC")
        nodes = {row[0]: Partition(*row) for row in c.fetchall()}
        tree = []
        for _, node in nodes.items():
            if node.parent_id in nodes: nodes[node.parent_id].children.append(node)
            else: tree.append(node)
        return tree