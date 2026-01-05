# data/repositories/idea_repository.py
import sqlite3
import hashlib
import os
from core.enums import FilterType

class IdeaRepository:
    def __init__(self, conn):
        self.conn = conn

    def add(self, title, content, color, category_id=None, item_type='text', data_blob=None, content_hash=None):
        c = self.conn.cursor()
        c.execute(
            'INSERT INTO ideas (title, content, color, category_id, item_type, data_blob, content_hash) VALUES (?,?,?,?,?,?,?)',
            (title, content, color, category_id, item_type, data_blob, content_hash)
        )
        self.conn.commit()
        return c.lastrowid

    def update(self, iid, title, content, color, category_id=None, item_type='text', data_blob=None):
        c = self.conn.cursor()
        c.execute(
            'UPDATE ideas SET title=?, content=?, color=?, category_id=?, item_type=?, data_blob=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (title, content, color, category_id, item_type, data_blob, iid)
        )
        self.conn.commit()

    def find_by_hash(self, content_hash):
        c = self.conn.cursor()
        c.execute("SELECT id FROM ideas WHERE content_hash = ?", (content_hash,))
        return c.fetchone()

    def update_timestamp(self, iid):
        c = self.conn.cursor()
        c.execute("UPDATE ideas SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (iid,))
        self.conn.commit()

    def toggle_field(self, iid, field):
        if field not in ['is_pinned', 'is_favorite']:
            raise ValueError("Invalid field for toggling")
        c = self.conn.cursor()
        c.execute(f'UPDATE ideas SET {field} = NOT {field} WHERE id=?', (iid,))
        self.conn.commit()

    def set_deleted(self, iid, state):
        c = self.conn.cursor()
        c.execute('UPDATE ideas SET is_deleted=? WHERE id=?', (1 if state else 0, iid))
        self.conn.commit()

    def move_category(self, iid, cat_id):
        c = self.conn.cursor()
        c.execute('UPDATE ideas SET category_id=? WHERE id=?', (cat_id, iid))
        self.conn.commit()

    def delete_permanent(self, iid):
        c = self.conn.cursor()
        c.execute('DELETE FROM ideas WHERE id=?', (iid,))
        c.execute('DELETE FROM idea_tags WHERE idea_id=?', (iid,))
        self.conn.commit()

    def get_by_id(self, iid, include_blob=False):
        c = self.conn.cursor()
        if include_blob:
            c.execute('SELECT * FROM ideas WHERE id=?', (iid,))
        else:
            c.execute('SELECT id, title, content, color, is_pinned, is_favorite, created_at, updated_at, category_id, item_type FROM ideas WHERE id=?', (iid,))
        return c.fetchone()

    def get_all(self, search: str, f_type: FilterType, f_val):
        c = self.conn.cursor()
        q = "SELECT DISTINCT i.* FROM ideas i LEFT JOIN idea_tags it ON i.id=it.idea_id LEFT JOIN tags t ON it.tag_id=t.id WHERE 1=1"
        p = []
        
        if f_type == FilterType.TRASH:
            q += ' AND i.is_deleted=1'
        else:
            q += ' AND (i.is_deleted=0 OR i.is_deleted IS NULL)'
        
        if f_type == FilterType.CATEGORY:
            if f_val is None: q += ' AND i.category_id IS NULL'
            else: q += ' AND i.category_id=?'; p.append(f_val)
        elif f_type == FilterType.TODAY:
            q += " AND date(i.updated_at,'localtime')=date('now','localtime')"
        elif f_type == FilterType.CLIPBOARD:
            q += " AND i.id IN (SELECT idea_id FROM idea_tags WHERE tag_id = (SELECT id FROM tags WHERE name = '剪贴板'))"
        elif f_type == FilterType.UNTAGGED:
            q += ' AND i.id NOT IN (SELECT idea_id FROM idea_tags)'
        elif f_type == FilterType.FAVORITE:
            q += ' AND i.is_favorite=1'
        elif f_type == FilterType.UNCATEGORIZED:
            q += ' AND i.category_id IS NULL'
        
        if search:
            q += ' AND (i.title LIKE ? OR i.content LIKE ? OR t.name LIKE ?)'
            p.extend([f'%{search}%']*3)
            
        q += ' ORDER BY i.is_pinned DESC, i.updated_at DESC'
        c.execute(q, p)
        return c.fetchall()

    def get_counts(self):
        c = self.conn.cursor()
        d = {}
        queries = {
            FilterType.ALL: "is_deleted=0 OR is_deleted IS NULL",
            FilterType.TODAY: "(is_deleted=0 OR is_deleted IS NULL) AND date(updated_at,'localtime')=date('now','localtime')",
            FilterType.CLIPBOARD: "(is_deleted=0 OR is_deleted IS NULL) AND id IN (SELECT idea_id FROM idea_tags WHERE tag_id = (SELECT id FROM tags WHERE name = '剪贴板'))",
            FilterType.UNCATEGORIZED: "(is_deleted=0 OR is_deleted IS NULL) AND category_id IS NULL",
            FilterType.UNTAGGED: "(is_deleted=0 OR is_deleted IS NULL) AND id NOT IN (SELECT idea_id FROM idea_tags)",
            FilterType.FAVORITE: "(is_deleted=0 OR is_deleted IS NULL) AND is_favorite=1",
            FilterType.TRASH: "is_deleted=1"
        }
        for k, v in queries.items():
            c.execute(f"SELECT COUNT(*) FROM ideas WHERE {v}")
            d[k.value] = c.fetchone()[0]
            
        c.execute("SELECT category_id, COUNT(*) FROM ideas WHERE (is_deleted=0 OR is_deleted IS NULL) GROUP BY category_id")
        d['categories'] = dict(c.fetchall())
        return d
